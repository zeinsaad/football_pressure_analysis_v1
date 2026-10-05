"""Tab 1: the full annotated match video."""
import streamlit as st

import config
from core import media
from ui.compat import STRETCH


def render() -> None:
    src = config.MATCH_VIDEO
    if not src.exists():
        st.error(f"Video not found: `{src}`. Check `MATCH_VIDEO` in config.py.")
        return

    info = media.info_of(src)
    c = st.columns(4)
    c[0].markdown(f'<div class="stat-n">{media.fmt_duration(info["duration"])}</div><div class="stat-l">length</div>', unsafe_allow_html=True)
    res = f'{info["width"]}x{info["height"]}' if info["width"] else "-"
    c[1].markdown(f'<div class="stat-n">{res}</div><div class="stat-l">resolution</div>', unsafe_allow_html=True)
    c[2].markdown(f'<div class="stat-n">{info["fps"] or "-"}</div><div class="stat-l">frames per second</div>', unsafe_allow_html=True)
    size = f'{info["size_mb"] / 1000:.1f} GB' if info["size_mb"] >= 1000 else f'{info["size_mb"]:.0f} MB'
    c[3].markdown(f'<div class="stat-n">{size}</div><div class="stat-l">file size</div>', unsafe_allow_html=True)
    st.write("")

    height_label = st.session_state.get("match_height_done", list(config.MATCH_HEIGHT_OPTIONS)[0])
    height = config.MATCH_HEIGHT_OPTIONS[height_label]
    ready = media.cached_web_copy(src, height if not media.is_browser_ready(src) else None)

    if ready is None:
        st.info(
            f"This file uses the `{info['codec']}` codec, which browsers cannot play. "
            "Convert it once to H.264 and the result is saved for next time."
        )
        a, b = st.columns([2, 1])
        height_label = a.selectbox("Quality", list(config.MATCH_HEIGHT_OPTIONS), key="match_height")
        height = config.MATCH_HEIGHT_OPTIONS[height_label]
        b.write("")
        b.write("")
        if b.button("Prepare video", type="primary", **STRETCH):
            bar = st.progress(0.0, text="Converting...")
            try:
                media.convert_for_browser(src, height, on_progress=lambda f: bar.progress(f, text=f"Converting... {f:.0%}"))
            except Exception as e:
                bar.empty()
                st.error(str(e))
                return
            st.session_state["match_height_done"] = height_label
            st.rerun()
        return

    st.video(str(ready))
    st.caption(f"Playing: `{ready.name}`")
