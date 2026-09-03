"""
Classify every player detection per frame against the fitted KMeans model,
then lock team assignment via WINDOWED voting -- not one whole-track
majority vote.

Why windowed, not whole-track: a same-team ID switch is invisible to team
assignment by definition (both segments vote for the same team) -- only a
CROSS-team switch corrupts a team label, and the tracking pipeline's own
team veto already guards against most of those upstream. Voting in windows
along each track's own timeline (instead of once over the whole track)
means a track that DOES flip mid-way is detected (switch_suspects) and each
segment gets the correct team, instead of one team silently winning a
global vote and mislabeling roughly half the track.

raw_team_votes / per_frame_team are kept non-destructive (same pattern as
tracker's class locking): per_frame_team is the raw noisy per-frame
predictions, track_team_segments is the final per-window decision, and
locked_team_by_id is kept for backward compatibility -- populated only for
tracks that never flip.
"""

from __future__ import annotations

from collections import defaultdict

import cv2

from .config import TeamAssignerConfig
from .embedder import SiglipEmbedder


# Classify player appearances using the trained KMeans kit clusters.
# Stores every prediction as a vote for each track without immediately
# forcing a final team assignment.
def classify_all_tracks(
    embedder: SiglipEmbedder, scaler, kmeans, tracking_cache: dict,
    locked_class_by_id: dict, video_path: str, config: TeamAssignerConfig,
) -> tuple[dict, dict]:
    """Returns (raw_team_votes, per_frame_team).

    raw_team_votes: {track_id: {team: vote_count}} -- whole-track totals,
    used only for the backward-compatible single-value fallback.

    per_frame_team: {(frame_idx, track_id): team} -- every individual
    prediction, kept so lock_teams_windowed can group them into windows.
    """
    player_ids = {tid for tid, cls in locked_class_by_id.items() if cls == "player"}
    raw_team_votes: dict = defaultdict(lambda: defaultdict(int))
    per_frame_team: dict = {}

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

                # Extract jersey appearance features and predict the team cluster.
                feat = embedder.extract(frame, t["bbox"])
                if feat is None:
                    continue

                scaled_feat = scaler.transform(feat.reshape(1, -1))
                team = int(kmeans.predict(scaled_feat)[0])
                raw_team_votes[t["track_id"]][team] += 1
                per_frame_team[(frame_idx, t["track_id"])] = team

        if frame_idx % config.log_every_n_frames == 0:
            print(f"  frame {frame_idx}")
        frame_idx += 1

    cap.release()
    print(f"\nClassified sampled frames for {len(raw_team_votes)} player tracks.")
    return dict(raw_team_votes), per_frame_team


def lock_teams_windowed(per_frame_team: dict, raw_team_votes: dict, config: TeamAssignerConfig) -> dict:
    """Groups per_frame_team into config.team_vote_window_frames-sized
    windows per track, majority-votes each window independently, and
    flags any track whose windows disagree.

    Returns a dict with:
      "track_team_segments": {track_id: [(window_start_frame, team), ...]}
          -- the real per-window history, sorted by window_start_frame.
          This is the source of truth every downstream consumer that
          needs frame-level correctness should use (see
          team_for_track_at_frame below), NOT locked_team_by_id or
          team_by_id.
      "locked_team_by_id": {track_id: team}
          -- backward-compatible single value, populated ONLY for tracks
          whose windows never disagree.
      "switch_suspects": [track_id, ...]
          -- tracks with a team flip across windows. Worth cross-checking
          against the tracking pipeline's own switch-detection tools --
          agreement is strong confirmation; a track flagged only here is
          a cross-team switch that upstream veto missed.
      "weak_windows": [(track_id, window_start_frame, team, majority_frac), ...]
          -- individual windows below config.weak_majority_threshold,
          which are noisier (not necessarily switches) and worth treating
          with more skepticism than a window backed by a full window's
          worth of confident votes.
    """
    window = config.team_vote_window_frames

    votes_by_id: dict = defaultdict(list)
    for (frame_idx, tid), team in per_frame_team.items():
        votes_by_id[tid].append((frame_idx, team))

    track_team_segments: dict = {}
    switch_suspects: list = []

    for tid, votes in votes_by_id.items():
        votes.sort(key=lambda x: x[0])
        windows: dict = defaultdict(lambda: defaultdict(int))
        for f, team in votes:
            windows[f // window][team] += 1

        segments = []
        for w in sorted(windows):
            team_here = max(windows[w], key=windows[w].get)
            segments.append((w * window, team_here))
        track_team_segments[tid] = segments

        unique_teams = {t for _, t in segments}
        if len(unique_teams) > 1:
            switch_suspects.append(tid)

    locked_team_by_id = {
        tid: segments[0][1] for tid, segments in track_team_segments.items()
        if len({t for _, t in segments}) == 1
    }

    print(f"{len(switch_suspects)} tracks show a team flip across windows -- likely a cross-team "
          f"ID switch surviving into the final tracking output (or a genuinely bad SigLIP "
          f"classification in some window -- check both before assuming it's a real switch):\n")
    for tid in switch_suspects:
        print(f"  track_id={tid}: {track_team_segments[tid]}")

    print(f"\n{len(locked_team_by_id)} tracks: single stable team (unchanged behavior).")
    print(f"{len(switch_suspects)} tracks: need per-segment team lookup via "
          f"team_for_track_at_frame(track_team_segments, tid, frame_idx) -- see track_team_segments.")

    weak_windows = []
    for tid, segments in track_team_segments.items():
        votes = votes_by_id[tid]
        windows_grouped: dict = defaultdict(lambda: defaultdict(int))
        for f, team in votes:
            windows_grouped[f // window][team] += 1
        for window_start, team_here in segments:
            w = window_start // window
            wv = windows_grouped[w]
            total = sum(wv.values())
            frac = wv[team_here] / total if total else 0
            if frac < config.weak_majority_threshold:
                weak_windows.append((tid, window_start, team_here, frac))

    if weak_windows:
        print(f"\n{len(weak_windows)} individual windows below weak_majority_threshold="
              f"{config.weak_majority_threshold} -- check these manually:")
        for tid, window_start, team_here, frac in weak_windows[:20]:
            print(f"  id={tid} window_start={window_start} team={team_here} majority_frac={frac:.2f}")

    return {
        "track_team_segments": track_team_segments,
        "locked_team_by_id": locked_team_by_id,
        "switch_suspects": switch_suspects,
        "weak_windows": weak_windows,
    }


def team_for_track_at_frame(track_team_segments: dict, tid, frame_idx: int, default=None):
    """Segment-aware team lookup -- the team in effect for a track at a
    specific frame, using the windowed segments. This is what goalkeeper
    centroid assignment and any downstream consumer (frame_table, render,
    passes) should use instead of a single static label, so a mid-track
    flip is handled correctly wherever team membership actually matters.

    Falls back to `default` for a track with no segment history at all
    (shouldn't normally happen for anything actually classified -- could
    happen for a track filtered out as a ghost before segments were built).
    """
    segments = track_team_segments.get(tid)
    if not segments:
        return default
    team = segments[0][1]
    for window_start, team_here in segments:
        if window_start <= frame_idx:
            team = team_here
        else:
            break
    return team
