"""The exported pressing statistics (data/stats/stats.json) turned into display-ready pieces.

The file is written by tools/export_stats.py from the executed stats notebook; this module only reads it.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Optional

import streamlit as st

import config
from ui.styles import accent, pretty_teams, short, team_chip

STATS_JSON = config.STATS_DIR / "stats.json"
TEAM_ORDER = ["BAR", "ATM"]                       # Barça is always on the left, as in every figure of the notebook

GROUPS = [("overview", "Overview"), ("pressing", "Pressing"), ("shape", "Defensive shape"),
          ("passing", "Passing"), ("players", "Players"), ("method", "Method & data")]


@st.cache_data(show_spinner=False)
def _load(path_str: str, mtime: float) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_stats() -> Optional[dict]:
    if not STATS_JSON.exists():
        return None
    try:
        return _load(str(STATS_JSON), STATS_JSON.stat().st_mtime)
    except (OSError, ValueError):
        return None


def asset(rel: str) -> Path:
    return config.STATS_DIR / rel


def section(data: dict, sid: str) -> Optional[dict]:
    return next((s for s in data["sections"] if s["id"] == sid), None)


# ------------------------------------------------------------------ numbers out of the tables
def _team_col(tb: dict) -> Optional[int]:
    for ci in range(tb["n_index"]):
        if any(r[ci] in TEAM_ORDER for r in tb["rows"]):
            return ci
    return None


def _num(x: str) -> Optional[float]:
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def value(data: dict, sid: str, idx: int, team: str, col: str, where: Optional[dict] = None) -> Optional[float]:
    s = section(data, sid)
    if not s or idx >= len(s["tables"]):
        return None
    tb = s["tables"][idx]; h = tb["header"]
    tc = _team_col(tb)
    if col not in h or tc is None:
        return None
    for r in tb["rows"]:
        if r[tc] != team:
            continue
        if where and any(k not in h or r[h.index(k)] != v for k, v in where.items()):
            continue
        return _num(r[h.index(col)])
    return None


# label, hint, section, table, column, filter, unit, decimals, which side leads ("high" / "low")
HEADLINE = [
    ("Pressing intensity", "share of out-of-possession time spent pressing", "m02", 0, "pressing_intensity_pct", None, "%", 1, "high"),
    ("Press-to-regain", "pressing episodes that end with the ball back within 5 s", "m14", 0, "regain_pct", {"scope": "all episodes"}, "%", 1, "high"),
    ("PPDA", "passes allowed per defensive action (lower = more aggressive)", "m06", 0, "PPDA", None, "", 2, "low"),
    ("Time to press", "median seconds to press after losing the ball", "m07", 0, "median_sec", None, "s", 2, "low"),
    ("Defensive line", "back-three depth, metres from their own goal", "m01", 0, "avg_line_depth_m", None, "m", 1, "high"),
    ("Block size", "area of the team out of possession, m² (smaller = tighter)", "m10", 0, "area_mean", None, "m²", 0, "low"),
    ("Pass success under pressure", "completed share of resolved passes", "m08", 0, "success_rate_pct", {"state": "under pressure"}, "%", 1, "high"),
]


def vs_panel_html(data: dict) -> str:
    rows = []
    for label, hint, sid, idx, col, where, unit, dec, lead_side in HEADLINE:
        a, b = (value(data, sid, idx, t, col, where) for t in TEAM_ORDER)
        if a is None or b is None:
            continue
        tot = a + b
        wa = 50.0 if tot <= 0 else max(8.0, min(92.0, 100 * a / tot))
        lead = 0 if a == b else (0 if (a > b) == (lead_side == "high") else 1)
        fmt = lambda v: f"{v:,.{dec}f}"
        sm = f"<small>{unit}</small>" if unit else ""
        first = " first" if not rows else ""
        rows.append(
            f'<div class="vs-row{first}">'
            f'<div class="vs-v{" lead" if lead == 0 and a != b else ""}">{fmt(a)}{sm}</div>'
            f'<div><div class="vs-l">{html.escape(label)}</div>'
            f'<div class="vs-track"><i style="width:{wa:.1f}%;background:{accent("BAR")}"></i><i style="width:{100 - wa:.1f}%;background:{accent("ATM")}"></i></div>'
            f'<div class="vs-h">{html.escape(hint)}</div></div>'
            f'<div class="vs-v right{" lead" if lead == 1 else ""}">{fmt(b)}{sm}</div></div>')
    if not rows:
        return ""
    head = (f'<div class="vs-teams"><span class="vs-team" style="--c:{accent("BAR")}">{short("BAR")}</span>'
            f'<span class="vs-mid-h">first half, out of possession</span>'
            f'<span class="vs-team" style="--c:{accent("ATM")}">{short("ATM")}</span></div>')
    return f'<div class="vs-panel">{head}{"".join(rows)}</div>'


# ------------------------------------------------------------------ tables
_HEADERS = {"ci95": "95% CI", "number": "#", "ppda": "PPDA", "50%": "Median", "enough_data": "Enough data", "pct_attacking_third": "% in attacking third"}
_UNITS = [("_pct_of_pitch", " (% of pitch)"), ("_pct", " (%)"), ("_m2", " (m²)"), ("_sec", " (s)"), ("_m", " (m)")]


def nice_header(h: str) -> str:
    if not h:
        return ""
    low = h.lower()
    if low in _HEADERS:
        return _HEADERS[low]
    if h.startswith("pct_"):
        h = "% " + h[4:]
    for suf, rep in _UNITS:
        if h.endswith(suf):
            h = h[:-len(suf)] + rep
            break
    h = h.replace("_", " ")
    return h[0].upper() + h[1:]


def _cell(h: str, v: str, is_index: bool) -> str:
    v = v.strip()
    if v in TEAM_ORDER:
        return team_chip(v)
    if v in ("True", "False"):
        return '<span class="yes">&#10003;</span>' if v == "True" else '<span class="no">&ndash;</span>'
    if v in ("NaN", "nan", "None", ""):
        return "&ndash;" if not is_index else ""
    if is_index:
        return html.escape(v.replace("_", " ").capitalize() if "_" in v else v)
    if re.fullmatch(r"-?\d{4,}", v):
        return f"{int(v):,}"
    if re.fullmatch(r"-?\d{4,}\.0+", v):
        return f"{int(float(v)):,}"
    return html.escape(v)


def table_html(tb: dict) -> str:
    n = tb["n_index"]; header = list(tb["header"])
    if header and header[0] == "" and any(r[0] in TEAM_ORDER for r in tb["rows"]):
        header[0] = "Team"
    ths = "".join(f'<th class="{"l" if i < n else ""}">{html.escape(nice_header(h))}</th>' for i, h in enumerate(header))
    body, prev = [], None
    for r in tb["rows"]:
        grp = prev is not None and n > 1 and r[0] != prev
        tds = []
        for i, v in enumerate(r):
            shown = "" if (i == 0 and n > 1 and r[0] == prev) else v
            tds.append(f'<td class="{"l" if i < n else ""}">{_cell(header[i], shown, i < n)}</td>')
        body.append(f'<tr class="{"grp" if grp else ""}">{"".join(tds)}</tr>')
        prev = r[0]
    return f'<div class="tbl-wrap"><table class="stbl"><thead><tr>{ths}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def table_csv(tb: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf); w.writerow(tb["header"]); w.writerows(tb["rows"])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


# ------------------------------------------------------------------ text
def md(text: str) -> str:
    """Notebook markdown -> markdown for the app ('$' is not maths; team codes become names)."""
    return pretty_teams(text).replace("$", r"\$")


def split_intro(text: str) -> tuple[str, str]:
    parts = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not parts:
        return "", ""
    return parts[0], "\n\n".join(parts[1:])


_NUM = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?\s?(?:%|m²|m\b|s\b)|\d+(?:\.\d+)?x)")


def finding_html(text: str) -> str:
    """One key finding as a card with a team-coloured edge and the figures in bold."""
    code = next((c for c in TEAM_ORDER if text.startswith(c)), None)
    body = _NUM.sub(r"<b>\1</b>", html.escape(text)).replace("\n", "<br>")
    colour = accent(code) if code else "#3a4a6b"
    return f'<div class="finding" style="--c:{colour}">{pretty_teams(body)}</div>'


def method_md(data: dict) -> str:
    keep = []
    for block in re.split(r"\n\s*\n", data.get("overview_md", "")):
        if block.startswith(("**Orientation", "**Definitions inherited", "| #")):
            keep.append(block)
    return "\n\n".join(keep)


# ------------------------------------------------------------------ exports
def csv_zip(data: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for s in data["sections"]:
            for tb in s["tables"]:
                z.writestr(f'{tb["id"]}.csv', table_csv(tb))
    return buf.getvalue()


def findings_text(data: dict) -> str:
    out = ["BARCA v ATLETICO, FIRST HALF: PRESSING STATS, KEY FINDINGS", "=" * 60, ""]
    for s in data["sections"]:
        if not s["summary"]:
            continue
        out.append(f'{s["number"]}. {s["title"]}')
        out += [("  - " if i["kind"] == "insight" else "  * note: ") + pretty_teams(i["text"]).replace("\n", " ") for i in s["summary"]]
        out.append("")
    return "\n".join(out)
