"""
Dark / light theme handling.

Streamlit has no public API for a true runtime theme switch, so this
overrides Streamlit's OWN theme CSS variables (the same ones config.toml
compiles into: --primary-color, --background-color,
--secondary-background-color, --text-color) rather than just re-styling
a handful of top-level containers. That matters because most native
widgets (buttons, selectbox, expander, dataframe, inputs) pull their
colors from those variables internally -- overriding only `.stApp`
leaves all of them still following config.toml's fixed `base = "dark"`,
which is exactly why light mode was unreadable: the page background
flipped to white but buttons/inputs/expanders kept dark-theme colors.

A second layer of explicit selectors below covers the specific widgets
whose contrast most commonly breaks even after the variables are set
(alerts, code blocks, dataframe header, disabled text) since a few
components don't fully key off the shared variables.

Charts read `plotly_template()` so Plotly figures match whichever mode
is active.
"""

import streamlit as st

_DARK = {
    "bg": "#0E1117",
    "bg_secondary": "#161B22",
    "card": "#1B212B",
    "text": "#E6E8EB",
    "text_muted": "#9AA4B2",
    "border": "#2A313C",
    "accent": "#3E7A4E",
    "input_bg": "#1B212B",
}

_LIGHT = {
    "bg": "#FFFFFF",
    "bg_secondary": "#F5F7FA",
    "card": "#FFFFFF",
    "text": "#1B2A38",
    "text_muted": "#5A6B7A",
    "border": "#D7DEE6",
    "accent": "#2F5D8A",
    "input_bg": "#FFFFFF",
}


def palette(mode: str) -> dict:
    return _DARK if mode == "dark" else _LIGHT


def plotly_template(mode: str) -> str:
    return "plotly_dark" if mode == "dark" else "plotly_white"


