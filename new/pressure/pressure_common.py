"""
pressure_common.py - shared setup for the team-pressure notebooks (put this file in the same folder as the notebooks).

Every notebook starts with:   from pressure_common import *
That one line (1) defines paths + constants, (2) loads player_frame_table / ball_frame_table from new_cache, (3) runs the data contract
(dtypes, team-label orientation, column-collision guard, identity helpers) and (4) gives shared helpers (zones, channels, runs, clock, state).

Edit the paths / FLIP_CHANNELS below, not inside the notebooks.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ---------------------------------------------------------------- constants
FPS = 25
PITCH_LENGTH = 105
PITCH_WIDTH = 68
TEAM_NAMES = {0: "Barca", 1: "Atletico"}      # re-derived from the table's team_name column below
ATTACK_SIGN = {0: 1.0, 1: -1.0}               # after the orientation step: team 0 attacks +x, team 1 attacks -x
FLIP_CHANNELS = False                         # True if left / right come out mirrored against what you see on video
CHANNEL_ORDER = ["left", "centre", "right"]
ZONE_ORDER_5 = ["own_third", "middle_third", "attacking_third"]

# ---------------------------------------------------------------- paths (single source of truth)
NEW_CACHE = Path(os.environ.get("PRESSURE_NEW_CACHE", r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)"
                                              r"\project\barca_atletico_first_half\new_cache"))
PLAYER_PATH = NEW_CACHE / "player_frame_table_named.parquet"
BALL_PATH = NEW_CACHE / "ball_frame_table_named.parquet"
VIDEO_PATH = NEW_CACHE / "annotated_teams.mp4"
EXPORT_DIR = NEW_CACHE / "pressure_analysis"       # json exports, clip index, stoppage check images
CLIPS_DIR = EXPORT_DIR / "clips"
STATE_DIR = EXPORT_DIR / "state"                   # hand-off between the notebooks
for _d in (EXPORT_DIR, CLIPS_DIR, STATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- load
player_frame_table = pd.read_parquet(PLAYER_PATH)
ball_frame_table = pd.read_parquet(BALL_PATH)
print("player table:", PLAYER_PATH.name, player_frame_table.shape)
print("ball table  :", BALL_PATH.name, ball_frame_table.shape)

# ---------------------------------------------------------------- data contract
NEED_PLAYER = ["frame_idx", "track_id", "role", "team", "pitch_x", "pitch_y", "is_carrier"]
NEED_BALL = ["frame_idx", "carrier_track_id", "carrier_team", "possession_team", "ball_pitch_x", "ball_pitch_y"]
NEED_CLIPS = ["name", "number", "x1", "y1", "x2", "y2", "foot_px_x", "foot_px_y"]      # only the clip notebook needs these

# accept the named-table spelling of the ball coordinates
_ren = {}
if "ball_pitch_x" not in ball_frame_table.columns and "pitch_x" in ball_frame_table.columns: _ren["pitch_x"] = "ball_pitch_x"
if "ball_pitch_y" not in ball_frame_table.columns and "pitch_y" in ball_frame_table.columns: _ren["pitch_y"] = "ball_pitch_y"
if _ren:
    ball_frame_table = ball_frame_table.rename(columns=_ren)
    print("ball table: renamed", _ren)

# COLUMN-COLLISION GUARD. The named player table already carries ball-derived columns (possession_team, carrier_track_id, is_stoppage, ...).
# The analysis merges the ball table's own copies onto the player table, which would create possession_team_x / _y and break every lookup.
# The ball table is the source of truth for those, so the player table's copies are dropped here.
_protected = set(NEED_PLAYER) | {"t_sec", "name", "number", "team_name", "attack_dir", "x1", "y1", "x2", "y2", "foot_px_x", "foot_px_y"}
_dups = (set(player_frame_table.columns) & set(ball_frame_table.columns)) - _protected - {"frame_idx"}
_dups |= {c for c in ("carrier_track_id", "carrier_team", "possession_team", "ball_pitch_x", "ball_pitch_y", "is_stoppage")
          if c in player_frame_table.columns}
if _dups:
    player_frame_table = player_frame_table.drop(columns=sorted(_dups))
    print("column guard: dropped from the player table (the ball table is the source for these):", sorted(_dups))
if "is_stoppage" in ball_frame_table.columns:                  # stoppages are re-detected in notebook 01 from carrier gaps
    ball_frame_table = ball_frame_table.drop(columns="is_stoppage")

player_frame_table["team"] = pd.to_numeric(player_frame_table["team"], errors="coerce").astype("float64")

# ORIENTATION: the analysis assumes team 0 = attacks +x (own goal at x=0), team 1 = attacks -x. The named tables can carry the opposite
# labelling (e.g. team 1 = Barca attacking +x), so the labels are swapped once here. attack_dir belongs to the physical team and is untouched;
# team NAMES are re-derived from the table's team_name column afterwards.
_ct_from_file = "carrier_team" in ball_frame_table.columns
if "attack_dir" in player_frame_table.columns:
    _ad0 = {int(k): float(np.sign(v)) for k, v in player_frame_table.dropna(subset=["team", "attack_dir"]).groupby("team")["attack_dir"].mean().items()}
    if _ad0 == {0: -1.0, 1: 1.0}:
        player_frame_table["team"] = 1.0 - player_frame_table["team"]
        for _col in ("carrier_team", "possession_team"):
            if _col in ball_frame_table.columns:
                ball_frame_table[_col] = 1.0 - pd.to_numeric(ball_frame_table[_col], errors="coerce")
        print("ORIENTATION: table had team 0 attacking -x / team 1 attacking +x -> team ids swapped on load "
              "(now team 0 attacks +x, team 1 attacks -x, as the analysis cells assume)")
    elif _ad0 != {0: 1.0, 1: -1.0}:
        raise AssertionError(f"attack_dir per team = {_ad0}: expected one team per direction (first half) - check the table")

_NICE = {"BAR": "Barca", "ATM": "Atletico"}
if "team_name" in player_frame_table.columns:
    _tn = player_frame_table.dropna(subset=["team", "team_name"]).groupby("team")["team_name"].agg(lambda s: s.mode().iat[0])
    TEAM_NAMES = {int(k): _NICE.get(str(v), str(v)) for k, v in _tn.items()}
print("TEAM_NAMES:", TEAM_NAMES)

player_frame_table["is_carrier"] = player_frame_table["is_carrier"].fillna(False).astype(bool)
player_frame_table = player_frame_table.drop_duplicates(["frame_idx", "track_id"]).reset_index(drop=True)

if "carrier_team" not in ball_frame_table.columns and "carrier_track_id" in ball_frame_table.columns:
    _team_of = player_frame_table.dropna(subset=["team"]).groupby("track_id")["team"].agg(lambda s: s.mode().iat[0])
    ball_frame_table["carrier_team"] = ball_frame_table["carrier_track_id"].map(_team_of)
    print("ball table: derived carrier_team from carrier_track_id")
if "possession_team" not in ball_frame_table.columns and "carrier_team" in ball_frame_table.columns:
    ball_frame_table["possession_team"] = ball_frame_table["carrier_team"]
    print("WARNING: ball table has no possession_team - using carrier_team (no gap fill)")
for _c in ["carrier_track_id", "carrier_team", "possession_team", "ball_pitch_x", "ball_pitch_y"]:
    if _c in ball_frame_table.columns:
        ball_frame_table[_c] = pd.to_numeric(ball_frame_table[_c], errors="coerce").astype("float64")
ball_frame_table = ball_frame_table.drop_duplicates("frame_idx").sort_values("frame_idx").reset_index(drop=True)

# the ball table's team labels must use the SAME ids as the player table (otherwise carrier / possession logic silently inverts)
if _ct_from_file:
    _team_of2 = player_frame_table.dropna(subset=["team"]).groupby("track_id")["team"].agg(lambda s: s.mode().iat[0])
    _has = ball_frame_table["carrier_track_id"].notna()
    _agree = float((ball_frame_table.loc[_has, "carrier_team"] == ball_frame_table.loc[_has, "carrier_track_id"].map(_team_of2)).mean())
    print(f"ball-table carrier_team agrees with the player table's team ids on {_agree:.1%} of carrier frames")
    assert _agree > 0.9, ("ball_frame_table.carrier_team uses different team ids than player_frame_table.team - the label swap above only "
                          "fits tables that were labelled the same way; check how the ball table was built")

_miss_p = [c for c in NEED_PLAYER if c not in player_frame_table.columns]
_miss_b = [c for c in NEED_BALL if c not in ball_frame_table.columns]
assert not _miss_p and not _miss_b, f"missing columns - player: {_miss_p} | ball: {_miss_b}"
_miss_c = [c for c in NEED_CLIPS if c not in player_frame_table.columns]
if _miss_c:
    print("NOTE: columns needed only for the clip notebook are missing:", _miss_c)

_ad = {int(k): float(np.sign(v)) for k, v in player_frame_table.dropna(subset=["team", "attack_dir"]).groupby("team")["attack_dir"].mean().items()} \
    if "attack_dir" in player_frame_table.columns else ATTACK_SIGN
assert _ad == ATTACK_SIGN, f"attack_dir says {_ad}, notebook assumes {ATTACK_SIGN}"

if "t_sec" in player_frame_table.columns:
    _fps = (player_frame_table.frame_idx.max() - player_frame_table.frame_idx.min()) / (player_frame_table.t_sec.max() - player_frame_table.t_sec.min())
    if abs(_fps - FPS) > 0.5:
        print(f"WARNING: table implies {_fps:.2f} fps but FPS={FPS}")

# identity helpers (named cache: one track_id = one shirt number + name)
def _mode(s):
    s = s.dropna()
    return s.mode().iat[0] if len(s) else np.nan
_g = player_frame_table.groupby("track_id")
_ti = pd.DataFrame({"role": _g["role"].agg(_mode), "team": _g["team"].agg(_mode)})
_ti["name"] = _g["name"].agg(_mode) if "name" in player_frame_table.columns else np.nan
_ti["number"] = _g["number"].agg(_mode) if "number" in player_frame_table.columns else np.nan
TRACK_ROLE = {int(i): r for i, r in _ti["role"].items()}
TRACK_TEAM = {int(i): t for i, t in _ti["team"].items()}
TRACK_NUM = {int(i): int(n) for i, n in _ti["number"].items() if pd.notna(n)}
TRACK_LABEL = {int(i): (f"#{int(r['number'])} {r['name']}" if pd.notna(r["number"]) else str(r["name"])) for i, r in _ti.iterrows()}
GK_IDS = {i for i, r in TRACK_ROLE.items() if r == "goalkeeper"}

print("\nroles:", player_frame_table["role"].value_counts(dropna=False).to_dict())
print(f"frames {player_frame_table.frame_idx.min()}..{player_frame_table.frame_idx.max()} | ball rows {len(ball_frame_table)} | "
      f"carrier coverage {ball_frame_table.carrier_track_id.notna().mean():.1%} | goalkeepers {sorted(GK_IDS)}")
print("data contract OK")

# ---------------------------------------------------------------- shared helpers
def zone_for_team(x, team):
    # thirds relative to `team`'s own attack direction (team 0 attacks +x, team 1 attacks -x)
    if pd.isna(x):
        return None
    if team == 0:
        return "own_third" if x < 35 else ("middle_third" if x < 70 else "attacking_third")
    return "own_third" if x > 70 else ("middle_third" if x > 35 else "attacking_third")

def channel_for_team(y, team):
    # left / centre / right in the team's OWN frame (180-degree rotation for team 1)
    if pd.isna(y):
        return None
    y_att = y if int(team) == 0 else PITCH_WIDTH - y
    ch = "left" if y_att < PITCH_WIDTH / 3 else ("right" if y_att > 2 * PITCH_WIDTH / 3 else "centre")
    if FLIP_CHANNELS:
        ch = {"left": "right", "right": "left"}.get(ch, ch)
    return ch

def mask_runs(frames, mask, max_gap=5, min_len=1):
    # contiguous True-runs of `mask` over `frames` (sorted frame numbers); gaps up to max_gap frames are bridged
    frames = np.asarray(frames)
    idx = np.flatnonzero(np.asarray(mask, bool))
    if len(idx) == 0:
        return []
    runs, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if frames[i] - frames[p] > max_gap + 1:
            runs.append((int(frames[s]), int(frames[p])))
            s = i
        p = i
    runs.append((int(frames[s]), int(frames[p])))
    return [(a, b) for a, b in runs if b - a + 1 >= min_len]

def team_frame_width(y_vals, iqr_mult=1.5):
    # IQR-trimmed lateral spread of a set of y positions (same definition as section 18)
    y = np.asarray(y_vals)
    if len(y) < 4:
        return np.nan
    q1, q3 = np.percentile(y, [25, 75])
    iqr = q3 - q1
    yt = y[(y >= q1 - iqr_mult * iqr) & (y <= q3 + iqr_mult * iqr)]
    return float(yt.max() - yt.min()) if len(yt) else np.nan

def clock_str(f):
    s = int(round(f / FPS))
    return f"{s // 60:02d}:{s % 60:02d}"

# ---------------------------------------------------------------- hand-off between notebooks
# columns kept when a big per-row table is handed to the next notebook (everything downstream only needs these)
STATE_COLS = {
    "off_ball_pressure": ["frame_idx", "track_id", "team", "carrier_team", "possession_team", "dist_to_carrier",
                          "closing_speed_mps", "stepped_out_of_line", "is_pressuring"],
}
_MANIFEST = STATE_DIR / "_manifest.json"

def save_state(ns, names, notebook):
    """Pickle the named variables of a notebook so the next notebooks can load them."""
    man = json.loads(_MANIFEST.read_text()) if _MANIFEST.exists() else {}
    rows = []
    for n in names:
        obj = ns[n]
        if isinstance(obj, pd.DataFrame) and n in STATE_COLS:
            obj = obj[[c for c in STATE_COLS[n] if c in obj.columns]]
        pd.to_pickle(obj, STATE_DIR / f"{n}.pkl")
        man[n] = notebook
        rows.append((n, type(obj).__name__, (STATE_DIR / f"{n}.pkl").stat().st_size / 1e6))
    _MANIFEST.write_text(json.dumps(man, indent=1))
    print(f"saved {len(rows)} variables to {STATE_DIR}")
    for n, t, mb in rows:
        print(f"  {n:<34}{t:<12}{mb:8.2f} MB")

def load_state(ns, names):
    """Load variables written by earlier notebooks into this notebook's namespace."""
    man = json.loads(_MANIFEST.read_text()) if _MANIFEST.exists() else {}
    for n in names:
        p = STATE_DIR / f"{n}.pkl"
        if not p.exists():
            raise FileNotFoundError(f"'{n}' not found - run {man.get(n, 'the earlier notebook that produces it')} first (looked in {STATE_DIR})")
        ns[n] = pd.read_pickle(p)
    print(f"loaded {len(names)} variables from {STATE_DIR}")
