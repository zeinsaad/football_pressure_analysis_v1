from dataclasses import dataclass
from typing import Optional


@dataclass
class FrameTableConfig:
    # Bound on the pitch-coord sanity check (flag_valid_pitch_coords) -- how
    # far outside the pitch rectangle a projected position can be before
    # it's nulled out as a degenerate-homography artifact rather than a
    # real (if slightly imprecise) position near the touchline.
    pitch_out_margin_m: float = 5.0

    # Set this if the clip crosses half-time (teams switch ends), so
    # attack_direction is inferred separately per half. Leave None for a
    # single continuous segment.
    half_boundary_frame: Optional[int] = None


# Default used by get_or_build_frame_tables() whenever the caller doesn't
# pass force_rebuild explicitly. FIX: this used to be defined here but never
# read anywhere in pipeline.py, so flipping it had zero effect unless a
# caller separately remembered to pass force_rebuild=True by hand.
FORCE_REBUILD_FRAME_TABLE = True
