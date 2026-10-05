"""Tab 1: the full annotated match video, always played at its best quality (original size)."""
import streamlit as st

import config
from core import media


def _stat(col, value: str, label: str) -> None:
    col.markdown(f'<div class="stat-n">{value}</div><div class="stat-l">{label}</div>', unsafe_allow_html=True)


def render() -> None:
    src = config.MATCH_VIDEO
    if not src.exists():
        st.error(f"Video not found: `{src}`. Check `MATCH_VIDEO` in config.py.")
        return

    info = media.info_of(src)
    c = st.columns(4)
    _stat(c[0], media.fmt_duration(info["duration"]), "length")
    _stat(c[1], f'{info["width"]}x{info["height"]}' if info["width"] else "-", "resolution")
    _stat(c[2], str(info["fps"] or "-"), "frames per second")
    size = f'{info["size_mb"] / 1000:.1f} GB' if info["size_mb"] >= 1000 else f'{info["size_mb"]:.0f} MB'
    _stat(c[3], size, "file size")
    st.write("")

    # Browsers only play H.264. If the file is something else it is converted once, at the original size and
    # at the best quality, with no question asked; every later visit plays the saved copy straight away.
    ready = media.cached_web_copy(src, None, config.MATCH_CRF)
    if ready is None:
        bar = st.progress(0.0, text="Preparing the match video at full quality (first time only)...")
        try:
            ready = media.convert_for_browser(src, None, crf=config.MATCH_CRF,
                                              on_progress=lambda f: bar.progress(f, text=f"Preparing the match video at full quality (first time only)... {f:.0%}"))
        except Exception as e:
            bar.empty()
            st.error(str(e))
            return
        bar.empty()

    st.video(str(ready))
    st.caption(f"Playing: `{ready.name}`")
