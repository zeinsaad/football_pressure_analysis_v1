from __future__ import annotations

import math
from collections import defaultdict

from .config import CarrierConfig
from .geometry import px_to_pitch

"""
Player-Ball Carrier Assigner
-----------------------------
- Phase 1 -- bbox overlap: ball center within bbox_overlap_margin_px of a
  player's bbox -> immediate candidate.
- Phase 2 -- pitch-space proximity fallback (only if phase 1 found nothing,
  not even a contested duel): nearest player within max_carrier_distance_m
  of the ball, in pitch meters via px_to_pitch on bbox bottom-center.
- Ambiguity: two near-tied candidates are flagged "contested" instead of
  arbitrarily picking the nearest -- falls through to the grace-hold path.
- Hysteresis + velocity-consistency gate: a new candidate must lead for
  min_frames_to_switch consecutive decision-eligible frames AND look like
  an actual touch (speed/direction change), not just a through-ball
  grazing a player's proximity zone.
"""


def player_bbox_distance(ball_xy_px, bbox, margin):
    x0, y0, x1, y1 = bbox
    cx, cy = ball_xy_px
    dx = max(x0 - cx, 0, cx - x1)
    dy = max(y0 - cy, 0, cy - y1)
    dist = (dx ** 2 + dy ** 2) ** 0.5
    return dist, dist <= margin


def player_feet_pitch(bbox, H, px_per_meter):
    """Bottom-center of the player's bbox (feet), projected to pitch space
    via the same homography used for the ball -- keeps both in the same
    coordinate system so distances are directly comparable."""
    x0, y0, x1, y1 = bbox
    feet_px = ((x0 + x1) / 2, y1)
    return px_to_pitch(feet_px, H, px_per_meter)


def best_with_margin(candidates, margin_ratio):
    """candidates: list of (track_id, dist), ascending distance = better.
    Returns (best_id, best_dist, ambiguous). Two nearly-tied candidates
    (e.g. a 50/50 duel) are flagged ambiguous instead of arbitrarily picking
    the nearest."""
    if not candidates:
        return None, None, False
    candidates = sorted(candidates, key=lambda c: c[1])
    best_id, best_dist = candidates[0]
    if len(candidates) == 1:
        return best_id, best_dist, False
    second_dist = candidates[1][1]
    ambiguous = second_dist <= 0 or best_dist >= margin_ratio * second_dist
    return best_id, best_dist, ambiguous


def ball_velocity_change(ball_tracked_cache, frame_idx, window, fps, total_frames):
    """Compares the ball's pitch-space velocity just before vs. just after
    frame_idx (using the full offline cache, so this is allowed to look
    ahead). Returns (speed_before, speed_after, angle_change_deg), or None if
    there isn't enough position data nearby to evaluate (e.g. near a
    lost-track boundary)."""
    def get_pt(f):
        e = ball_tracked_cache.get(f)
        return e["xy_pitch"] if e is not None else None

    f_before = max(frame_idx - window, 0)
    f_after = min(frame_idx + window, total_frames - 1)
    p_before, p_now, p_after = get_pt(f_before), get_pt(frame_idx), get_pt(f_after)
    if p_before is None or p_now is None or p_after is None:
        return None

    dt_before = (frame_idx - f_before) / fps
    dt_after = (f_after - frame_idx) / fps
    if dt_before <= 0 or dt_after <= 0:
        return None

    v_before = ((p_now[0] - p_before[0]) / dt_before, (p_now[1] - p_before[1]) / dt_before)
    v_after = ((p_after[0] - p_now[0]) / dt_after, (p_after[1] - p_now[1]) / dt_after)

    speed_before = (v_before[0] ** 2 + v_before[1] ** 2) ** 0.5
    speed_after = (v_after[0] ** 2 + v_after[1] ** 2) ** 0.5

    ang_before = math.atan2(v_before[1], v_before[0])
    ang_after = math.atan2(v_after[1], v_after[0])
    angle_diff = abs(math.degrees(ang_after - ang_before))
    angle_diff = min(angle_diff, 360.0 - angle_diff)

    return speed_before, speed_after, angle_diff


