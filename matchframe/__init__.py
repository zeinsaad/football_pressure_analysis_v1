"""
Frame table -- joins every upstream cache into player_frame_table /
ball_frame_table, the two tables every downstream stat module (passes,
pressure, possession, formation) reads from instead of the raw per-stage
caches. See pipeline.py for the full design note.
"""

from .config import FrameTableConfig, FORCE_REBUILD_FRAME_TABLE
from .pipeline import FrameTablePipeline, get_or_build_frame_tables, flag_valid_pitch_coords

__all__ = [
    "FrameTableConfig",
    "FORCE_REBUILD_FRAME_TABLE",
    "FrameTablePipeline",
    "get_or_build_frame_tables",
    "flag_valid_pitch_coords",
]
