"""Barça v Atlético: match video and build-up clips.   Run:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Barça v Atlético analysis", page_icon="⚽", layout="wide")

from tabs import clips_tab, full_match   # noqa: E402  (after set_page_config)
from ui.styles import inject_css          # noqa: E402

inject_css()

# To add a tab later: write tabs/<name>.py with a render() function and add one line here.
TABS = [
    ("Match video", full_match.render),
    ("Build-up clips", clips_tab.render),
]

st.markdown('<p class="app-title">Barça v Atlético, first half</p>'
            '<p class="app-sub">The annotated match and the build-ups that were kept or lost under pressure.</p>',
            unsafe_allow_html=True)

for tab, (_, render) in zip(st.tabs([name for name, _ in TABS]), TABS):
    with tab:
        render()
