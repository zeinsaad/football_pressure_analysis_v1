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

/* tabs: one wide bar, equal-width columns, big condensed capitals, the open tab filled with an accent underline.
   Written with ARIA roles (role=tablist / tab, aria-selected) because they exist in every Streamlit version; the data-baseweb names were removed in new versions. */
.stTabs [role="tablist"] { gap: .4rem !important; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: .35rem; margin-bottom: 1.3rem; }
.stTabs [role="tablist"]::after, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"], .stTabs .react-aria-SelectionIndicator { display: none !important; }
.stTabs [role="tab"] { flex: 1 1 0 !important; justify-content: center !important; height: 3.3rem !important; padding: 0 1rem !important; border-radius: 9px; background: transparent;
  color: var(--muted) !important; transition: background .15s ease, color .15s ease; }
.stTabs [role="tab"] [data-testid="stMarkdownContainer"] p { font-family: 'Barlow Condensed', 'Segoe UI', sans-serif !important; font-size: 1.25rem !important; font-weight: 600 !important;
  letter-spacing: .05em; white-space: nowrap; text-transform: uppercase; margin: 0 !important; color: inherit !important; }
.stTabs [role="tab"]:hover { color: var(--text) !important; background: rgba(110,168,254,.08); }
.stTabs [role="tab"][aria-selected="true"] { color: #fff !important; background: rgba(110,168,254,.16); box-shadow: inset 0 -3px 0 #6EA8FE; }
@media (max-width: 1100px) { .stTabs [role="tablist"] { flex-wrap: wrap; } .stTabs [role="tab"] { flex: 1 1 40% !important; height: 2.7rem !important; }
  .stTabs [role="tab"] [data-testid="stMarkdownContainer"] p { font-size: 1.1rem !important; } }

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

/* ---------- clip player dialog: video and analysis side by side ---------- */
.dlg-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:2rem; line-height:1.1; letter-spacing:.01em;
  border-left:5px solid var(--c); padding-left:.7rem; margin:0; }
