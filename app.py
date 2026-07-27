"""
Match analysis dashboard.

Run with:  streamlit run app.py

Structure is deliberately tab-per-stat: each tab reads only the cached
parquet/video artifacts it needs (never the raw per-stage caches), and
adding a new stat later (pressure, possession, formation) means adding one
more render_*_tab() function and one more entry in TABS -- nothing existing
has to change.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

import paths

try:
    from annotation import TEAM_COLORS  # BGR tuples, same colors as the rendered video
except ImportError:
    TEAM_COLORS = {0: (255, 90, 30), 1: (40, 40, 255)}  # fallback if annotation.py isn't on the path yet


def bgr_to_hex(bgr):
    b, g, r = bgr
    return f"#{r:02x}{g:02x}{b:02x}"


TEAM_NAMES = {0: "Team 0", 1: "Team 1"}  # rename these once you have real team names


st.set_page_config(page_title="Match analysis", layout="wide")


# ---------------------------------------------------------------------- #
#  Cached loaders -- st.cache_data keys on the file path + its mtime, so  #
#  editing paths.py or rebuilding a cache picks up automatically without  #
#  a manual "clear cache" step.                                          #
# ---------------------------------------------------------------------- #

@st.cache_data
def load_parquet(path: str, _mtime: float):
    return pd.read_parquet(path)


def load_parquet_if_exists(path: str):
    p = Path(path)
    if not p.exists():
        return None
    return load_parquet(path, p.stat().st_mtime)


def team_badge(team: int) -> str:
    color = bgr_to_hex(TEAM_COLORS.get(team, (150, 150, 150)))
    name = TEAM_NAMES.get(team, f"Team {team}")
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{color};'
        f'display:inline-block"></span>{name}</span>'
    )


# ---------------------------------------------------------------------- #
#  Tabs                                                                   #
# ---------------------------------------------------------------------- #

def render_video_tab():
    video_path = Path(paths.OUTPUT_VIDEO_PATH)
    if not video_path.exists():
        st.warning(f"No annotated video found at `{video_path}`. Run the render stage first.")
        return
    st.video(str(video_path))


def render_passes_tab():
    pass_events = load_parquet_if_exists(paths.PASS_EVENTS_CACHE_PATH)
    if pass_events is None:
        st.warning(
            f"No pass events found at `{paths.PASS_EVENTS_CACHE_PATH}`. "
            "Run `passes.ipynb` first."
        )
        return

    if pass_events.empty:
        st.info("No pass events detected for this match.")
        return

    team_summary = (
        pass_events.groupby("passer_team")
        .agg(attempted=("completed", "size"), completed=("completed", "sum"))
        .reset_index()
        .rename(columns={"passer_team": "team"})
    )
    team_summary["completion_pct"] = (team_summary["completed"] / team_summary["attempted"] * 100).round(1)

    cols = st.columns(len(team_summary) + 1)
    with cols[0]:
        st.metric("All passes", int(team_summary["attempted"].sum()))
        st.metric("Completed", int(team_summary["completed"].sum()))

    for i, row in team_summary.iterrows():
        with cols[i + 1]:
            st.markdown(team_badge(int(row["team"])), unsafe_allow_html=True)
            st.metric("Attempted", int(row["attempted"]))
            st.metric("Completed", int(row["completed"]), f"{row['completion_pct']}%")

    st.bar_chart(team_summary.set_index("team")[["attempted", "completed"]])

    with st.expander(f"All {len(pass_events)} pass events"):
        display_df = pass_events.copy()
        display_df["passer_team"] = display_df["passer_team"].map(lambda t: TEAM_NAMES.get(t, t))
        display_df["receiver_team"] = display_df["receiver_team"].map(lambda t: TEAM_NAMES.get(t, t))
        st.dataframe(display_df, width="stretch")


TABS = {
    "Match video": render_video_tab,
    "Passes": render_passes_tab,
    # add new stats here as they land, e.g.:
    # "Pressure": render_pressure_tab,
    # "Possession": render_possession_tab,
}


st.title("Match analysis")

tabs = st.tabs(list(TABS.keys()))
for tab, render_fn in zip(tabs, TABS.values()):
    with tab:
        render_fn()
