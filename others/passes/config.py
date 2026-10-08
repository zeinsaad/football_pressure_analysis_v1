from dataclasses import dataclass


@dataclass
class PassConfig:
    # Bridges the exact same short carrier-assigner gaps that possession_team
    # already bridges in ball_frame_table -- a pass shouldn't be allowed to
    # jump a gap the carrier assigner itself considers "possession lost".
    # No default on purpose -- always pass carrier_cfg.no_candidate_grace_frames
    # explicitly from main.py so this can never silently drift out of sync
    # with the carrier assigner's own grace period.
    max_gap_frames: int

    # A possession segment shorter than this is almost certainly a tracking
    # blip (carrier flickers onto a nearby player for a couple frames)
    # rather than genuine control -- drop it before it can become a fake
    # passer/receiver. New constant, no upstream equivalent to import --
    # tune against the segment-length sanity-check stats.
    min_segment_frames: int = 5

    # Fraction of the gap between two possession segments that must be
    # untracked ("lost") for the gap to be classified as "ball left play"
    # (shot, dribble knocked out of bounds, clearance) rather than a
    # continuous pass.
    ball_lost_gap_fraction_max: float = 0.5

    # Same margin convention as FrameTableConfig.pitch_out_margin_m -- ball
    # pitch position beyond the pitch rectangle by more than this during a
    # gap means it physically left the field, so that gap isn't a pass no
    # matter how short.
    pitch_out_margin_m: float = 5.0

    fps: float = 25.0


FORCE_REBUILD_PASSES = True
