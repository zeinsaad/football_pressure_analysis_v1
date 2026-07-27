from __future__ import annotations

import numpy as np

from .config import PX_PER_METER


def px_to_pitch(xy_px, H, px_per_meter: float = PX_PER_METER):
    """Projects an image-pixel point through homography H into pitch-space
    meters. Returns None if H is missing or the point is at infinity."""
    if H is None or xy_px is None:
        return None
    pt = np.array([xy_px[0], xy_px[1], 1.0])
    proj = H @ pt
    if abs(proj[2]) < 1e-8:
        return None
    x_m = proj[0] / proj[2] / px_per_meter
    y_m = proj[1] / proj[2] / px_per_meter
    return (x_m, y_m)