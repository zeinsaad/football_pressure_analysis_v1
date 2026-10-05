from __future__ import annotations

import cv2
import numpy as np

from .keypoints import LINE_PAIR_TO_KEYPOINT, TRUSTED_ANCHOR_POSE_INDICES


class CorrespondenceMixin:
    """Extracts pixel<->pitch point correspondences from a frame's model outputs."""

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