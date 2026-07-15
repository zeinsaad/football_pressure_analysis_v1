"""
Root pipeline entry point. Wires together, in order:

    detector -> homography -> tracker -> team_assigner -> render

Every stage uses a load-or-build cache pattern: if that stage's output
already exists on disk (per paths.py), it's loaded instead of recomputed.
Set force_rebuild=True on any get_or_build_cache() call below to force
that one stage to recompute.

Fill in every path in paths.py before running this.
"""

import paths

from detector import DetectionConfig, DetectionPipeline
from detector import get_or_build_cache as get_or_build_detection_cache

from homography import HomographyConfig, HomographyEngine
from homography import get_or_build_cache as get_or_build_homography_cache

from tracker import TrackingConfig, TrackingPipeline
from tracker import get_or_build_cache as get_or_build_tracking_cache

from team_assigner import TeamAssignerConfig, TeamAssignerPipeline
from team_assigner import get_or_build_cache as get_or_build_team_cache

from render import RenderConfig, RenderPipeline


def main():
    # ---- 1. detection ----
    det_cfg = DetectionConfig()
    det_pipeline = DetectionPipeline(det_cfg)
    det_pipeline.check_paths()
    detection_cache = get_or_build_detection_cache(
        det_pipeline, det_cfg.video_path, det_cfg.output_cache_path
    )

    # ---- 2. homography ----
    hom_cfg = HomographyConfig()
    hom_engine = HomographyEngine(hom_cfg)
    homography_cache = get_or_build_homography_cache(
        hom_engine, hom_cfg.video_path, hom_cfg.output_cache_path, ema_alpha=hom_cfg.ema_alpha
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

    # ---- 5. render ----
    render_cfg = RenderConfig()
    render_pipeline = RenderPipeline(render_cfg)
    output_path = render_pipeline.render(
        tracking_cache=tracking_cache,
        locked_class_by_id=locked_class_by_id,
        team_by_id=team_by_id,
    )

    print(f"\nPipeline complete. Annotated video: {output_path}")

    return {
        "detection_cache": detection_cache,
        "homography_cache": homography_cache,
        "tracking_cache": tracking_cache,
        "locked_class_by_id": locked_class_by_id,
        "team_result": team_result,
        "output_video_path": output_path,
    }


if __name__ == "__main__":
    main()
