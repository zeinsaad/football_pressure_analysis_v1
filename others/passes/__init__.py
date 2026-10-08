"""
Pass detection + stats -- built on player_frame_table / ball_frame_table.
See pipeline.py for the turnover-vs-pass classification design note.
"""

from .config import PassConfig, FORCE_REBUILD_PASSES
from .pipeline import PassesPipeline, get_or_build_pass_events
from .stats import team_pass_stats, top_passers

__all__ = [
    "PassConfig",
    "FORCE_REBUILD_PASSES",
    "PassesPipeline",
    "get_or_build_pass_events",
    "team_pass_stats",
    "top_passers",
]
