"""
Shared geometric utility functions used throughout the tracking pipeline.
"""

from __future__ import annotations

import numpy as np


# Compute the Intersection over Union (IoU) between two bounding boxes.
# IoU measures the amount of overlap between two boxes and is commonly used
# for duplicate detection and track association.
def iou(box1: list[float], box2: list[float]) -> float:
    xa1, ya1, xa2, ya2 = box1
    xb1, yb1, xb2, yb2 = box2
    ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
    ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = (xa2 - xa1) * (ya2 - ya1) + (xb2 - xb1) * (yb2 - yb1) - inter
    return inter / union if union > 0 else 0.0


# Compute the center point of a bounding box.
# The returned (x, y) coordinates are used for distance calculations,
# motion estimation, and track association.
def bbox_center(bbox: list[float]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2])