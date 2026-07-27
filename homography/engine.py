from __future__ import annotations

import cv2
import numpy as np
from ultralytics import YOLO

from .config import HomographyConfig
from .keypoints import (
    LINE_PAIR_TO_KEYPOINT,
    TRUSTED_ANCHOR_POSE_INDICES,
    build_pitch_keypoints,
    build_pose_keypoints,
)


class HomographyEngine:
    def __init__(self, config: HomographyConfig):
        self.config = config
        self.seg_model: YOLO | None = None
        self.pose_model: YOLO | None = None
        self.pitch_keypoints_real = build_pitch_keypoints(config.pitch_length, config.pitch_width)
        self.pose_keypoints_real = build_pose_keypoints(self.pitch_keypoints_real)
        self.reference_orientation_sign: float | None = None

    def check_paths(self) -> None:
        import os
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

    # -- correspondences -------------------------------------------------

    def get_correspondences(self, frame: np.ndarray, bootstrap_H: np.ndarray | None = None):
        """Extract (image_pts, world_pts_m, labels). Ambiguous line pairings
        are resolved via: (1) a pose-based anchor built only from the
        reliable subset, validated by inlier ratio; (2) bootstrap_H (the
        previous frame's H) if no anchor; (3) unresolved dual-candidate as
        last resort."""
        cfg = self.config
        sr = self.seg_model.predict(frame, conf=cfg.conf_thresh_seg, imgsz=cfg.img_size, verbose=False)[0]
        pr = self.pose_model.predict(frame, conf=cfg.conf_thresh_pose, imgsz=cfg.img_size, verbose=False)[0]

        pose_i, pose_w, pose_l, pose_idx = self._extract_pose(pr)
        centroid_i, centroid_w, centroid_l = self._extract_seg_centroids(sr)
        endpoint_lines = self._extract_seg_endpoint_candidates(sr)

        trusted = np.array([i in TRUSTED_ANCHOR_POSE_INDICES for i in pose_idx], dtype=bool)
        anchor_i = self._vstack(pose_i[trusted] if len(pose_i) else pose_i, centroid_i)
        anchor_w = self._vstack(pose_w[trusted] if len(pose_w) else pose_w, centroid_w)

        H_resolver, tag = None, "unresolved"
        if len(anchor_i) >= cfg.min_anchor_points:
            H_cand, mask_cand = self._compute_homography(anchor_i, anchor_w)
            if H_cand is not None:
                ratio = float(mask_cand.sum()) / len(mask_cand)
                if ratio >= cfg.min_anchor_inlier_ratio and int(mask_cand.sum()) >= cfg.min_anchor_points:
                    H_resolver, tag = H_cand, "anchor"
        if H_resolver is None and bootstrap_H is not None:
            H_resolver, tag = bootstrap_H, "bootstrap"

        resolved_i, resolved_w, resolved_l = [], [], []
        for p1, p2, key0, key1 in endpoint_lines:
            w0 = np.array(self.pitch_keypoints_real[key0], np.float32)
            w1 = np.array(self.pitch_keypoints_real[key1], np.float32)
            if H_resolver is not None:
                proj = cv2.perspectiveTransform(
                    np.array([[p1], [p2]], np.float32), H_resolver
                ).reshape(2, 2) / cfg.px_per_meter
                if np.linalg.norm(proj[0]-w1)+np.linalg.norm(proj[1]-w0) < np.linalg.norm(proj[0]-w0)+np.linalg.norm(proj[1]-w1):
                    p1, p2 = p2, p1
                resolved_i += [p1, p2]; resolved_w += [w0, w1]
                resolved_l += [f"{key0}_{tag}", f"{key1}_{tag}"]
            else:
                resolved_i += [p1, p2, p1, p2]; resolved_w += [w0, w1, w1, w0]
                resolved_l += [f"{key0}_unresolved"] * 2 + [f"{key1}_unresolved"] * 2

        resolved_i = np.array(resolved_i, np.float32) if resolved_i else np.empty((0, 2), np.float32)
        resolved_w = np.array(resolved_w, np.float32) if resolved_w else np.empty((0, 2), np.float32)

        ai = self._vstack(self._vstack(pose_i, centroid_i), resolved_i)
        aw = self._vstack(self._vstack(pose_w, centroid_w), resolved_w)
        return ai, aw, pose_l + centroid_l + resolved_l

    @staticmethod
    def _vstack(a, b):
        if len(a) and len(b): return np.vstack([a, b])
        return a if len(a) else b

    def _compute_homography(self, ai, aw):
        if len(ai) < 4: return None, None
        cfg = self.config
        return cv2.findHomography(ai, aw * cfg.px_per_meter, cv2.RANSAC, ransacReprojThreshold=cfg.ransac_thresh)

    # -- public API --------------------------------------------------------

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

    # -- orientation invariant, self-calibrating ----------------------------

    def _orientation_sign(self, H):
        pts = np.array([[[200.0, 540.0]], [[1700.0, 540.0]]], np.float32)
        proj = cv2.perspectiveTransform(pts, H).reshape(2, 2)
        return float(np.sign(proj[1, 0] - proj[0, 0]))

    def calibrate_reference_orientation_auto(self, video_path, sample_stride=50, max_samples=60, min_votes=5):
        """No manual reference frame needed: samples frames across the whole
        clip, votes (weighted by inlier count) on the majority orientation,
        and locks that in as the reference every H is checked against."""
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
        idxs = list(range(0, total, max(sample_stride, 1)))[:max_samples]

        prev, self.reference_orientation_sign = self.reference_orientation_sign, None
        votes, n_valid = {1.0: 0.0, -1.0: 0.0}, 0
        try:
            for idx in idxs:
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read(); cap.release()
                if not ret: continue
                H, mask, _, _, _ = self.get_homography_debug(frame)
                if H is None: continue
                sign = self._orientation_sign(H)
                if sign == 0: continue
                votes[sign] += float(mask.sum()) if mask is not None else 1.0
                n_valid += 1
        finally:
            self.reference_orientation_sign = prev

        if n_valid < min_votes:
            raise RuntimeError(f"Only {n_valid} valid samples -- can't calibrate reliably.")

        winner = 1.0 if votes[1.0] >= votes[-1.0] else -1.0
        total_w = votes[1.0] + votes[-1.0]
        agreement = 100 * votes[winner] / total_w if total_w else 0.0
        self.reference_orientation_sign = winner
        print(f"Orientation calibrated from {n_valid} frames -> sign={winner:+.0f} ({agreement:.1f}% agreement)")
        if agreement < 70.0:
            print("\u26A0\uFE0F  Low agreement -- pipeline may be unreliable on this clip.")
        return winner

    def _enforce_reference_orientation(self, H):
        if H is None or self.reference_orientation_sign is None:
            return H
        sign = self._orientation_sign(H)
        if sign == 0 or sign == self.reference_orientation_sign:
            return H
        L_px = self.config.pitch_length * self.config.px_per_meter
        F = np.array([[-1.0, 0.0, L_px], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        return (F @ H).astype(H.dtype)

    # -- internal extraction -----------------------------------------------

    def _extract_seg_centroids(self, results):
        if results.masks is None:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), []
        IP, WP, LB = [], [], []
        names = self.seg_model.names
        for mxy, ci in zip(results.masks.xy, results.boxes.cls):
            spec = LINE_PAIR_TO_KEYPOINT.get(names[int(ci)])
            if spec is None or spec["type"] != "centroid": continue
            key = spec["keys"][0]
            if key in self.pitch_keypoints_real:
                IP.append(self._centroid(mxy)); WP.append(self.pitch_keypoints_real[key]); LB.append(key)
        return np.array(IP, np.float32), np.array(WP, np.float32), LB

    def _extract_seg_endpoint_candidates(self, results):
        if results.masks is None: return []
        out = []
        names = self.seg_model.names
        for mxy, ci in zip(results.masks.xy, results.boxes.cls):
            spec = LINE_PAIR_TO_KEYPOINT.get(names[int(ci)])
            if spec is None or spec["type"] != "endpoints" or len(mxy) < 2: continue
            key0, key1 = spec["keys"]
            if key0 not in self.pitch_keypoints_real or key1 not in self.pitch_keypoints_real: continue
            p1, p2 = self._pca_endpoints(mxy)
            out.append((p1, p2, key0, key1))
        return out

    def _extract_pose(self, results):
        if results.keypoints is None or len(results.keypoints) == 0:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), [], []
        IP, WP, LB, IDX = [], [], [], []
        kpts = results.keypoints.xy[0].cpu().numpy()
        confs = results.keypoints.conf[0].cpu().numpy() if results.keypoints.conf is not None else np.ones(len(kpts))
        for idx, ((x, y), c) in enumerate(zip(kpts, confs)):
            if c < self.config.conf_thresh_pose or (x == 0 and y == 0) or idx not in self.pose_keypoints_real:
                continue
            IP.append([x, y]); WP.append(self.pose_keypoints_real[idx]); LB.append(f"pose_{idx}"); IDX.append(idx)
        return np.array(IP, np.float32), np.array(WP, np.float32), LB, IDX

    @staticmethod
    def _centroid(mask_xy):
        return mask_xy.astype(np.float32).mean(axis=0)

    @staticmethod
    def _pca_endpoints(mask_xy):
        p = mask_xy.astype(np.float32)
        c = p - p.mean(axis=0)
        _, _, vt = np.linalg.svd(c, full_matrices=False)
        proj = c @ vt[0]
        return p[np.argmin(proj)], p[np.argmax(proj)]
