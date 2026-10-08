"""Page header: football badge, title, the two teams' crests, and the dark / light switch (dark is the original look).

The three badges are your own image files in the icons folder (football_badge, barca_badge, atletico_madrid_badge; see config.ICON_FILES).
If a file is missing, a generic drawn shield in the club colours is used instead.
"""
import base64
from pathlib import Path

import streamlit as st

import config
from ui.compat import STRETCH

BADGE = (
    '<svg viewBox="0 0 64 76" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Football tactics analysis"><defs><clipPath id="shc"><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z"/></clipPath><linearGradient id="fld" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#16356b"/><stop offset="1" stop-color="#091a38"/></linearGradient><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F6DE8D"/><stop offset=".5" stop-color="#D4A93A"/><stop offset="1" stop-color="#9C7414"/></linearGradient><clipPath id="bc"><circle cx="32" cy="41" r="14"/></clipPath><radialGradient id="ball" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cfd6e4"/></radialGradient></defs><path d="M32 2 L60 12 V38 C60 56 46 68 32 74 C18 68 4 56 4 38 V12 Z" fill="url(#gold)"/><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z" fill="url(#fld)"/><g clip-path="url(#shc)"><rect x="8" y="55" width="24" height="16" fill="#004D98"/><rect x="32" y="55" width="24" height="16" fill="#CB3524"/><path d="M8 55 H56" stroke="url(#gold)" stroke-width="1.6"/><path d="M-4 22 L68 8" stroke="#ffffff" stroke-opacity=".05" stroke-width="14"/></g><g fill="url(#gold)"><polygon transform="translate(21 14.5) scale(0.62)" points="0,-5 1.5,-1.6 5,-1.5 2.3,0.8 3.1,4.3 0,2.3 -3.1,4.3 -2.3,0.8 -5,-1.5 -1.5,-1.6" /><polygon transform="translate(32 12) scale(0.78)" points="0,-5 1.5,-1.6 5,-1.5 2.3,0.8 3.1,4.3 0,2.3 -3.1,4.3 -2.3,0.8 -5,-1.5 -1.5,-1.6" /><polygon transform="translate(43 14.5) scale(0.62)" points="0,-5 1.5,-1.6 5,-1.5 2.3,0.8 3.1,4.3 0,2.3 -3.1,4.3 -2.3,0.8 -5,-1.5 -1.5,-1.6" /></g><circle cx="32" cy="41" r="14" fill="url(#ball)" stroke="#0a1224" stroke-width="1.3"/><polygon points="32.0,35.8 36.9,39.4 35.1,45.2 28.9,45.2 27.1,39.4" fill="#0a1224"/><g stroke="#0a1224" stroke-width="1.1" stroke-linecap="round"><line x1="32.0" y1="35.8" x2="32.0" y2="31.4"/><line x1="36.9" y1="39.4" x2="41.1" y2="38.0"/><line x1="35.1" y1="45.2" x2="37.6" y2="48.8"/><line x1="28.9" y1="45.2" x2="26.4" y2="48.8"/><line x1="27.1" y1="39.4" x2="22.9" y2="38.0"/></g><g fill="#0a1224" clip-path="url(#bc)"><polygon points="37.9,32.9 36.7,29.2 39.8,26.9 43.0,29.2 41.8,32.9"/><polygon points="41.5,44.1 44.6,41.8 47.8,44.1 46.6,47.8 42.7,47.8"/><polygon points="32.0,51.0 35.1,53.3 33.9,57.0 30.1,57.0 28.9,53.3"/><polygon points="22.5,44.1 21.3,47.8 17.4,47.8 16.2,44.1 19.4,41.8"/><polygon points="26.1,32.9 22.2,32.9 21.0,29.2 24.2,26.9 27.3,29.2"/></g><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width=".8"/></svg>'
)

_DRAWN = {
    "BAR": (
        '<svg viewBox="0 0 64 76" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="BAR"><defs><clipPath id="cBAR"><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z"/></clipPath><linearGradient id="cBARg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient></defs><path d="M32 2 L60 12 V38 C60 56 46 68 32 74 C18 68 4 56 4 38 V12 Z" fill="#EDEFF4"/><g clip-path="url(#cBAR)"><rect x="4" y="0" width="14" height="80" fill="#004D98"/><rect x="18" y="0" width="14" height="80" fill="#A50044"/><rect x="32" y="0" width="14" height="80" fill="#004D98"/><rect x="46" y="0" width="14" height="80" fill="#A50044"/><rect x="0" y="0" width="64" height="40" fill="url(#cBARg)"/></g><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-opacity=".9"/></svg>'
    ),
    "ATM": (
        '<svg viewBox="0 0 64 76" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ATM"><defs><clipPath id="cATM"><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z"/></clipPath><linearGradient id="cATMg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient></defs><path d="M32 2 L60 12 V38 C60 56 46 68 32 74 C18 68 4 56 4 38 V12 Z" fill="#EDEFF4"/><g clip-path="url(#cATM)"><rect x="4" y="0" width="14" height="80" fill="#CB3524"/><rect x="18" y="0" width="14" height="80" fill="#F2F2F2"/><rect x="32" y="0" width="14" height="80" fill="#CB3524"/><rect x="46" y="0" width="14" height="80" fill="#F2F2F2"/><rect x="0" y="0" width="64" height="40" fill="url(#cATMg)"/></g><path d="M32 6 L56 14.5 V38 C56 53.5 44 64.5 32 70 C20 64.5 8 53.5 8 38 V14.5 Z" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-opacity=".9"/></svg>'
    ),
}


