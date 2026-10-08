"""
Section 3 — Match timeline.
Pressure events as a Gantt-style strip, turnovers as markers, and the
5-minute pressing-intensity timeline as a grouped bar chart.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules import data_loader, theme


def render(data: dict, mode: str) -> None:
    names = data_loader.team_names(data)
    colors = {names[t]: data_loader.team_color(t) for t in names}
    tmpl = theme.plotly_template(mode)

    st.header("Match timeline")
    st.markdown(
        '<div class="section-caption">Pressure events over time, turnovers, and pressing intensity by 5-minute bin.</div>',
        unsafe_allow_html=True,
    )

    # ---------------- pressure events strip ----------------
    events = data_loader.df(data, "events", "pressure_events")
    if not events.empty:
        events["team_name"] = events["team"].map(names)
        events["start_min"] = events["start_sec"] / 60
        events["end_min"] = events["end_sec"] / 60

        fig = go.Figure()
        for team_id, team_name in names.items():
            sub = events[events["team"] == team_id]
            fig.add_trace(go.Bar(
                x=(sub["end_min"] - sub["start_min"]),
                y=[team_name] * len(sub),
                base=sub["start_min"],
                orientation="h",
                marker_color=data_loader.team_color(team_id),
                name=team_name,
                customdata=sub[["duration_sec", "max_n_pressing", "regained_ball"]],
                hovertemplate=(
                    "%{y}<br>start: %{base:.1f} min<br>duration: %{customdata[0]:.1f}s"
                    "<br>max simultaneous pressers: %{customdata[1]}<br>regained: %{customdata[2]}<extra></extra>"
                ),
            ))
        fig.update_layout(
            barmode="overlay", template=tmpl, height=260,
            xaxis_title="match minute", yaxis_title="",
            margin=dict(l=10, r=10, t=10, b=10),
            legend_title_text="",
        )
        st.subheader("Pressure events")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No pressure-event data found in the export.")

    st.divider()

    # ---------------- pressing intensity timeline ----------------
    st.subheader("Pressing intensity by 5-minute bin")
    tl = data_loader.df(data, "team", "pressing_intensity_timeline")
    if not tl.empty:
        value_cols = [c for c in tl.columns if c != "bin_label"]
        melted = tl.melt(id_vars="bin_label", value_vars=value_cols, var_name="team", value_name="pct")
        melted["team"] = melted["team"].astype(str).map(lambda t: names.get(int(t), t) if t.lstrip("-").isdigit() else t)
        fig2 = px.bar(
            melted, x="bin_label", y="pct", color="team", barmode="group",
            color_discrete_map=colors,
            labels={"pct": "% time under pressure", "bin_label": "match minute bin", "team": ""},
            template=tmpl,
        )
        fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("No pressing-intensity timeline found in the export.")

    st.divider()

    # ---------------- turnovers table ----------------
    st.subheader("Turnovers & press response")
    turnovers = data_loader.df(data, "events", "turnovers")
    if not turnovers.empty:
        turnovers["team_name"] = turnovers["losing_team"].map(names)
        st.dataframe(
            turnovers[["team_name", "loss_sec", "gain_sec", "time_to_press_sec", "press_response", "regained_within_window"]]
            .rename(columns={"team_name": "losing team", "loss_sec": "lost ball (s)", "gain_sec": "opponent gained (s)"})
            .sort_values("lost ball (s)"),
            width='stretch', height=320,
        )
    else:
        st.info("No turnover data found in the export.")