.st-key-dlg_prev button, .st-key-dlg_next button { min-height:2.5rem; border-radius:999px; font-size:1.5rem; line-height:1; padding:0 0 .2rem 0; }
.st-key-dlg_prev button p, .st-key-dlg_next button p { font-size:1.6rem !important; line-height:1; margin:0; }
.dlg-chips { margin-left:1rem; font-family:'Barlow',sans-serif; font-size:1rem; vertical-align:middle; }
.dlg-count { text-align:center; font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.35rem; color:#fff; font-variant-numeric:tabular-nums; }
.dlg-count span { color:var(--muted); font-weight:500; font-size:1rem; }
.dlg-facts { margin-left:1rem; color:var(--muted); font-family:'Barlow',sans-serif; font-weight:500; font-size:.95rem; letter-spacing:0; vertical-align:middle; }
.dlg-facts b { color:#fff; font-weight:600; }
.st-key-clip_video { border-radius:12px; overflow:hidden; background:#000; border:1px solid var(--line); box-shadow:0 8px 26px rgba(0,0,0,.4); }
.st-key-clip_video video { display:block; width:100%; aspect-ratio:16/9; max-height:calc(100vh - 260px); object-fit:contain; background:#000; }
.ap-head { display:flex; align-items:center; gap:.6rem; font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:1.25rem;
  letter-spacing:.1em; text-transform:uppercase; color:#fff; margin:0 0 .5rem 0; }
.ap-bar { width:5px; height:1.2em; border-radius:3px; background:var(--c); }
.st-key-clip_analysis { max-height:calc(100vh - 250px); min-height:calc(100vh - 250px); overflow-y:auto; background:#121a29 !important; border-color:var(--line) !important;
  border-radius:12px !important; padding:.4rem .5rem; scrollbar-width:thin; scrollbar-color:#34425f transparent; }
.st-key-clip_analysis p, .st-key-clip_analysis li { line-height:1.65; font-size:1.02rem; color:#D5DCEA; }
.ap-card { --bg: color-mix(in srgb, var(--c) 9%, #121a29); position:relative; border:1px solid color-mix(in srgb, var(--c) 28%, #1f2a42); border-left:4px solid var(--c);
  background:linear-gradient(135deg, var(--bg) 0%, #121a29 78%); border-radius:4px 12px 12px 4px; padding:.75rem 1rem .6rem; margin:.35rem 0 .8rem 0; box-shadow:0 2px 14px rgba(0,0,0,.22); }
.ap-card-h { display:flex; align-items:center; gap:.6rem; font-family:'Barlow Condensed',sans-serif; font-weight:700; letter-spacing:.11em; text-transform:uppercase; font-size:1.08rem; color:var(--c); margin-bottom:.4rem; }
.ap-card-i { display:inline-flex; align-items:center; justify-content:center; width:1.45rem; height:1.45rem; border-radius:50%; font-family:'Barlow',sans-serif; font-weight:700; font-size:.82rem;
  color:#0E1420; background:var(--c); }
.ap-card-b p { margin:0 0 .5rem 0; line-height:1.62; font-size:1.02rem; color:#D5DCEA; }
.ap-verdict .ap-card-b p { color:#fff; font-weight:500; font-size:1.06rem; }
.ap-card-b b { color:#fff; font-weight:600; }
.ap-card-b ul, .ap-card-b ol { list-style:none; margin:.1rem 0 .35rem 0; padding:0; counter-reset:apn; }
.ap-card-b li { position:relative; padding:.5rem .7rem .5rem 2.5rem; margin:0 0 .4rem 0; border-radius:8px; background:rgba(255,255,255,.035); line-height:1.55; font-size:1rem; color:#D5DCEA; }
.ap-card-b li::before { counter-increment:apn; content:counter(apn); position:absolute; left:.6rem; top:.55rem; width:1.35rem; height:1.35rem; border-radius:6px; text-align:center; line-height:1.35rem;
  font-size:.8rem; font-weight:700; color:#0E1420; background:var(--c); }
.ap-card-b ul li::before { content:""; width:.5rem; height:.5rem; border-radius:50%; left:.85rem; top:.95rem; }
.ap-sec { font-family:'Barlow Condensed',sans-serif; font-weight:700; letter-spacing:.09em; text-transform:uppercase; font-size:1.05rem; color:var(--c, #8D9AB3); }
.ap-sec { display:flex; align-items:center; gap:.55rem; color:var(--muted); margin:1rem 0 .15rem 0; padding-top:.7rem; border-top:1px solid #1f2a42; }
.ap-n { display:inline-flex; align-items:center; justify-content:center; width:1.35rem; height:1.35rem; border-radius:6px; background:#1b2540; color:#9fb3d6; font-size:.8rem; }
@media (max-width: 900px) { .st-key-clip_analysis { max-height:none; min-height:0; } }

/* clip cards */
.clip-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1.45rem;
  line-height: 1.1; margin: .55rem 0 .25rem 0; }
.star-mark { color: #FFD24D; margin-left: .35rem; font-size: .9em; }
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
.stbl tr.grp td { border-top: 2px solid #34425f; }
.stbl tr.sub td { border-top: 1px solid #2a3753; }
.stbl tr.tot td { background: rgba(110,168,254,.08); color: #fff; font-weight: 600; }
.stbl td.ind { padding-left: 1.5rem; color: #C3CCDD; }
.stbl td.ind::before { content: "– "; color: #4a5b80; }
.stbl td.bar { white-space: nowrap; }
.stbl .bv { display: inline-block; min-width: 3.1em; text-align: right; }
.stbl .bt { display: inline-block; width: 84px; height: 7px; margin-left: .6rem; vertical-align: middle; background: #1b2540; border-radius: 4px; overflow: hidden; }
.stbl .bt i { display: block; height: 100%; background: var(--bc, #6EA8FE); border-radius: 4px; }
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
.st-key-hero_wrap { padding:1.25rem 1.8rem; margin:0 0 1.2rem 0; border:1px solid var(--line); border-radius:16px; position:relative; overflow:hidden;
  background: radial-gradient(120% 140% at 0% 0%, rgba(0,77,152,.40) 0%, rgba(21,29,46,0) 55%), radial-gradient(120% 140% at 100% 100%, rgba(203,53,36,.34) 0%, rgba(21,29,46,0) 55%), #131B2B;
  box-shadow: 0 6px 22px rgba(0,0,0,.28); }
.st-key-hero_wrap::before { content:""; position:absolute; left:0; right:0; top:0; height:3px; background:linear-gradient(90deg, #004D98 0%, #A50044 22%, #D4A93A 50%, #CB3524 78%, #F2F2F2 100%); }
.st-key-hero_wrap [data-testid="stColumn"]:last-child, .st-key-hero_wrap [data-testid="column"]:last-child { border-left:1px solid rgba(255,255,255,.10); padding-left:1.2rem; }
.hero { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:1.5rem; margin:0; }
.hero-badge { padding-right:1.5rem; border-right:1px solid rgba(255,255,255,.10); }
.hero-badge svg { display:block; width:72px; height:86px; filter:drop-shadow(0 4px 10px rgba(0,0,0,.5)); }
.hero-eyebrow { font-size:.76rem; letter-spacing:.24em; text-transform:uppercase; color:#9fb3d6; font-weight:600; }
.hero-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:2.9rem; line-height:1.05; letter-spacing:.015em; margin:.2rem 0 .3rem 0; color:#fff; text-transform:uppercase; }
.hero-title i { font-style:normal; color:#D4A93A; font-weight:500; margin:0 .6rem; font-size:.62em; letter-spacing:.12em; vertical-align:.18em; }
.hero-sub { color:#b6c2da; font-size:1rem; line-height:1.45; max-width:46rem; }
.hero-vs { display:flex; align-items:center; gap:1rem; padding-left:1.5rem; border-left:1px solid rgba(255,255,255,.10); }
.hero-team { text-align:center; }
.hero-team-n { margin-top:.3rem; font-family:'Barlow Condensed',sans-serif; font-weight:600; letter-spacing:.1em; font-size:.95rem; color:#dfe7f5; text-transform:uppercase; }
.hero-vs-t { color:#8D9AB3; font-size:.72rem; letter-spacing:.22em; text-transform:uppercase; border:1px solid rgba(255,255,255,.16); border-radius:999px; padding:.28rem .55rem; }
.tcrest { width:48px; height:57px; margin:0 auto; }
.tcrest svg { display:block; width:48px; height:57px; filter:drop-shadow(0 3px 7px rgba(0,0,0,.45)); }
.tcrest-img { margin:0 auto; width:58px; height:62px; }
/* your own badge images: the backdrop (checkerboard / white) is removed when they are loaded, so the team crests sit directly on the card;
   the football badge has dark lines, so it keeps a soft white tile */
img.icon-img { display:block; box-sizing:border-box; object-fit:contain; background:transparent; filter:drop-shadow(0 3px 8px rgba(0,0,0,.55)); }
.hero-badge img.icon-img { width:86px; height:86px; background:#fff; border-radius:16px; padding:8px; filter:none; box-shadow:0 3px 12px rgba(0,0,0,.45); }
.tcrest-img img.icon-img { width:58px; height:62px; }
@media (max-width: 820px) { .hero { grid-template-columns:auto 1fr; } .hero-vs { grid-column:1 / -1; justify-content:center; border-left:0; padding-left:0; } .hero-title { font-size:2.1rem; } .hero-badge { padding-right:1rem; } }

/* dark / light switch: one quiet pill button, shows the mode you can switch to */
.st-key-theme_btn { display:flex; justify-content:center; }
.st-key-theme_btn button { border:1px solid rgba(255,255,255,.16) !important; background:rgba(255,255,255,.04) !important; color:#dfe7f5 !important; border-radius:999px !important;
  min-height:2.3rem !important; padding:.3rem 1.1rem !important; width:auto !important; transition:background .15s ease, border-color .15s ease; }
.st-key-theme_btn button p { margin:0 !important; font-size:.78rem !important; font-weight:600 !important; letter-spacing:.14em; text-transform:uppercase; color:inherit !important; }
.st-key-theme_btn button:hover { border-color:#6EA8FE !important; background:rgba(110,168,254,.12) !important; color:#fff !important; }
.st-key-theme_btn button:focus-visible { outline:2px solid #6EA8FE !important; outline-offset:2px; }
.st-key-theme_btn [data-testid="stIconMaterial"] { color:#D4A93A !important; font-size:1.15rem !important; }
</style>
"""


HIDE_BAR_CSS = """
<style>
/* Streamlit's own top bar (Deploy, Stop, menu, running indicator) and footer are hidden; the page starts higher because the bar no longer takes space */
[data-testid="stHeader"], header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stDeployButton"], [data-testid="stMainMenu"], [data-testid="stStatusWidget"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; visibility: hidden !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.6rem !important; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if config.HIDE_STREAMLIT_BAR:
        st.markdown(HIDE_BAR_CSS, unsafe_allow_html=True)


# Light mode: the dark design is inverted as a whole (the original is dark); photos, video, badges and team colours are turned
# back so they keep their real colours.
LIGHT_CSS = """
<style>
html { filter: invert(1) hue-rotate(180deg); }
img, video, canvas, .crest, .tcrest, .hero-badge svg, .chip-team, .vs-track { filter: invert(1) hue-rotate(180deg); }
/* the badge images have their own (more specific) filter in dark mode; in light mode they must be turned back too, or their colours stay inverted */
img.icon-img, .hero-badge img.icon-img { filter: invert(1) hue-rotate(180deg) !important; }
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