def _remove_backdrop(im):
    """Badge images saved from a web page often carry the grey / white 'transparent' checkerboard as real pixels. Every near-white or light-grey
    pixel connected to the image border is made transparent (the white or grey parts INSIDE the badge are not connected to the border, so they stay)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(im)                                                   # photos / jpgs can carry a "rotate when displayed" flag; browsers obey it, so must we
    im = im.convert("RGBA")
    im.thumbnail((360, 360))                                                           # small is enough for a 60-90 px badge, and keeps the flood fill fast
    w, h = im.size
    px = im.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 16 or (min(r, g, b) >= 168 and max(r, g, b) - min(r, g, b) <= 22):  # transparent, white or light grey
                mp[x, y] = 255
    border = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    for seed in border:
        if mp[seed] == 255:
            ImageDraw.floodfill(mask, seed, 128)                                      # 128 = background connected to the border
    back = mask.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.MaxFilter(3))      # one pixel wider: removes the light fringe of the anti-aliased edge
    alpha = back.point(lambda v: 255 - v).filter(ImageFilter.GaussianBlur(0.7))
    im.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
    return im.crop(box) if box else im


@st.cache_data(show_spinner=False)
def _data_uri(path_str: str, mtime: float) -> str:
    import io
    from PIL import Image
    path = Path(path_str)
    try:
        out = io.BytesIO()
        _remove_backdrop(Image.open(path)).save(out, format="PNG")
        return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:                                                                  # cannot be processed: show the file as it is
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[path.suffix.lower()]
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _icon(key: str):
    """Data-URI of the user's image for MAIN / BAR / ATM, or None when the file is not there."""
    stem = config.ICON_FILES[key]
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        f = config.ICONS_DIR / f"{stem}{ext}"
        if f.exists():
            return _data_uri(str(f), f.stat().st_mtime)
    return None


def _crest_html(code: str) -> str:
    uri = _icon(code)
    if uri:
        return f'<div class="tcrest-img"><img class="icon-img" alt="{code}" src="{uri}"></div>'
    return f'<div class="tcrest">{_DRAWN[code]}</div>'


def _team(code: str) -> str:
    t = config.TEAMS[code]
    return f'<div class="hero-team">{_crest_html(code)}<div class="hero-team-n">{t["short"]}</div></div>'


def _hero() -> str:
    main = _icon("MAIN")
    badge = f'<img class="icon-img" alt="Football" src="{main}">' if main else BADGE
    return (
        '<div class="hero">'
        f'<div class="hero-badge">{badge}</div>'
        '<div class="hero-main"><div class="hero-eyebrow">Football tactics analysis &middot; Computer vision &amp; LLMs</div>'
        '<div class="hero-title">Bar&ccedil;a<i>v</i>Atl&eacute;tico</div>'
        '<div class="hero-sub">Annotated match video, build-ups kept or lost under pressure, pressing and defensive-shape statistics.</div></div>'
        f'<div class="hero-vs">{_team("BAR")}<span class="hero-vs-t">vs</span>{_team("ATM")}</div>'
        '</div>'
    )


def _flip_theme() -> None:
    st.session_state["light_mode"] = not st.session_state.get("light_mode", False)       # apply_theme() reads this


def render_header() -> None:
    """One full-width card (same width as the tab bar): badge, title, the two crests, and a single Dark / Light button on its right."""
    light = st.session_state.get("light_mode", False)
    with st.container(key="hero_wrap"):
        left, right = st.columns([8.8, 1.3], vertical_alignment="center")
        left.markdown(_hero(), unsafe_allow_html=True)
        with right:
            label, icon, glyph = ("Dark", ":material/dark_mode:", "\u263E") if light else ("Light", ":material/light_mode:", "\u2600")
            try:
                st.button(label, key="theme_btn", icon=icon, on_click=_flip_theme, help=f"Switch to {label.lower()} mode", **STRETCH)
            except TypeError:                                                                  # older Streamlit: no icon argument
                st.button(f"{glyph} {label}", key="theme_btn", on_click=_flip_theme, help=f"Switch to {label.lower()} mode", **STRETCH)
