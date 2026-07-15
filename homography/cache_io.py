"""
Homography cache I/O: build (raw pass + EMA smoothing + gap-fill), save,
load, and load-or-build.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from .engine import HomographyEngine


def save_cache(homography_cache: list, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(homography_cache, f)
    print(f"💾 Homography cache saved to '{path}'.")


def load_cache(path: str) -> list:
    with open(path, "rb") as f:
        return pickle.load(f)


def build_cache(engine: HomographyEngine, video_path: str, ema_alpha: float) -> list:
    """Compute homography for every frame, EMA-smooth, and gap-fill with the
    last valid H. Returns list[np.ndarray | None], one per frame."""
    if engine.seg_model is None or engine.pose_model is None:
        engine.load_models()

    print(f"📐 Computing homography for '{video_path}' ...")
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"Cannot open video: {video_path}"

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    raw_cache: list[np.ndarray | None] = []

    for _ in tqdm(range(total_frames), desc="Computing homography"):
        ret, frame = cap.read()
        if not ret:
            raw_cache.append(None)
            continue
        raw_cache.append(engine.get_homography(frame))

    cap.release()

    valid = sum(1 for h in raw_cache if h is not None)
    print(f"  Raw valid frames: {valid}/{total_frames} ({100*valid/total_frames:.1f}%)")

    smoothed: list[np.ndarray | None] = [None] * total_frames
    H_ema: np.ndarray | None = None

    for i, H in enumerate(raw_cache):
        if H is not None:
            H_ema = H.copy() if H_ema is None else ema_alpha * H + (1 - ema_alpha) * H_ema
            smoothed[i] = H_ema.copy()
        else:
            smoothed[i] = H_ema.copy() if H_ema is not None else None

    valid_smoothed = sum(1 for h in smoothed if h is not None)
    print(f"  After EMA + gap-fill: {valid_smoothed}/{total_frames} ({100*valid_smoothed/total_frames:.1f}%)")

    return smoothed


def get_or_build_cache(
    engine: HomographyEngine, video_path: str, cache_path: str,
    ema_alpha: float = 0.3, force_rebuild: bool = False,
) -> list:
    """Load homography_cache from cache_path if it already exists, otherwise
    build it over video_path and save the result."""
    if os.path.exists(cache_path) and not force_rebuild:
        print(f"✅ Homography cache found at '{cache_path}' — loading.")
        return load_cache(cache_path)

    print(f"📦 No cache found at '{cache_path}' (or force_rebuild=True) — computing homography...")
    cache = build_cache(engine, video_path, ema_alpha)
    save_cache(cache, cache_path)
    return cache
