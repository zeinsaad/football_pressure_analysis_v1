"""
Detection cache I/O: save, load, load-or-build, and summary stats.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import numpy as np


def save_cache(detection_cache: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(detection_cache, f)
    print(f"Saved cache to {path}")


def load_cache(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def get_or_build_cache(pipeline, video_path: str, cache_path: str, force_rebuild: bool = False) -> dict:
    """
    Load detection_cache from cache_path if it already exists, otherwise run
    the pipeline over video_path and save the result.

    Set force_rebuild=True to ignore an existing cache and recompute
    (e.g. after retraining a model).
    """
    if os.path.exists(cache_path) and not force_rebuild:
        print(f"✅ Detection cache found at '{cache_path}' — loading.")
        cache = load_cache(cache_path)
        print_summary(cache)
        return cache

    print(f"📦 No cache found at '{cache_path}' (or force_rebuild=True) — running detection...")
    if pipeline.multi_model is None or pipeline.ball_model is None:
        pipeline.load_models()

    return pipeline.run_on_video(video_path=video_path, save_to=cache_path)


def print_summary(detection_cache: dict) -> None:
    total_frames_cached = len(detection_cache)
    if total_frames_cached == 0:
        print("Empty cache.")
        return

    ball_present_frames = sum(
        1 for dets in detection_cache.values() if any(d["class"] == "ball" for d in dets)
    )
    ball_low_conf_frames = sum(
        1 for dets in detection_cache.values()
        if any(d["class"] == "ball" and d.get("low_confidence") for d in dets)
    )

    gk_counts = [sum(1 for d in dets if d["class"] == "goalkeeper") for dets in detection_cache.values()]
    ref_counts = [sum(1 for d in dets if d["class"] == "referee") for dets in detection_cache.values()]
    player_counts = [sum(1 for d in dets if d["class"] == "player") for dets in detection_cache.values()]

    print(f"\nTotal frames cached: {total_frames_cached}")
    print(f"Ball present: {ball_present_frames} ({100*ball_present_frames/total_frames_cached:.1f}%)")
    print(f"Ball present but low confidence: {ball_low_conf_frames}")
    print(
        f"Ball missing entirely: {total_frames_cached - ball_present_frames} "
        f"({100*(total_frames_cached-ball_present_frames)/total_frames_cached:.1f}%)"
    )

    print(f"\nGoalkeeper count/frame -> avg: {np.mean(gk_counts):.2f}, min: {min(gk_counts)}, max: {max(gk_counts)}")
    print(f"Referee count/frame    -> avg: {np.mean(ref_counts):.2f}, min: {min(ref_counts)}, max: {max(ref_counts)}")
    print(f"Player count/frame     -> avg: {np.mean(player_counts):.2f}, min: {min(player_counts)}, max: {max(player_counts)}")
