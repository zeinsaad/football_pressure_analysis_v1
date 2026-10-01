"""
Section 2 — Pitch pressure heatmap.
Renders the notebook's binned pressure grid (Section 20, pressure_heatmap_grid)
as a single vectorized Heatmap trace over a pitch, one team at a time or
side by side.

Perf note: this used to draw one Plotly shape per grid cell (a few hundred
add_shape() calls per team) -- cheap-looking but expensive to build and to
render client-side. It's now one go.Heatmap trace per team, built from a
small numpy grid; the grid itself is cached so repeated reruns (theme
toggle, nav clicks) don't redo the conversion for data that hasn't changed.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from modules import data_loader, theme
from utils import pitch


@st.cache_data(show_spinner=False)
def _cells_to_grid(cells: tuple) -> tuple:
    """
    list-of-cell-dicts -> (x_centers, y_centers, z_grid) for a single go.Heatmap trace.
    Cached: identical `cells` (same team, same export) never gets rebuilt twice.

    `cells` arrives here as a tuple of tuples-of-(key, value) pairs (see the cache_key
    construction in _heat_figure) since Streamlit's cache needs a hashable argument --
    reconstruct plain dicts first.
    """
    cells = [dict(c) for c in cells]
    if not cells:
        return [], [], np.array([[]])

    x_edges = sorted({round(c["x_min"], 4) for c in cells} | {round(c["x_max"], 4) for c in cells})
    y_edges = sorted({round(c["y_min"], 4) for c in cells} | {round(c["y_max"], 4) for c in cells})
    x_centers = [(x_edges[i] + x_edges[i + 1]) / 2 for i in range(len(x_edges) - 1)]
    y_centers = [(y_edges[i] + y_edges[i + 1]) / 2 for i in range(len(y_edges) - 1)]

    x_index = {round(xc, 4): i for i, xc in enumerate(x_centers)}
    y_index = {round(yc, 4): i for i, yc in enumerate(y_centers)}

    grid = np.full((len(y_centers), len(x_centers)), np.nan)
    for c in cells:
        xc = round((c["x_min"] + c["x_max"]) / 2, 4)
        yc = round((c["y_min"] + c["y_max"]) / 2, 4)
        xi, yi = x_index.get(xc), y_index.get(yc)
        if xi is not None and yi is not None:
            grid[yi, xi] = c["pct_of_team_total"]

    return x_centers, y_centers, grid


def _heat_figure(cells: list, length: float, width: float, mode: str, color: str, title: str) -> go.Figure:
    fig = pitch.base_pitch_figure(length, width, mode)
    if not cells:
        fig.update_layout(title=title)
        return fig

    # cache_data needs a hashable key -- cells is a list of small dicts, so pass as a tuple of
    # sorted items; cheap even for a few hundred cells and only runs once per distinct dataset
    cache_key = tuple(sorted((tuple(sorted(c.items())) for c in cells)))
    x_centers, y_centers, grid = _cells_to_grid(cache_key)

    fig.add_trace(go.Heatmap(
        z=grid, x=x_centers, y=y_centers,
        colorscale=[[0, "rgba(0,0,0,0)"], [1, color]],
        zmin=0, zmax=max((c["pct_of_team_total"] for c in cells), default=1) or 1,
        showscale=True, opacity=0.85,
        colorbar=dict(title="% of team's<br>own pressure", thickness=12, len=0.7),
        hovertemplate="%{z:.2f}%<extra></extra>",
    ))
    fig.update_layout(title=title)
    return fig


def render(data: dict, mode: str) -> None:
    names = data_loader.team_names(data)
    length = data["meta"]["pitch_length_m"]
    width = data["meta"]["pitch_width_m"]
    grid = data["team"].get("pressure_heatmap_grid", {})

    st.header("Pressure heatmap")
    st.markdown(
        '<div class="section-caption">Where each team\'s pressure concentrated, normalized to that team\'s own total (darker = more).</div>',
        unsafe_allow_html=True,
    )

    view = st.radio("View", ["Side by side", "Single team"], horizontal=True, label_visibility="collapsed")

    with st.spinner("Rendering heatmap…"):
        if view == "Side by side":
            cols = st.columns(len(names))
            for col, (team_id, team_name) in zip(cols, names.items()):
                with col:
                    cells = grid.get(str(team_id), grid.get(team_id, []))
                    fig = _heat_figure(cells, length, width, mode, data_loader.team_color(team_id), team_name)
                    st.plotly_chart(fig, width='stretch')
        else:
            team_id = st.selectbox("Team", list(names.keys()), format_func=lambda t: names[t])
            cells = grid.get(str(team_id), grid.get(team_id, []))
            fig = _heat_figure(cells, length, width, mode, data_loader.team_color(team_id), names[team_id])
            st.plotly_chart(fig, width='stretch')