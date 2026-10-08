# ============================================================================================
# Annotate the video from the NAMED tracking cache (notebook 2 output) -- runs locally on CPU.
#  * players: foot ellipse in team colour + label (LABEL_STYLE)
#  * goalkeepers magenta, referees black, off-pitch / extra people grey ("OFF" / "EXTRA")
#  * duplicate boxes (a second box on an already boxed person): thin ellipse, no label
#  * interpolated boxes: thin ellipse + "~" before the label, so you can see what was filled
#  * ball: yellow marker
#  * top-left panel: frame, time, named / unknown / interpolated box counts in this frame
# Set START_FRAME / END_FRAME to render only a part for a quick check.
# ============================================================================================
import os
import io
import pickle
import cv2
import numpy as np

VIDEO_PATH    = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\clip.mkv"
TRACKING_PATH = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\barca_atletico_tracking_cache_named (4).pkl"
OUTPUT_PATH   = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache\annotated_teams.mp4"

START_FRAME = 0          # first frame to render
END_FRAME   = None       # None = until the end of the video (e.g. 3000 for a 2-minute check)

# ---- colours (BGR) ----
TEAM_COLORS = {"BAR": (160, 60, 20),     # blue
               "ATM": (40, 40, 220)}     # red
GOALKEEPER_COLOR = (255, 0, 255)    # magenta
REFEREE_COLOR    = (20, 20, 20)     # black
UNKNOWN_COLOR    = (160, 160, 160)  # grey (id with no team)
BALL_COLOR       = (0, 255, 255)    # yellow, same for every ball detection
TEXT_COLOR       = (255, 255, 255)  # white label text

LABEL_STYLE = "number_name"   # "number" -> 7 | "team_number" -> ATM 7 | "number_name" -> 7 Griezmann | "id" -> #207
SHOW_UNKNOWN_LABELS = False   # True = grey boxes show "?<id>" (useful to find a piece id to name later)
MARK_INTERPOLATED   = True    # thin ellipse + "~" for boxes filled by interpolation
SHOW_PANEL          = True
FONT, FONT_SCALE, FONT_THICK = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
UNKNOWN_ID_START = 10_000     # ids >= this are unknown / untracked (Cell 10e)


# ---- load the cache (with a fallback for pickles written with numpy 2 and read with numpy 1) ----
class _NumpyCompatUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith("numpy._core"):
            module = module.replace("numpy._core", "numpy.core", 1)
        return super().find_class(module, name)


with open(TRACKING_PATH, "rb") as fh:
    _raw = fh.read()
try:
    data = pickle.loads(_raw)
except ModuleNotFoundError:
    data = _NumpyCompatUnpickler(io.BytesIO(_raw)).load()
cache = data["tracking_cache"]
player_info = data.get("player_info", {})
locked = data.get("locked_class_by_id", {})
print(f"Cache: {len(cache)} frames | ids with info: {len(player_info)}")


def category(t):
    tid = t["track_id"]
    cls = player_info.get(tid, {}).get("class") or locked.get(tid) or t.get("class", "player")
    if cls == "other" or t.get("unknown") or t.get("untracked") or tid >= UNKNOWN_ID_START:
        return "unknown"
    if cls in ("goalkeeper", "referee"):
        return cls
    return "player" if (t.get("team") or player_info.get(tid, {}).get("team")) in TEAM_COLORS else "unknown"


def color_of(t, cat):
    if cat == "goalkeeper":
        return GOALKEEPER_COLOR
    if cat == "referee":
        return REFEREE_COLOR
    if cat == "player":
        return TEAM_COLORS[t.get("team") or player_info[t["track_id"]]["team"]]
    return UNKNOWN_COLOR


def label_of(t, cat):
    tid = t["track_id"]
    info = player_info.get(tid, {})
    if t.get("duplicate"):
        return ""
    if cat == "unknown":
        nm = str(info.get("name", ""))
        if nm in ("off-pitch", "extra"):
            return "OFF" if nm == "off-pitch" else "EXTRA"
        return f"?{tid}" if SHOW_UNKNOWN_LABELS else ""
    if cat == "referee":
        return "AR" if "assistant" in str(info.get("name", "")).lower() else "REF"
    num, name, team = t.get("number", info.get("number")), t.get("name", info.get("name")), t.get("team", info.get("team"))
    if LABEL_STYLE == "id" or num is None:
        txt = f"#{tid}" if LABEL_STYLE == "id" or not name else str(name)
    elif LABEL_STYLE == "number":
        txt = f"{num}"
    elif LABEL_STYLE == "team_number":
        txt = f"{team} {num}"
    else:
        txt = f"{num} {name}"
    if cat == "goalkeeper" and LABEL_STYLE != "id":
        txt = f"GK {txt}"
    if MARK_INTERPOLATED and t.get("interpolated") and not t.get("snapped_to_detection"):
        txt = "~" + txt
    return txt


