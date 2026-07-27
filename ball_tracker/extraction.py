from __future__ import annotations


def _count_nearby_players(pred_xy_px, frame_tracks, locked_class_by_id, radius_px):
    """How many player/goalkeeper tracks have their bbox center within
    radius_px of the predicted ball position -- used to detect a duel/scramble."""
    if pred_xy_px is None:
        return 0
    px, py = pred_xy_px
    count = 0
    for t in frame_tracks:
        if locked_class_by_id.get(t["track_id"]) not in ("player", "goalkeeper"):
            continue
        x0, y0, x1, y1 = t["bbox"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if (cx - px) ** 2 + (cy - py) ** 2 <= radius_px ** 2:
            count += 1
    return count


def get_ball_detection(detection_cache, frame_idx, min_conf, cfg=None,
                        tracking_cache=None, locked_class_by_id=None, pred_xy_px=None):
    """Crowd-aware confidence floor. When cfg + tracking_cache +
    locked_class_by_id + pred_xy_px are all supplied, a candidate near a
    cluster of players (a duel/scramble -- where boot/shin-guard false
    positives cluster) needs to clear cfg.crowd_min_conf instead of just
    min_conf. Falls back to the plain min_conf filter (original behavior)
    when the extra context isn't given, so this stays usable standalone
    (e.g. for quick debug lookups)."""
    dets = detection_cache.get(frame_idx, [])
    ball_dets = [d for d in dets if d.get("class") == "ball" and d.get("conf", 0) >= min_conf]
    if not ball_dets:
        return None
    best = max(ball_dets, key=lambda d: d["conf"])

    if cfg is not None and tracking_cache is not None and locked_class_by_id is not None:
        frame_tracks = tracking_cache.get(frame_idx, {}).get("tracks", [])
        n_nearby = _count_nearby_players(pred_xy_px, frame_tracks, locked_class_by_id, cfg.crowd_radius_px)
        if n_nearby >= cfg.crowd_min_players and best["conf"] < cfg.crowd_min_conf:
            return None

    bbox = best["bbox"]
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return {"xy": (cx, cy), "conf": best["conf"]}