def inject_css(mode: str) -> None:
    c = palette(mode)
    st.markdown(
        f"""
        <style>
        /* --- Streamlit's own theme variables: drives most native widgets automatically --- */
        :root, .stApp {{
            --primary-color: {c['accent']};
            --background-color: {c['bg']};
            --secondary-background-color: {c['bg_secondary']};
            --text-color: {c['text']};
        }}

        .stApp {{
            background-color: {c['bg']};
            color: {c['text']};
        }}
        .stApp, .stApp p, .stApp span, .stApp label, .stApp li {{
            color: {c['text']};
        }}

        section[data-testid="stSidebar"] {{
            background-color: {c['bg_secondary']};
            border-right: 1px solid {c['border']};
        }}
        section[data-testid="stSidebar"] * {{
            color: {c['text']} !important;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: {c['text']} !important;
        }}

        /* --- metric cards --- */
        div[data-testid="stMetric"] {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 10px;
            padding: 14px 16px;
        }}
        div[data-testid="stMetricLabel"] {{ color: {c['text_muted']} !important; }}
        div[data-testid="stMetricValue"] {{ color: {c['text']} !important; }}

        /* --- inputs: text_input, selectbox, number_input --- */
        .stTextInput input, .stNumberInput input, div[data-baseweb="select"] > div {{
            background-color: {c['input_bg']} !important;
            color: {c['text']} !important;
            border-color: {c['border']} !important;
        }}
        div[data-baseweb="popover"] * {{
            color: {c['text']} !important;
        }}
        div[data-baseweb="popover"] {{
            background-color: {c['card']} !important;
        }}

        /* --- buttons --- */
        .stButton button, .stDownloadButton button {{
            background-color: {c['card']};
            color: {c['text']} !important;
            border: 1px solid {c['border']};
        }}
        .stButton button:hover, .stDownloadButton button:hover {{
            border-color: {c['accent']};
            color: {c['accent']} !important;
        }}

        /* --- radio / toggle labels --- */
        .stRadio label, .stToggle label, .stCheckbox label {{
            color: {c['text']} !important;
        }}

        /* --- expander --- */
        details[data-testid="stExpander"] {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        details[data-testid="stExpander"] summary {{
            color: {c['text']} !important;
        }}

        /* --- dataframe / table --- */
        div[data-testid="stDataFrame"] {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}

        /* --- tabs --- */
        .stTabs [data-baseweb="tab"] {{ color: {c['text_muted']} !important; }}
        .stTabs [aria-selected="true"] {{ color: {c['accent']} !important; }}

        /* --- captions / muted text --- */
        .stCaption, [data-testid="stCaptionContainer"] {{
            color: {c['text_muted']} !important;
        }}
        .section-caption {{
            color: {c['text_muted']};
            font-size: 0.9rem;
            margin-top: -6px;
            margin-bottom: 14px;
        }}

        /* --- custom card helper, used by the connect form on the home page --- */
        .card {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 14px;
        }}

        /* --- home page hero --- */
        .hero-wrap {{
            text-align: center;
            padding: 48px 20px 28px 20px;
        }}
        .hero-badge {{
            width: 72px;
            height: 72px;
            margin: 0 auto 18px auto;
            border-radius: 20px;
            background: linear-gradient(135deg, {c['accent']}, {c['accent']}CC);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.2rem;
        }}
        .hero-title {{
            font-size: 2rem;
            font-weight: 800;
            color: {c['text']};
            margin-bottom: 8px;
        }}
        .hero-subtitle {{
            font-size: 1.05rem;
            color: {c['text_muted']};
            margin-bottom: 14px;
        }}
        .hero-desc {{
            font-size: 0.9rem;
            color: {c['text_muted']};
            max-width: 560px;
            margin: 0 auto;
            line-height: 1.5;
        }}

        /* --- checklist rows on the loader page --- */
        .check-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 8px;
            font-size: 0.92rem;
        }}
        .check-row .icon {{ font-size: 1.05rem; }}
        .check-row .label {{ color: {c['text']}; font-weight: 500; flex: 1; }}
        .check-row .path {{ color: {c['text_muted']}; font-size: 0.76rem; font-family: monospace; }}
        .check-row.pending {{ opacity: 0.55; }}
        .check-row.ok {{ border-color: rgba(29, 158, 117, 0.45); }}
        .check-row.warn {{ border-color: rgba(217, 160, 44, 0.45); }}
        .check-row.fail {{ border-color: rgba(214, 69, 69, 0.55); }}

        /* --- centered path caption on the loader page, shown under "Connecting to…" --- */
        .check-row-path-only {{
            display: inline-block;
            color: {c['text_muted']};
            font-size: 0.78rem;
            font-family: monospace;
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 4px 10px;
        }}

        /* --- sidebar branding block --- */
        .sidebar-brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 4px 2px 18px 2px;
        }}
        .brand-badge {{
            width: 42px;
            height: 42px;
            min-width: 42px;
            border-radius: 11px;
            background: linear-gradient(135deg, {c['accent']}, {c['accent']}CC);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
        }}
        .brand-title {{
            font-weight: 700;
            font-size: 1.05rem;
            color: {c['text']};
            line-height: 1.2;
        }}
        .brand-subtitle {{
            font-size: 0.76rem;
            color: {c['text_muted']};
            line-height: 1.2;
        }}

        /* --- sidebar section labels --- */
        .nav-section-label {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: {c['text_muted']};
            text-transform: uppercase;
            margin: 4px 2px 8px 2px;
        }}

        /* --- nav buttons: left-aligned, full-width, active = primary (accent) --- */
        section[data-testid="stSidebar"] .stButton button {{
            text-align: left;
            justify-content: flex-start;
            font-weight: 500;
            border-radius: 8px;
            padding: 8px 12px;
            margin-bottom: 2px;
        }}
        section[data-testid="stSidebar"] .stButton button p {{
            text-align: left;
        }}
        section[data-testid="stSidebar"] .stButton button[kind="secondary"] {{
            background-color: transparent;
            border: 1px solid transparent;
            color: {c['text_muted']} !important;
        }}
        section[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {{
            background-color: {c['card']};
            border-color: {c['border']};
            color: {c['text']} !important;
        }}
        section[data-testid="stSidebar"] .stButton button[kind="primary"] {{
            background-color: {c['accent']};
            border: 1px solid {c['accent']};
            color: #FFFFFF !important;
        }}

        /* --- status pill (data-source connection) --- */
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 999px;
            margin: 2px 0 10px 0;
        }}
        .status-pill.ok {{
            background: rgba(29, 158, 117, 0.14);
            color: #1D9E75;
            border: 1px solid rgba(29, 158, 117, 0.35);
        }}
        .status-pill.warn {{
            background: rgba(217, 160, 44, 0.14);
            color: #D9A02C;
            border: 1px solid rgba(217, 160, 44, 0.35);
        }}

        /* --- thin divider matching the palette (replaces default st.divider look) --- */
        .sidebar-hr {{
            border: none;
            border-top: 1px solid {c['border']};
            margin: 14px 0;
        }}

        /* --- sidebar footer --- */
        .sidebar-footer {{
            font-size: 0.72rem;
            color: {c['text_muted']};
            text-align: center;
            padding-top: 10px;
        }}

        /* --- native Streamlit header bar (deploy button / menu) --- */
        header[data-testid="stHeader"] {{
            background-color: {c['bg']};
            border-bottom: 1px solid {c['border']};
        }}
        header[data-testid="stHeader"] svg {{
            fill: {c['text_muted']};
        }}
        header[data-testid="stHeader"] button:hover svg {{
            fill: {c['accent']};
        }}
        /* Deploy button isn't relevant for a local analysis tool -- hidden.
           Remove these two rules to bring it back if you ever do publish this. */
        [data-testid="stAppDeployButton"],
        [data-testid="stDeployButton"],
        .stDeployButton,
        button[title="Deploy this app"] {{
            display: none !important;
        }}

        /* --- custom breadcrumb bar just under the native header --- */
        .app-topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 2px 0 16px 0;
            margin-top: -8px;
            margin-bottom: 8px;
            border-bottom: 1px solid {c['border']};
        }}
        .app-topbar-crumb {{
            font-size: 0.88rem;
            color: {c['text_muted']};
        }}
        .app-topbar-crumb .crumb-brand {{
            color: {c['text']};
            font-weight: 600;
        }}
        .app-topbar-crumb .crumb-arrow {{
            margin: 0 6px;
            opacity: 0.6;
        }}
        .app-topbar-crumb .crumb-current {{
            color: {c['accent']};
            font-weight: 600;
        }}
        .app-topbar-mode {{
            font-size: 0.78rem;
            color: {c['text_muted']};
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* --- loading spinner: match brand accent instead of Streamlit's default --- */
        .stSpinner > div {{
            border-top-color: {c['accent']} !important;
        }}
        .stSpinner p {{
            color: {c['text_muted']} !important;
        }}

        /* --- code blocks --- */
        code, .stCodeBlock, pre {{
            background-color: {c['bg_secondary']} !important;
            color: {c['text']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )