"""Look and feel: one stylesheet plus small HTML helpers (chips)."""
import streamlit as st

import config

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap');

:root {
  --bg: #0E1420; --surface: #151D2E; --line: #26324A;
  --text: #E8EDF5; --muted: #8D9AB3;
}
.stApp { font-family: 'Barlow', 'Segoe UI', sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }

.app-title { font-family: 'Barlow Condensed', 'Segoe UI', sans-serif; font-weight: 700;
  font-size: 2.5rem; line-height: 1.05; letter-spacing: .01em; margin: 0; }
.app-sub { color: var(--muted); margin: .3rem 0 1.4rem 0; font-size: 1.02rem; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { padding: .55rem 0; font-size: 1.05rem; font-weight: 500; }

/* chips */
.chip { display: inline-block; padding: .14rem .62rem; border-radius: 999px; font-size: .8rem;
  font-weight: 600; margin-right: .35rem; line-height: 1.5; }
.chip-team { color: #fff; border-left: 5px solid; }
.chip-out { border: 1px solid currentColor; }

.chip-analysis { color: var(--muted); border: 1px solid var(--line); background: transparent; }

/* analysis panel in the player dialog */
.section-label { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.1rem;
  letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin: 1.1rem 0 .45rem 0; }
.analysis-h { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.05rem;
  letter-spacing: .04em; text-transform: uppercase; color: var(--muted); margin: .9rem 0 .25rem 0; }
.analysis-h:first-child { margin-top: .1rem; }
.analysis-preview { color: var(--text); line-height: 1.6; }
.analysis-empty { border: 1px dashed var(--line); border-radius: 10px; padding: .9rem 1rem;
  color: var(--muted); font-size: .95rem; }

/* clip cards */
.clip-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.45rem;
  line-height: 1.1; margin: .55rem 0 .25rem 0; }
.clip-meta { color: var(--muted); font-size: .9rem; margin: .25rem 0 .1rem 0; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
div[data-testid="stImage"] img { border-radius: 6px; }

/* list rows */
.row-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.35rem; margin: 0; }

.stat-n { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 2rem; line-height: 1; }
.stat-l { color: var(--muted); font-size: .85rem; }
.empty { border: 1px dashed var(--line); border-radius: 10px; padding: 2.2rem; text-align: center; color: var(--muted); }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def team_chip(code: str) -> str:
    t = config.TEAMS.get(code, dict(short=code, bg="#334", edge="#889"))
    return f'<span class="chip chip-team" style="background:{t["bg"]};border-left-color:{t["edge"]}">{t["short"]}</span>'


def outcome_chip(key: str) -> str:
    o = config.OUTCOMES[key]
    return f'<span class="chip chip-out" style="color:{o["fg"]};background:{o["bg"]}">{o["label"]}</span>'


def analysis_chip() -> str:
    return '<span class="chip chip-analysis">Analysis</span>'


def stat(n, label: str) -> str:
    return f'<div class="stat-n">{n}</div><div class="stat-l">{label}</div>'
