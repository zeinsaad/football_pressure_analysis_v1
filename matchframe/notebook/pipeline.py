"""
Frame table -- joins every raw per-stage cache (homography, tracking, team
assignment, ball tracker, carrier assignment) into two normalized tables,
once:

- player_frame_table -- long format, one row per (frame_idx, track_id):
  pitch position, team, role, whether that player is the ball carrier this
  frame, and that player's team's attack_direction for the half.
- ball_frame_table -- one row per frame_idx: ball position, source
  (detected/smoothed/lost), current carrier, and possession_team (carried
  forward through gaps, bounded by the carrier assigner's own
  no_candidate_grace_frames, so "who currently has the ball" stays defined
  across a brief loose-ball frame without silently overriding the carrier
  assigner's own decision that possession has become genuinely unknown).

Everything downstream (passes, pressure, possession, formation stats) reads
only these two tables -- never the raw per-stage caches directly.

Pitch-coord validity: the homography pipeline occasionally produces a
degenerate H for a frame (near-singular matrix slipping past its own
degeneracy/determinant checks), which blows up every player's projected
pitch_x/pitch_y in that frame at once. flag_valid_pitch_coords is a
mandatory step (not optional) in build_player_frame_table so garbage frames
can't silently corrupt anything downstream that aggregates over pitch
coordinates. This is a symptom-level guard, not a fix for the underlying
homography bug.
"""

from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from matchframe.config import FrameTableConfig


