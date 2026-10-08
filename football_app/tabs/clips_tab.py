"""Tab 2: build-up clips with team / outcome filters, grid or list view, and a player dialog."""
from __future__ import annotations

import html
import re

import streamlit as st

import config
from core import media, stars
from core.clips import Clip, load_analysis, parse_analysis, scan_clips, strip_rules
from ui.compat import STRETCH
from ui.styles import analysis_chip, outcome_chip, team_chip

PAGE_SIZE = 12
GRID_COLS = 3

TEAM_FILTER = {"All teams": None, "Barcelona": "BAR", "Atlético Madrid": "ATM"}
OUTCOME_FILTER = {"All": None, "Kept the ball": "kept", "Lost the ball": "lost"}
SORTS = {
    "Match time": lambda c: c.match_second,
    "Latest first": lambda c: -c.match_second,
}


# ------------------------------------------------------------------ small widgets
def _choice(label: str, options: list[str], key: str) -> str:
    """Segmented control where available, horizontal radio on older Streamlit."""
    if hasattr(st, "segmented_control"):
        return st.segmented_control(label, options, default=options[0], key=key, label_visibility="collapsed") or options[0]
    return st.radio(label, options, horizontal=True, key=key, label_visibility="collapsed")


def _thumb(clip: Clip) -> None:
    img = media.thumbnail(clip.path)
    if img:
        st.image(str(img), **STRETCH)
    else:
        st.markdown('<div class="empty">No preview</div>', unsafe_allow_html=True)


def _duration(clip: Clip) -> str:
    return media.fmt_duration(media.info_of(clip.path)["duration"])


def _chips(clip: Clip) -> str:
    return team_chip(clip.team) + outcome_chip(clip.outcome) + (analysis_chip() if clip.has_analysis else "")


def _star_button(clip: Clip, starred: set[str], where: str) -> None:
    """One click stars / un-stars the clip and writes the file at once (stars survive closing the app)."""
    on = stars.is_starred(clip, starred)
    st.button("\u2605" if on else "\u2606", key=f"star_{where}_{clip.team}_{clip.outcome}_{clip.stem}", type="primary" if on else "secondary",
              help="Starred. Click to remove the star" if on else "Star this clip", on_click=stars.toggle, args=(clip,), **STRETCH)


def _star_mark(clip: Clip, starred: set[str]) -> str:
    return '<span class="star-mark">\u2605</span>' if stars.is_starred(clip, starred) else ""


# ------------------------------------------------------------------ player dialog
def _step(delta: int) -> None:
    n = len(st.session_state["_dlg_paths"])
    st.session_state["_dlg_idx"] = (st.session_state["_dlg_idx"] + delta) % n


_ITEM_RE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")


def _as_markdown(text: str, keep_breaks: bool = False, paragraphs: bool = False) -> str:
    """Plain LLM text -> safe markdown: '$' is not read as maths.

    keep_breaks: single line breaks stay line breaks. paragraphs: every line becomes its own paragraph (list items stay together),
    which is how the analysis files are written (one paragraph per line, no blank lines between them).
    """
    text = text.replace("$", r"\$")
    if paragraphs:
        lines, out = text.split("\n"), []
        for i, line in enumerate(lines):
            out.append(line)
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if line.strip() and nxt.strip() and not (_ITEM_RE.match(line) and _ITEM_RE.match(nxt)):
                out.append("")
        return "\n".join(out)
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", text) if keep_breaks else text


def _scroll_box():
    """Bordered box that scrolls on its own. Fixed height works on every Streamlit version; the CSS in styles.py makes it fill the screen."""
    try:
        return st.container(border=True, height=640, key="clip_analysis")
    except TypeError:                                   # older Streamlit: no key / height
        try:
            return st.container(border=True, height=640)
        except TypeError:
            return st.container(border=True)


