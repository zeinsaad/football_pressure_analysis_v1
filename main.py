"""
Root pipeline entry point. Wires together, in order:

    detector -> homography -> tracker -> team_assigner -> ball_tracker
             -> carrier assignment -> frame_table -> passes -> render

Every stage uses a load-or-build cache pattern: if that stage's output
already exists on disk, it's loaded instead of recomputed. Flip the
matching force-rebuild flag to force just that one stage to recompute.
File paths live in paths.py. Force-rebuild flags and tunable constants
(PX_PER_METER, FPS, etc.) live in each stage's own config.py -- paths.py
holds paths only.

frame_table and passes are pure post-processing over already-computed
caches (no video/model access), same category as ball_tracker and
ball_carrier -- so they slot in right after carrier assignment, before
render. render doesn't depend on either, so ordering relative to render
doesn't matter functionally; they're placed before it here so the full
stats stack finishes before the (slower) render pass starts.

Team resolution: team_assigner's output includes team_by_id (a flat,
lossy fallback -- one label per track, wrong for roughly half the frames
of any track flagged in team_result["switch_suspects"]), track_team_segments
(the real per-window history), and team_colors (the auto-detected real
average kit color per cluster, extracted from calibration torso-crop
pixels -- self-corrects across reruns even if KMeans' cluster label 0/1
assignment flips, unlike a hardcoded color-per-label mapping). Both
frame_table and render need track_team_segments threaded through, not just
team_by_id, or they silently fall back to the wrong team for any
switch_suspect track; render also needs team_colors so it never has to
guess which numeric label is which real team.
"""

import paths

from detector import DetectionConfig, DetectionPipeline
from detector import get_or_build_cache as get_or_build_detection_cache

from homography import HomographyConfig, HomographyEngine
from homography import get_or_build_cache as get_or_build_homography_cache
from homography import FORCE_REBUILD_HOMOGRAPHY

from tracker import TrackingConfig, TrackingPipeline
from tracker import get_or_build_cache as get_or_build_tracking_cache

from team_assigner import TeamAssignerConfig, TeamAssignerPipeline
from team_assigner import get_or_build_cache as get_or_build_team_cache

from ball_tracker import BallTrackerConfig, CarrierConfig
from ball_tracker import get_or_build_ball_tracked_cache, get_or_build_ball_carrier_cache
from ball_tracker import FORCE_REBUILD_BALL_TRACKER, FORCE_REBUILD_CARRIER, PX_PER_METER

from matchframe import FrameTableConfig, FrameTablePipeline
from matchframe import get_or_build_frame_tables, FORCE_REBUILD_FRAME_TABLE

from passes import PassConfig, PassesPipeline
from passes import get_or_build_pass_events, FORCE_REBUILD_PASSES
from passes import team_pass_stats, top_passers

from render import RenderConfig, RenderPipeline