def run_carrier_assigner(ball_tracked_cache, tracking_cache, locked_class_by_id,
                          homography_cache, carrier_cfg: CarrierConfig, total_frames,
                          px_per_meter=10.0):
    ball_carrier_cache = {}
    current_carrier = None
    candidate_streak = defaultdict(int)
    no_candidate_run = 0  # consecutive frames with no accepted candidate

    for frame_idx in range(total_frames):
        ball_entry = ball_tracked_cache.get(frame_idx)
        frame_tracks = tracking_cache.get(frame_idx, {}).get("tracks", [])
        player_tracks = [t for t in frame_tracks
                          if locked_class_by_id.get(t["track_id"]) in ("player", "goalkeeper")]

        if ball_entry is None or ball_entry["xy_px"] is None or not player_tracks:
            no_candidate_run += 1
            if no_candidate_run > carrier_cfg.no_candidate_grace_frames:
                current_carrier = None
                candidate_streak.clear()
            ball_carrier_cache[frame_idx] = {
                "track_id": current_carrier,  # still shows the held carrier during the grace window
                "method": None,
                "ball_source": ball_entry["source"] if ball_entry else None,
            }
            continue

        ball_source = ball_entry["source"]
        drive_decision = ball_source in carrier_cfg.decision_sources
        can_display = ball_source in carrier_cfg.display_sources

        best_candidate = None
        best_method = None

        if drive_decision:
            # Phase 1 -- bbox overlap, with margin-based ambiguity check
            touching = []
            for t in player_tracks:
                dist, is_touch = player_bbox_distance(
                    ball_entry["xy_px"], t["bbox"], carrier_cfg.bbox_overlap_margin_px
                )
                if is_touch:
                    touching.append((t["track_id"], dist))

            p1_id, p1_dist, p1_ambiguous = best_with_margin(touching, carrier_cfg.candidate_margin_ratio)

            if p1_id is not None and not p1_ambiguous:
                best_candidate, best_method = p1_id, "overlap"
            elif p1_ambiguous:
                best_method = "contested"  # a fair duel -- don't guess, fall through to grace-hold

            # Phase 2 -- proximity in pitch space, only if phase 1 found
            # nothing (not even a contested duel -- a contested duel should
            # not be overridden by a further-away proximity match)
            if best_candidate is None and best_method != "contested" and ball_entry["xy_pitch"] is not None:
                H = homography_cache[frame_idx] if frame_idx < len(homography_cache) else None
                proximity = []
                for t in player_tracks:
                    feet_pitch = player_feet_pitch(t["bbox"], H, px_per_meter)
                    if feet_pitch is None:
                        continue
                    pdist = ((ball_entry["xy_pitch"][0] - feet_pitch[0]) ** 2 +
                             (ball_entry["xy_pitch"][1] - feet_pitch[1]) ** 2) ** 0.5
                    if pdist <= carrier_cfg.max_carrier_distance_m:
                        proximity.append((t["track_id"], pdist))

                p2_id, p2_dist, p2_ambiguous = best_with_margin(proximity, carrier_cfg.candidate_margin_ratio)
                if p2_id is not None and not p2_ambiguous:
                    best_candidate, best_method = p2_id, "proximity"
                elif p2_ambiguous:
                    best_method = "contested"

            if best_candidate is None:
                no_candidate_run += 1
                if carrier_cfg.clear_on_no_candidate and no_candidate_run > carrier_cfg.no_candidate_grace_frames:
                    current_carrier = None
                    candidate_streak.clear()
            else:
                no_candidate_run = 0

        # --- hysteresis + velocity-consistency gate (only advances on decision-eligible frames) ---
        if drive_decision and best_candidate is not None:
            if best_candidate == current_carrier:
                candidate_streak[best_candidate] = 0
            else:
                # Requires a touch-like velocity change before counting this
                # frame as evidence for a switch. A through-ball merely
                # passing near a player usually leaves the ball's trajectory
                # unchanged; a real touch usually changes its speed and/or
                # direction.
                touch_check = ball_velocity_change(
                    ball_tracked_cache, frame_idx, carrier_cfg.velocity_check_window,
                    carrier_cfg.fps, total_frames
                )
                touch_like = True
                if touch_check is not None:
                    speed_before, speed_after, angle_delta = touch_check
                    speed_delta = abs(speed_after - speed_before)
                    touch_like = (speed_delta >= carrier_cfg.min_speed_change_mps or
                                  angle_delta >= carrier_cfg.min_angle_change_deg)

                if touch_like:
                    candidate_streak[best_candidate] += 1
                    if candidate_streak[best_candidate] >= carrier_cfg.min_frames_to_switch:
                        current_carrier = best_candidate
                        candidate_streak.clear()
                # else: inconclusive evidence -- don't increment (but don't
                # reset other candidates' streaks either; a real touch a
                # couple frames later within the same duel can still
                # complete the switch)

        ball_carrier_cache[frame_idx] = {
            "track_id": current_carrier if can_display else None,
            "method": best_method,
            "ball_source": ball_source,
        }

    return ball_carrier_cache
