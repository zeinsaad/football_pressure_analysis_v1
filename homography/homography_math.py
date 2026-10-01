from __future__ import annotations

import cv2
import numpy as np


class HomographyMathMixin:
    """Fits the homography matrix from correspondences and converts pixel<->pitch points."""

    def _compute_homography(self, ai, aw):
        if len(ai) < 4: return None, None
        cfg = self.config
        return cv2.findHomography(ai, aw * cfg.px_per_meter, cv2.RANSAC, ransacReprojThreshold=cfg.ransac_thresh)

    def get_homography(self, frame: np.ndarray, bootstrap_H: np.ndarray | None = None) -> np.ndarray | None:
        ai, aw, _ = self.get_correspondences(frame, bootstrap_H)
        H, _ = self._compute_homography(ai, aw)
        return self._enforce_reference_orientation(H)

    def get_homography_debug(self, frame: np.ndarray, bootstrap_H: np.ndarray | None = None):
        ai, aw, labels = self.get_correspondences(frame, bootstrap_H)
        H, mask = self._compute_homography(ai, aw)
        return self._enforce_reference_orientation(H), mask, ai, aw, labels

    def pixel_to_pitch(self, H, px, py):
        pt = cv2.perspectiveTransform(np.array([[[px, py]]], np.float32), H).reshape(2)
        return float(pt[0] / self.config.px_per_meter), float(pt[1] / self.config.px_per_meter)