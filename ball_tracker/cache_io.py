from __future__ import annotations

import os
import pickle
from pathlib import Path

import paths
from .carrier import run_carrier_assigner
from .config import BallTrackerConfig, CarrierConfig, FORCE_REBUILD_BALL_TRACKER, FORCE_REBUILD_CARRIER, PX_PER_METER
from .tracking import run_ball_tracker


def save_cache(cache, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(cache, f)
    print(f"\U0001F4BE Saved to '{path}'.")


def load_cache(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def get_or_build_ball_tracked_cache(
    detection_cache, tracking_cache, locked_class_by_id, homography_cache,
    cfg: BallTrackerConfig, cache_path: str = paths.BALL_TRACKED_CACHE_PATH,
    total_frames: int | None = None, force_rebuild: bool | None = None,
):
    if force_rebuild is None:
        force_rebuild = FORCE_REBUILD_BALL_TRACKER

    if os.path.exists(cache_path) and not force_rebuild:
        print(f"\u2705 Loaded cache from '{cache_path}'.")
        return load_cache(cache_path)

    if total_frames is None:
        total_frames = max(detection_cache.keys()) + 1

    ball_tracked_cache, stats = run_ball_tracker(
        detection_cache, tracking_cache, locked_class_by_id, homography_cache, cfg, total_frames
    )
    print("Frames processed:", total_frames)
    for k, v in stats.items():
        print(f"  {k}: {v} ({100*v/total_frames:.1f}%)")

    save_cache(ball_tracked_cache, cache_path)
    return ball_tracked_cache


def get_or_build_ball_carrier_cache(
    ball_tracked_cache, tracking_cache, locked_class_by_id, homography_cache,
    cfg: CarrierConfig, cache_path: str = paths.BALL_CARRIER_CACHE_PATH,
    total_frames: int | None = None, force_rebuild: bool | None = None,
    px_per_meter: float = PX_PER_METER,
):
    if force_rebuild is None:
        force_rebuild = FORCE_REBUILD_CARRIER

    if os.path.exists(cache_path) and not force_rebuild:
        print(f"\u2705 Loaded cache from '{cache_path}'.")
        return load_cache(cache_path)

    if total_frames is None:
        total_frames = max(ball_tracked_cache.keys()) + 1

    ball_carrier_cache = run_carrier_assigner(
        ball_tracked_cache, tracking_cache, locked_class_by_id, homography_cache,
        cfg, total_frames, px_per_meter=px_per_meter,
    )

    n_assigned = sum(1 for v in ball_carrier_cache.values() if v["track_id"] is not None)
    n_contested = sum(1 for v in ball_carrier_cache.values() if v["method"] == "contested")
    print(f"Frames with a carrier assigned: {n_assigned}/{total_frames} ({100*n_assigned/total_frames:.1f}%)")
    print(f"Frames flagged contested: {n_contested}/{total_frames} ({100*n_contested/total_frames:.1f}%)")

    save_cache(ball_carrier_cache, cache_path)
    return ball_carrier_cache