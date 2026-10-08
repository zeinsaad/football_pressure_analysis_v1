"""Tab 4: the tactical conclusions text file, laid out as a readable report."""
from __future__ import annotations

import datetime as dt
import html

import streamlit as st

import config
from core import conclusions
from ui.compat import STRETCH


def render() -> None:
    doc, path = conclusions.load()
    if doc is None:
        found = path is not None and path.exists()
        st.markdown('<div class="empty">' + ("The conclusions file is empty or could not be read." if found else
                    "No conclusions file found yet.") + f'<br>Expected file: <code>{html.escape(str(path))}</code><br>'
                    "Check <code>CONCLUSIONS_FILE</code> in config.py.</div>", unsafe_allow_html=True)
        return

    when = dt.datetime.fromtimestamp(doc.mtime).strftime("%d %b %Y, %H:%M")
    head, side = st.columns([5, 1.4], vertical_alignment="center")
    with head:
        st.markdown(f'<div class="concl-title">{html.escape(doc.title or "Tactical conclusions")}</div>'
                    f'<div class="concl-meta">{html.escape(doc.path.name)} &middot; updated {when}</div>', unsafe_allow_html=True)
    with side:
        if st.button("Reload file", key="concl_reload", **STRETCH):
            conclusions._load.clear()
            st.rerun()

    if not doc.sections:                                              # no headings recognised: show the text as it is
        with st.container(border=True):
            st.markdown(conclusions.to_markdown(doc.raw))
    elif doc.intro:
        with st.container(border=True):
            st.markdown(conclusions.to_markdown(doc.intro))
    for s in doc.sections:
        with st.container(border=True):
            st.markdown(f'<div class="sec-title" style="margin-bottom:.4rem">{html.escape(s.title)}</div>', unsafe_allow_html=True)
            if s.body:
                st.markdown(conclusions.to_markdown(s.body))

    st.download_button("Download the text file", doc.raw, file_name=doc.path.name, mime="text/plain")
