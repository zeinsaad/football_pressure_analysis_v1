"""
Calibration: sample SigLIP torso embeddings across the whole match (only
from tracks locked as "player" — goalkeeper/referee excluded), then fit
KMeans(k=2) to separate the two kits.
"""

from __future__ import annotations

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder


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

    if len(calibration_features) > config.max_calibration_samples:
        rng = np.random.default_rng(42)
        keep_idx = rng.choice(len(calibration_features), size=config.max_calibration_samples, replace=False)
        keep_idx.sort()
        calibration_features = calibration_features[keep_idx]
        calibration_meta = [calibration_meta[i] for i in keep_idx]
        print(f"Subsampled down to {config.max_calibration_samples} (random, spanning full range).")

    print(f"Feature shape: {calibration_features.shape}")
    return calibration_features, calibration_meta


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
