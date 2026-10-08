"""
Loads and lightly normalizes the notebook's JSON export
(see the original notebook's Section 20 export cell).
"""

import json
import os
from typing import Optional

import pandas as pd
import streamlit as st


@st.cache_data(show_spinner="Loading match data…")
def load_export(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        raw = json.load(f)
    return raw


def team_names(data: dict) -> dict:
    """{'0': 'Barca', '1': 'Atletico'} -> {0: 'Barca', 1: 'Atletico'}"""
    return {int(k): v for k, v in data["meta"]["team_names"].items()}


def team_color(team_id: int) -> str:
    """Consistent color per team across every chart in the app."""
    palette = {0: "#1D9E75", 1: "#534AB7"}
    return palette.get(team_id, "#888888")


def df(data: dict, *keys) -> pd.DataFrame:
    """Walk nested dict keys and return a DataFrame, e.g. df(data, 'team', 'pressing_profile')."""
    node = data
    for k in keys:
        node = node[k]
    return pd.DataFrame(node)