def main():
    # ---- 1. detection ----
    det_cfg = DetectionConfig()
    det_pipeline = DetectionPipeline(det_cfg)
    det_pipeline.check_paths()
    detection_cache = get_or_build_detection_cache(
        det_pipeline, det_cfg.video_path, det_cfg.output_cache_path,
    )

    # ---- 2. homography ----
    # get_or_build_cache loads the seg/pose models and auto-calibrates
    # orientation itself the first time it actually needs to build.
    hom_cfg = HomographyConfig()
    hom_engine = HomographyEngine(hom_cfg)
    hom_engine.check_paths()
    homography_cache = get_or_build_homography_cache(
        hom_engine, hom_cfg.video_path, hom_cfg.output_cache_path,
        ema_alpha=hom_cfg.ema_alpha, force_rebuild=FORCE_REBUILD_HOMOGRAPHY,
    )

    # ---- 3. tracking ----
    trk_cfg = TrackingConfig()
    trk_pipeline = TrackingPipeline(trk_cfg)
    trk_pipeline.check_paths()
    tracking_result = get_or_build_tracking_cache(
        trk_pipeline, trk_cfg.video_path, trk_cfg.output_cache_path,
        detection_cache=detection_cache,
    )
    tracking_cache = tracking_result["tracking_cache"]
    locked_class_by_id = tracking_result["locked_class_by_id"]
    total_frames = len(tracking_cache)

    # ---- 4. team assignment ----
    team_cfg = TeamAssignerConfig()
    team_pipeline = TeamAssignerPipeline(team_cfg)
    team_pipeline.check_paths()
    team_result = get_or_build_team_cache(
        team_pipeline, team_cfg.video_path, team_cfg.output_cache_path,
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        homography_cache=homography_cache,
    )
    team_by_id = team_result["team_by_id"]
    # Segment-aware team history -- the real per-frame source of truth.
    # team_by_id alone is wrong for roughly half the frames of any track in
    # team_result["switch_suspects"]; everything below that needs a team
    # label per frame (frame_table, render) must use this, not team_by_id.
    track_team_segments = team_result["track_team_segments"]
    # Auto-detected real average kit color per cluster label -- self-
    # corrects across reruns even if KMeans' 0/1 label assignment flips.
    team_colors = team_result["team_colors"]

    # ---- 5. ball tracking (Kalman + RTS smoother) ----
    ball_cfg = BallTrackerConfig()
    ball_tracked_cache = get_or_build_ball_tracked_cache(
        detection_cache=detection_cache, tracking_cache=tracking_cache,
        locked_class_by_id=locked_class_by_id, homography_cache=homography_cache,
        cfg=ball_cfg, cache_path=paths.BALL_TRACKED_CACHE_PATH,
        force_rebuild=FORCE_REBUILD_BALL_TRACKER,
    )

    # ---- 6. ball-carrier assignment ----
    carrier_cfg = CarrierConfig()
    ball_carrier_cache = get_or_build_ball_carrier_cache(
        ball_tracked_cache=ball_tracked_cache, tracking_cache=tracking_cache,
        locked_class_by_id=locked_class_by_id, homography_cache=homography_cache,
        cfg=carrier_cfg, cache_path=paths.BALL_CARRIER_CACHE_PATH,
        force_rebuild=FORCE_REBUILD_CARRIER, px_per_meter=PX_PER_METER,
    )

    # ---- 7. frame table (stats join layer) ----
    # Joins every cache above into player_frame_table / ball_frame_table --
    # the only two tables everything past this point reads from.
    # track_team_segments is required here (not just team_by_id) so every
    # row's team is resolved per-frame -- see frame_table.py's
    # team_for_track_at_frame.
    frame_table_cfg = FrameTableConfig()
    frame_table_pipeline = FrameTablePipeline(frame_table_cfg)
    player_frame_table, ball_frame_table = get_or_build_frame_tables(
        frame_table_pipeline,
        player_cache_path=paths.PLAYER_FRAME_TABLE_CACHE_PATH,
        ball_cache_path=paths.BALL_FRAME_TABLE_CACHE_PATH,
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        team_by_id=team_by_id, track_team_segments=track_team_segments,
        homography_cache=homography_cache,
        ball_carrier_cache=ball_carrier_cache, ball_tracked_cache=ball_tracked_cache,
        total_frames=total_frames,
        pitch_length=hom_cfg.pitch_length, pitch_width=hom_cfg.pitch_width,
        px_per_meter=PX_PER_METER,
        possession_gap_limit=carrier_cfg.no_candidate_grace_frames,
        force_rebuild=FORCE_REBUILD_FRAME_TABLE,
    )

    # ---- 8. pass stats ----
    # max_gap_frames is always taken from carrier_cfg here, never hardcoded
    # in PassConfig -- keeps segment-bridging in sync with the carrier
    # assigner's own grace period, same reasoning as possession_gap_limit
    # above.
    pass_cfg = PassConfig(
        max_gap_frames=carrier_cfg.no_candidate_grace_frames,
        fps=ball_cfg.fps,
    )
    passes_pipeline = PassesPipeline(pass_cfg)
    pass_events = get_or_build_pass_events(
        passes_pipeline,
        cache_path=paths.PASS_EVENTS_CACHE_PATH,
        player_frame_table=player_frame_table, ball_frame_table=ball_frame_table,
        pitch_length=hom_cfg.pitch_length, pitch_width=hom_cfg.pitch_width,
        force_rebuild=FORCE_REBUILD_PASSES,
    )

    scored_passes = pass_events[~pass_events["is_turnover"]]
    n_turnovers = int(pass_events["is_turnover"].sum())
    print(
        f"\nPass events: {len(scored_passes)} scored "
        f"({n_turnovers} filtered as turnovers, not fake failed passes)"
    )
    print(team_pass_stats(scored_passes).to_string(index=False))

    # ---- 9. render ----
    # track_team_segments passed so render resolves team per-frame, same
    # as frame_table does. team_colors passed so the video always uses
    # each team's real detected kit color instead of a hardcoded guess.
    render_cfg = RenderConfig()
    render_pipeline = RenderPipeline(render_cfg)
    output_path = render_pipeline.render(
        tracking_cache=tracking_cache,
        locked_class_by_id=locked_class_by_id,
        team_by_id=team_by_id,
        track_team_segments=track_team_segments,
        #team_colors=team_colors,
        team_colors={0: (179, 0, 0), 1: (110, 238, 255)},
        ball_carrier_cache=ball_carrier_cache,
    )

    print(f"\nPipeline complete. Annotated video: {output_path}")

    return {
        "detection_cache": detection_cache,
        "homography_cache": homography_cache,
        "tracking_cache": tracking_cache,
        "locked_class_by_id": locked_class_by_id,
        "team_result": team_result,
        "ball_tracked_cache": ball_tracked_cache,
        "ball_carrier_cache": ball_carrier_cache,
        "player_frame_table": player_frame_table,
        "ball_frame_table": ball_frame_table,
        "pass_events": pass_events,
        "output_video_path": output_path,
    }


if __name__ == "__main__":
    main()
