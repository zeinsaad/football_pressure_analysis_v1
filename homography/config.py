"""
Homography configuration. Paths come from the project-root paths.py — fill
them in there, not here. Only thresholds/runtime knobs live in this file.
"""

from dataclasses import dataclass

try:
    from paths import SEG_MODEL_PATH, POSE_MODEL_PATH, VIDEO_PATH, HOMOGRAPHY_CACHE_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in SEG_MODEL_PATH / POSE_MODEL_PATH / VIDEO_PATH / HOMOGRAPHY_CACHE_PATH "
          "in the project-root paths.py.")
    SEG_MODEL_PATH = ""
    POSE_MODEL_PATH = ""
    VIDEO_PATH = ""
    HOMOGRAPHY_CACHE_PATH = ""


@dataclass
class HomographyConfig:
    # ---- model paths (sourced from paths.py) ----
    seg_model_path: str = SEG_MODEL_PATH
    pose_model_path: str = POSE_MODEL_PATH

    # ---- video / cache paths (sourced from paths.py) ----
    video_path: str = VIDEO_PATH
    output_cache_path: str = HOMOGRAPHY_CACHE_PATH

    # ---- model thresholds ----
    conf_thresh_seg: float = 0.25
    conf_thresh_pose: float = 0.20
    img_size: int = 960

    # ---- pitch geometry ----
    px_per_meter: int = 10
    ransac_thresh: float = 25.0
    pitch_length: float = 105.0
    pitch_width: float = 68.0

    # ---- temporal smoothing ----
    ema_alpha: float = 0.3   # EMA smoothing factor across frames when building the cache
