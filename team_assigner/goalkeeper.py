"""
Goalkeeper team assignment via pitch-space centroid proximity.

For each goalkeeper track, compute its average pitch-space position and the
average pitch-space position of each team's players (via homography), then
assign the goalkeeper to whichever team centroid is closer. Uses pitch
coordinates, not raw pixel distance — pixel-space distance is distorted by
camera perspective.

Team centroids are built using team_for_track_at_frame per SAMPLED
POSITION, not one flat team label per track -- so a switch_suspect track's
positions are correctly split between the two teams' centroids instead of
all being attributed to whichever team happened to win that track's
now-defunct whole-track vote.
"""

from __future__ import annotations

import cv2
import numpy as np

from .config import TeamAssignerConfig
from .classification import team_for_track_at_frame


# Convert a pixel coordinate from the camera view into real pitch coordinates
# using the homography transformation.
def project_to_pitch(point_px: tuple[float, float], H: np.ndarray, px_per_meter: int) -> tuple[float, float]:
    pt = cv2.perspectiveTransform(
        np.array([[[point_px[0], point_px[1]]]], dtype=np.float32), H
    ).reshape(2)
    return float(pt[0] / px_per_meter), float(pt[1] / px_per_meter)


# Get the player's ground contact point from the bounding box.
# The bottom-center point is used because it represents the player's location
# on the pitch better than the box center.
def bbox_foot_point(bbox: list[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


# Retrieve the homography matrix for a specific frame.
# Supports both frame-indexed lists and dictionaries.
def get_homography_at(homography_cache, frame_idx: int):
    """Homography cache may be a list indexed by frame or a dict keyed by frame_idx."""
    if isinstance(homography_cache, dict):
        return homography_cache.get(frame_idx)
    if 0 <= frame_idx < len(homography_cache):
        return homography_cache[frame_idx]
    return None


# Collect sampled pitch-space positions for a specific tracked player, WITH
# the frame_idx each position came from -- needed so callers can resolve
# which team was actually in effect at each sampled frame (see
# team_for_track_at_frame), instead of assuming one team for the whole
# track.
def get_track_positions_with_frame(
    track_id: int, tracking_cache: dict, homography_cache, px_per_meter: int, sample_stride: int = 10,
) -> list[tuple[int, tuple[float, float]]]:
    """Returns [(frame_idx, (pitch_x, pitch_y)), ...]."""
    positions = []
    for frame_idx, data in tracking_cache.items():
        if frame_idx % sample_stride != 0:
            continue
        for t in data["tracks"]:
            if t["track_id"] == track_id:
                H = get_homography_at(homography_cache, frame_idx)
                if H is not None:
                    pos = project_to_pitch(bbox_foot_point(t["bbox"]), H, px_per_meter)
                    positions.append((frame_idx, pos))
                break
    return positions


def get_track_positions(
    track_id: int, tracking_cache: dict, homography_cache, px_per_meter: int, sample_stride: int = 10,
) -> list[tuple[float, float]]:
    """Backward-compatible wrapper -- positions only, no frame index."""
    return [pos for _, pos in get_track_positions_with_frame(
        track_id, tracking_cache, homography_cache, px_per_meter, sample_stride
    )]


# Assign goalkeeper identities to teams by comparing their pitch-space location
# with the average pitch position of each team's players.
def assign_goalkeepers(
    tracking_cache: dict, locked_class_by_id: dict, track_team_segments: dict,
    homography_cache, config: TeamAssignerConfig,
) -> tuple[dict, dict]:
    """Returns (goalkeeper_team_assignment, team_centroids).

    Takes track_team_segments (not locked_team_by_id) so EVERY classified
    player track -- including switch_suspects -- contributes its positions
    to the correct team centroid, attributing each sampled position to
    whichever team was actually in effect at that frame.
    """
    goalkeeper_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "goalkeeper"}
    print(f"Goalkeeper tracks to assign: {sorted(goalkeeper_ids)}")

    # Gather pitch positions of players belonging to each team, resolved
    # per-frame via track_team_segments -- not one flat label per track.
    team_positions = {0: [], 1: []}
    for tid in track_team_segments:
        for frame_idx, pos in get_track_positions_with_frame(
            tid, tracking_cache, homography_cache, config.px_per_meter, config.gk_position_sample_stride
        ):
            team = team_for_track_at_frame(track_team_segments, tid, frame_idx)
            if team is not None:
                team_positions[team].append(pos)

    # Calculate each team's average pitch location.
    team_centroids = {
        team: np.mean(positions, axis=0) if positions else None
        for team, positions in team_positions.items()
    }
    print(f"\nTeam 0 centroid (pitch m): {team_centroids[0]}")
    print(f"Team 1 centroid (pitch m): {team_centroids[1]}")

    goalkeeper_team_assignment = {}
    for gk_id in goalkeeper_ids:
        gk_positions = get_track_positions(
            gk_id, tracking_cache, homography_cache, config.px_per_meter, config.gk_position_sample_stride
        )
        if not gk_positions:
            print(f"  id={gk_id}: no valid pitch positions found -- skipping")
            continue

        # Compute the goalkeeper's average pitch position.
        gk_centroid = np.mean(gk_positions, axis=0)

        # Compare goalkeeper position to both team centroids.
        dist0 = np.linalg.norm(gk_centroid - team_centroids[0]) if team_centroids[0] is not None else np.inf
        dist1 = np.linalg.norm(gk_centroid - team_centroids[1]) if team_centroids[1] is not None else np.inf

        assigned_team = 0 if dist0 < dist1 else 1
        goalkeeper_team_assignment[gk_id] = assigned_team

        print(f"  id={gk_id} | pitch pos: ({gk_centroid[0]:.1f}, {gk_centroid[1]:.1f})m "
              f"| dist_to_team0={dist0:.1f}m dist_to_team1={dist1:.1f}m -> team {assigned_team}")

    return goalkeeper_team_assignment, team_centroids
