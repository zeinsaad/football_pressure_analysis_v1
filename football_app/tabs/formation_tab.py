"""Tab: the formation of both teams (number + name) on one pitch."""
from __future__ import annotations

import html

import streamlit as st

import config
from core import formation
from ui.compat import STRETCH


def _embed(doc: str, height: int) -> None:
    """st.iframe on current Streamlit, components.html on older versions (it is being removed from new ones)."""
    if hasattr(st, "iframe"):
        st.iframe(doc, height=height)
    else:
        import streamlit.components.v1 as components
        components.html(doc, height=height, scrolling=False)


def render() -> None:
    data = formation.load()
    if data is None:
        st.markdown('<div class="empty">No formation yet.<br>Run the <code>Formation</code> cell of the stats notebook (before section 1). '
                    f'Expected file: <code>{html.escape(str(formation.FORMATION_JSON))}</code></div>', unsafe_allow_html=True)
        return

    if not formation.has_lineup(data):
        st.markdown('<div class="empty">No formation lineup yet.<br>Run the <code>Formation</code> cell of the stats notebook (before section 1).</div>',
                    unsafe_allow_html=True)
        return
    show_names = st.checkbox("Show names", value=True, key="formation_names")

    _embed(formation.lineup_html(data, show_names), 740)
    st.caption("Every player on his real position: goalkeeper, defenders, midfielders and forwards, from left to right as his team sees it "
               "(looking at the opponent's goal). Each team stays in its own half; the numbers in the title are defenders - midfielders - forwards. "
               "Positions are inferred from where each player plays (see the build-up notebook) and can be corrected there. "
               "Barça attacks left to right, Atlético right to left. Hover a player for his number, name and position.")
    with st.expander("Players in this view"):
        st.dataframe(formation.lineup_table(data), hide_index=True, **STRETCH)
