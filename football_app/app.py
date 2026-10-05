"""Barça v Atlético: match video, build-up clips, pressing stats and tactical conclusions.   Run:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Barça v Atlético analysis", page_icon="⚽", layout="wide")

from tabs import clips_tab, conclusions_tab, full_match, stats_tab   # noqa: E402  (after set_page_config)
from ui.header import render_header         # noqa: E402
from ui.styles import apply_theme, inject_css   # noqa: E402

inject_css()

# To add a tab later: write tabs/<name>.py with a render() function and add one line here.
TABS = [
    ("Match video", full_match.render),
    ("Build-up clips", clips_tab.render),
    ("Stats", stats_tab.render),
    ("Tactical conclusions", conclusions_tab.render),
]

render_header()
apply_theme()

# Only the selected tab is computed (the others are drawn empty until opened). Older Streamlit versions draw all tabs.
try:
    _tabs, _lazy = st.tabs([name for name, _ in TABS], key="main_tabs", on_change="rerun"), True
except TypeError:
    _tabs, _lazy = st.tabs([name for name, _ in TABS]), False

for tab, (_, render) in zip(_tabs, TABS):
    with tab:
        if not _lazy or getattr(tab, "open", True):
            render()
