"""
TeamAssignerPipeline: orchestrates SigLIP calibration, classification,
majority-vote locking, and pitch-space goalkeeper assignment.

Usage:

    from team_assigner import TeamAssignerConfig, TeamAssignerPipeline, get_or_build_cache

    pipeline = TeamAssignerPipeline(TeamAssignerConfig())
    team_cache = get_or_build_cache(
        pipeline, cfg.video_path, cfg.output_cache_path,
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        homography_cache=homography_cache,
    )
"""

from __future__ import annotations

import os

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder
from .calibration import sample_calibration_features, fit_kmeans
from .classification import classify_all_tracks, lock_teams
from .goalkeeper import assign_goalkeepers
from .cache_io import save_cache


class TeamAssignerPipeline:
    def __init__(self, config: TeamAssignerConfig):
        self.config = config
        self.embedder: SiglipEmbedder | None = None

    def check_paths(self) -> None:
        cfg = self.config
        print("Checking paths...")
        for p in [cfg.tracking_cache_path, cfg.video_path, cfg.homography_cache_path]:
            print(p, "->", "OK" if os.path.exists(p) else "MISSING")

    def load_models(self) -> None:
        self.embedder = SiglipEmbedder(self.config)
        print(f"SigLIP embedder ready on device={self.config.device}.")

    def run(
        self, tracking_cache: dict, locked_class_by_id: dict, homography_cache,
        video_path: str | None = None, save_to: str | None = None,
    ) -> dict:
        cfg = self.config
        video_path = video_path or cfg.video_path

        if self.embedder is None:
            self.load_models()

        # --- calibration ---
        calibration_features, calibration_meta = sample_calibration_features(
            self.embedder, tracking_cache, locked_class_by_id, video_path, cfg
        )
        scaler, kmeans, cluster_labels = fit_kmeans(calibration_features)

        # --- classification + locking ---
        raw_team_votes = classify_all_tracks(
            self.embedder, scaler, kmeans, tracking_cache, locked_class_by_id, video_path, cfg
        )
        locked_team_by_id = lock_teams(raw_team_votes, cfg)

        # --- goalkeeper assignment ---
        goalkeeper_team_assignment, team_centroids = assign_goalkeepers(
            tracking_cache, locked_class_by_id, locked_team_by_id, homography_cache, cfg
        )

        # --- merge ---
        final_team_by_id = dict(locked_team_by_id)
        final_team_by_id.update(goalkeeper_team_assignment)

        referee_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "referee"}
        print(f"Referee tracks (no team assigned): {sorted(referee_ids)}")

        result = {
            "team_by_id": final_team_by_id,
            "raw_team_votes": raw_team_votes,
            "goalkeeper_team_assignment": goalkeeper_team_assignment,
            "team_centroids": team_centroids,
        }

        print(f"\nFinal team assignment ({len(final_team_by_id)} tracks):")
        for tid in sorted(final_team_by_id):
            role = locked_class_by_id.get(tid, "?")
            print(f"  id={tid:2d} | {role:10s} | team={final_team_by_id[tid]}")

        if save_to:
            save_cache(result, save_to)

        return result
