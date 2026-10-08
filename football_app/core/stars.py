"""Starred clips: a small JSON file next to the app, so the stars survive closing the browser, stopping Streamlit or restarting the PC."""
from __future__ import annotations

import json
import time
from pathlib import Path

import config


def key(clip) -> str:
    """Stable identity of a clip: team / outcome / file name (not its place in the list, so sorting never moves a star)."""
    return f"{clip.team}/{clip.outcome}/{clip.stem}"


def load(path: Path | None = None) -> set[str]:
    path = path or config.STARS_FILE
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("starred", []))
    except (OSError, ValueError, AttributeError):
        try:                                                      # unreadable file: keep a copy, start clean, never lose data silently
            path.replace(path.with_name(f"{path.stem}.corrupt-{int(time.time())}.json"))
        except OSError:
            pass
        return set()


def _save(starred: set[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(updated=time.strftime("%Y-%m-%dT%H:%M:%S"), starred=sorted(starred)), indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)                                             # atomic: a crash while saving cannot leave a half-written file


def is_starred(clip, starred: set[str]) -> bool:
    return key(clip) in starred


def toggle(clip, path: Path | None = None) -> bool:
    """Star / un-star a clip and write the file right away. Returns the new state."""
    path = path or config.STARS_FILE
    s = load(path)
    k = key(clip)
    now = k not in s
    s.add(k) if now else s.discard(k)
    _save(s, path)
    return now
