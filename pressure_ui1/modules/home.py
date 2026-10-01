"""
Home page -- the FIRST screen the app shows. Asks for the match video,
then hands off straight to modules.checks, which auto-connects to the
pipeline (the known root in pipeline_paths.py, no manual entry needed)
and ticks through each required cache with a loader.

Note: the uploaded video isn't currently read by any section -- every
page in this app is driven entirely by the pipeline's precomputed
exports (the JSON export, the LLM report, the already-rendered output
video). This step exists as the entry gesture and to capture which
match you're pointing the app at; wiring the raw upload into the
pipeline itself would be a separate change if you want it to actually
trigger processing rather than just naming the session.
"""

import os
import tempfile

import streamlit as st


def _save_upload(uploaded_file) -> str:
    tmp_dir = os.path.join(tempfile.gettempdir(), "pressure_ui_uploads")
    os.makedirs(tmp_dir, exist_ok=True)
    dest = os.path.join(tmp_dir, uploaded_file.name)
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def render() -> None:
    st.markdown(
        """
        <div class="hero-wrap">
            <div class="hero-badge">⚽</div>
            <div class="hero-title">Team Pressure Analysis</div>
            <div class="hero-subtitle">Computer-vision pressing metrics, turned into a full tactical breakdown.</div>
            <div class="hero-desc">
                Upload your match video to get started. Once it's in, the app connects to your
                analysis pipeline and checks everything automatically.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        video_file = st.file_uploader(
            "Match video",
            type=["mp4", "mov", "avi", "mkv"],
            key="home_video_upload",
            label_visibility="collapsed",
        )
        clicked = st.button(
            "Start analysis →",
            type="primary",
            width="stretch",
            key="home_start_btn",
            disabled=video_file is None,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if clicked and video_file is not None:
            st.session_state.input_video_name = video_file.name
            st.session_state.input_video_path = _save_upload(video_file)
            st.session_state.input_mode = "pipeline"
            st.session_state.app_stage = "checking"
            st.rerun()
