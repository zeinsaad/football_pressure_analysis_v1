"""
Render the full annotated tracking video locally from a saved tracking-cache pickle.

Run this on your Windows machine (venv_clean) once you've downloaded the tracking
cache pickle (OUTPUT_TRACKING_CACHE_PATH from the notebook, e.g.
barca_atletico_tracking_cache_final.pkl) and the matching source video. This does
NOT re-run any tracking/detection -- it only draws the boxes/labels already
computed in the notebook onto the video frames.

Set the paths below, then run:
    venv_clean\Scripts\activate
    python render_from_cache.py

Requires: opencv-python, numpy
    pip install opencv-python numpy
"""

import colorsys
import os
import pickle

import cv2

# ---- paths: edit these ----
CACHE_PATH = "barca_atletico_tracking_cache_full_first_half_v2.pkl"
VIDEO_PATH = "barca_atletico_46m53s.mkv"
OUTPUT_PATH = "annotated_local.mp4"

SHOW_FRAME_NUMBER = True
SHOW_BALL = True

# ---- frame range: set START_FRAME/END_FRAME to render a clip instead of the
# whole video. END_FRAME=None means "go to the end". Both default to the full
# video, so leaving these alone changes nothing.
START_FRAME = 0
END_FRAME = 10000      # e.g. 3000 to render only the first 3000 frames


def id_to_color(track_id):
    hue = (track_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.95)
    return (int(b * 255), int(g * 255), int(r * 255))


CLASS_COLOR_OVERRIDE = {"goalkeeper": (0, 200, 255), "referee": (0, 0, 255)}


def draw_pill_label(frame, text, x, y, color, font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    pad_x, pad_y = 6, 4
    x1, y1 = int(x), int(y - th - 2 * pad_y)
    x2, y2 = int(x + tw + 2 * pad_x), int(y)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1, lineType=cv2.LINE_AA)
    cv2.putText(frame, text, (x1 + pad_x, y2 - pad_y), font, font_scale,
                (255, 255, 255), thickness, cv2.LINE_AA)


def main():
    if not os.path.exists(CACHE_PATH):
        raise FileNotFoundError(f"Tracking cache not found: {CACHE_PATH}")
    if not os.path.exists(VIDEO_PATH):
        raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

    with open(CACHE_PATH, "rb") as f:
        cache_data = pickle.load(f)
    tracking_cache = cache_data["tracking_cache"]
    locked_class_by_id = cache_data["locked_class_by_id"]

    counts = {}
    for cls in locked_class_by_id.values():
        counts[cls] = counts.get(cls, 0) + 1
    print(f"Loaded cache: {len(tracking_cache)} frames, "
          f"{len(locked_class_by_id)} final identities {counts}")

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {frame_w}x{frame_h} @ {fps:.2f}fps, {total_frames} frames")

    # Clamp the requested range to what the video actually has.
    end_frame = total_frames if END_FRAME is None else min(END_FRAME, total_frames)
    start_frame = max(0, min(START_FRAME, end_frame))
    n_frames_to_render = end_frame - start_frame
    print(f"Rendering frames {start_frame} -> {end_frame} ({n_frames_to_render} frames)")

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        # Note: CAP_PROP_POS_FRAMES seeking is exact on most mp4/H.264 sources but
        # can land a few frames off on some mkv/VFR containers -- if you need
        # frame-exact alignment for a specific diagnostic, trust the printed f_idx
        # values rather than assuming the seek landed exactly on START_FRAME.

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (frame_w, frame_h))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for: {OUTPUT_PATH}")

    progress_every = max(50, n_frames_to_render // 30) if n_frames_to_render > 0 else 50
    f_idx = start_frame
    while f_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        data = tracking_cache.get(f_idx, {"ball": None, "tracks": []})

        if SHOW_FRAME_NUMBER:
            cv2.putText(frame, f"frame={f_idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 255), 2, cv2.LINE_AA)

        for t in data["tracks"]:
            x1, y1, x2, y2 = [int(v) for v in t["bbox"]]
            tid = t["track_id"]
            cls = locked_class_by_id.get(tid, t["class"])
            color = CLASS_COLOR_OVERRIDE.get(cls, id_to_color(tid))

            if cls == "goalkeeper":
                cx, cy = (x1 + x2) // 2, y2
                cv2.ellipse(frame, (cx, cy), (int((x2 - x1) * 0.5), 8), 0, 0, 360,
                            color, 3, cv2.LINE_AA)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, lineType=cv2.LINE_AA)
            draw_pill_label(frame, f"#{tid} {cls[:3].upper()}", x1, y1, color)

        if SHOW_BALL and data.get("ball") is not None:
            bx1, by1, bx2, by2 = [int(v) for v in data["ball"]["bbox"]]
            cx, cy = (bx1 + bx2) // 2, (by1 + by2) // 2
            cv2.circle(frame, (cx, cy), 6, (0, 255, 255), -1, lineType=cv2.LINE_AA)

        writer.write(frame)

        if (f_idx - start_frame) % progress_every == 0:
            print(f"  frame {f_idx}/{end_frame}")
        f_idx += 1

    cap.release()
    writer.release()
    print(f"\nDone. Wrote {f_idx - start_frame} frames ({start_frame}->{f_idx}) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()