def _analysis_panel(clip: Clip) -> None:
    """The whole analysis, always visible next to the video: the verdict as a highlighted call-out, then each section.
    The panel scrolls on its own when the text is long, so the video never moves out of view."""
    accent = config.TEAMS.get(clip.team, {}).get("accent", "#6EA8FE")
    st.markdown(f'<div class="ap-head" style="--c:{accent}"><span class="ap-bar"></span>Tactical analysis</div>',
                unsafe_allow_html=True)
    with _scroll_box():
        text = load_analysis(clip)
        if not text:
            st.markdown('<div class="analysis-empty">No analysis is available for this clip yet.</div>',
                        unsafe_allow_html=True)
            return
        sections = parse_analysis(text)
        if not sections:                                   # free text
            st.markdown(_as_markdown(strip_rules(text), keep_breaks=True))
            return
        n = 0
        for title, body in sections:
            kind = _card_kind(title)
            if kind:
                st.markdown(f'<div class="ap-card ap-{kind}" style="--c:{accent if kind == "verdict" else CARD_COLORS[kind]}">'
                            f'<div class="ap-card-h"><span class="ap-card-i">{CARD_ICONS[kind]}</span>{html.escape(title)}</div>'
                            f'<div class="ap-card-b">{_body_html(body)}</div></div>', unsafe_allow_html=True)
            else:
                n += 1
                st.markdown(f'<div class="ap-sec"><span class="ap-n">{n}</span>{html.escape(title)}</div>',
                            unsafe_allow_html=True)
                st.markdown(_as_markdown(body, paragraphs=True))


CARD_COLORS = {"why": "#E8B04B", "counterfactual": "#A78BFA"}
CARD_ICONS = {"verdict": "\u2713", "why": "?", "counterfactual": "\u21c4"}


def _card_kind(title: str) -> str:
    t = title.strip().lower()
    for k in ("verdict", "why", "counterfactual"):
        if t.startswith(k):
            return k
    return ""


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _inline(text: str) -> str:
    return _BOLD_RE.sub(r"<b>\1</b>", html.escape(text))


def _body_html(body: str) -> str:
    """Analysis text -> HTML for the highlighted cards: paragraphs, bullet / numbered lists (numbers drawn as badges), **bold**."""
    out, items, ordered = [], [], False

    def flush():
        nonlocal items
        if items:
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag}>")
            items = []

    for line in body.split("\n"):
        if not line.strip():
            flush()
            continue
        m = _ITEM_RE.match(line)
        if m:
            is_ord = bool(re.match(r"^\s*\d+[.)]", line))
            if items and is_ord != ordered:
                flush()
            ordered = is_ord
            items.append(_inline(line[m.end():].strip()))
        else:
            flush()
            out.append(f"<p>{_inline(line.strip())}</p>")
    flush()
    return "".join(out)


VIEWER_CSS = """
<style>
/* viewer mode: the page header and tab bar step aside and the content uses the whole screen width */
.st-key-hero_wrap, .stTabs [role="tablist"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 99vw !important; padding-top: .8rem !important; padding-left: 1.2rem !important; padding-right: 1.2rem !important; }
[data-testid="stLayoutWrapper"]:has(> .st-key-hero_wrap), [data-testid="stElementContainer"]:has(> .st-key-hero_wrap), .stElementContainer:has(> .st-key-hero_wrap) { display: none !important; }
[data-testid="stTabPanel"] { padding-top: 0 !important; }
.stTabs [data-baseweb="tab-list"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-bottom: 0 !important; }
.st-key-clip_video video, div[data-testid="stVideo"] video { width: 100% !important; max-height: calc(100vh - 125px) !important; background: #000; border-radius: 12px; }
.st-key-clip_analysis, .st-key-clip_analysis > div { height: calc(100vh - 150px) !important; max-height: calc(100vh - 150px) !important; }
/* drag handle between video and analysis; the script iframe takes no space */
.ap-split { flex: 0 0 16px; align-self: stretch; cursor: col-resize; display: flex; align-items: center; justify-content: center; border-radius: 8px; transition: background .15s ease; }
.ap-split i { width: 4px; height: 56px; border-radius: 3px; background: #34425f; transition: background .15s ease, height .15s ease; }
.ap-split:hover, .ap-dragging .ap-split { background: rgba(110,168,254,.14); }
.ap-split:hover i, .ap-dragging .ap-split i { background: #6EA8FE; height: 90px; }
.ap-dragging video, .ap-dragging iframe { pointer-events: none !important; }
[data-testid="stElementContainer"]:has(> [data-testid="stIFrame"]), [data-testid="stElementContainer"]:has(iframe[height="0"]), .stElementContainer:has(iframe[height="0"]) { position: absolute !important; height: 0 !important; overflow: hidden !important; margin: 0 !important; }
</style>
"""


