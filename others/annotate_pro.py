# ============================================================================================
# annotate_pro.py -- broadcast-style annotation of the named tracking cache.
# All settings are in annotation_config.py (same folder).
#
#   python annotate_pro.py preview    -> a few annotated frames (PNG + grid) to check the look first
#   python annotate_pro.py render     -> the full video
#   python annotate_pro.py preview --config other_config.py
#
# Look: translucent ground ring in team colour, label above the head = [number badge | name  POS].
# Labels never cover each other: each frame they are placed by a small solver (above the head,
# shifted left/right, or raised one level with a thin leader line), kept stable over time.
# ============================================================================================
import io
import os
import sys
import pickle
import importlib.util
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- config
_args = sys.argv[1:]
MODE = next((a for a in _args if a in ("preview", "render")), "preview")
_cfg_path = _args[_args.index("--config") + 1] if "--config" in _args else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotation_config.py")
_spec = importlib.util.spec_from_file_location("annotation_config", _cfg_path)
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
print(f"Config: {_cfg_path} | mode: {MODE}")

UNKNOWN_ID_START = 10_000


def rgb(c):
    return (int(c[2]), int(c[1]), int(c[0]))


# ---------------------------------------------------------------- cache
class _NumpyCompatUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith("numpy._core"):
            module = module.replace("numpy._core", "numpy.core", 1)
        return super().find_class(module, name)


