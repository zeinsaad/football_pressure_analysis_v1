"""
HomographyEngine: computes a per-frame homography matrix mapping pixel
coordinates to real-world pitch coordinates (meters), using a segmentation
model for pitch lines fused with a pose model for pitch keypoints.
"""

from __future__ import annotations

import cv2
import numpy as np
from ultralytics import YOLO

from .config import HomographyConfig
from .keypoints import LINE_PAIR_TO_KEYPOINT, build_pitch_keypoints, build_pose_keypoints


class HomographyEngine:
    """Computes H (3x3) mapping pixel coordinates to pitch-meter space."""

    def __init__(self, config: HomographyConfig):
        self.config = config
        self.seg_model: YOLO | None = None
        self.pose_model: YOLO | None = None

        self.pitch_keypoints_real = build_pitch_keypoints(config.pitch_length, config.pitch_width)
        self.pose_keypoints_real = build_pose_keypoints(self.pitch_keypoints_real)

    # ------------------------------------------------------------------ #
    #  Setup                                                              #
    # ------------------------------------------------------------------ #

    def load_models(self) -> None:
        cfg = self.config
        self.seg_model = YOLO(cfg.seg_model_path)
        self.pose_model = YOLO(cfg.pose_model_path)
        print("Segmentation model classes:", self.seg_model.names)
        print("Pose model loaded.")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_homography(self, frame: np.ndarray) -> np.ndarray | None:
        """Return H (3x3) for *frame*, or None if not enough points found."""
        if self.seg_model is None or self.pose_model is None:
            raise RuntimeError("Models not loaded — call load_models() first.")

        cfg = self.config
        sr = self.seg_model.predict(frame, conf=cfg.conf_thresh_seg, imgsz=cfg.img_size, verbose=False)[0]
        pr = self.pose_model.predict(frame, conf=cfg.conf_thresh_pose, imgsz=cfg.img_size, verbose=False)[0]

        si, sw = self._extract_seg(sr)
        pi, pw = self._extract_pose(pr)

        if len(si) and len(pi):
            ai, aw = np.vstack([si, pi]), np.vstack([sw, pw])
        elif len(pi):
            ai, aw = pi, pw
        else:
            ai, aw = si, sw

        if len(ai) < 4:
            return None

        H, _ = cv2.findHomography(
            ai, aw * cfg.px_per_meter,
            cv2.RANSAC,
            ransacReprojThreshold=cfg.ransac_thresh,
        )
        return H

    def pixel_to_pitch(self, H: np.ndarray, px: float, py: float) -> tuple[float, float]:
        """Project a single pixel point to pitch coordinates (meters)."""
        pt = cv2.perspectiveTransform(
            np.array([[[px, py]]], dtype=np.float32), H
        ).reshape(2)
        return float(pt[0] / self.config.px_per_meter), float(pt[1] / self.config.px_per_meter)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _extract_seg(self, results) -> tuple[np.ndarray, np.ndarray]:
        if results.masks is None:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32)

        IP, WP = [], []
        names = self.seg_model.names

        for mxy, ci in zip(results.masks.xy, results.boxes.cls):
            class_name = names[int(ci)]
            if class_name not in LINE_PAIR_TO_KEYPOINT:
                continue
            spec = LINE_PAIR_TO_KEYPOINT[class_name]

            if spec["type"] == "endpoints" and len(mxy) >= 2:
                p1, p2 = self._pca_endpoints(mxy)
                cands = [p1, p2]
            else:
                cands = [self._centroid(mxy)]

            for pt, key in zip(cands, spec["keys"]):
                if key in self.pitch_keypoints_real:
                    IP.append(pt)
                    WP.append(self.pitch_keypoints_real[key])

        return np.array(IP, np.float32), np.array(WP, np.float32)

    def _extract_pose(self, results) -> tuple[np.ndarray, np.ndarray]:
        if results.keypoints is None or len(results.keypoints) == 0:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32)

        IP, WP = [], []
        kpts = results.keypoints.xy[0].cpu().numpy()
        confs = (
            results.keypoints.conf[0].cpu().numpy()
            if results.keypoints.conf is not None
            else np.ones(len(kpts))
        )

        for idx, ((x, y), c) in enumerate(zip(kpts, confs)):
            if c < self.config.conf_thresh_pose or (x == 0 and y == 0) or idx not in self.pose_keypoints_real:
                continue
            IP.append([x, y])
            WP.append(self.pose_keypoints_real[idx])

        return np.array(IP, np.float32), np.array(WP, np.float32)

    @staticmethod
    def _centroid(mask_xy: np.ndarray) -> np.ndarray:
        return mask_xy.astype(np.float32).mean(axis=0)

    @staticmethod
    def _pca_endpoints(mask_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = mask_xy.astype(np.float32)
        c = p - p.mean(axis=0)
        _, _, vt = np.linalg.svd(c, full_matrices=False)
        proj = c @ vt[0]
        return p[np.argmin(proj)], p[np.argmax(proj)]
