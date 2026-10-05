from __future__ import annotations

from collections import defaultdict

from .config import BallTrackerConfig
from .extraction import get_ball_detection
from .geometry import px_to_pitch
from .kalman import BallKalmanTracker
from .smoothing import rts_smooth


def run_ball_tracker(detection_cache, tracking_cache, locked_class_by_id,
                      homography_cache, cfg: BallTrackerConfig, total_frames):
    """
    Output schema per frame:
        {frame_idx: {
            "xy_px": (x, y) or None,
            "xy_pitch": (x, y) or None,
            "source": "detected" | "smoothed" | "lost",
            "conf": float or None,
        }}

    'detected'  -- a real detection this frame.
    'smoothed'  -- RTS-interpolated within a gap that closed on both sides.
    'lost'      -- no trustworthy position (includes what used to be
                   unconfirmed forward-only "predicted" frames -- pure
                   forward extrapolation isn't trustworthy since the ball
                   can bounce/deflect anywhere before the next real
                   detection confirms it).
    """
    tracker = BallKalmanTracker(cfg)
    ball_tracked_cache = {}
    stats = defaultdict(int)

    seg_frames, seg_x_filt, seg_P_filt = [], [], []
    seg_x_pred, seg_P_pred = [], []
    seg_was_detected, seg_raw_meas, seg_conf = [], [], []

    def flush_segment():
        if not seg_frames:
            return
        x_smooth, P_smooth = rts_smooth(tracker.F, seg_x_filt, seg_P_filt, seg_x_pred, seg_P_pred)

        detected_positions = [i for i, d in enumerate(seg_was_detected) if d]
        last_detected_idx = max(detected_positions) if detected_positions else -1

        for i, f in enumerate(seg_frames):
            H = homography_cache[f] if f < len(homography_cache) else None
            if seg_was_detected[i]:
                xy_px = seg_raw_meas[i]
                source = "detected"
                conf = seg_conf[i]
            elif i < last_detected_idx:
                xy_px = tuple(x_smooth[i][:2])
                source = "smoothed"
                conf = None
            else:
                xy_px = None
                source = "lost"
                conf = None

            ball_tracked_cache[f] = {
                "xy_px": xy_px,
                "xy_pitch": px_to_pitch(xy_px, H, cfg.px_per_meter) if xy_px is not None else None,
                "source": source, "conf": conf,
            }
            stats[source] += 1

        seg_frames.clear(); seg_x_filt.clear(); seg_P_filt.clear()
        seg_x_pred.clear(); seg_P_pred.clear()
        seg_was_detected.clear(); seg_raw_meas.clear(); seg_conf.clear()

    def _speed_ok(det_xy, last_xy_px, gap_frames, frame_idx):
        """Rejects detections that imply an unrealistic ball speed, on top of
        the Mahalanobis gate. Only checked after a miss, since adjacent-frame
        jumps are already tightly constrained by the gate."""
        if gap_frames == 0:
            return True
        H_now = homography_cache[frame_idx] if frame_idx < len(homography_cache) else None
        cur_pitch = px_to_pitch(det_xy, H_now, cfg.px_per_meter)
        last_pitch = px_to_pitch(tuple(last_xy_px), H_now, cfg.px_per_meter)
        if cur_pitch is None or last_pitch is None:
            return True  # can't evaluate without homography -- fall back to Mahalanobis only
        elapsed_s = (gap_frames + 1) / cfg.fps
        implied_speed = (((cur_pitch[0] - last_pitch[0]) ** 2 +
                           (cur_pitch[1] - last_pitch[1]) ** 2) ** 0.5) / elapsed_s
        return implied_speed <= cfg.max_ball_speed_mps

    for frame_idx in range(total_frames):
        if not tracker.initialized:
            # No predicted position yet, so the crowd check can't run --
            # falls back to the plain min_detection_conf filter for this frame.
            det = get_ball_detection(detection_cache, frame_idx, cfg.min_detection_conf,
                                      cfg=cfg, tracking_cache=tracking_cache,
                                      locked_class_by_id=locked_class_by_id, pred_xy_px=None)
            if det is not None:
                tracker.init(*det["xy"])
                seg_frames.append(frame_idx)
                seg_x_filt.append(tracker.x.copy())
                seg_P_filt.append(tracker.P.copy())
                seg_x_pred.append(None)
                seg_P_pred.append(None)
                seg_was_detected.append(True)
                seg_raw_meas.append(det["xy"])
                seg_conf.append(det["conf"])
            else:
                ball_tracked_cache[frame_idx] = {
                    "xy_px": None, "xy_pitch": None, "source": "lost", "conf": None,
                }
                stats["lost"] += 1
            continue

        x_pred, P_pred = tracker.predict()
        P_pred_full = tracker.P.copy()
        x_pred_full = tracker.x.copy()

        # Crowd-aware confidence floor, using the just-computed predicted
        # position to check how many players are clustered around it.
        det = get_ball_detection(detection_cache, frame_idx, cfg.min_detection_conf,
                                  cfg=cfg, tracking_cache=tracking_cache,
                                  locked_class_by_id=locked_class_by_id,
                                  pred_xy_px=tuple(x_pred_full[:2]))

        accepted = False
        if det is not None:
            dist = tracker.mahalanobis(det["xy"])
            gate_ok = dist <= cfg.mahalanobis_gate
            speed_ok = _speed_ok(det["xy"], x_pred_full[:2], tracker.gap_frames, frame_idx) if gate_ok else False
            if gate_ok and speed_ok:
                tracker.update(det["xy"])
                accepted = True
            elif gate_ok and not speed_ok:
                stats["rejected_speed"] += 1

        seg_frames.append(frame_idx)
        seg_x_pred.append(x_pred_full)
        seg_P_pred.append(P_pred_full)

        if accepted:
            seg_x_filt.append(tracker.x.copy())
            seg_P_filt.append(tracker.P.copy())
            seg_was_detected.append(True)
            seg_raw_meas.append(det["xy"])
            seg_conf.append(det["conf"])
        else:
            tracker.mark_missed()
            seg_x_filt.append(x_pred_full)
            seg_P_filt.append(P_pred_full)
            seg_was_detected.append(False)
            seg_raw_meas.append(None)
            seg_conf.append(None)

            if tracker.gap_frames > cfg.max_track_gap_frames:
                tracker.initialized = False
                flush_segment()
                ball_tracked_cache[frame_idx] = {
                    "xy_px": None, "xy_pitch": None, "source": "lost", "conf": None,
                }
                stats["lost"] += 1

    flush_segment()
    return ball_tracked_cache, dict(stats)


