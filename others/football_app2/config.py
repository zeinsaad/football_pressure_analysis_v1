"""Paths and look-up tables. Edit this file only; nothing else has hard-coded paths."""
import os
from pathlib import Path

# Project root. Override with the FOOTBALL_BASE environment variable if the folder moves.
BASE = Path(os.environ.get(
    "FOOTBALL_BASE",
    r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project",
))

# Tab 1: full annotated match video
MATCH_VIDEO = BASE / "barca_atletico_first_half" / "new_cache" / "annotated_teams.mp4"

# Tab 2: build-up clips (only the hand-checked "good" folders)
CLIPS_ROOT = BASE / "new" / "press" / "buildup_output" / "clips_buildup"
CLIP_FOLDERS = {
    "kept": CLIPS_ROOT / "kept_under_pressure" ,
    "lost": CLIPS_ROOT / "lost_under_pressure" ,
}

# Analyses are read from the clip's own folder: b119_BAR_32-26.mp4 -> b119_BAR_32-26_analysis.txt
# Optional legacy fallback, used only when a clip has no _analysis.txt: {"b119_BAR_32-26": "paragraph...", ...}
EXPLANATIONS_FILE = CLIPS_ROOT / "explanations.json"

# Browser-playable copies and thumbnails are stored here (safe to delete)
CACHE_DIR = Path(__file__).parent / ".cache"

TEAMS = {
    "BAR": dict(name="Barcelona", short="Barça", bg="#004D98", edge="#A50044", accent="#1E78FF"),
    "ATM": dict(name="Atlético Madrid", short="Atlético", bg="#CB3524", edge="#F2F2F2", accent="#EB3737"),
}

OUTCOMES = {
    "kept": dict(label="Kept the ball", detail="Progressed despite pressure", fg="#5FD3A8", bg="rgba(63,182,139,.16)"),
    "lost": dict(label="Lost the ball", detail="Ball lost under pressure", fg="#FF9A76", bg="rgba(240,120,80,.16)"),
}

# Full-match video: when the file is not browser-playable it is converted ONCE, automatically, at its original size.
# CRF is the H.264 quality (lower = better and bigger; 18 is visually lossless, 23 is the ffmpeg default).
MATCH_CRF = 18

# Tab 3: statistics exported from the stats notebook (python tools/export_stats.py <notebook>)
STATS_DIR = Path(__file__).parent / "data" / "stats"

# Tab 4: tactical conclusions (plain text). A copy in data/ is used only if the original path is missing.
CONCLUSIONS_FILE = BASE / "new" / "press" / "bar_atm_tactical_conclusions.txt"
CONCLUSIONS_FALLBACK = Path(__file__).parent / "data" / "bar_atm_tactical_conclusions.txt"
