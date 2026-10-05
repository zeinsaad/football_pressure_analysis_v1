"""
Team Pressure Analysis — Streamlit UI
Entry point: wires together the sidebar navigation, the dark/light toggle,
and hands off to each section's render() function in modules/.

Run with:  streamlit run app.py
Data:      auto-detected from your pipeline's paths.py when it's importable
           (see modules/pipeline_paths.py); otherwise set the path manually
           in the sidebar, or place pressure_analysis_export.json in data/.
"""

import os

import streamlit as st

from modules import data_loader, theme, overview, heatmap, timeline, passmap, video, llm_report, pipeline_paths

# hardcoded as a safety net -- normally overridden by paths.UI_EXPORT_PATH once
# pipeline_paths.py successfully imports your real paths.py
FALLBACK_DATA_PATH = (
    os.path.join(pipeline_paths.PIPELINE_ROOT, "barca_atletico_first_half", "cache", "pressure_analysis_export.json")
    if pipeline_paths.PIPELINE_ROOT
    else "data/pressure_analysis_export.json"
)

PAGES = {
    "Overview": overview,
    "LLM report": llm_report,
    "Pressure heatmap": heatmap,
    "Match timeline": timeline,
    "Pass map & outcomes": passmap,
    "Output video": video,
}

NAV_ICONS = {
    "Overview": "📊",
    "LLM report": "📝",
    "Pressure heatmap": "🔥",
    "Match timeline": "⏱️",
    "Pass map & outcomes": "🎯",
    "Output video": "🎬",
}


def _hr() -> None:
    st.markdown('<hr class="sidebar-hr">', unsafe_allow_html=True)


def render_sidebar() -> str:
    with st.sidebar:
        # --- branding ---
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="brand-badge">⚽</div>
                <div>
                    <div class="brand-title">Pressure Analysis</div>
                    <div class="brand-subtitle">Computer-vision pressing metrics</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --- navigation ---
        st.markdown('<div class="nav-section-label">Sections</div>', unsafe_allow_html=True)
        for name in PAGES:
            icon = NAV_ICONS.get(name, "•")
            is_active = st.session_state.page_name == name
            if st.button(
                f"{icon}   {name}",
                key=f"nav_{name}",
                width="stretch",
                type="primary" if is_active else "secondary",
            ):
                if not is_active:
                    st.session_state.page_name = name
                    st.rerun()
        page_name = st.session_state.page_name

        _hr()

        # --- appearance ---
        st.markdown('<div class="nav-section-label">Appearance</div>', unsafe_allow_html=True)
        is_dark = st.toggle(
            "🌙 Dark mode" if st.session_state.theme_mode == "dark" else "☀️ Light mode",
            value=(st.session_state.theme_mode == "dark"),
        )
        new_mode = "dark" if is_dark else "light"
        if new_mode != st.session_state.theme_mode:
            st.session_state.theme_mode = new_mode
            st.rerun()

        _hr()

        # --- data source ---
        st.markdown('<div class="nav-section-label">Data source</div>', unsafe_allow_html=True)
        pstatus = pipeline_paths.status(extra_root=st.session_state.pipeline_root)
        if pstatus["importable"]:
            st.markdown('<div class="status-pill ok">● paths.py connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-pill warn">● Manual mode</div>', unsafe_allow_html=True)

        with st.expander("Settings", expanded=not pstatus["importable"]):
            root_input = st.text_input(
                "Pipeline root (folder containing paths.py)",
                value=st.session_state.pipeline_root,
                help="Only needed if this app isn't run from inside your pipeline project.",
            )
            st.session_state.pipeline_root = root_input

            pstatus = pipeline_paths.status(extra_root=root_input)
            if pstatus["missing"]:
                st.caption("Not defined in paths.py yet (using fallbacks): " + ", ".join(pstatus["missing"]))

            default_data_path = pipeline_paths.get("UI_EXPORT_PATH", FALLBACK_DATA_PATH, extra_root=root_input)
            st.session_state.data_path = st.text_input("pressure_analysis_export.json path", value=default_data_path)

        st.markdown('<div class="sidebar-footer">Team Pressure Analysis · v1.0</div>', unsafe_allow_html=True)

    return page_name


def render_topbar(page_name: str) -> None:
    mode_label = "🌙 Dark" if st.session_state.theme_mode == "dark" else "☀️ Light"
    st.markdown(
        f"""
        <div class="app-topbar">
            <div class="app-topbar-crumb">
                <span class="crumb-brand">⚽ Pressure Analysis</span>
                <span class="crumb-arrow">›</span>
                <span class="crumb-current">{page_name}</span>
            </div>
            <div class="app-topbar-mode">{mode_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Team Pressure Analysis",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "dark"
    if "pipeline_root" not in st.session_state:
        st.session_state.pipeline_root = pipeline_paths.PIPELINE_ROOT
    if "page_name" not in st.session_state:
        st.session_state.page_name = next(iter(PAGES))
    if "data_path" not in st.session_state:
        st.session_state.data_path = pipeline_paths.get(
            "UI_EXPORT_PATH", FALLBACK_DATA_PATH, extra_root=st.session_state.pipeline_root
        )

    page_name = render_sidebar()
    theme.inject_css(st.session_state.theme_mode)
    render_topbar(page_name)

    data = data_loader.load_export(st.session_state.data_path)
    if data is None:
        st.error(
            f"Couldn't find or parse **{st.session_state.data_path}**.\n\n"
            "Run the notebook's Section 20 export cell first (it writes to `paths.UI_EXPORT_PATH` "
            "if that's defined, otherwise `pressure_analysis_export.json`), then check the path in "
            "the sidebar's **Data source** settings."
        )
        st.stop()

    with st.spinner(f"Loading {page_name}…"):
        PAGES[page_name].render(data, st.session_state.theme_mode)


if __name__ == "__main__":
    main()