def bbox_foot_point(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def flag_valid_pitch_coords(df, pitch_length, pitch_width, margin_m=5.0, verbose=True):
    """Null out pitch_x/pitch_y wherever a frame's homography produced an
    out-of-plausible-range projection (degenerate H slipping past the
    homography pipeline's own degeneracy checks, blowing up every player's
    projected position in that frame at once). Doesn't fix the underlying
    homography bug -- stops garbage frames from silently corrupting
    anything downstream that aggregates over pitch_x/pitch_y (direction
    inference, distance calcs, press triggers, etc)."""
    df = df.copy()
    x_ok = df["pitch_x"].between(-margin_m, pitch_length + margin_m)
    y_ok = df["pitch_y"].between(-margin_m, pitch_width + margin_m)
    valid = x_ok & y_ok & df["pitch_x"].notna() & df["pitch_y"].notna()

    if verbose:
        n_bad = (~valid & df["pitch_x"].notna()).sum()
        n_total = df["pitch_x"].notna().sum()
        pct = n_bad / max(n_total, 1) * 100
        print(f"Pitch coord sanity filter -> {n_bad}/{n_total} rows ({pct:.1f}%) out of plausible range, nulled out")

    df.loc[~valid, ["pitch_x", "pitch_y"]] = np.nan
    return df


class FrameTablePipeline:
    """Builds player_frame_table / ball_frame_table from every upstream
    stage cache, plus attack_direction inference. Config-driven, no video
    or model access -- pure post-processing over already-computed caches,
    same category as ball_tracker / ball_carrier."""

    def __init__(self, cfg: "FrameTableConfig"):
        self.cfg = cfg

    # ---- player table ----

    def build_player_frame_table(
        self, tracking_cache, locked_class_by_id, team_by_id, homography_cache,
        ball_carrier_cache, total_frames, pitch_length, pitch_width, px_per_meter,
    ):
        """Long format: one row per (frame_idx, track_id). pitch_x/pitch_y
        are NaN wherever that frame's homography is missing (e.g. before
        orientation calibration locks in) or implausible (degenerate H) --
        left as NaN rather than dropped, so frame counts stay comparable
        across columns and every stat module decides for itself how to
        handle missing pitch data."""
        rows = []
        for f in range(total_frames):
            frame_tracks = tracking_cache.get(f, {}).get("tracks", [])
            if not frame_tracks:
                continue

            H = homography_cache[f] if f < len(homography_cache) else None
            carrier_id = ball_carrier_cache.get(f, {}).get("track_id")

            feet_px = np.array([bbox_foot_point(t["bbox"]) for t in frame_tracks], dtype=np.float32)
            if H is not None:
                proj = cv2.perspectiveTransform(feet_px.reshape(-1, 1, 2), H).reshape(-1, 2)
                pitch_xy = proj / px_per_meter
            else:
                pitch_xy = np.full((len(frame_tracks), 2), np.nan)

            for t, (fx, fy), (px, py) in zip(frame_tracks, feet_px, pitch_xy):
                tid = t["track_id"]
                rows.append((
                    f, tid,
                    locked_class_by_id.get(tid, t["class"]),
                    team_by_id.get(tid),
                    float(fx), float(fy),
                    float(px), float(py),
                    tid == carrier_id,
                ))

        df = pd.DataFrame(rows, columns=[
            "frame_idx", "track_id", "role", "team",
            "x_px", "y_px", "pitch_x", "pitch_y", "is_carrier",
        ])
        df["team"] = df["team"].astype("Int64")
        df = flag_valid_pitch_coords(df, pitch_length, pitch_width, margin_m=self.cfg.pitch_out_margin_m)
        return df

    # ---- ball table ----

    def build_ball_frame_table(self, ball_tracked_cache, ball_carrier_cache, team_by_id,
                                total_frames, possession_gap_limit):
        """One row per frame_idx. possession_team forward-fills carrier_team
        through gaps (ball lost, carrier not re-confirmed yet), bounded by
        possession_gap_limit -- the same short gaps the carrier assigner
        itself considers "still held" (no_candidate_grace_frames),
        reverting to null beyond that, same as carrier_track_id does."""
        rows = []
        for f in range(total_frames):
            ball = ball_tracked_cache.get(f, {})
            carrier = ball_carrier_cache.get(f, {})
            xy_px = ball.get("xy_px")
            xy_pitch = ball.get("xy_pitch")
            carrier_id = carrier.get("track_id")
            rows.append((
                f,
                xy_px[0] if xy_px else np.nan, xy_px[1] if xy_px else np.nan,
                xy_pitch[0] if xy_pitch else np.nan, xy_pitch[1] if xy_pitch else np.nan,
                ball.get("source"), ball.get("conf"),
                carrier_id,
                team_by_id.get(carrier_id) if carrier_id is not None else None,
            ))

        df = pd.DataFrame(rows, columns=[
            "frame_idx", "ball_x_px", "ball_y_px", "ball_pitch_x", "ball_pitch_y",
            "ball_source", "ball_conf", "carrier_track_id", "carrier_team",
        ])
        df["carrier_track_id"] = df["carrier_track_id"].astype("Int64")
        df["carrier_team"] = df["carrier_team"].astype("Int64")
        df["possession_team"] = df["carrier_team"].ffill(limit=possession_gap_limit)
        return df

    # ---- attack direction ----

    def infer_attack_direction_from_gk(self, player_frame_table, pitch_length, half_boundary_frame=None):
        """Infer each team's attacking direction from goalkeeper position,
        not centroid drift -- a keeper sits near their own goal line almost
        the entire match regardless of phase of play, making this stable
        even over a short continuous clip where both teams' centroids might
        drift the same way during a single sustained attack."""
        df = player_frame_table[
            player_frame_table["pitch_x"].notna() & (player_frame_table["role"] == "goalkeeper")
        ]
        if df.empty:
            print("No goalkeeper rows found -- check the 'role' label used for keepers.")
            return {}

        total_frames = int(player_frame_table["frame_idx"].max()) + 1
        if half_boundary_frame is None:
            halves = [(0, total_frames)]
        else:
            halves = [(0, half_boundary_frame), (half_boundary_frame, total_frames)]

        direction_by_team_half = {}
        for half_idx, (start, end) in enumerate(halves):
            seg = df[(df["frame_idx"] >= start) & (df["frame_idx"] < end)]
            for team in seg["team"].dropna().unique():
                team_seg = seg[seg["team"] == team]
                gk_x = team_seg["pitch_x"].median()
                n_rows = len(team_seg)
                direction_by_team_half[(int(team), half_idx)] = 1 if gk_x < pitch_length / 2 else -1
                print(
                    f"  team {int(team)} half {half_idx}: GK median pitch_x={gk_x:.1f} "
                    f"(n={n_rows} rows) -> direction={direction_by_team_half[(int(team), half_idx)]}"
                )

        return direction_by_team_half

    def attach_attack_direction(self, player_frame_table, direction_by_team_half, half_boundary_frame=None):
        """Adds an attack_direction column, looked up per row from (team,
        half). Rows with unknown team or no inferred direction get None
        rather than a guessed default."""
        if half_boundary_frame is None:
            half_idx = pd.Series(0, index=player_frame_table.index)
        else:
            half_idx = (player_frame_table["frame_idx"] >= half_boundary_frame).astype(int)

        player_frame_table = player_frame_table.copy()
        player_frame_table["attack_direction"] = [
            direction_by_team_half.get((int(t), h)) if pd.notna(t) else None
            for t, h in zip(player_frame_table["team"], half_idx)
        ]
        player_frame_table["attack_direction"] = player_frame_table["attack_direction"].astype("Int64")
        return player_frame_table

    # ---- orchestration ----

    def build(self, tracking_cache, locked_class_by_id, team_by_id, homography_cache,
              ball_carrier_cache, ball_tracked_cache, total_frames,
              pitch_length, pitch_width, px_per_meter, possession_gap_limit):
        player_df = self.build_player_frame_table(
            tracking_cache, locked_class_by_id, team_by_id, homography_cache,
            ball_carrier_cache, total_frames, pitch_length, pitch_width, px_per_meter,
        )
        ball_df = self.build_ball_frame_table(
            ball_tracked_cache, ball_carrier_cache, team_by_id, total_frames,
            possession_gap_limit=possession_gap_limit,
        )
        direction_map = self.infer_attack_direction_from_gk(
            player_df, pitch_length, half_boundary_frame=self.cfg.half_boundary_frame,
        )
        player_df = self.attach_attack_direction(
            player_df, direction_map, half_boundary_frame=self.cfg.half_boundary_frame,
        )
        return player_df, ball_df, direction_map


def get_or_build_frame_tables(
    pipeline: FrameTablePipeline, player_cache_path, ball_cache_path,
    tracking_cache, locked_class_by_id, team_by_id, homography_cache,
    ball_carrier_cache, ball_tracked_cache, total_frames,
    pitch_length, pitch_width, px_per_meter, possession_gap_limit,
    force_rebuild=False,
):
    """Load-or-build, same pattern as every other stage. Rebuilding always
    goes through FrameTablePipeline.build (which always applies
    flag_valid_pitch_coords and attack-direction inference) -- there's no
    code path that produces player_frame_table without both applied,
    cached or not."""
    player_path = Path(player_cache_path)
    ball_path = Path(ball_cache_path)

    if player_path.exists() and ball_path.exists() and not force_rebuild:
        print("Loaded frame tables from cache.")
        return pd.read_parquet(player_path), pd.read_parquet(ball_path)

    player_df, ball_df, _ = pipeline.build(
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        team_by_id=team_by_id, homography_cache=homography_cache,
        ball_carrier_cache=ball_carrier_cache, ball_tracked_cache=ball_tracked_cache,
        total_frames=total_frames, pitch_length=pitch_length, pitch_width=pitch_width,
        px_per_meter=px_per_meter, possession_gap_limit=possession_gap_limit,
    )

    player_path.parent.mkdir(parents=True, exist_ok=True)
    ball_path.parent.mkdir(parents=True, exist_ok=True)
    player_df.to_parquet(player_path, index=False)
    ball_df.to_parquet(ball_path, index=False)
    print("Saved frame tables to cache.")
    return player_df, ball_df
