"""
Processes detections from the dedicated ball model by selecting
the highest-confidence ball candidate for each frame. 
If the selected detection has low confidence,
it is flagged (not discarded) so downstream modules can decide whether to trust or ignore it.

"""

from __future__ import annotations


def process_ball_detections(ball_model_dets: list[dict], low_conf_flag: float) -> list[dict]:

    if not ball_model_dets:
        return []

    best = max(ball_model_dets, key=lambda d: d["conf"])
    best["low_confidence"] = best["conf"] < low_conf_flag
    best["class"] = "ball"

    return [best]
