from __future__ import annotations

import cv2
import numpy as np


# Homography flips: findHomography has no idea what "left" or "right" means --
# it just fits whatever points it's given. When those points are ambiguous, it can
# lock onto a mirrored (left-right flipped) version of the correct mapping. It still
# looks fine visually, but every player position from that frame ends up on the wrong
# side of the pitch. This class detects and fixes that, frame by frame.
class OrientationMixin:
    """Self-calibrates and enforces a consistent left-right pitch orientation."""

    def _orientation_sign(self, H):
        # Checks if a homography is "normal" or "mirrored".
        # Projects a left-side and a right-side pixel point through H. If orientation
        # is correct, the right pixel should land further right on the pitch too.
        # Returns +1 (normal) or -1 (mirrored).
        pts = np.array([[[200.0, 540.0]], [[1700.0, 540.0]]], np.float32)
        proj = cv2.perspectiveTransform(pts, H).reshape(2, 2)
        return float(np.sign(proj[1, 0] - proj[0, 0]))

    def calibrate_reference_orientation_auto(self, video_path, sample_stride=50, max_samples=60, min_votes=5):
        # Figures out the "correct" orientation for this video automatically.
        # Samples frames across the whole match, checks each one's orientation sign,
        # and takes a confidence-weighted vote (better homographies count more).
        # The winning sign becomes the reference every future frame is checked against.
        # Avoids needing a human to manually pick one "correct" reference frame.
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
        idxs = list(range(0, total, max(sample_stride, 1)))[:max_samples]

        # Clear any existing reference first -- otherwise get_homography_debug()
        # below would auto-correct samples using the OLD reference before the
        # new one is even computed, which would bias the vote.
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
                if sign == 0: continue  # degenerate case, uninformative

                # Weight each vote by inlier count so confident frames count more.
                votes[sign] += float(mask.sum()) if mask is not None else 1.0
                n_valid += 1
        finally:
            # Restore prior state no matter what -- keeps the object clean if
            # something above raised an exception mid-loop.
            self.reference_orientation_sign = prev

        # Fail loudly instead of calibrating off too little evidence.
        if n_valid < min_votes:
            raise RuntimeError(f"Only {n_valid} valid samples -- can't calibrate reliably.")

        winner = 1.0 if votes[1.0] >= votes[-1.0] else -1.0
        total_w = votes[1.0] + votes[-1.0]
        agreement = 100 * votes[winner] / total_w if total_w else 0.0
        self.reference_orientation_sign = winner
        print(f"Orientation calibrated from {n_valid} frames -> sign={winner:+.0f} ({agreement:.1f}% agreement)")
        if agreement < 70.0:
            # Low agreement = correspondences are often ambiguous on this clip,
            # so homography quality may be shaky in general, not just orientation.
            print("\u26A0\uFE0F  Low agreement -- pipeline may be unreliable on this clip.")
        return winner

    def _enforce_reference_orientation(self, H):
        # The actual per-frame fix, applied every time a homography is computed.
        # If this H's orientation already matches the calibrated reference (or
        # there's no reference yet), leave it alone. Otherwise, apply a horizontal
        # flip so it matches -- keeps every frame's homography consistent, so a
        # player's pitch position can't suddenly jump to the opposite side of the
        # field just because one frame's correspondence resolution flipped.
        if H is None or self.reference_orientation_sign is None:
            return H
        sign = self._orientation_sign(H)
        if sign == 0 or sign == self.reference_orientation_sign:
            return H
        L_px = self.config.pitch_length * self.config.px_per_meter
        # Horizontal-flip matrix: negate x, then shift by pitch length so the
        # flipped coordinate stays within [0, L_px] instead of going negative.
        F = np.array([[-1.0, 0.0, L_px], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        return (F @ H).astype(H.dtype)