

from __future__ import annotations

# Compute the Intersection over Union (IoU) between two bounding boxes.
# IoU measures how much two boxes overlap and is used for duplicate detection.
def iou(box1: list[float], box2: list[float]) -> float:
    """Intersection-over-union for two [x1, y1, x2, y2] boxes."""
    xa1, ya1, xa2, ya2 = box1
    xb1, yb1, xb2, yb2 = box2

    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = (xa2 - xa1) * (ya2 - ya1)
    area_b = (xb2 - xb1) * (yb2 - yb1)
    union = area_a + area_b - inter_area

    return inter_area / union if union > 0 else 0.0


# Apply standard Non-Maximum Suppression (NMS) separately for each object class.
# Removes lower-confidence duplicate detections of the same class that overlap
# above the IoU threshold, keeping only the highest-confidence detection.
def same_class_nms(dets: list[dict], iou_thresh: float) -> list[dict]:
    """Standard per-class NMS. dets: list of dicts with 'bbox', 'conf', 'class'."""
    by_class: dict[str, list[dict]] = {}
    for d in dets:
        by_class.setdefault(d["class"], []).append(d)

    kept: list[dict] = []
    for _, cls_dets in by_class.items():
        cls_dets = sorted(cls_dets, key=lambda d: d["conf"], reverse=True)
        used = [False] * len(cls_dets)
        for i in range(len(cls_dets)):
            if used[i]:
                continue
            kept.append(cls_dets[i])
            for j in range(i + 1, len(cls_dets)):
                if used[j]:
                    continue
                if iou(cls_dets[i]["bbox"], cls_dets[j]["bbox"]) >= iou_thresh:
                    used[j] = True
    return kept


# Remove duplicate player detections when they overlap a goalkeeper or referee.
# If a player box overlaps a goalkeeper/referee box above the IoU threshold,
# the player detection is discarded because the more specific class is preferred.
def cross_class_suppress_players(dets: list[dict], iou_thresh: float) -> list[dict]:
    """
    If a 'player' box overlaps a 'goalkeeper' or 'referee' box above iou_thresh,
    drop the player box (gk/referee wins). Pure detection-level dedup for the
    case where the model emits two competing boxes for the same person —
    no color/classifier logic involved.
    """
    priority_boxes = [d for d in dets if d["class"] in ("goalkeeper", "referee")]
    player_boxes = [d for d in dets if d["class"] == "player"]
    other_boxes = [d for d in dets if d["class"] not in ("goalkeeper", "referee", "player")]

    kept_players = []
    for p in player_boxes:
        suppressed = any(
            iou(p["bbox"], pb["bbox"]) >= iou_thresh for pb in priority_boxes
        )
        if not suppressed:
            kept_players.append(p)

    return priority_boxes + kept_players + other_boxes
