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

Team resolution: team_by_id (from team_assignment.pkl) is a flat, lossy
fallback for any track flagged in switch_suspects -- it collapses a
track's whole lifespan to one team, picked by total-vote count across
windows. For a track that genuinely changes team label mid-match (a
cross-team ID switch the tracking pipeline's own veto didn't catch), that
flat value is WRONG for roughly half the track's frames. Both
build_player_frame_table and build_ball_frame_table now resolve team via
track_team_segments (the team_assigner's per-window history) per row,
falling back to team_by_id only for a track with no segment history at
all. See team_for_track_at_frame below.

--- Fixes applied in this revision (see inline comments at each site) ---
1. build_ball_frame_table: xy_px/xy_pitch presence check used truthiness
   (`if xy_px else`), which throws ValueError if the cache ever stores a
   numpy array instead of a tuple/list. Now uses `is not None`.
2. FORCE_REBUILD_FRAME_TABLE (config.py) is now actually read by
   get_or_build_frame_tables instead of sitting unused.
3. team_for_track_at_frame now defensively sorts segments by window_start
   instead of assuming the input list is already sorted.
4. infer_attack_direction_from_gk now takes total_frames explicitly
   instead of recomputing it from player_frame_table["frame_idx"].max(),
   which undercounts whenever trailing frames have zero detected tracks
   (those frames never get a row at all).
5. possession_team no longer conflates "no carrier" (genuine gap, should
   forward-fill) with "carrier present but team unresolved" (almost always
   a referee holding the ball at a stoppage -- should NOT be silently
   papered over with the last team's possession). New columns
   possession_team_is_filled / carrier_team_unresolved make both cases
   inspectable downstream.
6. possession_gap_limit is now validated -- pandas treats ffill(limit=None)
   as "fill forever", which would silently defeat the entire point of
   bounding the fill to short gaps.
7. ball_frame_table now also gets a carrier_attack_direction column,
   reusing the same direction_by_team_half map computed for the player
   table, instead of downstream code having to join back to
   player_frame_table just to know which way the carrier's team attacks.
8. attack_direction_map is now persisted (small JSON sidecar) alongside
   the parquet caches, instead of being discarded once a fresh build
   finishes -- previously irrecoverable from a cache hit.
9. get_or_build_frame_tables now checks a total_frames metadata sidecar
   and expected-columns schema before trusting a cache hit, and writes
   both parquet files atomically (temp file + rename) so a crash mid-write
   can't leave one of the two cache files stale relative to the other.
"""

import json
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from matchframe.config import FORCE_REBUILD_FRAME_TABLE, FrameTableConfig


def bbox_foot_point(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def team_for_track_at_frame(track_team_segments, team_by_id, tid, frame_idx):
    """Segment-aware team lookup. track_team_segments[tid] is expected to be
    a sorted list of (window_start_frame, team) -- the team in effect at
    frame_idx is whichever window's start is the latest one <= frame_idx.
    Falls back to the flat team_by_id only for a track with no segment
    history at all (shouldn't happen for anything the team_assigner
    actually classified; could happen for a track that predates that
    pipeline stage, or one filtered out as a ghost before segments were
    built), and for a track with no resolvable team at all (referees --
    they aren't in team_by_id or track_team_segments), where it returns
    None."""
    segments = track_team_segments.get(tid)
    if not segments:
        return team_by_id.get(tid)

    # FIX: defensive sort. Nothing upstream currently guarantees
    # track_team_segments[tid] arrives sorted by window_start -- if it
    # ever isn't (e.g. built via dict/append order for a switch_suspect
    # track), the "last window <= frame_idx wins" walk below would
    # silently resolve to the wrong team for some frames with no error.
    segments = sorted(segments, key=lambda s: s[0])

    team = segments[0][1]
    for window_start, team_here in segments:
        if window_start <= frame_idx:
            team = team_here
        else:
            break
    return team


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
        self, tracking_cache, locked_class_by_id, team_by_id, track_team_segments,
        homography_cache, ball_carrier_cache, total_frames, pitch_length, pitch_width, px_per_meter,
    ):
        """Long format: one row per (frame_idx, track_id). pitch_x/pitch_y
        are NaN wherever that frame's homography is missing (e.g. before
        orientation calibration locks in) or implausible (degenerate H) --
        left as NaN rather than dropped, so frame counts stay comparable
        across columns and every stat module decides for itself how to
        handle missing pitch data. team is resolved per-row via
        track_team_segments, not a flat per-track value -- see
        team_for_track_at_frame."""
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
                    team_for_track_at_frame(track_team_segments, team_by_id, tid, f),
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
                                track_team_segments, total_frames, possession_gap_limit,
                                direction_by_team_half=None, half_boundary_frame=None):
        """One row per frame_idx. possession_team forward-fills carrier_team
        only across a genuine loose-ball gap (carrier_track_id is null),
        bounded by possession_gap_limit -- the same short gaps the carrier
        assigner itself considers "still held" (no_candidate_grace_frames),
        reverting to null beyond that, same as carrier_track_id does.
        carrier_team is resolved per-row via track_team_segments, not a
        flat per-track value -- see team_for_track_at_frame.

        A carrier can be present with an unresolved team (almost always a
        referee at a stoppage/dead ball, since referees aren't in
        team_by_id/track_team_segments). That's a different situation from
        "no carrier" and must not be forward-filled the same way -- see
        possession_team_is_filled / carrier_team_unresolved below.

        If direction_by_team_half is given, also attaches
        carrier_attack_direction (which way the current possessing team is
        attacking), so downstream code doesn't have to join back to
        player_frame_table just to get that."""
        if possession_gap_limit is None or possession_gap_limit < 0:
            # FIX: pandas treats ffill(limit=None) as "fill forever", which
            # would silently defeat the whole point of bounding
            # possession_team to short gaps -- fail loudly instead.
            raise ValueError(
                "possession_gap_limit must be a non-negative int; got "
                f"{possession_gap_limit!r}. limit=None in pandas means "
                "'forward-fill indefinitely', not 'no limit given'."
            )

        rows = []
        for f in range(total_frames):
            ball = ball_tracked_cache.get(f, {})
            carrier = ball_carrier_cache.get(f, {})
            xy_px = ball.get("xy_px")
            xy_pitch = ball.get("xy_pitch")
            carrier_id = carrier.get("track_id")
            rows.append((
                f,
                # FIX: was `if xy_px else` (truthiness) -- throws
                # ValueError if xy_px/xy_pitch is ever a numpy array
                # (e.g. straight out of the Kalman/RTS state) rather than
                # a plain tuple/list. `is not None` is unambiguous either way.
                xy_px[0] if xy_px is not None else np.nan,
                xy_px[1] if xy_px is not None else np.nan,
                xy_pitch[0] if xy_pitch is not None else np.nan,
                xy_pitch[1] if xy_pitch is not None else np.nan,
                ball.get("source"), ball.get("conf"),
                carrier_id,
                team_for_track_at_frame(track_team_segments, team_by_id, carrier_id, f)
                if carrier_id is not None else None,
            ))

        df = pd.DataFrame(rows, columns=[
            "frame_idx", "ball_x_px", "ball_y_px", "ball_pitch_x", "ball_pitch_y",
            "ball_source", "ball_conf", "carrier_track_id", "carrier_team",
        ])
        df["carrier_track_id"] = df["carrier_track_id"].astype("Int64")
        df["carrier_team"] = df["carrier_team"].astype("Int64")

        # FIX: gate the forward-fill on carrier_track_id being null (a
        # genuine loose-ball gap), not on carrier_team being null. A row
        # where carrier_track_id IS set but carrier_team came back None
        # (referee holding the ball) must keep its own null, not inherit
        # whichever team last had it -- that was previously
        # indistinguishable from a real gap.
        no_carrier = df["carrier_track_id"].isna()
        carrier_team_unresolved = df["carrier_track_id"].notna() & df["carrier_team"].isna()

        filled = df["carrier_team"].ffill(limit=possession_gap_limit)
        df["possession_team"] = df["carrier_team"]
        df.loc[no_carrier, "possession_team"] = filled[no_carrier]
        df["possession_team"] = df["possession_team"].astype("Int64")

        # Lets downstream code (or a quick audit) tell "this
        # possession_team value came from an actual carrier" apart from
        # "this was forward-filled through a gap", and spot
        # referee/dead-ball frames explicitly instead of them silently
        # blending into whichever possession segment preceded them.
        df["possession_team_is_filled"] = no_carrier & df["possession_team"].notna()
        df["carrier_team_unresolved"] = carrier_team_unresolved

        if direction_by_team_half is not None:
            if half_boundary_frame is None:
                half_idx = pd.Series(0, index=df.index)
            else:
                half_idx = (df["frame_idx"] >= half_boundary_frame).astype(int)
            df["carrier_attack_direction"] = [
                direction_by_team_half.get((int(t), h)) if pd.notna(t) else None
                for t, h in zip(df["carrier_team"], half_idx)
            ]
            df["carrier_attack_direction"] = df["carrier_attack_direction"].astype("Int64")

        return df

    # ---- attack direction ----

    def infer_attack_direction_from_gk(self, player_frame_table, pitch_length, total_frames, half_boundary_frame=None):
        """Infer each team's attacking direction from goalkeeper position,
        not centroid drift -- a keeper sits near their own goal line almost
        the entire match regardless of phase of play, making this stable
        even over a short continuous clip where both teams' centroids might
        drift the same way during a single sustained attack.

        total_frames is now taken from the caller (the same value used to
        build the frame table) rather than recomputed from
        player_frame_table["frame_idx"].max() + 1 -- frames with zero
        detected tracks never get a row at all, so that local recomputation
        could undercount real match length (e.g. a trailing
        stoppage/blackout) and silently drift from every other
        "total_frames" in this pipeline."""
        df = player_frame_table[
            player_frame_table["pitch_x"].notna() & (player_frame_table["role"] == "goalkeeper")
        ]
        if df.empty:
            print("No goalkeeper rows found -- check the 'role' label used for keepers.")
            return {}

        if half_boundary_frame is None:
            halves = [(0, total_frames)]
        else:
            halves = [(0, half_boundary_frame), (half_boundary_frame, total_frames)]

        direction_by_team_half = {}
        for half_idx, (start, end) in enumerate(halves):
            seg = df[(df["frame_idx"] >= start) & (df["frame_idx"] < end)]
            teams_seen = seg["team"].dropna().unique()
            if len(teams_seen) == 0:
                print(f"  half {half_idx}: no goalkeeper rows with a resolved team -- attack_direction stays null here.")
            for team in teams_seen:
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

    def build(self, tracking_cache, locked_class_by_id, team_by_id, track_team_segments,
              homography_cache, ball_carrier_cache, ball_tracked_cache, total_frames,
              pitch_length, pitch_width, px_per_meter, possession_gap_limit):
        player_df = self.build_player_frame_table(
            tracking_cache, locked_class_by_id, team_by_id, track_team_segments,
            homography_cache, ball_carrier_cache, total_frames, pitch_length, pitch_width, px_per_meter,
        )
        # Direction is computed right after the player table exists and
        # BEFORE the ball table is built, so build_ball_frame_table can
        # attach carrier_attack_direction in the same pass instead of
        # downstream code having to join back to player_frame_table for it.
        direction_map = self.infer_attack_direction_from_gk(
            player_df, pitch_length, total_frames, half_boundary_frame=self.cfg.half_boundary_frame,
        )
        player_df = self.attach_attack_direction(
            player_df, direction_map, half_boundary_frame=self.cfg.half_boundary_frame,
        )
        ball_df = self.build_ball_frame_table(
            ball_tracked_cache, ball_carrier_cache, team_by_id, track_team_segments,
            total_frames, possession_gap_limit=possession_gap_limit,
            direction_by_team_half=direction_map, half_boundary_frame=self.cfg.half_boundary_frame,
        )
        return player_df, ball_df, direction_map


# ---- cache I/O helpers ----

def _direction_map_path(player_cache_path):
    p = Path(player_cache_path)
    return p.with_name(p.stem + "_attack_direction.json")


def _meta_path(player_cache_path):
    p = Path(player_cache_path)
    return p.with_name(p.stem + ".meta.json")


def _save_direction_map(direction_map, path):
    # JSON object keys must be strings -- (team, half) tuples get packed
    # as "team:half" and unpacked again in _load_direction_map.
    serializable = {f"{team}:{half}": direction for (team, half), direction in direction_map.items()}
    path.write_text(json.dumps(serializable))


def _load_direction_map(path):
    """Not called by get_or_build_frame_tables itself (attack_direction is
    already baked into player_frame_table either way) -- exposed so you can
    recover the raw {(team, half): direction} map and its audit trail after
    a cache hit, without having to regroup player_frame_table yourself."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    direction_map = {}
    for key, direction in raw.items():
        team_str, half_str = key.split(":")
        direction_map[(int(team_str), int(half_str))] = direction
    return direction_map


def _atomic_write_parquet(df, path):
    """Write to a temp file in the same directory, then rename. Two
    sequential to_parquet() calls (one per table) aren't atomic as a pair --
    a crash between them could previously leave a freshly-written
    player_frame_table sitting next to a stale ball_frame_table (or vice
    versa) with no signal that they're out of sync. Renaming is atomic on
    the same filesystem, so each individual file is always either the old
    complete version or the new complete version, never a partial write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".parquet.tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    df.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, path)


def get_or_build_frame_tables(
    pipeline: FrameTablePipeline, player_cache_path, ball_cache_path,
    tracking_cache, locked_class_by_id, team_by_id, track_team_segments, homography_cache,
    ball_carrier_cache, ball_tracked_cache, total_frames,
    pitch_length, pitch_width, px_per_meter, possession_gap_limit,
    force_rebuild=None,
):
    """Load-or-build, same pattern as every other stage. Rebuilding always
    goes through FrameTablePipeline.build (which always applies
    flag_valid_pitch_coords and attack-direction inference) -- there's no
    code path that produces player_frame_table without both applied,
    cached or not.

    force_rebuild=None (the default) defers to FORCE_REBUILD_FRAME_TABLE in
    config.py -- FIX: that flag previously existed but was never read here,
    so setting it had no effect unless a caller separately remembered to
    pass force_rebuild=True by hand. Pass force_rebuild explicitly
    (True/False) to override the config default for one call.

    A cache hit is now also gated on: (a) a total_frames metadata sidecar
    matching the total_frames passed in this call, and (b) the loaded
    parquet files containing the columns this version of the pipeline
    expects. Either check failing triggers a full rebuild instead of
    silently serving a stale or schema-mismatched cache."""
    if force_rebuild is None:
        force_rebuild = FORCE_REBUILD_FRAME_TABLE

    player_path = Path(player_cache_path)
    ball_path = Path(ball_cache_path)
    direction_path = _direction_map_path(player_path)
    meta_path = _meta_path(player_path)

    expected_player_cols = {
        "frame_idx", "track_id", "role", "team", "x_px", "y_px",
        "pitch_x", "pitch_y", "is_carrier", "attack_direction",
    }
    expected_ball_cols = {
        "frame_idx", "ball_x_px", "ball_y_px", "ball_pitch_x", "ball_pitch_y",
        "ball_source", "ball_conf", "carrier_track_id", "carrier_team",
        "possession_team", "possession_team_is_filled", "carrier_team_unresolved",
    }

    if player_path.exists() and ball_path.exists() and not force_rebuild:
        player_df = pd.read_parquet(player_path)
        ball_df = pd.read_parquet(ball_path)

        meta_ok = False
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta_ok = meta.get("total_frames") == total_frames

        schema_ok = (
            expected_player_cols.issubset(player_df.columns)
            and expected_ball_cols.issubset(ball_df.columns)
        )

        if meta_ok and schema_ok:
            print("Loaded frame tables from cache.")
            return player_df, ball_df

        print(
            "Cached frame tables failed the staleness/schema check "
            f"(meta_ok={meta_ok}, schema_ok={schema_ok}) -- rebuilding instead of "
            "silently serving a stale or mismatched cache."
        )

    player_df, ball_df, direction_map = pipeline.build(
        tracking_cache=tracking_cache, locked_class_by_id=locked_class_by_id,
        team_by_id=team_by_id, track_team_segments=track_team_segments,
        homography_cache=homography_cache,
        ball_carrier_cache=ball_carrier_cache, ball_tracked_cache=ball_tracked_cache,
        total_frames=total_frames, pitch_length=pitch_length, pitch_width=pitch_width,
        px_per_meter=px_per_meter, possession_gap_limit=possession_gap_limit,
    )

    _atomic_write_parquet(player_df, player_path)
    _atomic_write_parquet(ball_df, ball_path)
    _save_direction_map(direction_map, direction_path)
    meta_path.write_text(json.dumps({"total_frames": total_frames}))

    print("Saved frame tables to cache.")
    return player_df, ball_df
