from __future__ import annotations

import os
import pickle
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

import paths
from .config import FORCE_REBUILD_HOMOGRAPHY
from .engine import HomographyEngine


def save_cache(cache, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(cache, f)
    print(f"\U0001F4BE Saved to '{path}'.")


def load_cache(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _disagreement_px(H_a, H_b, pitch_keypoints_real, px_per_meter):
    pts = (np.array(list(pitch_keypoints_real.values()), np.float32) * px_per_meter).reshape(-1, 1, 2)
    try:
        pa = cv2.perspectiveTransform(pts, np.linalg.inv(H_a)).reshape(-1, 2)
        pb = cv2.perspectiveTransform(pts, np.linalg.inv(H_b)).reshape(-1, 2)
    except np.linalg.LinAlgError:
        return float("inf")
    return float(np.median(np.linalg.norm(pa - pb, axis=1)))


def _tag(labels):
    if any(l.endswith("_unresolved") for l in labels):
        return "unresolved"
    if any(l.endswith("_bootstrap") for l in labels):
        return "bootstrap"
    if any(l.endswith("_anchor") for l in labels):
        return "anchor"
    return "none"


def _ensure_ready(engine: HomographyEngine, video_path: str) -> None:
    """Load models and auto-calibrate orientation if not already done.
    This used to be two manual notebook cells the caller had to remember
    to run in order (load_models -> calibrate_reference_orientation_auto
    -> build_cache); folding it in here is what the old root main.py was
    missing, silently building H's with no orientation enforcement."""
    if engine.seg_model is None or engine.pose_model is None:
        engine.load_models()
    if engine.reference_orientation_sign is None:
        cfg = engine.config
        engine.calibrate_reference_orientation_auto(
            video_path,
            sample_stride=cfg.calib_sample_stride,
            max_samples=cfg.calib_max_samples,
            min_votes=cfg.calib_min_votes,
        )


def build_cache(engine: HomographyEngine, video_path: str, ema_alpha: float) -> list:
    """Confidence/jump-adaptive EMA, seeded only from anchor-resolved frames.
    Loads models and auto-calibrates orientation first if that hasn't
    happened yet."""
    _ensure_ready(engine, video_path)

    cfg = engine.config
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    smoothed, H_ema = [None] * total, None
    n_jumps, valid = 0, 0

    for i in tqdm(range(total), desc="Homography"):
        ret, frame = cap.read()
        if not ret:
            smoothed[i] = H_ema.copy() if H_ema is not None else None
            continue

        H_raw, mask, _, _, labels = engine.get_homography_debug(frame, bootstrap_H=H_ema)
        tag = _tag(labels)

        if H_raw is not None:
            valid += 1
            n_in = int(mask.sum()) if mask is not None else 0
            conf = min(1.0, n_in / max(cfg.min_inliers_full_confidence, 1))
            if H_ema is None:
                if tag == "anchor":
                    H_ema = H_raw.copy()
            else:
                jump = _disagreement_px(H_raw, H_ema, engine.pitch_keypoints_real, cfg.px_per_meter) > cfg.jump_px_threshold \
                       and conf >= cfg.jump_confidence_threshold
                alpha = ema_alpha * conf
                if jump:
                    alpha = max(alpha, cfg.jump_alpha)
                    n_jumps += 1
                alpha = float(np.clip(alpha, cfg.min_alpha, cfg.max_alpha))
                H_ema = alpha * H_raw + (1 - alpha) * H_ema

        smoothed[i] = H_ema.copy() if H_ema is not None else None

    cap.release()
    n_ok = sum(1 for h in smoothed if h is not None)
    print(f"Valid: {valid}/{total} | Final coverage: {n_ok}/{total} ({100*n_ok/total:.1f}%) | Jumps corrected: {n_jumps}")
    return smoothed


def get_or_build_cache(engine, video_path, cache_path, ema_alpha=0.3, force_rebuild=None):
    """Loads cache_path if it exists (and force_rebuild isn't set), otherwise
    builds it (models + orientation calibration + full-clip H cache) and
    saves it to cache_path. force_rebuild defaults to
    FORCE_REBUILD_HOMOGRAPHY (in homography/config.py) when not given explicitly."""
    if force_rebuild is None:
        force_rebuild = FORCE_REBUILD_HOMOGRAPHY

    if os.path.exists(cache_path) and not force_rebuild:
        print(f"\u2705 Loaded cache from '{cache_path}'.")
        return load_cache(cache_path)

    cache = build_cache(engine, video_path, ema_alpha)
    save_cache(cache, cache_path)
    return cache