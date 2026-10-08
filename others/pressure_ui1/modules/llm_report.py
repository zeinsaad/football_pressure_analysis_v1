"""
Section 6 — LLM report.
Displays the tactical narrative report your `team_pressure_llm_report.ipynb`
notebook already generated and saved to disk (paths.LLM_REPORT_PATH) --
this page doesn't call any LLM API itself, it just finds and renders the
existing markdown file, same pattern as modules/video.py for the rendered
video.
"""

import os

import streamlit as st

from modules import pipeline_paths

# matches paths.LLM_REPORT_PATH = "barca_atletico_first_half/cache/barca_atletico_pressing_report.md"
FALLBACK_REPORT_PATH = os.path.join(
    "barca_atletico_first_half", "cache", "barca_atletico_pressing_report.md"
)


def render(data: dict, mode: str) -> None:
    st.header("LLM report")
    st.markdown(
        '<div class="section-caption">The tactical write-up generated from these metrics by Claude — '
        "run <code>team_pressure_llm_report.ipynb</code> to create or refresh it.</div>",
        unsafe_allow_html=True,
    )

    pipeline_root = st.session_state.get("pipeline_root", "")
    # prefer the path the home-page checklist already verified, so this doesn't re-resolve
    # (and potentially disagree with) what the user was shown before the app opened
    auto_path = st.session_state.get("resolved_paths", {}).get("LLM_REPORT_PATH") or pipeline_paths.get(
        "LLM_REPORT_PATH", None, extra_root=pipeline_root
    )

    source = st.radio(
        "Source", ["Auto-detect from paths.py", "Enter a path manually"], horizontal=True, key="llm_report_source"
    )

    report_path = None
    if source == "Auto-detect from paths.py":
        if auto_path:
            report_path = auto_path
        else:
            root = pipeline_root or pipeline_paths.PIPELINE_ROOT
            fallback = os.path.join(root, FALLBACK_REPORT_PATH) if root else FALLBACK_REPORT_PATH
            st.warning(
                "`LLM_REPORT_PATH` isn't defined in your paths.py (or paths.py isn't importable). "
                f"Falling back to `{fallback}` — add that constant to paths.py for auto-detection, "
                "or enter the path manually."
            )
            report_path = fallback
    else:
        report_path = st.text_input(
            "Path to the report (.md)", value=auto_path or os.path.join(pipeline_root, FALLBACK_REPORT_PATH)
        )

    if not report_path:
        return

    if not os.path.exists(report_path):
        st.error(
            f"No file found at `{report_path}`.\n\n"
            "Run `team_pressure_llm_report.ipynb` first — it writes this file after the real "
            "report call (the one after the free dry run and the Haiku smoke test)."
        )
        return

    st.caption(f"Source: `{report_path}`")
    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()

    if not report_text.strip():
        st.warning("The report file exists but is empty.")
        return

    st.markdown(report_text)

    st.divider()
    st.download_button(
        "Download report (.md)",
        data=report_text,
        file_name=os.path.basename(report_path),
        mime="text/markdown",
    )
