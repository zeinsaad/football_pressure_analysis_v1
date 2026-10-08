"""Find and describe the clip files. Name format written by the notebook: b119_BAR_32-26.mp4"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

import config

NAME_RE = re.compile(r"^b(?P<id>\d+)_(?P<team>[A-Za-z]{3})_(?P<min>\d{1,3})-(?P<sec>\d{2})$")


@dataclass(frozen=True)
class Clip:
    path: Path
    buildup_id: int
    team: str          # "BAR" / "ATM"
    outcome: str       # "kept" / "lost"
    minute: int
    second: int
    size_mb: float
    mtime: float

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def time_label(self) -> str:
        return f"{self.minute:02d}:{self.second:02d}"

    @property
    def match_second(self) -> int:
        return self.minute * 60 + self.second


@st.cache_data(ttl=30, show_spinner=False)
def scan_clips() -> tuple[list[Clip], list[str], list[str]]:
    """Returns (clips, folders_missing, files_with_unrecognised_names)."""
    clips, missing, bad = [], [], []
    for outcome, folder in config.CLIP_FOLDERS.items():
        if not folder.exists():
            missing.append(str(folder))
            continue
        for p in sorted(folder.glob("*.mp4")):
            m = NAME_RE.match(p.stem)
            if not m:
                bad.append(p.name)
                continue
            s = p.stat()
            clips.append(Clip(path=p, buildup_id=int(m["id"]), team=m["team"].upper(), outcome=outcome,
                              minute=int(m["min"]), second=int(m["sec"]),
                              size_mb=round(s.st_size / 1e6, 1), mtime=s.st_mtime))
    return clips, missing, bad


@st.cache_data(ttl=10, show_spinner=False)
def load_explanations() -> dict[str, str]:
    f = config.EXPLANATIONS_FILE
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