SPLITTER_JS = r"""
<script>
(function () {
  var P = window.parent, D = P.document;
  if (P.__clipSplitInstalled) { P.__clipSplitRefresh && P.__clipSplitRefresh(); return; }
  var code = "(" + function () {
    var KEY = "clipSplitFrac", DEFAULT = 0.68, MIN = 0.22, MAX = 0.82;
    function load() { try { var v = parseFloat(localStorage.getItem(KEY)); return v >= MIN && v <= MAX ? v : DEFAULT; } catch (e) { return DEFAULT; } }
    function save(v) { try { localStorage.setItem(KEY, String(v)); } catch (e) {} }
    var frac = load();
    function cols() {
      var head = document.querySelector(".ap-head"); if (!head) return null;
      var right = head.closest('[data-testid="stColumn"], [data-testid="column"]');
      var row = right && right.parentElement; if (!row) return null;
      var left = null;
      for (var i = 0; i < row.children.length; i++) { var c = row.children[i]; if (c !== right && c.querySelector && c.querySelector("video, [data-testid=stVideo], [data-testid=stAlert]")) left = c; }
      return left ? { row: row, left: left, right: right } : null;
    }
    function apply() {
      var c = cols(); if (!c) return;
      var h = c.row.querySelector(":scope > .ap-split");
      if (!h) {
        h = document.createElement("div"); h.className = "ap-split"; h.title = "Drag to resize. Double-click to reset.";
        h.innerHTML = "<i></i>"; c.row.insertBefore(h, c.right);
        h.addEventListener("mousedown", start); h.addEventListener("dblclick", function () { frac = DEFAULT; save(frac); apply(); });
      }
      c.row.style.setProperty("gap", "0", "important");
      c.left.style.cssText += ";flex:" + (frac * 1000) + " 1 0 !important;width:auto !important;min-width:0 !important;padding-right:.4rem";
      c.right.style.cssText += ";flex:" + ((1 - frac) * 1000) + " 1 0 !important;width:auto !important;min-width:0 !important;padding-left:.4rem";
    }
    function start(e) {
      var c = cols(); if (!c) return; e.preventDefault();
      var r = c.row.getBoundingClientRect(); c.row.classList.add("ap-dragging"); document.body.style.userSelect = "none";
      function move(ev) { frac = Math.min(MAX, Math.max(MIN, (ev.clientX - r.left) / r.width)); apply(); }
      function up() { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
        c.row.classList.remove("ap-dragging"); document.body.style.userSelect = ""; save(frac); }
      document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
    }
    var t = null;
    new MutationObserver(function () { clearTimeout(t); t = setTimeout(apply, 40); }).observe(document.body, { childList: true, subtree: true });
    window.__clipSplitRefresh = apply; apply();
  } + ")();";
  var s = D.createElement("script"); s.textContent = code; D.head.appendChild(s); P.__clipSplitInstalled = true;
})();
</script>
"""


def _install_splitter() -> None:
    """Drag handle between video and analysis (small script that runs in the page itself; the chosen width is remembered in the browser)."""
    try:
        import streamlit.components.v1 as components
        components.html(SPLITTER_JS, height=0)
    except Exception:
        pass                                             # the fixed layout still works without it


def _close_viewer() -> None:
    st.session_state["_dlg_idx"] = None


