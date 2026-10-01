"""
Draws an empty football pitch as Plotly shapes, reused by the heatmap
and pass-map sections so both look consistent.
"""

import plotly.graph_objects as go


def add_pitch_shapes(fig: go.Figure, length: float, width: float, line_color: str = "#888888") -> go.Figure:
    box_depth, box_width = 16.5, 40.3
    six_depth, six_width = 5.5, 18.3
    common = dict(line=dict(color=line_color, width=1.4), fillcolor="rgba(0,0,0,0)")

    # outer boundary
    fig.add_shape(type="rect", x0=0, y0=0, x1=length, y1=width, **common)
    # halfway line
    fig.add_shape(type="line", x0=length / 2, y0=0, x1=length / 2, y1=width, line=dict(color=line_color, width=1.2))
    # center circle
    fig.add_shape(
        type="circle",
        x0=length / 2 - 9.15, y0=width / 2 - 9.15,
        x1=length / 2 + 9.15, y1=width / 2 + 9.15,
        line=dict(color=line_color, width=1.2),
    )
    # penalty boxes
    fig.add_shape(type="rect", x0=0, y0=(width - box_width) / 2, x1=box_depth, y1=(width + box_width) / 2, **common)
    fig.add_shape(
        type="rect",
        x0=length - box_depth, y0=(width - box_width) / 2,
        x1=length, y1=(width + box_width) / 2,
        **common,
    )
    # six-yard boxes
    fig.add_shape(type="rect", x0=0, y0=(width - six_width) / 2, x1=six_depth, y1=(width + six_width) / 2, **common)
    fig.add_shape(
        type="rect",
        x0=length - six_depth, y0=(width - six_width) / 2,
        x1=length, y1=(width + six_width) / 2,
        **common,
    )
    return fig


def base_pitch_figure(length: float, width: float, mode: str) -> go.Figure:
    line_color = "#6B7684" if mode == "dark" else "#B7C0CA"
    fig = go.Figure()
    add_pitch_shapes(fig, length, width, line_color)
    fig.update_xaxes(range=[-3, length + 3], visible=False)
    fig.update_yaxes(range=[-3, width + 3], visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(
        template="plotly_dark" if mode == "dark" else "plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
