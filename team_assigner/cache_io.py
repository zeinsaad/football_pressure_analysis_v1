"""
Team assignment cache I/O: save, load, load-or-build.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path


def save_cache(result: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(result, f)
    print(f"\nSaved to {path}")


def load_cache(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def get_or_build_cache(
    pipeline, video_path: str, cache_path: str,
    tracking_cache: dict, locked_class_by_id: dict, homography_cache,
    force_rebuild: bool = False,
) -> dict:
    """
    Load {"team_by_id":, "track_team_segments":, "switch_suspects":,
    "weak_windows":, "raw_team_votes":, "goalkeeper_team_assignment":,
    "team_centroids":} from cache_path if it already exists, otherwise run
    the full team-assignment pipeline and save it.

    "team_by_id" is a flat, lossy single-label-per-track fallback -- for
    any track_id in "switch_suspects" it is NOT frame-accurate. Anything
    downstream that needs per-frame correctness (frame_table, render,
    passes) should use "track_team_segments" via
    team_assigner.classification.team_for_track_at_frame instead of
    trusting "team_by_id" alone.
    """
    if os.path.exists(cache_path) and not force_rebuild:
        print(f"✅ Team assignment cache found at '{cache_path}' — loading.")
        return load_cache(cache_path)

    print(f"📦 No cache found at '{cache_path}' (or force_rebuild=True) — running team assignment...")
    if pipeline.embedder is None:
        pipeline.load_models()

    return pipeline.run(
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        homography_cache=homography_cache, video_path=video_path, save_to=cache_path,
    )
