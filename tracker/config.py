"""
Tracker configuration. Paths come from the project-root paths.py — fill
them in there, not here. Only thresholds/runtime knobs live in this file.
"""

from dataclasses import dataclass, field

import torch

try:
    from paths import DETECTION_CACHE_PATH, OSNET_WEIGHTS_PATH, VIDEO_PATH, TRACKING_CACHE_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in DETECTION_CACHE_PATH / OSNET_WEIGHTS_PATH / VIDEO_PATH / TRACKING_CACHE_PATH "
          "in the project-root paths.py.")
    DETECTION_CACHE_PATH = ""
    OSNET_WEIGHTS_PATH = ""
    VIDEO_PATH = ""
    TRACKING_CACHE_PATH = ""


@dataclass
class TrackingConfig:
    # ---- paths (sourced from paths.py) ----
    detection_cache_path: str = DETECTION_CACHE_PATH
    osnet_weights_path: str = OSNET_WEIGHTS_PATH
    video_path: str = VIDEO_PATH
    output_cache_path: str = TRACKING_CACHE_PATH

    # ---- runtime ----
    # auto-detects: CUDA index 0 if a GPU is available (Kaggle/Colab), else CPU
    device: int | str = field(default_factory=lambda: 0 if torch.cuda.is_available() else "cpu")

    # ---- class mapping ----
    class_to_id: dict = field(default_factory=lambda: {"player": 0, "goalkeeper": 1, "referee": 2})

    # ---- BoT-SORT tracker params ----
    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.6
    track_buffer: int = 100
    match_thresh: float = 0.8
    proximity_thresh: float = 0.5
    appearance_thresh: float = 0.25
    cmc_method: str = "sof"
    frame_rate: int = 25

    # ---- tracklet splitting ----
    # force a split at every same-class contact, so no identity is ever trusted
    # to survive an occlusion just because the raw tracker ID didn't change
    contact_iou_thresh: float = 0.3

    # ---- pre-link noise filtering ----
    # drop tracklets shorter than this BEFORE linking (too short to carry
    # reliable appearance/motion signal)
    min_tracklet_len: int = 20

    # ---- global linking parameters ----
    max_link_gap: int = 500       # max frames between tracklet-end and next tracklet-start to link
    min_link_score: float = 0.3   # minimum combined appearance+motion score to accept a link
    embed_window: int = 8         # frames used for head/tail embedding averaging
    motion_weight: float = 0.3    # weight of the motion penalty in the combined score
    motion_norm_px: float = 300.0 # pixel distance that saturates the motion penalty to 1.0

    # ---- final ghost-track filter + ratio-aware class locking ----
    min_track_length: int = 300
    min_confirm_frames_abs: int = 10
    min_confirm_ratio: float = 0.02
    max_ids_per_class_expected: dict = field(
        default_factory=lambda: {"goalkeeper": 2, "referee": 3}
    )   # sanity check only, not enforced

    debug_linking: bool = True
    log_every_n_frames: int = 200
