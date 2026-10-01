"""
Team assigner configuration. Paths come from the project-root paths.py —
fill them in there, not here. Only thresholds/runtime knobs live in this file.
"""

from dataclasses import dataclass

import torch

try:
    from paths import TRACKING_CACHE_PATH, VIDEO_PATH, HOMOGRAPHY_CACHE_PATH, TEAM_CACHE_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in TRACKING_CACHE_PATH / VIDEO_PATH / HOMOGRAPHY_CACHE_PATH / TEAM_CACHE_PATH "
          "in the project-root paths.py.")
    TRACKING_CACHE_PATH = ""
    VIDEO_PATH = ""
    HOMOGRAPHY_CACHE_PATH = ""
    TEAM_CACHE_PATH = ""


@dataclass
class TeamAssignerConfig:
    # ---- paths (sourced from paths.py) ----
    tracking_cache_path: str = TRACKING_CACHE_PATH
    video_path: str = VIDEO_PATH
    homography_cache_path: str = HOMOGRAPHY_CACHE_PATH
    output_cache_path: str = TEAM_CACHE_PATH

    # ---- torso crop: avoid shorts/socks/skin/head, focus on the jersey ----
    torso_top_ratio: float = 0.15
    torso_bottom_ratio: float = 0.50
    torso_side_margin: float = 0.20
    min_bbox_area: int = 900

    # ---- calibration sampling ----
    calibration_frame_stride: int = 15     # frames sampled to fit the KMeans clusters
    classification_frame_stride: int = 8   # frames sampled to classify each track
    max_calibration_samples: int = 6000

    # ---- smoothing ----
    weak_majority_threshold: float = 0.7   # below this, flag the track/window for review

    # ---- windowed team voting (switch-robust) ----
    # each segment to its own correct team instead of one flat label per track.
    team_vote_window_frames: int = 500

    # ---- auto team-color extraction ----
    # Measures each KMeans cluster's real average jersey color from calibration
    # crops, so it self-corrects if cluster 0/1 flips between reruns.
    color_extraction_min_area_percentile: float = 75.0
    color_grass_dominance_thresh: float = 1.15
    color_saturation_boost_factor: float = 2.2
    color_min_lightness: float = 0.25
    color_max_lightness: float = 0.75

    # ---- pitch projection (for goalkeeper assignment) ----
    px_per_meter: int = 10
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0
    gk_position_sample_stride: int = 10

    # ---- SigLIP ----
    siglip_model_name: str = "google/siglip-base-patch16-224"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    log_every_n_frames: int = 300