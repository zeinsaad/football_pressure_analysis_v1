"""
Pass detection -- built directly on player_frame_table / ball_frame_table,
same rule as every other stat module: reads only those two tables, never
raw per-stage caches.

A pass is only scored (completed/failed) if the ball's tracking during the
gap between two possession segments looks like a continuous, on-pitch
transfer. If the ball was untracked for most of the gap, or its projected
pitch position left the field, the transition is a turnover -- not scored
either way -- so a lost dribble or a shot that hands the ball to the other
team doesn't get counted as a "failed pass".

completed = same-team receiver. failed = opponent-team receiver (a genuine
interception -- ball control transferred continuously, just to the wrong
team).

Known open limitation: still can't perfectly tell a short misplaced pass
from a tackle dispossession that happens to look continuous (no ball-out,
no long lost-tracking gap). Defender-proximity or ball-velocity-direction
checks would tighten this further -- not implemented here.
"""

from pathlib import Path

import pandas as pd


class PassesPipeline:
    """Detects pass events from player_frame_table / ball_frame_table.
    Config-driven, no video or model access -- pure post-processing, same
    category as ball_tracker / ball_carrier / frame_table."""

    def __init__(self, cfg: "PassConfig"):
        self.cfg = cfg

    def build_possession_segments(self, ball_frame_table, player_frame_table):
        """One row per possession segment: [track_id, team, start_frame,
        end_frame, n_frames]. Bridges same-player gaps <= cfg.max_gap_frames
        (mirrors the carrier assigner's own grace period) and drops
        segments shorter than cfg.min_segment_frames as tracking noise."""
        cfg = self.cfg
        team_by_track = (
            player_frame_table[["track_id", "team"]]
            .dropna()
            .drop_duplicates("track_id")
            .set_index("track_id")["team"]
        )

        carrier = ball_frame_table[["frame_idx", "carrier_track_id"]].sort_values("frame_idx")

        segments = []
        cur_id = seg_start = last_seen_frame = None

        def flush(end_frame):
            if cur_id is None:
                return
            n_frames = end_frame - seg_start + 1
            if n_frames >= cfg.min_segment_frames:
                segments.append((cur_id, team_by_track.get(cur_id), seg_start, end_frame, n_frames))

        for f, tid in zip(carrier["frame_idx"], carrier["carrier_track_id"]):
            tid = None if pd.isna(tid) else int(tid)
            if tid is None:
                continue  # gap frame -- bridging handled below when the carrier reappears

            if cur_id is None:
                cur_id, seg_start, last_seen_frame = tid, f, f
                continue

            if tid == cur_id and (f - last_seen_frame) <= cfg.max_gap_frames:
                last_seen_frame = f
                continue

            flush(last_seen_frame)
            cur_id, seg_start, last_seen_frame = tid, f, f

        flush(last_seen_frame)

        seg_df = pd.DataFrame(segments, columns=["track_id", "team", "start_frame", "end_frame", "n_frames"])
        seg_df["team"] = seg_df["team"].astype("Int64")
        return seg_df

    def classify_transitions(self, seg_df, ball_frame_table, pitch_length, pitch_width):
        """One row per segment-to-segment transition, scored either as a
        pass (outcome = completed/failed) or a turnover (is_turnover=True,
        outcome=None) based on ball tracking continuity during the gap."""
        cfg = self.cfg
        seg_df = seg_df.sort_values("start_frame").reset_index(drop=True)
        ball = ball_frame_table.set_index("frame_idx").sort_index()

        events = []
        for i in range(len(seg_df) - 1):
            passer, receiver = seg_df.iloc[i], seg_df.iloc[i + 1]
            if passer["track_id"] == receiver["track_id"]:
                continue

            gap_start, gap_end = passer["end_frame"] + 1, receiver["start_frame"] - 1
            gap = ball.loc[gap_start:gap_end] if gap_end >= gap_start else ball.iloc[0:0]
            n_gap = len(gap)

            lost_frac = (gap["ball_source"] == "lost").mean() if n_gap else 0.0

            out_of_bounds = False
            if n_gap:
                x_ok = gap["ball_pitch_x"].between(-cfg.pitch_out_margin_m, pitch_length + cfg.pitch_out_margin_m)
                y_ok = gap["ball_pitch_y"].between(-cfg.pitch_out_margin_m, pitch_width + cfg.pitch_out_margin_m)
                tracked = gap["ball_pitch_x"].notna() & gap["ball_pitch_y"].notna()
                out_of_bounds = bool((tracked & ~(x_ok & y_ok)).any())

            is_turnover = (lost_frac > cfg.ball_lost_gap_fraction_max) or out_of_bounds
            outcome = None
            if not is_turnover:
                outcome = "completed" if passer["team"] == receiver["team"] else "failed"

            events.append((
                passer["track_id"], passer["team"], passer["end_frame"],
                receiver["track_id"], receiver["team"], receiver["start_frame"],
                gap_start, gap_end, n_gap, round(lost_frac, 2), out_of_bounds,
                is_turnover, outcome,
            ))

        cols = ["passer_id", "passer_team", "passer_end_frame",
                "receiver_id", "receiver_team", "receiver_start_frame",
                "gap_start", "gap_end", "gap_frames", "ball_lost_frac", "ball_out_of_bounds",
                "is_turnover", "outcome"]
        events_df = pd.DataFrame(events, columns=cols)
        events_df["passer_team"] = events_df["passer_team"].astype("Int64")
        events_df["receiver_team"] = events_df["receiver_team"].astype("Int64")
        return events_df

    def build(self, player_frame_table, ball_frame_table, pitch_length, pitch_width):
        seg_df = self.build_possession_segments(ball_frame_table, player_frame_table)
        events_df = self.classify_transitions(seg_df, ball_frame_table, pitch_length, pitch_width)
        return events_df


def get_or_build_pass_events(
    pipeline: PassesPipeline, cache_path, player_frame_table, ball_frame_table,
    pitch_length, pitch_width, force_rebuild=False,
):
    """Load-or-build, same pattern as every other stage. events_df includes
    turnovers -- filter is_turnover before scoring stats (see stats.py)."""
    events_path = Path(cache_path)

    if events_path.exists() and not force_rebuild:
        print("Loaded pass events from cache.")
        return pd.read_parquet(events_path)

    events_df = pipeline.build(player_frame_table, ball_frame_table, pitch_length, pitch_width)

    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_df.to_parquet(events_path, index=False)
    print("Saved pass events to cache.")
    return events_df
