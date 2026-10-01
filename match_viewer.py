# ============================================================================================
# match_viewer.py -- interactive offline viewer: hover a player with the mouse to see who he is.
# Same drawing as the rendered video (annotate_pro.py + annotation_config.py, same folder): rings, ball circle,
# carrier triangle, HUD. Labels appear only for the hovered / pinned player (or everybody with L).
#
#   python match_viewer.py                      (optional: --config other_config.py)
#
# Mouse : hover a player  -> label above his head + info card bottom-left (name, position, team, ball, id)
#         left click      -> PIN him (his label follows him while playing); click empty grass to unpin
# Keys  : SPACE play/pause   D / ->  +1 frame   A / <-  -1 frame   W / ^  +5 s   S / v  -5 s
#         L  all labels on/off      H  help on/off      Q / ESC  quit      trackbar = seek
# Hover fix: the window shows the frame at exactly VIEWER_WIDTH (no OpenCV window scaling), and mouse
# coordinates are converted back to video pixels -> hover lands on the right player at any size.
# ============================================================================================
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import annotate_pro as AP           # loads config + match cache + ball + carrier

C = AP.C
WIN = "Match viewer"
KEY_LEFT, KEY_UP, KEY_RIGHT, KEY_DOWN = 2424832, 2490368, 2555904, 2621440      # cv2.waitKeyEx (Windows)
HOVER_EXPAND = 0.15
HELP = ["SPACE play / pause", "A D  or arrows  -/+ 1 frame", "W S  -/+ 5 s", "click  pin a player",
        "L  all labels", "H  hide help", "Q / ESC  quit"]


class Viewer:
    def __init__(self, cap, fps, W, H, n):
        self.cap, self.fps, self.W, self.H, self.n = cap, fps, W, H, n
        self.R = AP.Renderer(W, H, fps)
        self.s = self.R.scale
        self.disp_w = int(min(getattr(C, "VIEWER_WIDTH", 1600), W))
        self.k = self.disp_w / W                                   # video px -> display px
        self.f, self.pos, self.raw = 0, 0, None
        self.mouse = None                                          # in VIDEO pixels
        self.pinned, self.show_all, self.show_help = None, False, True
        self.playing, self.dirty = False, True
        self._people_frame = None
        _ld = (lambda px: ImageFont.truetype(AP.FONT_PATH, px)) if AP.FONT_PATH else (lambda px: ImageFont.load_default())
        self.f_big, self.f_small = _ld(max(12, int(20 * self.s))), _ld(max(10, int(15 * self.s)))
        self.cards = {}

    # ---------------------------------------------------------------- video
    def read(self, f):
        f = int(min(max(f, 0), self.n - 1))
        if f != self.pos:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = self.cap.read()
        if not ok:
            return False
        self.f, self.pos, self.raw, self.dirty = f, f + 1, img, True
        return True

    # ---------------------------------------------------------------- hit test on what was drawn
    def hit(self):
        if self.mouse is None:
            return None
        x, y = self.mouse
        best = None
        for p in getattr(self.R, "people", []):
            x1, y1, x2, y2 = p["box"]
            ex, ey = (x2 - x1) * HOVER_EXPAND, (y2 - y1) * HOVER_EXPAND
            if x1 - ex <= x <= x2 + ex and y1 - ey <= y <= y2 + ey:
                dd = np.hypot(x - (x1 + x2) / 2, y - (y1 + y2) / 2) / max(y2 - y1, 1)
                if best is None or dd < best[0]:
                    best = (dd, p)
        return best[1] if best else None

    # ---------------------------------------------------------------- info card
    def card(self, p):
        t = p["t"]
        src = ("interpolated" if t.get("source") == "interpolated" or t.get("interpolated") else
               "auto-assigned" if t.get("source") == "auto" or t.get("auto_assigned") else
               "recovered" if t.get("source") == "recovered" else "tracked")
        key = (p["key"], t["track_id"], src, p["carrier"])
        if key in self.cards:
            return self.cards[key]
        if p["kind"] == "offpitch":
            lines = [("Off-pitch person", self.f_big, (255, 255, 255)),
                     ("not one of the 25 on the pitch", self.f_small, (215, 215, 215))]
        else:
            if p["kind"] == "referee":
                title, sub = p["name"], "Match official"
            else:
                title = f"#{p['num']}  {p['name']}" if p["num"] is not None else p["name"]
                sub = (f"{p['pos']}  ·  " if p["pos"] else "") + C.TEAMS[p["team"]]["name"]
            lines = [(title, self.f_big, (255, 255, 255)), (sub, self.f_small, (215, 215, 215))]
            if p["carrier"]:
                lines.append(("has the ball", self.f_small, AP.rgb(C.CARRIER_TRIANGLE_COLOR)))
            lines.append((f"id {t['track_id']}  ·  {src}", self.f_small, (160, 160, 160)))
        pad, bar = int(10 * self.s), max(4, int(5 * self.s))
        hts = [fn.getbbox("ÁÍgjp")[3] - fn.getbbox("ÁÍgjp")[1] for _, fn, _ in lines]
        w = max(int(fn.getlength(tx)) for tx, fn, _ in lines) + 2 * pad + bar
        h = sum(hts) + 2 * pad + int(pad * 0.6) * (len(lines) - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=self.R.sp.radius, fill=AP.rgb(C.LABEL_BG_COLOR) + (230,))
        dr.rectangle([0, 0, bar, h - 1], fill=AP.rgb(AP.ring_color(p["kind"], p["team"])) + (255,))
        y = pad
        for (tx, fn, col), hh in zip(lines, hts):
            dr.text((bar + pad, y - fn.getbbox("ÁÍgjp")[1]), tx, font=fn, fill=tuple(col) + (255,))
            y += hh + int(pad * 0.6)
        arr = np.asarray(img).astype(np.float32)
        a = arr[..., 3:4] / 255.0
        self.cards[key] = (arr[..., [2, 1, 0]] * a, a)
        return self.cards[key]

    # ---------------------------------------------------------------- compose
    def compose(self):
        if self._people_frame != self.f:                           # boxes of THIS frame for the hit test
            self.R.frame(self.raw.copy(), self.f, label_keys=set())
            self._people_frame = self.f
        hov = self.hit()
        keys = set()
        if hov is not None:
            keys.add(hov["key"])
        if self.pinned is not None:
            keys.add(self.pinned)
        img = self.R.frame(self.raw.copy(), self.f, label_keys=None if self.show_all else keys, highlight_keys=keys)
        info = hov or next((p for p in self.R.people if p["key"] == self.pinned), None)
        if info is not None:
            spr = self.card(info)
            m = int(14 * self.s)
            AP.blend(img, spr, m, self.H - spr[1].shape[0] - m)
        disp = cv2.resize(img, (self.disp_w, int(round(self.H * self.k))), interpolation=cv2.INTER_AREA)
        self.status(disp)
        return disp

    def status(self, img):
        txt = f"{'PLAY' if self.playing else 'PAUSE'}  frame {self.f}"
        if self.pinned is not None:
            txt += f"  |  pinned: {self.pinned[3]}"
        lines = [txt] + (HELP if self.show_help else [])
        fs, lh = 0.5, 20
        w = max(cv2.getTextSize(l, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] for l in lines) + 20
        x0, y0 = img.shape[1] - w - 10, 10
        roi = img[y0:y0 + lh * len(lines) + 8, x0:x0 + w]
        roi[:] = (roi * 0.35 + np.array(C.LABEL_BG_COLOR) * 0.65).astype(np.uint8)
        for i, l in enumerate(lines):
            cv2.putText(img, l, (x0 + 10, y0 + lh * (i + 1) - 4), cv2.FONT_HERSHEY_SIMPLEX, fs,
                        (255, 255, 255) if i == 0 else (200, 200, 200), 1, cv2.LINE_AA)

    # ---------------------------------------------------------------- mouse (display px -> video px)
    def on_mouse(self, ev, x, y, flags, _):
        vx, vy = x / self.k, y / self.k
        if ev == cv2.EVENT_MOUSEMOVE:
            self.mouse, self.dirty = (vx, vy), True
        elif ev == cv2.EVENT_LBUTTONDOWN:
            self.mouse = (vx, vy)
            p = self.hit()
            self.pinned = p["key"] if (p is not None and p["kind"] != "offpitch") else None
            self.dirty = True


