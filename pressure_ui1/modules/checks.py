"""
Checklist / loader page -- shown between the video-upload home page and
the normal multi-page app. Auto-connects to the pipeline (or the files
uploaded manually via modules.manual_connect) and ticks through each
required cache by NAME ONLY -- no path or root is ever printed here, by
design, so this stays a clean product-feeling loader rather than a debug
screen. If a required cache is missing, it hands off to the error page
with one clear instruction, still with no paths shown.

Each row holds for at least MIN_STEP_SEC before ticking, regardless of
how fast the actual existence check resolves -- purely so the loader
reads as a real multi-stage check rather than a instant flash.
"""

import os
import time

import streamlit as st

from modules import pipeline_paths

# (display name, paths.py attribute, required-to-open-the-app)
CHECK_ITEMS = [
    ("Detection cache", "PLAYER_FRAME_TABLE_CACHE_PATH", True),
    ("Ball tracking cache", "BALL_FRAME_TABLE_CACHE_PATH", True),
    ("Pressure metrics", "UI_EXPORT_PATH", True),
    ("Tactical report", "LLM_REPORT_PATH", False),
    ("Output video", "OUTPUT_VIDEO_PATH", False),
]

MIN_STEP_SEC = 2.0  # each cache holds on "checking" for at least this long before ticking


def _resolve_from_pipeline(root: str) -> list[dict]:
    results = []
    for label, attr, required in CHECK_ITEMS:
        path = pipeline_paths.get(attr, None, extra_root=root)
        results.append({"label": label, "attr": attr, "path": path, "required": required,
                         "exists": bool(path) and os.path.exists(path)})
    return results


def _resolve_from_upload() -> list[dict]:
    # uploaded mode has no detection/tracking caches of its own -- those two checks are
    # skipped entirely rather than shown as failing, since they're not applicable here
    uploaded = st.session_state.get("uploaded_paths", {})
    results = []
    for label, attr, required in CHECK_ITEMS:
        if attr not in uploaded:
            continue
        path = uploaded.get(attr)
        results.append({"label": label, "attr": attr, "path": path, "required": required,
                         "exists": bool(path) and os.path.exists(path)})
    return results


def render() -> None:
    st.markdown(
        """
        <div class="hero-wrap" style="padding-top:56px; padding-bottom:0px;">
            <div class="hero-badge">⚽</div>
            <div class="hero-title">Team Pressure Analysis</div>
            <div class="hero-subtitle">Computer-vision pressing metrics, turned into a full tactical breakdown.</div>
        </div>
        <div style="text-align:center; font-weight:600; margin-bottom:22px;">Analyzing your match…</div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        if st.session_state.get("input_mode") == "upload":
            items = _resolve_from_upload()
        else:
            items = _resolve_from_pipeline(st.session_state.get("pipeline_root", pipeline_paths.PIPELINE_ROOT))

        # render every row as "pending" first, then tick them one at a time in place --
        # each placeholder streams to the browser as soon as it's written, so the
        # time.sleep() calls below produce a real sequential-tick effect in one script run
        placeholders = {}
        for item in items:
            placeholders[item["attr"]] = st.empty()
            placeholders[item["attr"]].markdown(
                f'<div class="check-row pending"><span class="icon">⏳</span>'
                f'<span class="label">{item["label"]}</span></div>',
                unsafe_allow_html=True,
            )

        missing_required = []
        resolved_paths = {}
        for item in items:
            time.sleep(MIN_STEP_SEC)
            resolved_paths[item["attr"]] = item["path"]
            if item["exists"]:
                icon, css = "✅", "ok"
            elif item["required"]:
                icon, css = "❌", "fail"
                missing_required.append(item)
            else:
                icon, css = "⚠️", "warn"
            placeholders[item["attr"]].markdown(
                f'<div class="check-row {css}"><span class="icon">{icon}</span>'
                f'<span class="label">{item["label"]}</span></div>',
                unsafe_allow_html=True,
            )

        time.sleep(0.6)  # brief pause so the last tick is readable before we move on

        st.session_state.resolved_paths = resolved_paths
        if missing_required:
            st.session_state.missing_required = missing_required
            st.session_state.app_stage = "error"
        else:
            st.session_state.data_path = resolved_paths.get("UI_EXPORT_PATH")
            st.session_state.app_stage = "ready"
        st.rerun()


def render_error() -> None:
    st.markdown(
        """
        <div class="hero-wrap" style="padding-top:56px; padding-bottom:8px;">
            <div class="hero-badge">⚠️</div>
            <div class="hero-title" style="font-size:1.5rem;">Pipeline output not found</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.error(
            "**Please run `main.py` — the pipeline cache doesn't exist yet.**\n\n"
            "The following required item(s) weren't found. Run the pipeline (or the notebook "
            "section that writes them) first, then come back and try again."
        )
        for item in st.session_state.get("missing_required", []):
            st.markdown(
                f'<div class="check-row fail"><span class="icon">❌</span>'
                f'<span class="label">{item["label"]}</span></div>',
                unsafe_allow_html=True,
            )

        st.write("")
        if st.button("Change pipeline folder or upload files instead →", type="primary", width="stretch"):
            st.session_state.app_stage = "manual_connect"
            st.rerun()
