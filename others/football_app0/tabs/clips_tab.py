"""Tab 2: build-up clips with team / outcome filters, grid or list view, and a player dialog."""
from __future__ import annotations

import streamlit as st

import config
from core import media
from core.clips import Clip, load_explanations, scan_clips
from ui.compat import STRETCH
from ui.styles import outcome_chip, stat, team_chip

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


# ------------------------------------------------------------------ player dialog
def _step(delta: int) -> None:
    n = len(st.session_state["_dlg_paths"])
    st.session_state["_dlg_idx"] = (st.session_state["_dlg_idx"] + delta) % n


@st.dialog("Clip", width="large")
def player_dialog() -> None:
    paths = st.session_state["_dlg_paths"]          # filtered playlist, in the order shown
    clips = {c.path.as_posix(): c for c in scan_clips()[0]}
    clip = clips[paths[st.session_state["_dlg_idx"]]]
    team = config.TEAMS.get(clip.team, {}).get("name", clip.team)

    st.markdown(
        f'<div class="clip-title" style="font-size:1.8rem;margin-top:0">{team}, {clip.time_label}</div>'
        f'{team_chip(clip.team)}{outcome_chip(clip.outcome)}',
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Preparing video (first time only)..."):
            playable = media.convert_for_browser(clip.path)
    except Exception as e:
        st.error(str(e))
        playable = None
    if playable:
        try:
            st.video(str(playable), autoplay=True)
        except TypeError:                              # older Streamlit has no autoplay argument
            st.video(str(playable))

    info = media.info_of(clip.path)
    st.caption(f"Build-up {clip.buildup_id}, {media.fmt_duration(info['duration'])} long, "
               f"{config.OUTCOMES[clip.outcome]['detail'].lower()}.")

    text = load_explanations().get(clip.stem)
    st.markdown("**Explanation**")
    if text:
        st.write(text)
    else:
        st.caption("No written explanation for this clip yet.")

    left, mid, right = st.columns([1, 2, 1])
    left.button("Previous", on_click=_step, args=(-1,), **STRETCH, disabled=len(paths) < 2)
    mid.markdown(f'<div class="clip-meta" style="text-align:center;padding-top:.5rem">'
                 f'{st.session_state["_dlg_idx"] + 1} of {len(paths)}</div>', unsafe_allow_html=True)
    right.button("Next", on_click=_step, args=(1,), **STRETCH, disabled=len(paths) < 2)


def _open(paths: list[str], idx: int) -> None:
    st.session_state["_dlg_paths"] = paths
    st.session_state["_dlg_idx"] = idx
    player_dialog()


# ------------------------------------------------------------------ views
def _grid(page: list[Clip], playlist: list[str], offset: int) -> None:
    for r in range(0, len(page), GRID_COLS):
        cols = st.columns(GRID_COLS)
        for col, clip in zip(cols, page[r:r + GRID_COLS]):
            with col, st.container(border=True):
                _thumb(clip)
                team = config.TEAMS.get(clip.team, {}).get("short", clip.team)
                st.markdown(
                    f'<div class="clip-title">{team}, {clip.time_label}</div>'
                    f'{team_chip(clip.team)}{outcome_chip(clip.outcome)}'
                    f'<div class="clip-meta">Build-up {clip.buildup_id}, {_duration(clip)}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Play clip", key=f"open_g_{clip.stem}_{clip.outcome}", **STRETCH):
                    _open(playlist, playlist.index(clip.path.as_posix()))


def _list(page: list[Clip], playlist: list[str], offset: int) -> None:
    for clip in page:
        with st.container(border=True):
            a, b, c = st.columns([1.3, 4, 1.2], vertical_alignment="center")
            with a:
                _thumb(clip)
            with b:
                team = config.TEAMS.get(clip.team, {}).get("name", clip.team)
                st.markdown(
                    f'<div class="row-title">{team}, {clip.time_label}</div>'
                    f'{team_chip(clip.team)}{outcome_chip(clip.outcome)}'
                    f'<div class="clip-meta">Build-up {clip.buildup_id}, {_duration(clip)}, {clip.size_mb:.0f} MB</div>',
                    unsafe_allow_html=True,
                )
            with c:
                if st.button("Play clip", key=f"open_l_{clip.stem}_{clip.outcome}", **STRETCH):
                    _open(playlist, playlist.index(clip.path.as_posix()))


# ------------------------------------------------------------------ tab
def render() -> None:
    clips, missing, bad = scan_clips()
    for m in missing:
        st.error(f"Folder not found: `{m}`. Check `CLIP_FOLDERS` in config.py.")
    if bad:
        st.warning(f"{len(bad)} file(s) skipped because the name does not look like `b119_BAR_32-26.mp4`: {', '.join(bad[:5])}")
    if not clips:
        st.markdown('<div class="empty">No clips found yet.</div>', unsafe_allow_html=True)
        return

    # counts
    cols = st.columns(5)
    counts = [
        (len(clips), "clips"),
        (sum(c.outcome == "kept" for c in clips), "kept the ball"),
        (sum(c.outcome == "lost" for c in clips), "lost the ball"),
        (sum(c.team == "BAR" for c in clips), "Barcelona"),
        (sum(c.team == "ATM" for c in clips), "Atlético Madrid"),
    ]
    for col, (n, label) in zip(cols, counts):
        col.markdown(stat(n, label), unsafe_allow_html=True)
    st.write("")

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
            st.rerun()
        if p3.button("Next page", disabled=page_no >= pages, **STRETCH):
            st.session_state["page"] = page_no + 1
            st.rerun()

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
            st.rerun()
        if st.button("Rescan folders"):
            scan_clips.clear()
            st.rerun()