def summarize_gaps(ball_tracked_cache, total_frames, cfg: BallTrackerConfig):
    """Debug helper -- gap length distribution. Not part of the main
    pipeline; call manually if you want the printout."""
    import numpy as np

    gaps = []
    current_gap = 0
    for f in range(total_frames):
        src = ball_tracked_cache[f]["source"]
        if src == "detected":
            if current_gap > 0:
                gaps.append(current_gap)
            current_gap = 0
        else:
            current_gap += 1
    if current_gap > 0:
        gaps.append(current_gap)

    gaps = np.array(gaps)
    if len(gaps) == 0:
        print("No gaps -- every frame detected (unlikely at ~55% recall, check input).")
        return

    print(f"Number of gap runs: {len(gaps)}")
    print(f"Mean gap length: {gaps.mean():.1f} frames")
    print(f"Median gap length: {np.median(gaps):.1f} frames")
    print(f"Max gap length: {gaps.max()} frames")
    print(f"Gaps > max_track_gap_frames ({cfg.max_track_gap_frames}): {(gaps > cfg.max_track_gap_frames).sum()}")

    source_counts = defaultdict(int)
    for f in range(total_frames):
        source_counts[ball_tracked_cache[f]["source"]] += 1
    print()
    for src, count in source_counts.items():
        print(f"  {src}: {count} ({100*count/total_frames:.1f}%)")
