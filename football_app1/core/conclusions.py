"""Reads the plain-text tactical conclusions file and splits it into readable sections.

The layout of the text file is not fixed, so headings are recognised in the usual ways and anything else is shown as normal text:
    # Markdown heading                      1. NUMBERED ALL-CAPS HEADING        ALL-CAPS HEADING
    Any short line underlined with ==== or ----
A file with no headings at all is shown as one block. A missing or unreadable file is never an error.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import streamlit as st

import config

_ENCODINGS = ("utf-8-sig", "cp1252")
_RULE = re.compile(r"^\s*[=\-_*~]{3,}\s*$")
_MD_HEAD = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")
_CAPS_HEAD = re.compile(r"^\s*(?:(?:\d+|[IVX]+)[.)]\s+)?([A-ZÀ-Ý][A-ZÀ-Ý0-9 &/,'’:()+\-–]{2,80})\s*$")
_BULLET = re.compile(r"^\s*(?:[-*•·▪‣–]|\d+[.)])\s+")


@dataclass
class Section:
    title: str
    body: str


@dataclass
class Conclusions:
    path: Path
    mtime: float
    title: str = ""
    intro: str = ""
    sections: list[Section] = field(default_factory=list)
    raw: str = ""


def find_file() -> Optional[Path]:
    for p in (config.CONCLUSIONS_FILE, config.CONCLUSIONS_FALLBACK):
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def _read(path: Path) -> Optional[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc).replace("\r\n", "\n").replace("\r", "\n").strip() or None
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1").replace("\r\n", "\n").strip() or None


def _heading(lines: list[str], i: int) -> Optional[str]:
    """Title if line i is a heading, else None."""
    line = lines[i]
    if not line.strip() or _RULE.match(line):
        return None
    if m := _MD_HEAD.match(line):
        return m.group(1).strip()
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    if _RULE.match(nxt) and len(line.strip()) <= 90:                       # underlined title
        return line.strip().rstrip(":")
    if (m := _CAPS_HEAD.match(line)) and sum(c.isalpha() for c in line) >= 3 and not line.rstrip().endswith("."):
        return m.group(1).strip().rstrip(":")
    return None


def parse(text: str) -> tuple[str, str, list[Section]]:
    """(document title, intro text, sections). The title is the first heading when it comes before any body text."""
    lines = text.split("\n")
    secs: list[list] = []
    pre: list[str] = []
    for i, line in enumerate(lines):
        if _RULE.match(line):
            continue
        h = _heading(lines, i)
        if h:
            secs.append([h, []])
        elif secs:
            secs[-1][1].append(line.rstrip())
        else:
            pre.append(line.rstrip())
    sections = [Section(t, "\n".join(b).strip()) for t, b in secs]
    intro = "\n".join(pre).strip()
    title = ""
    if sections and not intro:                                              # first heading with no body = document title
        if not sections[0].body and len(sections) > 1:
            title = sections.pop(0).title
    elif intro and "\n" not in intro and len(intro) <= 100 and sections:    # one short line above the first heading
        title, intro = intro, ""
    return title, intro, [s for s in sections if s.body or s.title]


def _is_wrapped(block: list[str]) -> bool:
    """A paragraph that was hard-wrapped at ~70-80 columns: join it instead of breaking after every line."""
    lines = [l for l in block if l.strip()]
    return len(lines) > 2 and sum(len(l) for l in lines) / len(lines) > 55 and not any(_BULLET.match(l) for l in lines)


def to_markdown(body: str) -> str:
    """Plain text -> markdown: bullets become a list, wrapped paragraphs are joined, other line breaks are kept; '$' is not maths."""
    out = []
    for block in re.split(r"\n\s*\n", body.replace("$", r"\$")):
        lines = block.split("\n")
        if all(_BULLET.match(l) or not l.strip() or l.startswith(("  ", "\t")) for l in lines) and any(_BULLET.match(l) for l in lines):
            items = []
            for l in lines:
                if _BULLET.match(l):
                    items.append("- " + _BULLET.sub("", l, count=1).strip())
                elif items:
                    items[-1] += " " + l.strip()
            out.append("\n".join(items))
        elif _is_wrapped(lines):
            out.append(" ".join(l.strip() for l in lines))
        else:
            out.append("  \n".join(l.strip() for l in lines))
    return "\n\n".join(out)


@st.cache_data(ttl=10, show_spinner=False)
def _load(path_str: str, mtime: float) -> Optional[Conclusions]:
    p = Path(path_str)
    text = _read(p)
    if not text:
        return None
    title, intro, sections = parse(text)
    return Conclusions(path=p, mtime=mtime, title=title, intro=intro, sections=sections, raw=text)


def load() -> tuple[Optional[Conclusions], Optional[Path]]:
    """(conclusions or None, the file that was looked at)."""
    p = find_file()
    if p is None:
        return None, config.CONCLUSIONS_FILE
    try:
        return _load(str(p), p.stat().st_mtime), p
    except OSError:
        return None, p
