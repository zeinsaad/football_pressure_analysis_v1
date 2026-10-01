"""
Section 5 — Output video.
Plays the video your pipeline's own render step already produced
(render.RenderPipeline.render(), main.py Step 9) — auto-located via
paths.OUTPUT_VIDEO_PATH. This page doesn't process or re-annotate
anything; it just finds and displays the existing file.
"""

import os

import streamlit as st

from modules import pipeline_paths


def render(data: dict, mode: str) -> None:
    st.header("Output video")
    st.markdown(
        '<div class="section-caption">The annotated video your pipeline already rendered.</div>',
        unsafe_allow_html=True,
    )

    pipeline_root = st.session_state.get("pipeline_root", "")
    auto_path = pipeline_paths.get("OUTPUT_VIDEO_PATH", None, extra_root=pipeline_root)

    source = st.radio("Source", ["Auto-detect from paths.py", "Enter a path manually"], horizontal=True)

    video_path = None
    if source == "Auto-detect from paths.py":
        if auto_path:
            video_path = auto_path
        else:
            st.warning(
                "`OUTPUT_VIDEO_PATH` isn't defined in your paths.py (or paths.py isn't importable). "
                "Add that constant where `render.RenderPipeline.render()` writes its output, or enter "
                "the path manually."
            )
    else:
        video_path = st.text_input("Path to the rendered video (.mp4)", value=auto_path or "")

    if not video_path:
        return

    if not os.path.exists(video_path):
        st.error(f"No file found at `{video_path}`.")
        return

    st.caption(f"Source: `{video_path}`")
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    st.video(video_bytes)
    st.download_button(
        "Download video",
        data=video_bytes,
        file_name=os.path.basename(video_path),
        mime="video/mp4",
    )
