"""
Tracking cache I/O: save, load, load-or-build.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path


def save_cache(result: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(result, f)
    print(f"Saved to {path}")
    print("Raw per-frame classes preserved in tracking_cache; final labels in locked_class_by_id.")


def load_cache(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def get_or_build_cache(
    pipeline, video_path: str, cache_path: str,
    detection_cache: dict, force_rebuild: bool = False,
) -> dict:
    """
    Load {"tracking_cache":, "locked_class_by_id":} from cache_path if it
    already exists, otherwise run the full tracking pipeline and save it.

    detection_cache is required — the tracker needs it to build detections
    per frame (and to pull ball detections when rebuilding the final cache).
    """
    if os.path.exists(cache_path) and not force_rebuild:
        print(f"✅ Tracking cache found at '{cache_path}' — loading.")
        return load_cache(cache_path)

    print(f"📦 No cache found at '{cache_path}' (or force_rebuild=True) — running tracking pipeline...")
    if pipeline.tracker is None:
        pipeline.load_models()

    return pipeline.run(detection_cache=detection_cache, video_path=video_path, save_to=cache_path)
