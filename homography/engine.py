from __future__ import annotations

import os

from ultralytics import YOLO

from .config import HomographyConfig
from .keypoints import build_pitch_keypoints, build_pose_keypoints
from .correspondences import CorrespondenceMixin
from .homography_math import HomographyMathMixin
from .orientation import OrientationMixin


class HomographyEngine(CorrespondenceMixin, HomographyMathMixin, OrientationMixin):
    def __init__(self, config: HomographyConfig):
        self.config = config
        self.seg_model: YOLO | None = None
        self.pose_model: YOLO | None = None
        self.pitch_keypoints_real = build_pitch_keypoints(config.pitch_length, config.pitch_width)
        self.pose_keypoints_real = build_pose_keypoints(self.pitch_keypoints_real)
        self.reference_orientation_sign: float | None = None

    def check_paths(self) -> None:
        cfg = self.config
        for name, p in (("seg_model_path", cfg.seg_model_path),
                        ("pose_model_path", cfg.pose_model_path),
                        ("video_path", cfg.video_path)):
            status = "\u2705" if os.path.exists(p) else "\u274c MISSING:"
            print(f"{status} {name} -> {p}")

    def load_models(self) -> None:
        cfg = self.config
        self.seg_model = YOLO(cfg.seg_model_path)
        self.pose_model = YOLO(cfg.pose_model_path)