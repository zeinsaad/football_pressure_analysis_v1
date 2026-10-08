"""Tab 1: the full annotated match video, always played at its best quality (original size)."""
import streamlit as st

import config
from core import media


def render() -> None:
    src = config.MATCH_VIDEO
    if not src.exists():
        st.error(f"Video not found: `{src}`. Check `MATCH_VIDEO` in config.py.")
        return

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
