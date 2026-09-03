"""
Calibration: sample SigLIP torso embeddings across the whole match (only
from tracks locked as "player" — goalkeeper/referee excluded), then fit
KMeans(k=2) to separate the two kits. Also auto-extracts each cluster's
real average kit color from the raw torso-crop pixels, so downstream
rendering never has to guess or hardcode which numeric cluster label (0/1)
maps to which real-world team -- see compute_team_colors.
"""

from __future__ import annotations

import colorsys

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder


# Collect player torso embeddings from different frames across the match.
# These samples are used to learn the two team kit clusters with KMeans.
def sample_calibration_features(
    embedder: SiglipEmbedder, tracking_cache: dict, locked_class_by_id: dict,
    video_path: str, config: TeamAssignerConfig,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Returns (calibration_features, calibration_meta) where calibration_meta
    is a list of (frame_idx, track_id) aligned with calibration_features rows."""
    player_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "player"}
    print(f"Player-class tracks eligible for calibration: {len(player_ids)}")

    calibration_features = []
    calibration_meta: list[tuple[int, int]] = []

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % config.calibration_frame_stride == 0:
            data = tracking_cache.get(frame_idx, {"tracks": []})
            for t in data["tracks"]:
                if t["track_id"] not in player_ids:
                    continue
                feat = embedder.extract(frame, t["bbox"])
                if feat is not None:
                    calibration_features.append(feat)
                    calibration_meta.append((frame_idx, t["track_id"]))

        if frame_idx % config.log_every_n_frames == 0:
            print(f"  scanning frame {frame_idx} -- {len(calibration_features)} samples so far")
        frame_idx += 1

    cap.release()

    calibration_features = np.array(calibration_features)
    print(f"\nCollected {len(calibration_features)} SigLIP calibration embeddings "
          f"across the full match (frames 0-{frame_idx - 1}).")

    # Limit the number of samples while keeping a random distribution over the match.
    if len(calibration_features) > config.max_calibration_samples:
        rng = np.random.default_rng(42)
        keep_idx = rng.choice(len(calibration_features), size=config.max_calibration_samples, replace=False)
        keep_idx.sort()
        calibration_features = calibration_features[keep_idx]
        calibration_meta = [calibration_meta[i] for i in keep_idx]
        print(f"Subsampled down to {config.max_calibration_samples} (random, spanning full range).")

    print(f"Feature shape: {calibration_features.shape}")
    return calibration_features, calibration_meta


# Normalize embeddings and fit a two-cluster KMeans model to separate the
# two team kits. The silhouette score is used to evaluate cluster quality.
def fit_kmeans(calibration_features: np.ndarray) -> tuple[StandardScaler, KMeans, np.ndarray]:
    """Returns (scaler, kmeans, cluster_labels). Prints a silhouette-score
    sanity check — >0.5 well separated, 0.2-0.5 weak, <0.2 not meaningfully
    separated (consider zero-shot text-image similarity instead)."""
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(calibration_features)

    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
    cluster_labels = kmeans.fit_predict(scaled_features)

    print(f"Cluster sizes: {np.bincount(cluster_labels)}")

    sample_idx = np.random.default_rng(0).choice(
        len(scaled_features), size=min(2000, len(scaled_features)), replace=False
    )
    sil_score = silhouette_score(scaled_features[sample_idx], cluster_labels[sample_idx])
    print(f"\nSilhouette score (sampled): {sil_score:.3f}")
    print("  > 0.5 -> well separated")
    print("  0.2-0.5 -> weak separation, expect noisy per-frame team assignment")
    print("  < 0.2 -> clusters not meaningfully separated -- consider zero-shot SigLIP")
    print("           text-image similarity instead of KMeans on the pooled vector")

    return scaler, kmeans, cluster_labels


def _is_grass_dominant(pixels_bgr: np.ndarray, thresh: float) -> np.ndarray:
    """Vectorized grass filter -- True where green is clearly the dominant
    channel (typical pitch grass: bright, saturated green). pixels_bgr is
    (N, 3). thresh is a ratio, not an absolute, so it holds up across
    different lighting/exposure."""
    b, g, r = pixels_bgr[:, 0], pixels_bgr[:, 1], pixels_bgr[:, 2]
    return (g > b * thresh) & (g > r * thresh)


def _boost_saturation(
    bgr: tuple[int, int, int], factor: float, min_lightness: float, max_lightness: float,
) -> tuple[int, int, int]:
    b, g, r = [c / 255.0 for c in bgr]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s = min(1.0, s * factor)
    l = max(min_lightness, min(max_lightness, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(b * 255), int(g * 255), int(r * 255))


def compute_team_colors(
    embedder: SiglipEmbedder, calibration_meta: list[tuple[int, int]], cluster_labels: np.ndarray,
    tracking_cache: dict, video_path: str, config: TeamAssignerConfig,
) -> dict:
    """For each of the two clusters, computes a representative BGR color
    from the actual torso-crop pixels used during calibration (not the
    SigLIP embedding itself), and returns it saturation-boosted for use as
    a render color. This is what render/annotation should use for
    TEAM_COLORS, instead of a hardcoded guess -- since KMeans cluster label
    0 vs. 1 is arbitrary per run (depends on centroid initialization/
    convergence, not which team is "really" 0), a fixed color-per-label
    mapping can silently end up backwards after any recalibration. Tying
    the color to the cluster's actual pixel content instead makes it
    self-correcting.

    Two things address raw-pixel-averaging pitfalls found during real-match
    debugging, both empirically validated (not just theoretical) against
    this match's own footage:

    1. Small/distant bboxes have a grass margin only a few pixels wide even
       after the torso-crop side margins, so ANY grass bleed at the crop
       edge disproportionately skews a tiny crop's average -- confirmed by
       inspecting actual sampled crops. Only bboxes above the
       config.color_extraction_min_area_percentile-th percentile of this
       match's own candidate bbox sizes are used, computed from the data,
       not a fixed guess (a fixed absolute area threshold can end up above
       every bbox this footage ever produces).
    2. Even after that, and after excluding grass-dominant pixels directly,
       raw-averaged colors from real broadcast footage came out muted/
       desaturated (confirmed: filtering barely moved the extracted values,
       so this reflects genuine broadcast color grading/lighting, not a
       crop-quality bug). A saturation boost afterward makes the result
       visually usable as a render color without changing which cluster
       maps to which color.

    Returns {0: (b,g,r), 1: (b,g,r)} -- saturation-boosted, ready to use.
    """
    # ---- Step 1: pick the crop-size floor from this match's own data ----
    areas_by_key: dict[tuple[int, int], float] = {}
    for frame_idx, track_id in calibration_meta:
        data = tracking_cache.get(frame_idx, {"tracks": []})
        for t in data["tracks"]:
            if t["track_id"] == track_id:
                x1, y1, x2, y2 = t["bbox"]
                areas_by_key[(frame_idx, track_id)] = (x2 - x1) * (y2 - y1)
                break

    if not areas_by_key:
        print("No calibration candidates to compute team colors from -- returning gray fallback for both.")
        return {0: (128, 128, 128), 1: (128, 128, 128)}

    min_area = float(np.percentile(list(areas_by_key.values()), config.color_extraction_min_area_percentile))
    print(f"Color extraction: using only bboxes above the "
          f"{config.color_extraction_min_area_percentile:.0f}th percentile "
          f"(area >= {min_area:.0f}px^2) of {len(areas_by_key)} candidates.")

    # ---- Step 2: single sequential video pass, only over frames actually needed ----
    sums = {0: np.zeros(3, dtype=np.float64), 1: np.zeros(3, dtype=np.float64)}
    counts = {0: 0, 1: 0}
    crops_used = {0: 0, 1: 0}
    crops_skipped_too_small = 0
    grass_pixels_excluded = 0
    total_pixels_seen = 0

    by_frame: dict = {}
    for (frame_idx, track_id), label in zip(calibration_meta, cluster_labels):
        by_frame.setdefault(frame_idx, []).append((track_id, int(label)))

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    max_needed = max(by_frame.keys())
    while frame_idx <= max_needed:
        needed = frame_idx in by_frame
        if needed:
            ret, frame = cap.read()
        else:
            ret = cap.grab()
            frame = None
        if not ret:
            break
        if needed:
            data = tracking_cache.get(frame_idx, {"tracks": []})
            bbox_by_id = {t["track_id"]: t["bbox"] for t in data["tracks"]}
            for track_id, label in by_frame[frame_idx]:
                bbox = bbox_by_id.get(track_id)
                if bbox is None:
                    continue
                if areas_by_key.get((frame_idx, track_id), 0) < min_area:
                    crops_skipped_too_small += 1
                    continue

                torso = embedder.get_torso_crop(frame, bbox)
                if torso is None or torso.size == 0:
                    continue

                pixels = torso.reshape(-1, 3).astype(np.float64)
                total_pixels_seen += len(pixels)

                grass_mask = _is_grass_dominant(pixels, config.color_grass_dominance_thresh)
                grass_pixels_excluded += int(grass_mask.sum())

                kept = pixels[~grass_mask]
                if len(kept) == 0:
                    continue

                sums[label] += kept.sum(axis=0)
                counts[label] += len(kept)
                crops_used[label] += 1
        frame_idx += 1
    cap.release()

    print(f"Crops skipped as too small: {crops_skipped_too_small}")
    print(f"Crops used: team0={crops_used[0]}, team1={crops_used[1]}")
    print(f"Excluded {grass_pixels_excluded}/{total_pixels_seen} pixels "
          f"({100 * grass_pixels_excluded / max(total_pixels_seen, 1):.1f}%) as grass-dominant.")

    team_colors_raw = {}
    for label in (0, 1):
        if counts[label] > 0:
            b, g, r = (sums[label] / counts[label]).astype(int)
            team_colors_raw[label] = (int(b), int(g), int(r))
        else:
            team_colors_raw[label] = (128, 128, 128)
            print(f"  [WARNING] cluster {label} got zero usable pixels for color extraction "
                  f"-- using gray fallback. Try lowering color_extraction_min_area_percentile "
                  f"in the config if this happens.")

    # ---- Step 3: saturation boost -- makes a muted-but-accurate extraction
    # visually usable without changing which cluster maps to which color ----
    team_colors = {
        label: _boost_saturation(
            bgr, config.color_saturation_boost_factor,
            config.color_min_lightness, config.color_max_lightness,
        )
        for label, bgr in team_colors_raw.items()
    }

    print(f"Raw extracted team colors (BGR):    {team_colors_raw}")
    print(f"Saturation-boosted team colors (BGR): {team_colors}")

    return team_colors
