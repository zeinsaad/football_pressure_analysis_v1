"""
Tracker configuration. Paths come from the project-root paths.py, while this file
contains the tracking parameters and runtime settings used by the pipeline.
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
    # Input/output paths loaded from the project's paths.py file.
    detection_cache_path: str = DETECTION_CACHE_PATH
    osnet_weights_path: str = OSNET_WEIGHTS_PATH
    video_path: str = VIDEO_PATH
    output_cache_path: str = TRACKING_CACHE_PATH

    # Runtime settings.
    # Automatically uses GPU (CUDA) if available; otherwise falls back to CPU.
    device: int | str = field(default_factory=lambda: 0 if torch.cuda.is_available() else "cpu")

    # Mapping between class names and the IDs expected by the tracker.
    class_to_id: dict = field(default_factory=lambda: {"player": 0, "goalkeeper": 1, "referee": 2})

    # BoT-SORT tracking parameters.
    track_high_thresh: float = 0.5      # Minimum confidence for primary track association.
    track_low_thresh: float = 0.1       # Lower confidence limit for secondary association.
    new_track_thresh: float = 0.6       # Minimum confidence required to create a new track.
    track_buffer: int = 100             # Frames to keep a lost track before removing it.
    match_thresh: float = 0.8           # Minimum score required to match a detection to a track.
    proximity_thresh: float = 0.5       # Maximum allowed spatial distance for matching.
    appearance_thresh: float = 0.25     # Minimum appearance similarity for ReID matching.
    cmc_method: str = "sof"             # Camera motion compensation method.
    frame_rate: int = 25                # Video frame rate used by the tracker.

    # Split tracklets whenever same-class detections overlap enough to indicate
    # a possible identity switch.
    contact_iou_thresh: float = 0.3

    # Ignore very short tracklets before global linking, as they do not provide
    # enough appearance or motion information to be reliable.
    min_tracklet_len: int = 20

    # Parameters controlling global tracklet linking.
    max_link_gap: int = 500       # Maximum frame gap allowed between linked tracklets.
    min_link_score: float = 0.3   # Minimum combined appearance and motion score to link tracklets.
    embed_window: int = 8         # Number of frames used to average head/tail embeddings.
    motion_weight: float = 0.3    # Weight assigned to motion when computing the link score.
    motion_norm_px: float = 300.0 # Pixel distance corresponding to the maximum motion penalty.

    # Remove unreliable tracks and assign a stable class label to confirmed tracks.
    min_track_length: int = 300
    min_confirm_frames_abs: int = 10
    min_confirm_ratio: float = 0.02
    max_ids_per_class_expected: dict = field(
        default_factory=lambda: {"goalkeeper": 2, "referee": 3}
    )   # Expected maximum IDs per class for sanity checking.

    # Debugging and progress logging.
    debug_linking: bool = True
    log_every_n_frames: int = 200