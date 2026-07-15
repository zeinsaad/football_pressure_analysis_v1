"""
Goalkeeper team assignment via pitch-space centroid proximity.

For each goalkeeper track, compute its average pitch-space position and the
average pitch-space position of each team's players (via homography), then
assign the goalkeeper to whichever team centroid is closer. Uses pitch
coordinates, not raw pixel distance — pixel-space distance is distorted by
camera perspective.
"""

from __future__ import annotations

import cv2
import numpy as np

from .config import TeamAssignerConfig


def project_to_pitch(point_px: tuple[float, float], H: np.ndarray, px_per_meter: int) -> tuple[float, float]:
    pt = cv2.perspectiveTransform(
        np.array([[[point_px[0], point_px[1]]]], dtype=np.float32), H
    ).reshape(2)
    return float(pt[0] / px_per_meter), float(pt[1] / px_per_meter)


def bbox_foot_point(bbox: list[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


def get_homography_at(homography_cache, frame_idx: int):
    """Homography cache may be a list indexed by frame or a dict keyed by frame_idx."""
    if isinstance(homography_cache, dict):
        return homography_cache.get(frame_idx)
    if 0 <= frame_idx < len(homography_cache):
        return homography_cache[frame_idx]
    return None


def get_track_positions(
    track_id: int, tracking_cache: dict, homography_cache, px_per_meter: int, sample_stride: int = 10,
) -> list[tuple[float, float]]:
    """Pitch-space positions for a track, sampled every sample_stride frames it appears in."""
    positions = []
    for frame_idx, data in tracking_cache.items():
        if frame_idx % sample_stride != 0:
            continue
        for t in data["tracks"]:
            if t["track_id"] == track_id:
                H = get_homography_at(homography_cache, frame_idx)
                if H is not None:
                    pos = project_to_pitch(bbox_foot_point(t["bbox"]), H, px_per_meter)
                    positions.append(pos)
                break
    return positions


def assign_goalkeepers(
    tracking_cache: dict, locked_class_by_id: dict, locked_team_by_id: dict,
    homography_cache, config: TeamAssignerConfig,
) -> tuple[dict, dict]:
    """Returns (goalkeeper_team_assignment, team_centroids)."""
    goalkeeper_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "goalkeeper"}
    print(f"Goalkeeper tracks to assign: {sorted(goalkeeper_ids)}")

    team_positions = {0: [], 1: []}
    for tid, team in locked_team_by_id.items():
        team_positions[team].extend(
            get_track_positions(tid, tracking_cache, homography_cache, config.px_per_meter, config.gk_position_sample_stride)
        )

    team_centroids = {
        team: np.mean(positions, axis=0) if positions else None
        for team, positions in team_positions.items()
    }
    print(f"\nTeam 0 centroid (pitch m): {team_centroids[0]}")
    print(f"Team 1 centroid (pitch m): {team_centroids[1]}")

    goalkeeper_team_assignment = {}
    for gk_id in goalkeeper_ids:
        gk_positions = get_track_positions(gk_id, tracking_cache, homography_cache, config.px_per_meter, config.gk_position_sample_stride)
        if not gk_positions:
            print(f"  id={gk_id}: no valid pitch positions found -- skipping")
            continue
        gk_centroid = np.mean(gk_positions, axis=0)

        dist0 = np.linalg.norm(gk_centroid - team_centroids[0]) if team_centroids[0] is not None else np.inf
        dist1 = np.linalg.norm(gk_centroid - team_centroids[1]) if team_centroids[1] is not None else np.inf

        assigned_team = 0 if dist0 < dist1 else 1
        goalkeeper_team_assignment[gk_id] = assigned_team
        print(f"  id={gk_id} | pitch pos: ({gk_centroid[0]:.1f}, {gk_centroid[1]:.1f})m "
              f"| dist_to_team0={dist0:.1f}m dist_to_team1={dist1:.1f}m -> team {assigned_team}")

    return goalkeeper_team_assignment, team_centroids