def _viewer(clips_by_path: dict[str, Clip]) -> None:
    """Full-screen clip view: video on the left, the whole analysis on the right, both always visible."""
    st.markdown(VIEWER_CSS, unsafe_allow_html=True)
    paths = st.session_state["_dlg_paths"]               # filtered playlist, in the order shown
    idx = st.session_state["_dlg_idx"] % len(paths)
    clip = clips_by_path.get(paths[idx])
    if clip is None:
        _close_viewer()
        st.rerun(scope="fragment")
        return
    team = config.TEAMS.get(clip.team, {}).get("name", clip.team)
    accent = config.TEAMS.get(clip.team, {}).get("accent", "#6EA8FE")
    starred = stars.load()

    # one header row: back | title + chips | star | previous | counter | next
    hb, h1, h2, h3, h4, h5 = st.columns([1.3, 7, .8, .8, 1.3, .8], vertical_alignment="center")
    if hb.button("\u2190  All clips", key="viewer_back", **STRETCH):
        _close_viewer()
        st.rerun(scope="fragment")
    h1.markdown(
        f'<div class="dlg-title" style="--c:{accent}">{team}, {clip.time_label}{_star_mark(clip, starred)}'
        f'<span class="dlg-chips">{_chips(clip)}</span>'
        f'<span class="dlg-facts">Build-up <b>{clip.buildup_id}</b> \u00b7 <b>{media.fmt_duration(media.info_of(clip.path)["duration"])}</b></span></div>',
        unsafe_allow_html=True)
    with h2:
        _star_button(clip, starred, "d")
    if h3.button("\u2039", key="dlg_prev", help="Previous clip", disabled=len(paths) < 2, **STRETCH):
        _step(-1)
        st.rerun(scope="fragment")
    h4.markdown(f'<div class="dlg-count">{idx + 1} <span>of {len(paths)}</span></div>', unsafe_allow_html=True)
    if h5.button("\u203a", key="dlg_next", help="Next clip", disabled=len(paths) < 2, **STRETCH):
        _step(1)
        st.rerun(scope="fragment")

    left, right = st.columns([2.2, 1], gap="medium")
    with left:
        try:
            with st.spinner("Preparing video (first time only)..."):
                playable = media.convert_for_browser(clip.path)
        except Exception as e:
            st.error(str(e))
            playable = None
        if playable:
            with st.container(key="clip_video") if _has_key() else st.container():
                try:
                    st.video(str(playable), autoplay=True)
                except TypeError:                          # older Streamlit has no autoplay argument
                    st.video(str(playable))
    with right:
        _analysis_panel(clip)
    _install_splitter()


def _has_key() -> bool:
    import inspect
    return "key" in inspect.signature(st.container).parameters


def _open(paths: list[str], idx: int) -> None:
    st.session_state["_dlg_paths"] = paths
    st.session_state["_dlg_idx"] = idx
    st.rerun(scope="fragment")


# ------------------------------------------------------------------ views
def _grid(page: list[Clip], playlist: list[str], offset: int) -> None:
    starred = stars.load()
    for r in range(0, len(page), GRID_COLS):
        cols = st.columns(GRID_COLS)
        for col, clip in zip(cols, page[r:r + GRID_COLS]):
            with col, st.container(border=True):
                _thumb(clip)
                team = config.TEAMS.get(clip.team, {}).get("short", clip.team)
                st.markdown(
                    f'<div class="clip-title">{team}, {clip.time_label}{_star_mark(clip, starred)}</div>'
                    f'{_chips(clip)}'
                    f'<div class="clip-meta">Build-up {clip.buildup_id}, {_duration(clip)}</div>',
                    unsafe_allow_html=True,
                )
                b1, b2 = st.columns([4, 1])
                if b1.button("Play clip", key=f"open_g_{clip.stem}_{clip.outcome}", **STRETCH):
                    _open(playlist, playlist.index(clip.path.as_posix()))
                with b2:
                    _star_button(clip, starred, "g")


def _list(page: list[Clip], playlist: list[str], offset: int) -> None:
    starred = stars.load()
    for clip in page:
        with st.container(border=True):
            a, b, c = st.columns([1.3, 4, 1.2], vertical_alignment="center")
            with a:
                _thumb(clip)
            with b:
                team = config.TEAMS.get(clip.team, {}).get("name", clip.team)
                st.markdown(
                    f'<div class="row-title">{team}, {clip.time_label}{_star_mark(clip, starred)}</div>'
                    f'{_chips(clip)}'
                    f'<div class="clip-meta">Build-up {clip.buildup_id}, {_duration(clip)}, {clip.size_mb:.0f} MB</div>',
                    unsafe_allow_html=True,
                )
            with c:
                c1, c2 = st.columns([3, 1])
                if c1.button("Play clip", key=f"open_l_{clip.stem}_{clip.outcome}", **STRETCH):
                    _open(playlist, playlist.index(clip.path.as_posix()))
                with c2:
                    _star_button(clip, starred, "l")


