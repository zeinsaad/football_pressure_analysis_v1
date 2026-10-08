"""
Section 4 — Pass map & outcome breakdown.
Where passes were released from (colored by outcome), plus the pressure
outcome taxonomy (progressed / forced sideways / lost, etc.) by team.
"""

import plotly.express as px
import streamlit as st

from modules import data_loader, theme
from utils import pitch

OUTCOME_COLORS = {
    "progressed_forward": "#1D9E75",
    "forced_sideways": "#E0A93A",
    "forced_backward": "#D9782E",
    "lost_intercepted": "#C0392B",
    "lost_tackled": "#8E2E2E",
    "lost_after_long_ball": "#6C4F9C",
    "retained_after_gap": "#5A6B7A",
    "unresolved": "#AAAAAA",
}


def render(data: dict, mode: str) -> None:
    names = data_loader.team_names(data)
    length = data["meta"]["pitch_length_m"]
    width = data["meta"]["pitch_width_m"]
    tmpl = theme.plotly_template(mode)

    st.header("Pass map & outcomes")
    st.markdown(
        '<div class="section-caption">Pass release locations and what pressure did to each pressured action.</div>',
        unsafe_allow_html=True,
    )

    # ---------------- pass map ----------------
    passes = data_loader.df(data, "events", "passes")
    if not passes.empty and "release_x" in passes.columns:
        team_id = st.selectbox("Team", list(names.keys()), format_func=lambda t: names[t], key="passmap_team")
        pressure_filter = st.radio("Show", ["All passes", "Under pressure only", "Not under pressure"], horizontal=True)

        sub = passes[passes["passer_team"] == team_id].copy()
        if pressure_filter == "Under pressure only":
            sub = sub[sub["under_pressure"] == True]  # noqa: E712
        elif pressure_filter == "Not under pressure":
            sub = sub[sub["under_pressure"] == False]  # noqa: E712

        fig = pitch.base_pitch_figure(length, width, mode)
        if "release_y" in sub.columns and not sub.empty:
            for outcome, grp in sub.groupby("pass_outcome_detail"):
                fig.add_scatter(
                    x=grp["release_x"], y=grp["release_y"], mode="markers",
                    name=str(outcome),
                    marker=dict(color=OUTCOME_COLORS.get(outcome, "#888888"), size=8, opacity=0.75),
                )
            fig.update_layout(title=f"{names[team_id]} — pass release points", legend_title_text="outcome")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Pass export has no release_y coordinate — release_x-only view isn't plotted on a 2D pitch.")
    else:
        st.info("No pass-level data (with coordinates) found in the export.")

    st.divider()

    # ---------------- outcome breakdown ----------------
    st.subheader("Pressured-action outcomes, by team")
    outcome_pct = data_loader.df(data, "team", "outcome_pct")
    if not outcome_pct.empty:
        outcome_pct["team_name"] = outcome_pct["team"].map(names)
        pressured = outcome_pct[outcome_pct.get("under_pressure", True) == True] if "under_pressure" in outcome_pct.columns else outcome_pct
        outcome_cols = [c for c in OUTCOME_COLORS if c in pressured.columns]
        melted = pressured.melt(id_vars="team_name", value_vars=outcome_cols, var_name="outcome", value_name="pct")
        fig2 = px.bar(
            melted, x="team_name", y="pct", color="outcome", barmode="stack",
            color_discrete_map=OUTCOME_COLORS,
            labels={"pct": "% of pressured actions", "team_name": ""},
            template=tmpl,
        )
        fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("No outcome breakdown found in the export.")

    st.divider()

    # ---------------- zone outcome table ----------------
    st.subheader("Disruption & turnover rate by zone")
    zone_outcome = data_loader.df(data, "team", "zone_outcome_summary")
    if not zone_outcome.empty:
        if "team" in zone_outcome.columns:
            zone_outcome["team_name"] = zone_outcome["team"].map(names)
        st.dataframe(zone_outcome, width='stretch')
    else:
        st.info("No zone outcome summary found in the export.")
