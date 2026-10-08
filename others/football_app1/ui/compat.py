"""Works on old and new Streamlit: `use_container_width` was replaced by `width="stretch"`."""
import inspect

import streamlit as st

_NEW = "width" in inspect.signature(st.button).parameters
STRETCH = {"width": "stretch"} if _NEW else {"use_container_width": True}
