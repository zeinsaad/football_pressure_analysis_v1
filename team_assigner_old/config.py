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
    torso_top_ratio: float = 0.15      # skip the top 15% of the box (head/neck)
    torso_bottom_ratio: float = 0.50   # keep only up to 50% of box height (avoid shorts)
    torso_side_margin: float = 0.20    # crop in 20% from each side (avoid arms/background)
    min_bbox_area: int = 900           # px^2, filters out small/distant crops from calibration

    # ---- calibration sampling ----
    calibration_frame_stride: int = 15     # frames sampled to FIT the KMeans clusters
    classification_frame_stride: int = 8   # frames sampled to CLASSIFY each track
    max_calibration_samples: int = 6000    # cap AFTER collecting across the whole match

    # ---- smoothing ----
    weak_majority_threshold: float = 0.7   # below this fraction, flag the track for manual review

    # ---- pitch projection (for goalkeeper assignment) ----
    px_per_meter: int = 10
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0
    gk_position_sample_stride: int = 10    # frames sampled when computing a track's pitch-space centroid

    # ---- SigLIP ----
    siglip_model_name: str = "google/siglip-base-patch16-224"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    log_every_n_frames: int = 300
