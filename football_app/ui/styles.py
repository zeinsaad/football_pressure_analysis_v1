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
/* The page header of Streamlit is fixed and about 3.75rem tall; the content needs to start below it or the title is cut. */
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 5rem !important; max-width: 1280px; }

.app-title { font-family: 'Barlow Condensed', 'Segoe UI', sans-serif; font-weight: 700;
  font-size: 2.5rem; line-height: 1.2; letter-spacing: .01em; margin: 0; padding-top: .15rem; overflow: visible; }
.app-sub { color: var(--muted); margin: .35rem 0 1.5rem 0; font-size: 1.02rem; line-height: 1.5; overflow: visible; }

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



/* ---------- stats tab ---------- */
.stats-meta { color: var(--muted); font-size: .92rem; margin: .1rem 0 1rem 0; }
.vs-panel { border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.4rem 1.3rem; background: linear-gradient(180deg, #151D2E 0%, #121a29 100%); }
.vs-teams { display: flex; justify-content: space-between; align-items: center; margin-bottom: .9rem; }
.vs-team { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 1.6rem; letter-spacing: .02em; border-bottom: 3px solid var(--c); padding-bottom: .1rem; }
.vs-mid-h { color: var(--muted); font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; }
.vs-row { display: grid; grid-template-columns: 110px 1fr 110px; gap: 1rem; align-items: center; padding: .62rem 0; border-top: 1px solid #1f2a42; }
.vs-row.first { border-top: none; }
.vs-v { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.9rem; line-height: 1; color: #8D9AB3; text-align: left; }
.vs-v.right { text-align: right; }
.vs-v.lead { color: #fff; font-weight: 700; }
.vs-v small { font-size: .95rem; font-weight: 500; margin-left: .15rem; color: var(--muted); }
.vs-l { text-align: center; font-weight: 600; font-size: .98rem; margin-bottom: .3rem; }
.vs-h { text-align: center; color: var(--muted); font-size: .78rem; margin-top: .3rem; }
.vs-track { display: flex; height: 8px; border-radius: 999px; overflow: hidden; gap: 3px; }
.vs-track i { display: block; height: 100%; }

.sec-head { display: flex; align-items: baseline; gap: .7rem; margin: .1rem 0 .15rem 0; }
.sec-num { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: .95rem; color: #0E1420; background: #6EA8FE;
  border-radius: 6px; padding: .02rem .5rem; letter-spacing: .02em; }
.sec-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 1.75rem; line-height: 1.2; margin: 0; }
.sec-desc { color: #C3CCDD; line-height: 1.6; margin: .15rem 0 .5rem 0; }
.sub-label { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1rem; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); margin: .9rem 0 .4rem 0; }

.finding { border: 1px solid var(--line); border-left: 4px solid var(--c, #3a4a6b); border-radius: 8px; background: #121a29;
  padding: .6rem .85rem; margin: 0 0 .5rem 0; line-height: 1.5; font-size: .95rem; }
.finding b { color: #fff; font-weight: 600; }
.finding-note { color: var(--muted); font-size: .84rem; line-height: 1.45; margin: .15rem 0 .35rem 0; padding-left: .2rem; }

.tbl-cap { color: var(--muted); font-size: .85rem; margin: .5rem 0 .3rem 0; font-weight: 500; }
.tbl-wrap { overflow: visible; border: 1px solid var(--line); border-radius: 10px; margin: 0 0 .5rem 0; }
table.stbl { border-collapse: collapse; width: 100%; table-layout: auto; font-size: .88rem; font-variant-numeric: tabular-nums; }
.stbl th { background: #10192a; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; font-size: .7rem;
  padding: .55rem .6rem; text-align: right; white-space: normal; line-height: 1.25; vertical-align: bottom; border-bottom: 1px solid var(--line); }
.stbl td { padding: .48rem .6rem; text-align: right; border-bottom: 1px solid #1d2840; white-space: normal; }
.stbl th.l, .stbl td.l { text-align: left; }
.stbl tr:last-child td { border-bottom: none; }
.stbl tbody tr:hover td { background: rgba(110,168,254,.06); }
.stbl tr.grp td { border-top: 1px solid #34425f; }
.stbl .chip { margin: 0; font-size: .74rem; padding: .08rem .5rem; }
.stbl .yes { color: #5FD3A8; } .stbl .no { color: #55627d; }

.fr-cap { font-size: .86rem; line-height: 1.4; margin: .4rem 0 .25rem 0; color: #D5DCEA; min-height: 2.4em; }
.fr-clock { display: inline-block; font-size: .72rem; font-weight: 600; letter-spacing: .04em; color: #8D9AB3; border: 1px solid var(--line);
  border-radius: 6px; padding: .02rem .4rem; margin-right: .4rem; font-variant-numeric: tabular-nums; }

/* ---------- conclusions tab ---------- */
.concl-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 1.7rem; line-height: 1.2; margin: 0 0 .5rem 0; }
.concl-intro { color: #C3CCDD; line-height: 1.7; font-size: 1.02rem; }
.concl-meta { color: var(--muted); font-size: .85rem; margin: 0 0 1rem 0; }

/* per-player cards */
.pc-head { display:flex; align-items:baseline; gap:.8rem; border-left:5px solid var(--c); padding-left:.7rem; margin:.1rem 0 .6rem 0; }
.pc-name { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.7rem; line-height:1.1; }
.pc-num { color:var(--muted); font-weight:500; font-size:1.2rem; }
.pc-team { color:var(--muted); font-size:.95rem; }
.pc-t { color:var(--muted); font-size:.88rem; margin-bottom:.5rem; }
table.pgrid { border-collapse:collapse; width:100%; margin-bottom:1rem; }
table.pgrid th, table.pgrid td { padding:.95rem .4rem; text-align:center; border:2px solid var(--surface); font-size:1.15rem; }
table.pgrid thead th { font-size:.8rem; color:var(--muted); font-weight:500; padding:.3rem; }
table.pgrid tbody th { text-align:right; font-size:.85rem; color:var(--muted); font-weight:500; width:3.6rem; }
table.pgrid td { font-weight:600; border-radius:4px; }
.pc-kv { display:flex; justify-content:space-between; padding:.55rem 0; border-top:1px solid var(--line); font-size:.95rem; }
.pc-kv span { color:var(--muted); }

/* big team photo (defensive shape) */
.ph-head { display:flex; align-items:center; gap:.7rem; border-left:5px solid var(--c); padding-left:.7rem; margin:.9rem 0 .5rem 0; }
.ph-team { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.5rem; line-height:1.1; }

/* hero header */
.hero { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:1.4rem; padding:1.1rem 1.6rem; margin:0 0 1.2rem 0;
  border:1px solid var(--line); border-radius:16px; position:relative; overflow:hidden;
  background: linear-gradient(100deg, rgba(0,77,152,.45) 0%, rgba(21,29,46,.96) 38%, rgba(21,29,46,.96) 62%, rgba(203,53,36,.40) 100%); }
.hero-badge svg { display:block; width:64px; height:76px; filter:drop-shadow(0 2px 6px rgba(0,0,0,.45)); }
.hero-eyebrow { font-size:.78rem; letter-spacing:.2em; text-transform:uppercase; color:#9fb3d6; font-weight:600; }
.hero-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:2.7rem; line-height:1.05; letter-spacing:.01em; margin:.15rem 0 .25rem 0; color:#fff; }
.hero-title i { font-style:normal; color:#8D9AB3; font-weight:500; margin:0 .35rem; }
.hero-sub { color:#b6c2da; font-size:1rem; line-height:1.45; }
.hero-vs { display:flex; align-items:center; gap:.9rem; }
.hero-team { text-align:center; font-family:'Barlow Condensed',sans-serif; font-weight:600; letter-spacing:.06em; font-size:.95rem; color:#dfe7f5; }
.hero-vs-t { color:#8D9AB3; font-size:.8rem; letter-spacing:.2em; text-transform:uppercase; }
.crest { width:50px; height:50px; border-radius:50%; background:var(--bg); border:3px solid var(--edge); display:grid; place-items:center;
  font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.05rem; color:#fff; letter-spacing:.04em; margin:0 auto .2rem auto; box-shadow:0 2px 8px rgba(0,0,0,.4); }
@media (max-width: 820px) { .hero { grid-template-columns:auto 1fr; } .hero-vs { grid-column:1 / -1; justify-content:center; } .hero-title { font-size:2.1rem; } }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# Light mode: the dark design is inverted as a whole (the original is dark); photos, video, badges and team colours are turned
# back so they keep their real colours.
LIGHT_CSS = """
<style>
html { filter: invert(1) hue-rotate(180deg); }
img, video, canvas, .crest, .hero-badge svg, .chip-team, .vs-track { filter: invert(1) hue-rotate(180deg); }
</style>
"""


def apply_theme() -> None:
    if st.session_state.get("light_mode"):
        st.markdown(LIGHT_CSS, unsafe_allow_html=True)


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


def short(code: str) -> str:
    return config.TEAMS.get(code, {}).get("short", code)


def accent(code: str) -> str:
    return config.TEAMS.get(code, {}).get("accent", "#6EA8FE")


def pretty_teams(text: str) -> str:
    """BAR / ATM in notebook text -> Barça / Atlético."""
    import re
    return re.sub(r"\b(BAR|ATM)\b", lambda m: short(m.group(1)), text)
