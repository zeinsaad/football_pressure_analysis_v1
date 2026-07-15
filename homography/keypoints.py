"""
Pitch keypoint definitions in real-world meters, and the mapping from
segmentation-model line-pair classes / pose-model keypoint indices to those
real-world points.

Keypoints are built via build_pitch_keypoints(pitch_length, pitch_width)
rather than hardcoded module constants, so HomographyConfig's pitch_length/
pitch_width are always the single source of truth.
"""

from __future__ import annotations


def build_pitch_keypoints(pitch_length: float, pitch_width: float) -> dict[str, tuple[float, float]]:
    return {
        "top_right_corner":              (pitch_length, 0.0),
        "halfway_top":                   (pitch_length / 2, 0.0),
        "halfway_bottom":                (pitch_length / 2, pitch_width),
        "center_spot":                   (pitch_length / 2, pitch_width / 2),
        "left_big_rect_top_outer":       (0.0, 13.85),
        "left_big_rect_top_inner":       (16.5, 13.85),
        "left_big_rect_bottom_outer":    (0.0, 54.15),
        "left_big_rect_bottom_inner":    (16.5, 54.15),
        "right_big_rect_top_outer":      (pitch_length, 13.85),
        "right_big_rect_top_inner":      (pitch_length - 16.5, 13.85),
        "right_big_rect_bottom_outer":   (pitch_length, 54.15),
        "right_big_rect_bottom_inner":   (pitch_length - 16.5, 54.15),
        "right_pen_spot":                (pitch_length - 11.0, 34.0),
        "left_small_rect_top_outer":     (0.0, 24.85),
        "left_small_rect_top_inner":     (5.5, 24.85),
        "left_small_rect_bottom_outer":  (0.0, 43.15),
        "left_small_rect_bottom_inner":  (5.5, 43.15),
        "right_small_rect_top_outer":    (pitch_length, 24.85),
        "right_small_rect_top_inner":    (pitch_length - 5.5, 24.85),
        "right_small_rect_bottom_outer": (pitch_length, 43.15),
        "right_small_rect_bottom_inner": (pitch_length - 5.5, 43.15),
        "left_big_rect_main_upper":      (16.5, 24.85),
        "left_big_rect_main_lower":      (16.5, 43.15),
        "right_big_rect_main_upper":     (pitch_length - 16.5, 24.85),
        "right_big_rect_main_lower":     (pitch_length - 16.5, 43.15),
        "circle_top":                    (pitch_length / 2, pitch_width / 2 - 9.15),
        "circle_bottom":                 (pitch_length / 2, pitch_width / 2 + 9.15),
        "circle_left":                   (pitch_length / 2 - 9.15, pitch_width / 2),
        "circle_right":                  (pitch_length / 2 + 9.15, pitch_width / 2),
    }


LINE_PAIR_TO_KEYPOINT = {
    "Side line top":          {"type": "endpoints", "keys": ["top_left_corner", "top_right_corner"]},
    "Middle line":            {"type": "endpoints", "keys": ["halfway_top", "halfway_bottom"]},
    "Circle central":         {"type": "centroid",  "keys": ["center_spot"]},
    "Big rect. left top":     {"type": "endpoints", "keys": ["left_big_rect_top_outer",      "left_big_rect_top_inner"]},
    "Big rect. left bottom":  {"type": "endpoints", "keys": ["left_big_rect_bottom_outer",   "left_big_rect_bottom_inner"]},
    "Big rect. left main":    {"type": "endpoints", "keys": ["left_big_rect_top_inner",      "left_big_rect_bottom_inner"]},
    "Big rect. right top":    {"type": "endpoints", "keys": ["right_big_rect_top_outer",     "right_big_rect_top_inner"]},
    "Big rect. right bottom": {"type": "endpoints", "keys": ["right_big_rect_bottom_outer",  "right_big_rect_bottom_inner"]},
    "Big rect. right main":   {"type": "endpoints", "keys": ["right_big_rect_top_inner",     "right_big_rect_bottom_inner"]},
    "Small rect. left top":   {"type": "endpoints", "keys": ["left_small_rect_top_outer",    "left_small_rect_top_inner"]},
    "Small rect. left bottom":{"type": "endpoints", "keys": ["left_small_rect_bottom_outer", "left_small_rect_bottom_inner"]},
    "Small rect. left main":  {"type": "endpoints", "keys": ["left_small_rect_top_inner",    "left_small_rect_bottom_inner"]},
    "Small rect. right top":  {"type": "endpoints", "keys": ["right_small_rect_top_outer",   "right_small_rect_top_inner"]},
    "Small rect. right bottom":{"type":"endpoints", "keys": ["right_small_rect_bottom_outer","right_small_rect_bottom_inner"]},
    "Small rect. right main": {"type": "endpoints", "keys": ["right_small_rect_top_inner",   "right_small_rect_bottom_inner"]},
}


def build_pose_keypoints(pitch_keypoints_real: dict[str, tuple[float, float]]) -> dict[int, tuple[float, float]]:
    return {
        9:  pitch_keypoints_real["left_big_rect_top_inner"],
        12: pitch_keypoints_real["left_big_rect_bottom_inner"],
        13: pitch_keypoints_real["halfway_top"],
        14: pitch_keypoints_real["circle_top"],
        15: pitch_keypoints_real["circle_bottom"],
        16: pitch_keypoints_real["halfway_bottom"],
        17: pitch_keypoints_real["right_big_rect_top_inner"],
        20: pitch_keypoints_real["right_big_rect_bottom_inner"],
        21: pitch_keypoints_real["right_pen_spot"],
        30: pitch_keypoints_real["circle_left"],
        31: pitch_keypoints_real["circle_right"],
    }