# ------------------------------------------------------------------ tab
def render() -> None:
    _browse()


@st.fragment                                   # filters, paging and the view switch re-run only this block
def _browse() -> None:
    with st.spinner("Loading clips..."):
        clips, missing, bad = scan_clips()
    for m in missing:
        st.error(f"Folder not found: `{m}`. Check `CLIP_FOLDERS` in config.py.")
    if bad:
        st.warning(f"{len(bad)} file(s) skipped because the name does not look like `b119_BAR_32-26.mp4`: {', '.join(bad[:5])}")
    if not clips:
        st.markdown('<div class="empty">No clips found yet.</div>', unsafe_allow_html=True)
        return

    if st.session_state.get("_dlg_idx") is not None:
        _viewer({c.path.as_posix(): c for c in clips})
        return

    # filters
    f1, f2, f3, f4 = st.columns([2.6, 2.4, 1.6, 1.4], vertical_alignment="bottom")
    with f1:
        st.caption("Team")
        team_label = _choice("Team", list(TEAM_FILTER), "f_team")
    with f2:
        st.caption("Outcome")
        outcome_label = _choice("Outcome", list(OUTCOME_FILTER), "f_outcome")
    with f3:
        sort_label = st.selectbox("Sort by", list(SORTS), key="f_sort")
    with f4:
        view = _choice("View", ["Grid", "List"], "f_view")

    team, outcome = TEAM_FILTER[team_label], OUTCOME_FILTER[outcome_label]
    shown = [c for c in clips if (team is None or c.team == team) and (outcome is None or c.outcome == outcome)]
    shown.sort(key=SORTS[sort_label])

    if not shown:
        st.markdown('<div class="empty">No clips match these filters.</div>', unsafe_allow_html=True)
        return

    # paging
    pages = max(1, -(-len(shown) // PAGE_SIZE))
    sig = (team, outcome, sort_label)
    if st.session_state.get("_page_sig") != sig:
        st.session_state["_page_sig"], st.session_state["page"] = sig, 1
    page_no = min(st.session_state.get("page", 1), pages)
    start = (page_no - 1) * PAGE_SIZE
    page = shown[start:start + PAGE_SIZE]
    playlist = [c.path.as_posix() for c in shown]

    st.caption(f"{len(shown)} clip{'s' if len(shown) != 1 else ''}" + (f", page {page_no} of {pages}" if pages > 1 else ""))
    (_grid if view == "Grid" else _list)(page, playlist, start)

    if pages > 1:
        st.write("")
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("Previous page", disabled=page_no <= 1, **STRETCH):
            st.session_state["page"] = page_no - 1
            st.rerun(scope="fragment")
        if p3.button("Next page", disabled=page_no >= pages, **STRETCH):
            st.session_state["page"] = page_no + 1
            st.rerun(scope="fragment")

    # library tools
    with st.expander("Library tools"):
        todo = [c for c in clips if media.cached_web_copy(c.path) is None]
        st.write(f"{len(clips) - len(todo)} of {len(clips)} clips are ready to play instantly. "
                 "The rest are converted the first time you open them.")
        if todo and st.button(f"Convert the other {len(todo)} now"):
            bar = st.progress(0.0)
            for i, c in enumerate(todo, 1):
                try:
                    media.convert_for_browser(c.path)
                except Exception as e:
                    st.error(f"{c.stem}: {e}")
                    break
                bar.progress(i / len(todo), text=f"{i} of {len(todo)}")
            st.rerun(scope="fragment")
        if st.button("Rescan folders and analyses"):
            scan_clips.clear()
            st.rerun(scope="fragment")
