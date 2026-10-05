"""
Section 1 — Team overview dashboard.
KPI cards, the master pressing-profile table, zone breakdown, PPDA, and
defensive-shape comparison (resting vs actively pressing).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from modules import data_loader, theme


def render(data: dict, mode: str) -> None:
    names = data_loader.team_names(data)
    colors = {names[t]: data_loader.team_color(t) for t in names}
    tmpl = theme.plotly_template(mode)

    st.header("Team overview")
    st.markdown(
        '<div class="section-caption">Pressing volume, effectiveness, and structure — one row per team.</div>',
        unsafe_allow_html=True,
    )

    profile = data_loader.df(data, "team", "pressing_profile")
    if "team_name" not in profile.columns and "team" in profile.columns:
        # tolerates an export produced before the notebook's _df() rename fix, where this
        # table's column stayed "team" (holding the team name string) instead of "team_name"
        if profile["team"].isin(names.values()).all():
            profile = profile.rename(columns={"team": "team_name"})
        else:
            profile["team_name"] = profile["team"].map(names)

    # ---------------- KPI cards ----------------
    cols = st.columns(len(profile))
    for col, (_, row) in zip(cols, profile.iterrows()):
        with col:
            st.subheader(row["team_name"])
            st.metric("Pressing intensity", f"{row.get('pct_opp_possession_pressured', float('nan')):.1f}%")
            st.metric("PPDA", f"{row.get('ppda', float('nan')):.2f}")
            st.metric("Regain rate (press events)", f"{row.get('press_event_regain_rate_pct', float('nan')):.1f}%")

    st.divider()

    left, right = st.columns([1.1, 1])

    # ---------------- zone breakdown ----------------
    with left:
        st.subheader("Pressure by pitch zone")
        zone_pct = data_loader.df(data, "team", "zone_pressure_pct")
        zone_pct["team_name"] = zone_pct["team"].map(names)
        melted = zone_pct.melt(
            id_vars="team_name",
            value_vars=[c for c in ["own_third", "middle_third", "attacking_third"] if c in zone_pct.columns],
            var_name="zone",
            value_name="pct",
        )
        zone_order = ["own_third", "middle_third", "attacking_third"]
        fig = px.bar(
            melted, x="zone", y="pct", color="team_name", barmode="group",
            category_orders={"zone": zone_order}, color_discrete_map=colors,
            labels={"pct": "% of team's own pressing", "zone": "", "team_name": "Team"},
            template=tmpl,
        )
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig, width='stretch')

    # ---------------- PPDA + turnover rate by zone ----------------
    with right:
        st.subheader("Turnover rate forced, by zone")
        rows = []
        for _, r in profile.iterrows():
            for zone_key, zone_label in [
                ("turnover_rate_own_third", "own_third"),
                ("turnover_rate_middle_third", "middle_third"),
                ("turnover_rate_attacking_third", "attacking_third"),
            ]:
                if zone_key in r:
                    rows.append({"team_name": r["team_name"], "zone": zone_label, "turnover_rate": r[zone_key]})
        turn_df = pd.DataFrame(rows)
        if not turn_df.empty:
            fig2 = px.bar(
                turn_df, x="zone", y="turnover_rate", color="team_name", barmode="group",
                category_orders={"zone": ["own_third", "middle_third", "attacking_third"]},
                color_discrete_map=colors,
                labels={"turnover_rate": "turnover rate (%)", "zone": "", "team_name": "Team"},
                template=tmpl,
            )
            fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
            st.plotly_chart(fig2, width='stretch')
        else:
            st.info("No zone turnover-rate fields found in the export.")

    st.divider()

    # ---------------- defensive shape ----------------
    st.subheader("Defensive shape — resting vs actively pressing")
    shape_state = data_loader.df(data, "team", "shape_by_pressure_state")
    if not shape_state.empty:
        shape_state["team_name"] = shape_state["team"].map(names)
        shape_state["state"] = shape_state["under_team_pressure"].map({True: "actively pressing", False: "resting"})
        fig3 = px.bar(
            shape_state, x="team_name", y="mean", color="state", barmode="group",
            labels={"mean": "compactness area (m²)", "team_name": "", "state": ""},
            template=tmpl,
        )
        fig3.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig3, width='stretch')
    else:
        st.info("No shape-by-pressure-state data found in the export.")

    st.divider()

    # ---------------- full profile table ----------------
    st.subheader("Full pressing profile")
    st.dataframe(profile.set_index("team_name"), width='stretch')