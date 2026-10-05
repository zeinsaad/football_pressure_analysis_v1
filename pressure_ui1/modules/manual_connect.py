"""
Manual connect page -- the FALLBACK screen, reached only from the error
page ("auto-connect couldn't find your pipeline") or the sidebar's
"Start over". Not shown on first load anymore -- see modules/home.py for
that (the video-upload landing screen) and modules/checks.py for the
loader that auto-connects afterward.

Two ways in here: point at the pipeline folder (paths.py drives
auto-detection, as everywhere else in this app), or upload the export
files directly if you don't have local access to the pipeline.
"""

import os
import tempfile

import streamlit as st

from modules import pipeline_paths


def _save_upload(uploaded_file) -> str:
    """Persist an uploaded file to a temp path and return that path."""
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
            <div class="hero-title">Connect your pipeline</div>
            <div class="hero-subtitle">We couldn't auto-connect — point the app at your data manually.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        tab_connect, tab_upload = st.tabs(["🔗  Connect pipeline folder", "⬆️  Upload files manually"])

        with tab_connect:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.caption(
                "Point this at the folder containing your pipeline's `paths.py`. The app reads "
                "PLAYER_FRAME_TABLE_CACHE_PATH, BALL_FRAME_TABLE_CACHE_PATH, UI_EXPORT_PATH, "
                "LLM_REPORT_PATH, and OUTPUT_VIDEO_PATH from it directly."
            )
            root_input = st.text_input(
                "Pipeline root folder",
                value=st.session_state.get("pipeline_root", pipeline_paths.PIPELINE_ROOT),
                key="manual_root_input",
            )
            if st.button("Analyze match →", type="primary", width="stretch", key="manual_connect_btn"):
                st.session_state.pipeline_root = root_input
                st.session_state.input_mode = "pipeline"
                st.session_state.app_stage = "checking"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with tab_upload:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.caption(
                "Upload the files your notebooks already produced. The pressure metrics export "
                "is required; the report and video are optional."
            )
            export_file = st.file_uploader(
                "pressure_analysis_export.json (required)", type=["json"], key="up_export"
            )
            report_file = st.file_uploader("Tactical report (optional, .md)", type=["md"], key="up_report")
            video_file = st.file_uploader("Rendered video (optional, .mp4)", type=["mp4"], key="up_video")

            if st.button("Analyze match →", type="primary", width="stretch", key="manual_upload_btn"):
                if export_file is None:
                    st.error("The pressure metrics export (.json) is required.")
                else:
                    st.session_state.uploaded_paths = {
                        "UI_EXPORT_PATH": _save_upload(export_file),
                        "LLM_REPORT_PATH": _save_upload(report_file) if report_file else None,
                        "OUTPUT_VIDEO_PATH": _save_upload(video_file) if video_file else None,
                    }
                    st.session_state.input_mode = "upload"
                    st.session_state.app_stage = "checking"
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