def main():
    cap, fps, W, H, n = AP.open_video()
    V = Viewer(cap, fps, W, H, n)
    V.read(getattr(C, "START_FRAME", 0) or 0)
    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)                  # 1 window px = 1 display px -> exact mouse mapping
    cv2.setMouseCallback(WIN, V.on_mouse)
    seek = {"to": None, "internal": False}

    def on_bar(v):
        if not seek["internal"]:
            seek["to"] = v
    cv2.createTrackbar("frame", WIN, 0, max(n - 1, 1), on_bar)

    while True:
        t0 = time.perf_counter()
        if seek["to"] is not None:
            V.read(seek["to"]); seek["to"] = None
        elif V.playing and not V.read(V.f + 1):
            V.playing = False
        if V.dirty:
            cv2.imshow(WIN, V.compose())
            V.dirty = False
            seek["internal"] = True
            cv2.setTrackbarPos("frame", WIN, V.f)
            seek["internal"] = False
        wait = max(1, int(1000 / fps - (time.perf_counter() - t0) * 1000)) if V.playing else 15
        k = cv2.waitKeyEx(wait)
        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break
        if k == -1:
            continue
        c = k & 0xFF
        if c in (ord("q"), 27):
            break
        elif c == ord(" "):
            V.playing = not V.playing; V.dirty = True
        elif k == KEY_RIGHT or c == ord("d"):
            V.playing = False; V.read(V.f + 1)
        elif k == KEY_LEFT or c == ord("a"):
            V.playing = False; V.read(V.f - 1)
        elif k == KEY_UP or c == ord("w"):
            V.read(V.f + int(5 * fps))
        elif k == KEY_DOWN or c == ord("s"):
            V.read(V.f - int(5 * fps))
        elif c == ord("l"):
            V.show_all = not V.show_all; V.dirty = True
        elif c == ord("h"):
            V.show_help = not V.show_help; V.dirty = True
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()