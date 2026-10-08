"""Page header: badge, title, the two teams, and the dark / light switch (dark is the original look)."""
import streamlit as st

import config

SHIELD = (
    '<svg viewBox="0 0 64 76" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Football tactics analysis">'
    '<defs><clipPath id="sh"><path d="M32 2 L60 12 V38 C60 56 46 68 32 74 C18 68 4 56 4 38 V12 Z"/></clipPath></defs>'
    '<g clip-path="url(#sh)"><rect width="32" height="76" fill="#004D98"/><rect x="32" width="32" height="76" fill="#CB3524"/>'
    '<rect x="29" width="6" height="76" fill="#F2C94C"/></g>'
    '<path d="M32 2 L60 12 V38 C60 56 46 68 32 74 C18 68 4 56 4 38 V12 Z" fill="none" stroke="#fff" stroke-width="2.5"/>'
    '<g fill="none" stroke="#fff" stroke-width="1.8" opacity=".95"><circle cx="32" cy="40" r="10"/><line x1="12" y1="40" x2="52" y2="40"/>'
    '<rect x="21" y="14" width="22" height="9"/><rect x="21" y="57" width="22" height="9"/></g>'
    '<g fill="#fff"><circle cx="32" cy="40" r="2.2"/><circle cx="24" cy="30" r="1.8"/><circle cx="40" cy="31" r="1.8"/>'
    '<circle cx="24" cy="50" r="1.8"/><circle cx="41" cy="49" r="1.8"/></g></svg>'
)


def _crest(code: str) -> str:
    t = config.TEAMS[code]
    return (f'<div class="hero-team"><div class="crest" style="--bg:{t["bg"]};--edge:{t["edge"]}">{code}</div>{t["short"]}</div>')


HERO = (
    '<div class="hero">'
    f'<div class="hero-badge">{SHIELD}</div>'
    '<div><div class="hero-eyebrow">Football tactics analysis &middot; Computer vision &amp; LLMs</div>'
    '<div class="hero-title">Bar&ccedil;a<i>v</i>Atl&eacute;tico</div>'
    '<div class="hero-sub">Annotated match video, build-ups kept or lost under pressure, pressing and defensive-shape statistics.</div></div>'
    f'<div class="hero-vs">{_crest("BAR")}<span class="hero-vs-t">v</span>{_crest("ATM")}</div>'
    '</div>'
)


def render_header() -> None:
    left, right = st.columns([8, 1.3], vertical_alignment="center")
    left.markdown(HERO, unsafe_allow_html=True)
    right.toggle("Light mode", key="light_mode", help="Dark is the default look.")
