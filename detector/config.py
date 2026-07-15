"""
Detector configuration. Paths come from the project-root paths.py — fill
them in there, not here. Only thresholds/runtime knobs live in this file.
"""

from dataclasses import dataclass, field

import torch

try:
    from paths import MULTI_MODEL_PATH, BALL_MODEL_PATH, VIDEO_PATH, DETECTION_CACHE_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in MULTI_MODEL_PATH / BALL_MODEL_PATH / VIDEO_PATH / DETECTION_CACHE_PATH "
          "in the project-root paths.py.")
    MULTI_MODEL_PATH = ""
    BALL_MODEL_PATH = ""
    VIDEO_PATH = ""
    DETECTION_CACHE_PATH = ""


@dataclass
class DetectionConfig:
    # ---- model paths (sourced from paths.py) ----
    multi_model_path: str = MULTI_MODEL_PATH
    ball_model_path: str = BALL_MODEL_PATH

    # ---- video / cache paths (sourced from paths.py) ----
    video_path: str = VIDEO_PATH
    output_cache_path: str = DETECTION_CACHE_PATH

    # ---- class mapping for the multiclass model ----
    # ball is intentionally included here for validation purposes only —
    # the pipeline never uses multi-model "ball" detections (see pipeline.py).
    multi_class_names: dict = field(default_factory=lambda: {
        0: "ball", 1: "goalkeeper", 2: "player", 3: "referee",
    })

    # ---- confidence thresholds ----
    conf_thresh_multi: float = 0.25
    conf_thresh_ball: float = 0.25
    ball_low_conf_flag: float = 0.15   # below this, ball det is flagged low_confidence (not dropped)

    # ---- NMS / suppression thresholds ----
    cross_class_iou_thresh: float = 0.5   # gk/referee suppresses overlapping player box
    same_class_nms_iou: float = 0.5

    # ---- runtime ----
    # auto-detects: CUDA index 0 if a GPU is available (Kaggle/Colab), else CPU
    # (your local machine has no GPU, so this will correctly resolve to "cpu")
    device: int | str = field(default_factory=lambda: 0 if torch.cuda.is_available() else "cpu")
    log_every_n_frames: int = 100
