"""Formation tab: every player's average position, written by the formation cell of the stats notebook (<stats folder>/formation.json).

Both teams are drawn on ONE pitch: Barca attacks left -> right, the other team right -> left. Pure inline SVG, no extra packages.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Optional

import streamlit as st

import config

FORMATION_JSON = config.STATS_DIR / "formation.json"
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 4, 4, 5, 5          # room around the pitch for names near the lines


@st.cache_data(show_spinner=False)
def _load(path_str: str, mtime: float) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load() -> Optional[dict]:
    if not FORMATION_JSON.exists():
        return None
    try:
        return _load(str(FORMATION_JSON), FORMATION_JSON.stat().st_mtime)
    except (OSError, ValueError):
        return None


def has_lineup(data: dict) -> bool:
    return bool(data.get("lineup")) and all(t.get("players") for t in data["lineup"].values())


def lineup_table(data: dict) -> list[dict]:
    return [dict(team=team, formation=v["formation"], line={"G": "GK", "D": "Defence", "M": "Midfield", "F": "Attack"}.get(p["line"], p["line"]),
                 number=p["number"], name=p["name"], position=p["position"] or "") for team, v in data["lineup"].items() for p in v["players"]]


def phase_table(data: dict, phase: str) -> list[dict]:
    rows = []
    for team, players in data["phases"][phase]["teams"].items():
        for p in players:
            rows.append(dict(team=team, number=p["number"], name=p["name"], position=p["position"] or "", seconds=p["seconds"]))
    return rows


def _pitch_html(data: dict, players_by_team: dict, show_names: bool, extra: dict | None = None, theme: str = "dark") -> str:
    """One self-contained HTML document with the pitch (for st.iframe / components.html). Hover a player for number, name and position."""
    L, W = data["pitch"]
    ltr = data["ltr_team"]
    teams = list(players_by_team)
    extra = extra or {}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-_PAD_L} {-_PAD_T} {L + _PAD_L + _PAD_R} {W + _PAD_T + _PAD_B}" '
         f'style="width:100%;height:auto;display:block;border-radius:10px" font-family="Arial,Helvetica,sans-serif">',
         f'<rect x="{-_PAD_L}" y="{-_PAD_T}" width="{L + _PAD_L + _PAD_R}" height="{W + _PAD_T + _PAD_B}" fill="#2f6b3a"/>']
    o += [f'<rect x="{i * L / 15:.2f}" y="0" width="{L / 15:.2f}" height="{W}" fill="{"#357a42" if i % 2 == 0 else "#2f6b3a"}"/>' for i in range(15)]
    ln = 'fill="none" stroke="#f4f4f0" stroke-width=".55"'
    o += [f'<rect x="0" y="0" width="{L}" height="{W}" {ln}/>', f'<line x1="{L / 2}" y1="0" x2="{L / 2}" y2="{W}" {ln}/>',
          f'<circle cx="{L / 2}" cy="{W / 2}" r="9.15" {ln}/>', f'<circle cx="{L / 2}" cy="{W / 2}" r=".45" fill="#f4f4f0"/>']
    for left in (True, False):
        o.append(f'<rect x="{0 if left else L - 16.5}" y="{W / 2 - 20.15}" width="16.5" height="40.3" {ln}/>')
        o.append(f'<rect x="{0 if left else L - 5.5}" y="{W / 2 - 9.16}" width="5.5" height="18.32" {ln}/>')
    palette = {code: (cfg["bg"], cfg["edge"]) for code, cfg in config.TEAMS.items()}
    fallback = [("#004D98", "#A50044"), ("#CB3524", "#F2F2F2")]
    for k, team in enumerate(teams):
        shirt, edge = palette.get(team, fallback[k % 2])
        below = team == ltr                                     # names: the left-to-right team below its circles, the other above, so neighbours do not collide
        for p in players_by_team[team]:
            cx, cy = p["x"], W - p["y"]                         # figure metres (y up) -> svg (y down)
            tip = f'{p["name"]}' + (f' #{p["number"]}' if p["number"] is not None else "") + (f' ({p["position"]})' if p["position"] else "") + extra.get("tip", lambda q: "")(p)
            o.append(f'<g><title>{html.escape(tip)}</title>'
                     f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="2.45" fill="{shirt}" stroke="{edge}" stroke-width=".7"/>'
                     f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="central" font-size="2.5" font-weight="700" fill="#fff">'
                     f'{"" if p["number"] is None else p["number"]}</text>')
            if show_names:
                ty = cy + 5.4 if below else cy - 3.9
                base = f'x="{cx:.2f}" y="{ty:.2f}" text-anchor="middle" font-size="2.1" font-weight="700"'
                o.append(f'<text {base} fill="none" stroke="{shirt}" stroke-width=".9" stroke-linejoin="round">{html.escape(p["name"])}</text>'
                         f'<text {base} fill="#fff">{html.escape(p["name"])}</text>')
            o.append("</g>")
    o.append("</svg>")
    muted = "#8d9ab3" if theme == "dark" else "#55607a"
    forms = extra.get("formations", {})
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4rem;margin-right:1.1rem"><i style="display:inline-block;width:.8rem;height:.8rem;border-radius:50%;'
        f'background:{palette.get(t, fallback[i % 2])[0]};border:2px solid {palette.get(t, fallback[i % 2])[1]}"></i>'
        f'{html.escape(config.TEAMS.get(t, {}).get("short", t))}{" " + html.escape(forms[t]) if t in forms else ""}, '
        f'{"attacks left to right" if t == ltr else "attacks right to left"}</span>'
        for i, t in enumerate(teams))
    return f'<div style="font:14px Arial,Helvetica,sans-serif;color:{muted};margin:0 0 .5rem 0">{chips}</div>' + "".join(o)


def lineup_html(data: dict, show_names: bool = True) -> str:
    """Each player on his real position (GK, defenders, midfielders, forwards; left to right as his team sees it), each team in its own half."""
    return _pitch_html(data, {t: v["players"] for t, v in data["lineup"].items()}, show_names,
                       dict(formations={t: v["formation"] for t, v in data["lineup"].items()}))


def formation_html(data: dict, phase: str, show_names: bool = True) -> str:
    """Average (median) position of every player in the chosen phase."""
    return _pitch_html(data, data["phases"][phase]["teams"], show_names,
                       dict(tip=lambda p: f' - {p["seconds"]} s in this phase', formations={t: v["formation"] for t, v in (data.get("lineup") or {}).items()}))
