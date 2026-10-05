"""
TeamAssignerPipeline: orchestrates SigLIP calibration, classification,
windowed per-track team locking, pitch-space goalkeeper assignment, and
auto team-color extraction.
"""

from __future__ import annotations

import os

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder
from .calibration import sample_calibration_features, fit_kmeans, compute_team_colors
from .classification import classify_all_tracks, lock_teams_windowed
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

        # --- auto team-color extraction ---
        # Real average kit color per cluster, computed from the same
        # torso-crop pixels used for calibration -- self-corrects across
        # reruns even if KMeans' cluster label 0/1 assignment flips, since
        # the color is tied to the cluster's actual pixel content, not a
        # fixed number. Downstream render/annotation should use this
        # instead of a hardcoded TEAM_COLORS guess.
        team_colors = compute_team_colors(
            self.embedder, calibration_meta, cluster_labels, tracking_cache, video_path, cfg
        )

        # --- classification ---
        raw_team_votes, per_frame_team = classify_all_tracks(
            self.embedder, scaler, kmeans, tracking_cache, locked_class_by_id, video_path, cfg
        )

        # --- windowed locking (switch-robust) ---
        # Returns track_team_segments (per-window history, the real source
        # of truth), locked_team_by_id (backward-compatible single value,
        # only for tracks that never flip), switch_suspects, weak_windows.
        lock_result = lock_teams_windowed(per_frame_team, raw_team_votes, cfg)
        track_team_segments = lock_result["track_team_segments"]
        locked_team_by_id = lock_result["locked_team_by_id"]
        switch_suspects = lock_result["switch_suspects"]
        weak_windows = lock_result["weak_windows"]

        # --- goalkeeper assignment ---
        # NOTE: takes track_team_segments, not locked_team_by_id -- so
        # switch_suspect tracks still contribute correctly to team
        # centroids instead of being silently excluded or mis-attributed.
        goalkeeper_team_assignment, team_centroids = assign_goalkeepers(
            tracking_cache, locked_class_by_id, track_team_segments, homography_cache, cfg
        )

        # --- merge: best-effort single label for simple consumers ---
        # locked_team_by_id already covers every non-flip track. For
        # switch_suspect tracks (which have >1 team and so are NOT in
        # locked_team_by_id), fall back to the segment with the most total
        # votes -- purely so team_by_id has SOME value for every track.
        # This is a LOSSY summary: anything needing frame accuracy must use
        # team_for_track_at_frame(track_team_segments, tid, frame_idx)
        # instead of trusting this fallback value.
        final_team_by_id = dict(locked_team_by_id)
        for tid in switch_suspects:
            votes = raw_team_votes.get(tid, {})
            # raw_team_votes is whole-track totals -- adequate for a rough
            # single-label fallback, doesn't need window-level totals here.
            if votes:
                final_team_by_id[tid] = max(votes, key=votes.get)
        final_team_by_id.update(goalkeeper_team_assignment)

        referee_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "referee"}
        print(f"Referee tracks (no team assigned): {sorted(referee_ids)}")

        result = {
            "team_by_id": final_team_by_id,               # single-label fallback -- lossy for switch_suspects
            "track_team_segments": track_team_segments,     # frame-accurate source of truth
            "switch_suspects": switch_suspects,              # tracks with a detected team flip
            "weak_windows": weak_windows,                    # individual low-confidence windows
            "raw_team_votes": raw_team_votes,
            "goalkeeper_team_assignment": goalkeeper_team_assignment,
            "team_centroids": team_centroids,
            "team_colors": team_colors,                      # auto-detected {0: (b,g,r), 1: (b,g,r)}
        }

        print(f"\nFinal team assignment ({len(final_team_by_id)} tracks):")
        for tid in sorted(final_team_by_id):
            role = locked_class_by_id.get(tid, "?")
            flip_note = "  <-- FLIP TRACK, single label is lossy, use track_team_segments" \
                if tid in switch_suspects else ""
            print(f"  id={tid:2d} | {role:10s} | team={final_team_by_id[tid]}{flip_note}")

        if save_to:
            save_cache(result, save_to)

        return result
