"""
Ball detection candidate selection.

Ball candidates come ONLY from the dedicated ball model — the multiclass
model's "ball" class is never used (it does not detect the ball reliably).
This is enforced structurally: this module only ever receives boxes that
already came from the ball model (see pipeline.py), so there is no branch
here that could accidentally pull in a multi-model ball box.
"""

from __future__ import annotations


def process_ball_detections(ball_model_dets: list[dict], low_conf_flag: float) -> list[dict]:
    """
    Reduce raw ball-model boxes for one frame down to at most one detection.

    Keeps only the single highest-confidence candidate if multiple boxes are
    returned — downstream tracking expects at most one ball per frame.

    Args:
        ball_model_dets: boxes from the dedicated ball model for one frame,
            each {"bbox": [...], "conf": float, "class": "ball", "source": "ball_model"}.
        low_conf_flag: confidence threshold below which the kept detection is
            marked low_confidence=True (it is not dropped, just flagged so
            downstream consumers can decide how much to trust it).

    Returns:
        [] if no candidates, else a single-element list with the best detection.
    """
    if not ball_model_dets:
        return []

    best = max(ball_model_dets, key=lambda d: d["conf"])
    best["low_confidence"] = best["conf"] < low_conf_flag
    best["class"] = "ball"

    return [best]
