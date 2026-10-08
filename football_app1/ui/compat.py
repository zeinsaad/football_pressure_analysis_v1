"""Works on old and new Streamlit: `use_container_width` was replaced by `width="stretch"`."""
from __future__ import annotations

import inspect

import streamlit as st

_NEW = "width" in inspect.signature(st.button).parameters
STRETCH = {"width": "stretch"} if _NEW else {"use_container_width": True}


def choice(label: str, options: list[str], key: str, default: str | None = None) -> str:
    """Segmented control where available, horizontal radio on older Streamlit. Always returns one of `options`."""
    default = default or options[0]
    if hasattr(st, "segmented_control"):
        return st.segmented_control(label, options, default=default, key=key, label_visibility="collapsed") or default
    return st.radio(label, options, index=options.index(default), horizontal=True, key=key, label_visibility="collapsed")
