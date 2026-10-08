"""Find and describe the clip files. Name format written by the notebook: b119_BAR_32-26.mp4

Each clip may have an LLM analysis next to it, with the same name plus "_analysis":
    b119_BAR_32-26.mp4  ->  b119_BAR_32-26_analysis.txt
A missing, empty or unreadable analysis file is never an error; the clip just has no analysis.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

import config

NAME_RE = re.compile(r"^b(?P<id>\d+)_(?P<team>[A-Za-z]{3})_(?P<min>\d{1,3})-(?P<sec>\d{2})$")
ANALYSIS_SUFFIX = "_analysis.txt"
PREVIEW_CHARS = 230                       # how much of a long analysis is shown before "Read full analysis"
_ENCODINGS = ("utf-8-sig", "cp1252")      # Notepad on Windows often saves as one of these


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
    has_analysis: bool = False

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def analysis_path(self) -> Path:
        return self.path.with_name(f"{self.stem}{ANALYSIS_SUFFIX}")

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
            has_analysis = bool(_read_text(p.with_name(f"{p.stem}{ANALYSIS_SUFFIX}")))
            clips.append(Clip(path=p, buildup_id=int(m["id"]), team=m["team"].upper(), outcome=outcome,
                              minute=int(m["min"]), second=int(m["sec"]),
                              size_mb=round(s.st_size / 1e6, 1), mtime=s.st_mtime,
                              has_analysis=has_analysis))
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


# ------------------------------------------------------------------ analysis text
def _read_text(path: Path) -> Optional[str]:
    """File content as clean text, or None if the file is missing, empty or unreadable."""
    try:
        raw = path.read_bytes() if path.is_file() else b""
    except OSError:
        return None
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc).replace("\r\n", "\n").strip() or None
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1").replace("\r\n", "\n").strip() or None


@st.cache_data(ttl=10, show_spinner=False)
def _read_text_cached(path_str: str, mtime: float) -> Optional[str]:
    """`mtime` only exists to invalidate the cache when the file is edited."""
    return _read_text(Path(path_str))


def load_analysis(clip: Clip) -> Optional[str]:
    """The clip's `<name>_analysis.txt`; falls back to the old explanations.json; None if neither exists."""
    p = clip.analysis_path
    try:
        text = _read_text_cached(str(p), p.stat().st_mtime) if p.is_file() else None
    except OSError:
        text = None
    return text or load_explanations().get(clip.stem) or None


def analysis_preview(text: str, limit: int = PREVIEW_CHARS) -> tuple[str, bool]:
    """(short plain-text teaser, was_it_shortened). Ends on a sentence when it can, otherwise on a word."""
    plain = re.sub(r"(?m)^\s*(?:#{1,6}|>|[-*\u2022])\s*", "", text).replace("**", "").replace("`", "")
    plain = " ".join(plain.split())
    if len(plain) <= limit:
        return plain, False
    cut = plain[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end >= limit * 0.5:
        return cut[:end + 1], True
    return cut[:cut.rfind(" ")].rstrip(",;:- ") + "\u2026", True


# Analysis files look like:  header line / ==== rule / "1. VERDICT" / "2. WHAT HAPPENED" / ... / "DATA FLAGS"
_RULE_RE = re.compile(r"^\s*[=\-_*]{3,}\s*$")
_HEAD_RE = re.compile(r"^\s*(?:\d+[.)]\s+)?([A-Z][A-Z0-9 &/,'-]*[A-Z0-9](?:\s*\([^)]*\))?)\s*:?\s*$")


# Also accepted as headings: "2. Why (ranked)" (numbered, mixed case, short, numbered in order), "## Why", "**Why**".
_NUM_HEAD_RE = re.compile(r"^\s*(\d+)[.)]\s+([A-Z][A-Za-z0-9 &/,'()\-]{1,40}?)\s*:?\s*$")
_MD_HEAD_RE = re.compile(r"^\s*(?:#{1,6}\s+|\*\*)\s*([^*#\n]{2,40}?)\s*\**\s*:?\s*$")


def _heading_of(line: str, seen: int) -> Optional[str]:
    """Title if `line` is a section heading, else None. `seen` = headings found so far (numbered headings must come in order)."""
    m = _HEAD_RE.match(line)
    if m:
        return m.group(1).strip().capitalize()
    m = _NUM_HEAD_RE.match(line)
    if m and int(m.group(1)) == seen + 1 and len(m.group(2).split()) <= 5 and not m.group(2).rstrip().endswith((".", ";", ",")):
        t = m.group(2).strip()
        return t.capitalize() if t.isupper() else t
    m = _MD_HEAD_RE.match(line)
    if m:
        t = m.group(1).strip()
        return t.capitalize() if t.isupper() else t
    return None


def parse_analysis(text: str) -> list[tuple[str, str]]:
    """[(title, body), ...] from a structured analysis; [] when the text has no recognisable sections.

    The header line and ==== rules are dropped (the player already shows team, time and build-up).
    Titles come back without their numbers ("WHY (ranked)" -> "Why (ranked)").
    """
    sections: list[list] = []
    for line in text.splitlines():
        if _RULE_RE.match(line):
            continue
        title = _heading_of(line, len(sections))
        if title:
            sections.append([title, []])
        elif sections:
            sections[-1][1].append(line.rstrip())
    out = [(t, "\n".join(b).strip()) for t, b in sections]
    return [(t, b) for t, b in out if b]


def strip_rules(text: str) -> str:
    """Remove ==== / ---- separator lines (used for text that has no sections)."""
    return "\n".join(l for l in text.splitlines() if not _RULE_RE.match(l)).strip()
