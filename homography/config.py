from dataclasses import dataclass

import paths

# Controls whether cached homography data should be rebuilt from scratch.
# These are not file paths, so they stay in this config instead of paths.py.
FORCE_REBUILD_HOMOGRAPHY = False

# Forces rebuilding pitch correspondences when the extraction logic changes.
# Rebuilding correspondences also requires rebuilding the homography.
FORCE_REBUILD_CORRESPONDENCES = False

if FORCE_REBUILD_CORRESPONDENCES:
    FORCE_REBUILD_HOMOGRAPHY = True


@dataclass
class HomographyConfig:
    # File locations for models, input video, and homography cache.
    seg_model_path: str = paths.SEG_MODEL_PATH
    pose_model_path: str = paths.POSE_MODEL_PATH
    video_path: str = paths.VIDEO_PATH
    output_cache_path: str = paths.HOMOGRAPHY_CACHE_PATH

    # Confidence thresholds for segmentation and pose detection models.
    conf_thresh_seg: float = 0.25
    conf_thresh_pose: float = 0.20

    # Input resolution used when running the detection models.
    img_size: int = 960

    # Pitch coordinate settings used for pixel-to-meter conversion.
    px_per_meter: int = 10
    pitch_length: float = 105.0
    pitch_width: float = 68.0

    # RANSAC settings for rejecting incorrect pitch landmark matches.
    ransac_thresh: float = 25.0

    # EMA smoothing settings to reduce frame-to-frame homography jitter.
    ema_alpha: float = 0.3
    min_inliers_full_confidence: int = 15
    min_alpha: float = 0.05
    max_alpha: float = 0.9

    # Detect sudden homography jumps and apply stronger smoothing.
    jump_px_threshold: float = 25.0
    jump_confidence_threshold: float = 0.5
    jump_alpha: float = 0.8

    # Minimum number and quality of pitch anchor points required to accept
    # a homography estimation.
    min_anchor_points: int = 4
    min_anchor_inlier_ratio: float = 0.7

    # Parameters for automatically finding the correct pitch orientation.
    calib_sample_stride: int = 50
    calib_max_samples: int = 60
    calib_min_votes: int = 5