def load_pickle(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    try:
        return pickle.loads(blob)
    except ModuleNotFoundError:
        return _NumpyCompatUnpickler(io.BytesIO(blob)).load()


def _optional(attr):
    p = getattr(C, attr, None)
    if not p:
        return None
    if not os.path.exists(p):
        print(f"[warn] {attr} not found -> not used: {p}")
        return None
    return load_pickle(p)


DATA = load_pickle(C.TRACKING_PATH)
BALL = _optional("BALL_CACHE_PATH")              # {frame: {"xy_px", "xy_pitch", "source", "conf"}}
CARRIER = _optional("CARRIER_CACHE_PATH")        # {frame: {"track_id", "possession_team", ...}} (new ids)
print(f"Ball cache: {'yes' if BALL else 'no'} | carrier cache: {'yes' if CARRIER else 'no'}")
CACHE = DATA["tracking_cache"]
PINFO = DATA.get("player_info", {})
LOCKED = DATA.get("locked_class_by_id", {})
print(f"Cache: {len(CACHE)} frames")

_missing = set()
for d in CACHE.values():
    for t in d["tracks"]:
        tm, num = t.get("team"), t.get("number")
        tm = t.get("team_name") or tm
        if tm in C.TEAMS and num is not None and (tm, int(num)) not in C.ROSTER:
            _missing.add((tm, int(num)))
if _missing:
    print(f"[warn] (team, number) in the cache but not in ROSTER -> shown with the cache name: {sorted(_missing)}")


def identity(t):
    """-> (kind, team, number, name, pos). kind: player / goalkeeper / referee / offpitch / duplicate"""
    tid = t["track_id"]
    info = PINFO.get(tid, {})
    cls = info.get("class") or LOCKED.get(tid) or t.get("class", "player")
    if t.get("duplicate"):
        return "duplicate", None, None, None, None
    if cls == "other" or tid >= UNKNOWN_ID_START or t.get("unknown") or t.get("untracked"):
        return "offpitch", None, None, None, None
    if cls == "referee":
        nm = str(info.get("name", t.get("name", "")))
        return "referee", None, None, (C.ASSISTANT_LABEL if "assistant" in nm.lower() else C.REFEREE_LABEL), None
    team = t.get("team_name") or (t.get("team") if isinstance(t.get("team"), str) else None) or info.get("team")
    num = t.get("number", info.get("number"))
    if team not in C.TEAMS:
        return "offpitch", None, None, None, None
    r = C.ROSTER.get((team, int(num))) if num is not None else None
    name = r["name"] if r else (t.get("name") or info.get("name") or "")
    pos = r["pos"] if r else ("GK" if cls == "goalkeeper" else "")
    kind = "goalkeeper" if (cls == "goalkeeper" or pos == "GK") else "player"
    return kind, team, num, name, pos


def ring_color(kind, team):
    if kind == "goalkeeper":
        return C.TEAMS[team]["gk_color"]
    if kind == "player":
        return C.TEAMS[team]["color"]
    if kind == "referee":
        return C.REFEREE_COLOR
    return C.OFFPITCH_COLOR


# ---------------------------------------------------------------- fonts + sprites
def _font_path():
    for p in C.FONT_PATHS:
        if os.path.exists(p):
            return p
    try:
        from matplotlib import font_manager
        return font_manager.findfont("DejaVu Sans:bold")
    except Exception:
        return None


FONT_PATH = _font_path()
print(f"Font: {FONT_PATH}")


class Sprites:
    def __init__(self, scale):
        s = scale
        size = max(9, int(round(C.LABEL_FONT_PX * s)))
        load = (lambda px: ImageFont.truetype(FONT_PATH, px)) if FONT_PATH else (lambda px: ImageFont.load_default())
        self.f_name, self.f_num, self.f_pos = load(size), load(size), load(max(8, int(size * 0.72)))
        self.pad = max(3, int(round(5 * s)))
        self.radius = max(2, int(round(4 * s)))
        self.cache = {}

    def _tw(self, font, txt):
        if not txt:
            return 0
        b = font.getbbox(txt)
        return b[2] - b[0]

    def label(self, kind, team, num, name, pos, carrier=False, full=False):
        """full=True -> number + name + position whatever the config says (hover / carrier)."""
        key = (kind, team, num, name, pos, carrier, full)
        if key in self.cache:
            return self.cache[key]
        p, r = self.pad, self.radius
        show_name = C.SHOW_NAME or full or kind == "referee"          # referees: REF / AR text, never empty
        name_txt = (name.upper() if C.NAME_UPPERCASE else name) if (show_name and name) else ""
        pos_txt = pos if ((C.SHOW_POSITION or full) and pos and kind != "referee") else ""
        num_txt = str(num) if (C.SHOW_NUMBER_BADGE and num is not None) else ""
        asc = self.f_name.getbbox("ÁÍgjp")
        th = asc[3] - asc[1]
        h = th + 2 * p
        badge_w = max(h, self._tw(self.f_num, num_txt) + 2 * p) if num_txt else 0
        name_w = self._tw(self.f_name, name_txt)
        pos_w = self._tw(self.f_pos, pos_txt)
        body_w = (p + name_w + (int(p * 1.2) + pos_w if pos_txt else 0) + p) if (name_txt or pos_txt) else 0
        ball_w = int(h * 0.95) if carrier else 0
        if carrier and not body_w:
            body_w = p
        w = badge_w + body_w + ball_w
        img = Image.new("RGBA", (w, h + 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = ring_color(kind, team)
        if body_w:
            d.rounded_rectangle([badge_w - r if badge_w else 0, 0, w - 1, h - 1], radius=r,
                                fill=rgb(C.LABEL_BG_COLOR) + (int(255 * C.LABEL_BG_ALPHA),))
            d.rectangle([badge_w, h - max(2, p // 2), w - 1 - r // 2, h - 1], fill=rgb(col) + (255,))   # team underline
        if badge_w:
            d.rounded_rectangle([0, 0, badge_w - 1, h - 1], radius=r, fill=rgb(col) + (255,))
            nb = self.f_num.getbbox(num_txt)
            d.text(((badge_w - (nb[2] - nb[0])) / 2 - nb[0], (h - th) / 2 - asc[1]), num_txt,
                   font=self.f_num, fill=(255, 255, 255, 255))
        x = badge_w + p
        if name_txt:
            d.text((x, (h - th) / 2 - asc[1]), name_txt, font=self.f_name, fill=rgb(C.LABEL_TEXT_COLOR) + (255,))
            x += name_w + int(p * 1.2)
        if pos_txt:
            pb = self.f_pos.getbbox(pos_txt)
            d.text((x, (h - (pb[3] - pb[1])) / 2 - pb[1] - 1), pos_txt, font=self.f_pos,
                   fill=rgb(C.POSITION_COLOR) + (255,))
        if carrier:                                          # ball icon = this player has the ball
            rr = h * 0.27
            cx, cy = w - ball_w / 2 - p * 0.3, h / 2
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=rgb(C.BALL_COLOR) + (255,), outline=(20, 20, 20, 255),
                      width=max(1, int(rr / 4)))
        arr = np.asarray(img).astype(np.float32)
        bgr, a = arr[..., [2, 1, 0]], arr[..., 3:4] / 255.0
        spr = (bgr * a, a)                                   # premultiplied
        self.cache[key] = spr
        return spr


def blend(frame, spr, x, y):
    pm, a = spr
    h, w = a.shape[:2]
    H, W = frame.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sx, sy = x0 - x, y0 - y
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    aa = a[sy:sy + y1 - y0, sx:sx + x1 - x0]
    frame[y0:y1, x0:x1] = (roi * (1 - aa) + pm[sy:sy + y1 - y0, sx:sx + x1 - x0]).astype(np.uint8)


# ---------------------------------------------------------------- drawing primitives
def draw_ring(frame, box, col, scale, faint=False):
    x1, y1, x2, y2 = box
    cx, cy = int(round((x1 + x2) / 2)), int(round(y2))
    rx = int(max((x2 - x1) * 0.62, 9 * scale))
    ry = max(int(rx * 0.33), 3)
    H, W = frame.shape[:2]
    a0, b0, a1, b1 = max(0, cx - rx - 2), max(0, cy - ry - 2), min(W, cx + rx + 3), min(H, cy + ry + 3)
    if a1 <= a0 or b1 <= b0:
        return
    alpha = C.RING_FILL_ALPHA * (0.5 if faint else 1.0)
    roi = frame[b0:b1, a0:a1]
    over = roi.copy()
    cv2.ellipse(over, (cx - a0, cy - b0), (rx, ry), 0, 0, 360, col, -1, cv2.LINE_AA)
    cv2.addWeighted(over, alpha, roi, 1 - alpha, 0, dst=roi)
    th = 1 if faint else max(1, int(round(C.RING_THICKNESS * scale)))
    cv2.ellipse(frame, (cx, cy), (rx, ry), 0, -25, 205, col, th, cv2.LINE_AA)


def draw_tracked_ball(frame, f, scale, raw_ball=None):
    """Yellow circle ON the ball, only for sources in BALL_DRAW_SOURCES (default: real detections only --
    smoothed / interpolated positions are not drawn). Radius from the detection box when available."""
    b = BALL.get(f)
    if not b or b.get("xy_px") is None or b.get("source") not in getattr(C, "BALL_DRAW_SOURCES", ("detected",)):
        return
    cx, cy = float(b["xy_px"][0]), float(b["xy_px"][1])
    r = None
    if raw_ball and raw_ball.get("bbox") is not None:
        x1, y1, x2, y2 = [float(v) for v in raw_ball["bbox"]]
        if abs((x1 + x2) / 2 - cx) < 12 and abs((y1 + y2) / 2 - cy) < 12:
            r = max(x2 - x1, y2 - y1) / 2 + 3 * scale
    r = int(round(r if r else getattr(C, "BALL_CIRCLE_RADIUS", 8) * scale))
    cv2.circle(frame, (int(round(cx)), int(round(cy))), max(r, 4), C.BALL_COLOR,
               max(1, int(round(getattr(C, "BALL_CIRCLE_THICKNESS", 2) * scale))), cv2.LINE_AA)


def draw_carrier_triangle(frame, box, scale):
    """Small flipped (downward) triangle just above the carrier's head."""
    x1, y1, x2, y2 = box
    s = max(5, int(round(getattr(C, "CARRIER_TRIANGLE_SIZE", 9) * scale)))
    cx, tip = int(round((x1 + x2) / 2)), int(round(y1 - 4 * scale))
    pts = np.array([[cx, tip], [cx - s, tip - int(1.5 * s)], [cx + s, tip - int(1.5 * s)]], np.int32)
    cv2.fillPoly(frame, [pts], C.CARRIER_TRIANGLE_COLOR, cv2.LINE_AA)
    cv2.polylines(frame, [pts], True, (20, 20, 20), max(1, int(round(scale))), cv2.LINE_AA)
    return int(1.5 * s + 4 * scale)                      # height used above the head


def draw_ball(frame, ball, scale):
    if not ball:
        return
    bb = ball.get("bbox") if isinstance(ball, dict) else ball
    if bb is None:
        return
    x1, y1, x2, y2 = [float(v) for v in bb]
    cx, top = int((x1 + x2) / 2), int(y1)
    s = max(6, int(9 * scale))
    pts = np.array([[cx, top - int(3 * scale)], [cx - s, top - int(3 * scale) - int(1.6 * s)],
                    [cx + s, top - int(3 * scale) - int(1.6 * s)]], np.int32)
    cv2.fillPoly(frame, [pts], C.BALL_COLOR, cv2.LINE_AA)
    cv2.polylines(frame, [pts], True, (20, 20, 20), max(1, int(scale)), cv2.LINE_AA)


# ---------------------------------------------------------------- label placement
def _ov(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


class LabelPlacer:
    """Places labels so they do not cover each other or other players' heads; stable over time."""
    LEVELS, SHIFTS = 4, (0.0, -0.6, 0.6, -1.1, 1.1)

    def __init__(self, scale):
        self.gap = max(4, int(C.LABEL_GAP_PX * scale))
        self.prev = {}                                     # key -> (x, y, frame)

    def place(self, items, W, H, f):
        if getattr(C, "LABEL_PLACEMENT", "avoid") == "fixed":       # always centred right above the head
            out = {}
            for i, it in enumerate(items):
                w, h = it["size"]
                hx, hy = it["anchor"]
                x = min(max(hx - w / 2, 2), W - w - 2)
                y = min(max(hy - self.gap - it.get("gap_extra", 0) - h, 2), H - h - 2)
                out[i] = (int(round(x)), int(round(y)), False)
            return out
        bodies = [(it["box"][0], it["box"][1] - 0.05 * (it["box"][3] - it["box"][1]), it["box"][2],
                   it["box"][1] + 0.65 * (it["box"][3] - it["box"][1])) for it in items]      # head + torso
        placed, out = [], {}
        for i in sorted(range(len(items)), key=lambda i: (-items[i].get("prio", 0), -items[i]["box"][3])):
            it = items[i]
            w, h = it["size"]
            hx, hy = it["anchor"]
            prev = self.prev.get(it["key"])
            best = None
            for lvl in range(self.LEVELS):
                y = hy - self.gap - it.get("gap_extra", 0) - h - lvl * (h + self.gap // 2 + 2)
                for sh in self.SHIFTS:
                    x = hx - w / 2 + sh * w * 0.5
                    x = min(max(x, 2), W - w - 2); yy = min(max(y, 2), H - h - 2)
                    r = (x, yy, x + w, yy + h)
                    cost = 6.0 * sum(_ov(r, p) for p in placed)
                    cost += 1.5 * sum(_ov(r, hb) for j, hb in enumerate(bodies) if j != i)
                    cost = cost / (w * h) + 0.30 * lvl + 0.08 * abs(sh)
                    if prev is not None and prev[2] == f - 1:
                        cost += 0.004 * (abs(x - prev[0]) + abs(yy - prev[1]))
                    if best is None or cost < best[0]:
                        best = (cost, x, yy, lvl, sh)
            _, x, y, lvl, sh = best
            if prev is not None and prev[2] == f - 1 and abs(x - prev[0]) + abs(y - prev[1]) < 3 * h:
                x, y = 0.55 * prev[0] + 0.45 * x, 0.55 * prev[1] + 0.45 * y         # glide, no jumps
            self.prev[it["key"]] = (x, y, f)
            placed.append((x, y, x + w, y + h))
            out[i] = (int(round(x)), int(round(y)), lvl > 0 or abs(sh) > 0.01)
        return out


# ---------------------------------------------------------------- HUD
class Hud:
    def __init__(self, sprites, scale):
        self.sp, self.s, self.last, self.spr = sprites, scale, None, None

    def draw(self, frame, f, fps, poss=None):
        t = C.CLOCK_OFFSET_S + f / fps
        clock = f"{int(t // 60):02d}:{int(t % 60):02d}"
        if (clock, poss) != self.last:
            self.last, self.spr = (clock, poss), self._build(clock, poss)
        m = int(12 * self.s)
        blend(frame, self.spr, m, m)

    def _build(self, clock, poss=None):
        f, p = self.sp.f_name, self.sp.pad
        teams = list(C.TEAMS.values())
        asc = f.getbbox("ÁÍgjp"); th = asc[3] - asc[1]
        row = th + 2 * p
        chip = int(row * 0.55)
        show_poss = getattr(C, "SHOW_POSSESSION", False) and CARRIER is not None
        if show_poss:
            pteam, pname = poss if poss else (None, None)
            ptxt = "Ball: " + ((C.TEAMS[pteam]["short"] + (f" · {pname}" if pname else "")) if pteam in C.TEAMS else "loose")
        name_w = max([int(f.getlength(tm["name"])) for tm in teams] + ([int(f.getlength(ptxt))] if show_poss else []))
        clk_w = int(f.getlength(clock)) + 2 * p
        w = p + chip + p + name_w + 2 * p + clk_w
        h = row * (len(teams) + (1 if show_poss else 0))
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=self.sp.radius,
                            fill=rgb(C.LABEL_BG_COLOR) + (int(255 * C.LABEL_BG_ALPHA),))
        for k, tm in enumerate(teams):
            y = k * row
            d.rectangle([p, y + (row - chip) // 2, p + chip, y + (row + chip) // 2], fill=rgb(tm["color"]) + (255,))
            d.text((2 * p + chip, y + (row - th) / 2 - asc[1]), tm["name"], font=f, fill=(255, 255, 255, 255))
        if show_poss:
            y = len(teams) * row
            d.line([p, y, w - clk_w - p, y], fill=(90, 90, 90, 255), width=1)
            if pteam in C.TEAMS:
                d.ellipse([p, y + (row - chip) // 2, p + chip, y + (row + chip) // 2], fill=rgb(C.BALL_COLOR) + (255,),
                          outline=rgb(C.TEAMS[pteam]["color"]) + (255,), width=max(2, chip // 4))
            d.text((2 * p + chip, y + (row - th) / 2 - asc[1]), ptxt, font=f, fill=(255, 255, 255, 255))
        cx = w - clk_w
        d.rectangle([cx, 0, w - 1 - self.sp.radius // 2, h - 1], fill=(255, 255, 255, 235))
        d.text((cx + p, (h - th) / 2 - asc[1]), clock, font=f, fill=rgb(C.LABEL_BG_COLOR) + (255,))
        arr = np.asarray(img).astype(np.float32)
        a = arr[..., 3:4] / 255.0
        return (arr[..., [2, 1, 0]] * a, a)


# ---------------------------------------------------------------- frame renderer
class Renderer:
    def __init__(self, W, H, fps):
        self.W, self.H, self.fps = W, H, fps
        self.scale = H / 1080.0
        self.sp = Sprites(self.scale)
        self.placer = LabelPlacer(self.scale)
        self.hud = Hud(self.sp, self.scale)
        self.smooth = {}                                    # key -> (box, frame)

    def _smoothed(self, key, box, f):
        prev = self.smooth.get(key)
        a = C.SMOOTHING
        if prev is not None and prev[1] == f - 1 and a > 0:
            box = tuple(a * p + (1 - a) * b for p, b in zip(prev[0], box))
        self.smooth[key] = (box, f)
        return box

    def frame(self, img, f, label_keys=None, highlight_keys=(), full_label_keys=()):
        """label_keys=None -> label everybody (video); a set of person keys -> only those (viewer hover / pin).
        After the call, self.people holds every drawn person (key, box, kind, ...) for hit-testing."""
        d = CACHE.get(f, {"ball": None, "tracks": []})
        car = CARRIER.get(f) if CARRIER else None
        cid = car.get("track_id") if car else None
        rings, labels, people = [], [], []
        tri_h = int(1.5 * max(5, round(getattr(C, "CARRIER_TRIANGLE_SIZE", 9) * self.scale)) + 4 * self.scale)
        tracks = list(d["tracks"]) + [dict(o, track_id=o.get("id", -1), unknown=True) for o in d.get("others", [])]
        for t in tracks:
            kind, team, num, name, pos = identity(t)
            if kind == "duplicate" and not C.DRAW_DUPLICATES:
                continue
            if kind == "offpitch" and not C.DRAW_OFFPITCH:
                continue
            if kind in ("offpitch", "duplicate"):
                key = (kind, team, num, t["track_id"])
            elif kind == "referee":                    # both assistants are labelled "AR" -> the id keeps them apart
                key = (kind, team, t["track_id"], name)
            else:
                key = (kind, team, num, name)
            box = self._smoothed(key, tuple(float(v) for v in t["bbox"]), f)
            col = ring_color(kind, team) if kind != "duplicate" else C.OFFPITCH_COLOR
            is_car = cid is not None and t["track_id"] == cid and kind in ("player", "goalkeeper")
            people.append({"key": key, "box": box, "kind": kind, "team": team, "num": num, "name": name,
                           "pos": pos, "t": t, "carrier": is_car})
            rings.append((box, col, kind in ("offpitch", "duplicate"), is_car, key))
            if kind in ("player", "goalkeeper", "referee") and (label_keys is None or key in label_keys):
                full = key in full_label_keys or (is_car and getattr(C, "CARRIER_SHOWS_NAME", False))
                spr = self.sp.label(kind, team, num if kind != "referee" else None, name, pos,
                                    carrier=is_car and getattr(C, "CARRIER_LABEL_ICON", False), full=full)
                h, w = spr[1].shape[:2]
                labels.append({"key": key, "spr": spr, "size": (w, h), "box": box, "prio": int(is_car),
                               "gap_extra": tri_h if is_car else 0, "anchor": ((box[0] + box[2]) / 2, box[1])})
        self.people = people
        for box, col, faint, is_car, key in sorted(rings, key=lambda r: r[0][3]):    # far players first
            x1, y1, x2, y2 = box
            rx = int(max((x2 - x1) * 0.62, 9 * self.scale))
            if key in highlight_keys:                                             # viewer: hovered / pinned
                cv2.ellipse(img, (int((x1 + x2) / 2), int(y2)), (rx + int(4 * self.scale), max(int(rx * 0.33), 3) + 2),
                            0, 0, 360, (255, 255, 255), max(2, int(2 * self.scale)), cv2.LINE_AA)
            draw_ring(img, box, col, self.scale, faint)
        if C.DRAW_BALL:
            if BALL is not None:
                draw_tracked_ball(img, f, self.scale, d.get("ball"))
            else:
                draw_ball(img, d.get("ball"), self.scale)
        pos = self.placer.place(labels, self.W, self.H, f)
        for i, it in enumerate(labels):                                    # tie every label to its player
            x, y, moved = pos[i]
            w, h = it["size"]
            hx, hy = it["anchor"]
            hy -= it["gap_extra"]                                           # carrier: tie to the triangle
            col = ring_color(it["key"][0], it["key"][1])
            lx = int(min(max(hx, x + 6), x + w - 6))
            if moved and C.LEADER_LINE:
                p1, p2 = (lx, y + h), (int(hx), int(hy) - 3)
                cv2.line(img, p1, p2, C.LABEL_BG_COLOR, max(2, int(3 * self.scale)), cv2.LINE_AA)
                cv2.line(img, p1, p2, (235, 235, 235), 1, cv2.LINE_AA)
                cv2.circle(img, p2, max(2, int(3 * self.scale)), col, -1, cv2.LINE_AA)
            else:                                                         # small pointer under the label
                t = max(4, int(5 * self.scale))
                tri = np.array([[lx - t, y + h - 1], [lx + t, y + h - 1], [lx, y + h + t]], np.int32)
                cv2.fillPoly(img, [tri], C.LABEL_BG_COLOR, cv2.LINE_AA)
        for i, it in enumerate(labels):
            x, y, _ = pos[i]
            blend(img, it["spr"], x, y)
        for p in people:                                                    # carrier marker on top of everything
            if p["carrier"]:
                draw_carrier_triangle(img, p["box"], self.scale)
        if C.SHOW_HUD:
            poss = None
            if car:
                pt = car.get("possession_team")
                pn = PINFO.get(cid, {}).get("number") if cid is not None else None
                rn = C.ROSTER.get((pt, int(pn))) if (pt and pn is not None) else None
                poss = (pt, rn["name"] if rn else (PINFO.get(cid, {}).get("name") if cid is not None else None))
            self.hud.draw(img, f, self.fps, poss)
        return img


# ---------------------------------------------------------------- video helpers
def open_video():
    cap = cv2.VideoCapture(C.VIDEO_PATH)
    assert cap.isOpened(), f"cannot open {C.VIDEO_PATH}"
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {W}x{H} @ {fps:.2f} fps, {n} frames")
    if n > 0 and abs(n - len(CACHE)) > 5:
        print(f"[warn] video has {n} frames, cache has {len(CACHE)} -- frame indices must match the video the "
              f"cache was built on, otherwise boxes drift off the players")
    return cap, fps, W, H, n


def pick_preview_frames(n_video):
    if C.PREVIEW_FRAMES != "auto":
        return sorted(int(f) for f in C.PREVIEW_FRAMES)
    a, b = C.PREVIEW_SEARCH_RANGE
    b = min(b, n_video - 1 if n_video > 0 else b)
    scored = []
    for f in range(a, b + 1, 5):
        d = CACHE.get(f)
        if not d:
            continue
        boxes = [t["bbox"] for t in d["tracks"] if identity(t)[0] in ("player", "goalkeeper", "referee")]
        if len(boxes) < 4:
            continue
        crowd = 0
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                bi, bj = boxes[i], boxes[j]
                hh = max(bi[3] - bi[1], bj[3] - bj[1])
                if abs((bi[0] + bi[2]) - (bj[0] + bj[2])) / 2 < 2.5 * hh and abs(bi[1] - bj[1]) < 0.8 * hh:
                    crowd += 1
        scored.append((f, len(boxes), crowd))
    if not scored:
        return [a]
    picks = []
    for f, _, _ in sorted(scored, key=lambda s: -s[2]):
        if len(picks) >= C.PREVIEW_N_CROWDED:
            break
        if all(abs(f - p) > 250 for p in picks):
            picks.append(f)
    busy = [s[0] for s in scored if s[1] >= 8] or [s[0] for s in scored]
    for q in np.linspace(0, len(busy) - 1, C.PREVIEW_N_EVEN + 2)[1:-1]:
        f = busy[int(q)]
        if all(abs(f - p) > 250 for p in picks):
            picks.append(f)
    return sorted(picks)


def run_preview():
    cap, fps, W, H, n = open_video()
    frames = pick_preview_frames(n)
    print(f"Preview frames: {frames}")
    os.makedirs(C.PREVIEW_DIR, exist_ok=True)
    R = Renderer(W, H, fps)
    want, f, shots = set(frames), 0, []
    last = max(frames)
    while f <= last:
        if f in want:
            ok, img = cap.read()
            if not ok:
                break
            R.smooth.clear(); R.placer.prev.clear()
            img = R.frame(img, f)
            path = os.path.join(C.PREVIEW_DIR, f"preview_{f:06d}.png")
            cv2.imwrite(path, img)
            shots.append(img)
            print(f"  saved {path}")
        elif not cap.grab():
            break
        f += 1
    cap.release()
    if shots:
        tw = 960
        tiles = [cv2.resize(s, (tw, int(s.shape[0] * tw / s.shape[1])), interpolation=cv2.INTER_AREA) for s in shots]
        if len(tiles) % 2:
            tiles.append(np.zeros_like(tiles[0]))
        grid = np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)])
        gp = os.path.join(C.PREVIEW_DIR, "preview_grid.jpg")
        cv2.imwrite(gp, grid, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"Grid: {gp}")


def run_render():
    cap, fps, W, H, n = open_video()
    last = (n - 1) if C.END_FRAME is None else min(C.END_FRAME, n - 1)
    if C.START_FRAME > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, C.START_FRAME)
    os.makedirs(os.path.dirname(C.OUTPUT_PATH), exist_ok=True)
    out = cv2.VideoWriter(C.OUTPUT_PATH, cv2.VideoWriter_fourcc(*C.CODEC), fps, (W, H))
    assert out.isOpened(), f"cannot write {C.OUTPUT_PATH}"
    R = Renderer(W, H, fps)
    try:
        from tqdm import tqdm
        bar = tqdm(total=last - C.START_FRAME + 1, unit="frame", mininterval=1.0)
    except ImportError:
        bar = None
    f = C.START_FRAME
    while f <= last:
        ok, img = cap.read()
        if not ok:
            print(f"video ended at frame {f}")
            break
        out.write(R.frame(img, f))
        f += 1
        if bar is not None:
            bar.update(1)
        elif (f - C.START_FRAME) % 1000 == 0:
            print(f"  {f - C.START_FRAME} frames")
    if bar is not None:
        bar.close()
    cap.release(); out.release()
    print(f"Saved {C.OUTPUT_PATH}")


if __name__ == "__main__":
    run_preview() if MODE == "preview" else run_render()