def draw_box(img, t):
    cat = category(t)
    col = color_of(t, cat)
    x1, y1, x2, y2 = [int(round(v)) for v in t["bbox"]]
    w = max(x2 - x1, 4)
    cx, fy = (x1 + x2) // 2, y2
    interp = MARK_INTERPOLATED and t.get("interpolated") and not t.get("snapped_to_detection")
    thick = 1 if (interp or cat == "unknown" or t.get("duplicate")) else 2
    cv2.ellipse(img, (cx, fy), (int(w * 0.6), max(int(w * 0.22), 3)), 0, -45, 235, col, thick, cv2.LINE_AA)
    txt = label_of(t, cat)
    if txt:
        (tw, th), base = cv2.getTextSize(txt, FONT, FONT_SCALE, FONT_THICK)
        bx1, by1 = cx - tw // 2 - 3, fy + max(int(w * 0.22), 3) + 2
        bx2, by2 = cx + tw // 2 + 3, by1 + th + base + 4
        cv2.rectangle(img, (bx1, by1), (bx2, by2), col, -1)
        cv2.putText(img, txt, (bx1 + 3, by2 - base - 2), FONT, FONT_SCALE, TEXT_COLOR, FONT_THICK, cv2.LINE_AA)
    return ("duplicate" if t.get("duplicate") else cat), interp


def draw_ball(img, ball):
    if not ball:
        return
    bb = ball.get("bbox") if isinstance(ball, dict) else ball
    if bb is None:
        return
    x1, y1, x2, y2 = [float(v) for v in bb]
    cx, top = int((x1 + x2) / 2), int(y1)
    pts = np.array([[cx, top - 4], [cx - 8, top - 18], [cx + 8, top - 18]], np.int32)
    cv2.fillPoly(img, [pts], BALL_COLOR, cv2.LINE_AA)
    cv2.polylines(img, [pts], True, (0, 0, 0), 1, cv2.LINE_AA)


def draw_panel(img, f, fps, counts):
    m, s = divmod(f / fps, 60)
    lines = [f"frame {f}  {int(m):02d}:{s:05.2f}",
             f"named {counts['named']}  GK {counts['goalkeeper']}  REF {counts['referee']}",
             f"off/extra {counts['unknown']}  dup {counts['duplicate']}  interp {counts['interp']}"]
    cv2.rectangle(img, (8, 8), (330, 8 + 22 * len(lines) + 6), (0, 0, 0), -1)
    for i, ln in enumerate(lines):
        cv2.putText(img, ln, (16, 30 + 22 * i), FONT, 0.55, TEXT_COLOR, 1, cv2.LINE_AA)


# ---- render ----
cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened(), f"cannot open {VIDEO_PATH}"
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
n_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
last = n_video - 1 if END_FRAME is None else min(END_FRAME, n_video - 1)
print(f"Video: {W}x{H} @ {fps:.2f} fps, {n_video} frames | rendering {START_FRAME}-{last}")
if abs(n_video - len(cache)) > 5:
    print(f"[warn] video has {n_video} frames but the cache has {len(cache)} -- check that clip.mkv is the same "
          f"video the cache was built on (frame indices must match)")
if START_FRAME > 0:
    cap.set(cv2.CAP_PROP_POS_FRAMES, START_FRAME)

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
out = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
assert out.isOpened(), f"cannot write {OUTPUT_PATH}"

try:
    from tqdm import tqdm
    bar = tqdm(total=last - START_FRAME + 1, unit="frame", mininterval=1.0)
except ImportError:
    bar = None

f = START_FRAME
while f <= last:
    ok, img = cap.read()
    if not ok:
        print(f"video ended at frame {f}")
        break
    fd = cache.get(f, {"ball": None, "tracks": []})
    counts = {"named": 0, "goalkeeper": 0, "referee": 0, "unknown": 0, "duplicate": 0, "interp": 0}
    # unknown first, named on top
    for t in sorted(fd["tracks"], key=lambda t: category(t) != "unknown"):
        cat, interp = draw_box(img, t)
        counts["named" if cat == "player" else cat] += 1
        counts["interp"] += int(bool(interp))
    draw_ball(img, fd.get("ball"))
    if SHOW_PANEL:
        draw_panel(img, f, fps, counts)
    out.write(img)
    f += 1
    if bar is not None:
        bar.update(1)
    elif (f - START_FRAME) % 1000 == 0:
        print(f"  {f - START_FRAME} frames")

if bar is not None:
    bar.close()
cap.release()
out.release()
print(f"Saved {OUTPUT_PATH}")