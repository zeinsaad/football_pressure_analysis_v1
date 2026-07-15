"""
Classify every player detection per frame against the fitted KMeans model,
then lock one team per track via majority vote (same pattern as tracker's
class locking — raw votes are kept non-destructively, locked_team_by_id
holds the final decision).
"""

from __future__ import annotations

from collections import defaultdict

import cv2

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder


def classify_all_tracks(
    embedder: SiglipEmbedder, scaler, kmeans, tracking_cache: dict,
    locked_class_by_id: dict, video_path: str, config: TeamAssignerConfig,
) -> dict:
    """Returns raw_team_votes: {track_id: {team: vote_count}}."""
    player_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "player"}
    raw_team_votes: dict = defaultdict(lambda: defaultdict(int))

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % config.classification_frame_stride == 0:
            data = tracking_cache.get(frame_idx, {"tracks": []})
            for t in data["tracks"]:
                if t["track_id"] not in player_ids:
                    continue
                feat = embedder.extract(frame, t["bbox"])
                if feat is None:
                    continue
                scaled_feat = scaler.transform(feat.reshape(1, -1))
                team = int(kmeans.predict(scaled_feat)[0])
                raw_team_votes[t["track_id"]][team] += 1

        if frame_idx % config.log_every_n_frames == 0:
            print(f"  frame {frame_idx}")
        frame_idx += 1

    cap.release()
    print(f"\nClassified sampled frames for {len(raw_team_votes)} player tracks.")
    return dict(raw_team_votes)


def lock_teams(raw_team_votes: dict, config: TeamAssignerConfig) -> dict:
    """Returns locked_team_by_id: {track_id: 0 or 1}. Prints a weak-majority
    flag for tracks below config.weak_majority_threshold."""
    locked_team_by_id = {}
    for tid, votes in raw_team_votes.items():
        locked_team_by_id[tid] = max(votes, key=votes.get)

    print("Locked team per player track:\n")
    for tid in sorted(locked_team_by_id):
        votes = raw_team_votes[tid]
        total = sum(votes.values())
        majority_frac = votes[locked_team_by_id[tid]] / total
        flag = "  <-- weak majority, check this track" if majority_frac < config.weak_majority_threshold else ""
        print(f"  id={tid:2d} | team={locked_team_by_id[tid]} | votes={dict(votes)} "
              f"| majority={majority_frac:.2f}{flag}")

    team0_count = sum(1 for t in locked_team_by_id.values() if t == 0)
    team1_count = sum(1 for t in locked_team_by_id.values() if t == 1)
    print(f"\nTeam 0: {team0_count} players | Team 1: {team1_count} players")

    return locked_team_by_id
