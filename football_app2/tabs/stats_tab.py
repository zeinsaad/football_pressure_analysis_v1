"""Tab 3: pressing statistics with the real photo frames behind every number."""
from __future__ import annotations

import html

import streamlit as st

import config
from core import stats
from ui.compat import STRETCH, choice
from ui.styles import accent, pretty_teams, short, stat

OVERVIEW_SECTIONS = ["m02", "m14", "m06", "m01", "m10", "m08b"]      # sections whose key findings are repeated on the overview


# ------------------------------------------------------------------ photo viewer
def _fr_step(delta: int) -> None:
    st.session_state["_fr_i"] = (st.session_state["_fr_i"] + delta) % len(st.session_state["_fr_items"])


@st.dialog("Real frame", width="large")
def frame_dialog() -> None:
    items, i = st.session_state["_fr_items"], st.session_state["_fr_i"]
    f = items[i]
    path = stats.asset(f["file"])
    st.markdown(f'<div class="clip-title" style="margin-top:0">{html.escape(pretty_teams(f["caption"]))}</div>'
                f'<span class="fr-clock">{html.escape(f["clock"])}</span><span class="fr-clock">frame {f["frame"]}</span>', unsafe_allow_html=True)
    if path.exists():
        st.image(str(path), **STRETCH)
    else:
        st.warning(f"Image not found: {path}")
    a, b, c = st.columns([1, 2, 1])
    a.button("Previous", key="fr_prev", on_click=_fr_step, args=(-1,), disabled=len(items) < 2, **STRETCH)
    b.markdown(f'<div class="clip-meta" style="text-align:center;padding-top:.5rem">{i + 1} of {len(items)}</div>', unsafe_allow_html=True)
    c.button("Next", key="fr_next", on_click=_fr_step, args=(1,), disabled=len(items) < 2, **STRETCH)


def _gallery(s: dict, g: dict) -> None:
    frames = g["frames"]
    if not frames:
        return
    st.markdown(f'<div class="sub-label">{html.escape(g["title"])} ({len(frames)})</div>', unsafe_allow_html=True)
    if g.get("intro_md"):
        st.caption(pretty_teams(g["intro_md"].replace("**", "")))

    shown = frames
    teams = {f["team"] for f in frames if f["team"]}
    if len(frames) > 6 and len(teams) > 1:
        labels = ["All teams"] + [short(t) for t in stats.TEAM_ORDER if t in teams]
        pick = choice("Team", labels, f"gal_{s['id']}_{g['id']}")
        if pick != "All teams":
            code = next(t for t in stats.TEAM_ORDER if short(t) == pick)
            shown = [f for f in frames if f["team"] == code]

    n = 3 if len(shown) <= 9 else 4
    for r in range(0, len(shown), n):
        for col, (j, f) in zip(st.columns(n), list(enumerate(shown))[r:r + n]):
            with col:
                p = stats.asset(f["thumb"])
                if p.exists():
                    st.image(str(p), **STRETCH)
                st.markdown(f'<div class="fr-cap"><span class="fr-clock">{html.escape(f["clock"])}</span>{html.escape(pretty_teams(f["caption"]))}</div>',
                            unsafe_allow_html=True)
                if st.button("Enlarge", key=f"fr_{s['id']}_{g['id']}_{f['file']}", **STRETCH):
                    st.session_state["_fr_items"], st.session_state["_fr_i"] = shown, j
                    frame_dialog()


# ------------------------------------------------------------------ one metric
def _tables(s: dict) -> None:
    tbs = s["tables"]
    if not tbs:
        return
    def one(tb: dict) -> None:
        if tb.get("caption"):
            st.markdown(f'<div class="tbl-cap">{html.escape(pretty_teams(tb["caption"]))}</div>', unsafe_allow_html=True)
        st.markdown(stats.table_html(tb), unsafe_allow_html=True)
        st.download_button("Download CSV", stats.table_csv(tb), file_name=f'{tb["id"]}.csv', mime="text/csv", key=f'dl_{tb["id"]}')
    first = tbs[0]
    if len(first["rows"]) > 12:
        with st.expander(f'Data table: {first.get("caption") or "all rows"} ({len(first["rows"])} rows)'):
            one(first)
    else:
        one(first)
    if len(tbs) > 1:
        with st.expander(f"More data tables ({len(tbs) - 1})"):
            for tb in tbs[1:]:
                one(tb)


def _findings(s: dict) -> None:
    insights = [i for i in s["summary"] if i["kind"] == "insight"]
    notes = [i for i in s["summary"] if i["kind"] == "note"] 
    if insights:
        st.markdown('<div class="sub-label" style="margin-top:0">Key findings</div>', unsafe_allow_html=True)
        st.markdown("".join(stats.finding_html(i["text"]) for i in insights), unsafe_allow_html=True)
    extra = [pretty_teams(n_) for n_ in s["notes"]] + [pretty_teams(i["text"]) for i in notes]
    if extra:
        st.markdown("".join(f'<div class="finding-note">{html.escape(t)}</div>' for t in extra), unsafe_allow_html=True)


def _section(data: dict, s: dict) -> None:
    with st.container(border=True):
        st.markdown(f'<div class="sec-head"><span class="sec-num">{html.escape(s["number"])}</span>'
                    f'<span class="sec-title">{html.escape(s["title"])}</span></div>', unsafe_allow_html=True)
        lead, rest = stats.split_intro(s["intro_md"])
        if lead:
            st.markdown(stats.md(lead))
        if rest:
            with st.expander("Definition and method"):
                st.markdown(stats.md(rest))

        left, right = st.columns([1.5, 1], gap="large")
        with left:
            for fig in s["figures"]:
                p = stats.asset(fig["file"])
                if p.exists():
                    st.image(str(p), caption=fig.get("caption") or None, **STRETCH)
            _tables(s)
        with right:
            _findings(s)
        for g in s["frame_groups"]:
            _gallery(s, g)
    st.write("")


# ------------------------------------------------------------------ views
def _kpis(data: dict) -> None:
    meta = data.get("meta", {})
    n_frames = sum(len(g["frames"]) for s in data["sections"] for g in s["frame_groups"])
    n_tables = sum(len(s["tables"]) for s in data["sections"])
    episodes = sum(v for t in stats.TEAM_ORDER if (v := stats.value(data, "m14", 0, t, "episodes", {"scope": "all episodes"})) is not None)
    items = [(f'{meta.get("possession_minutes", 0):.0f} min', "of tracked possession"),
             (f"{episodes:.0f}", "pressing episodes"),
             (str(len([s for s in data["sections"] if s["id"] != "m08b"])), "metrics"),
             (str(n_frames), "real photo frames")]
    for col, (n, label) in zip(st.columns(4), items):
        col.markdown(stat(n, label), unsafe_allow_html=True)
    st.write("")


def _overview(data: dict) -> None:
    meta = data.get("meta", {})
    bits = []
    if meta.get("possession_minutes"):
        bits.append(f'{meta["possession_minutes"]:.1f} min of possession tracked (match clock up to {meta.get("match_minutes", 0):.1f} min)')
    if meta.get("fps"):
        bits.append(f'{meta["fps"]:.0f} fps')
    if meta.get("pitch"):
        bits.append(f'pitch {meta["pitch"][0]} x {meta["pitch"][1]} m')
    own = meta.get("own_third_pressure_not_counted")
    if own:
        bits.append("pressure in a team's own third is not counted as pressing")
    if bits:
        st.markdown(f'<div class="stats-meta">{html.escape(" · ".join(bits))}</div>', unsafe_allow_html=True)

    panel = stats.vs_panel_html(data)
    if panel:
        st.markdown(panel, unsafe_allow_html=True)
    st.write("")

    st.markdown('<div class="section-label">What the numbers say</div>', unsafe_allow_html=True)
    secs = [s for sid in OVERVIEW_SECTIONS if (s := stats.section(data, sid)) and any(i["kind"] == "insight" for i in s["summary"])]
    for r in range(0, len(secs), 2):
        for col, s in zip(st.columns(2, gap="large"), secs[r:r + 2]):
            with col:
                st.markdown(f'<div class="analysis-h">{html.escape(s["number"])}. {html.escape(s["title"])}</div>', unsafe_allow_html=True)
                st.markdown("".join(stats.finding_html(i["text"]) for i in s["summary"] if i["kind"] == "insight"), unsafe_allow_html=True)
    st.caption("Open a topic above to see the tables and the real frames behind each number.")


def _method(data: dict) -> None:
    st.markdown('<div class="section-label">How to read these numbers</div>', unsafe_allow_html=True)
    text = stats.method_md(data)
    if text:
        st.markdown(stats.md(text))
    st.markdown('<div class="section-label">Download</div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    a.download_button("All tables (CSV, zip)", stats.csv_zip(data), file_name="barca_atletico_pressing_tables.zip", mime="application/zip", **STRETCH)
    b.download_button("Key findings (text)", stats.findings_text(data), file_name="barca_atletico_key_findings.txt", mime="text/plain", **STRETCH)
    c.download_button("Everything (JSON)", stats.STATS_JSON.read_bytes(), file_name="stats.json", mime="application/json", **STRETCH)
    st.caption(f'Exported from `{data.get("source_notebook", "the stats notebook")}` on {data.get("generated", "")[:10]}. '
               "Run `python tools/export_stats.py <notebook>` after re-running the notebook to refresh this tab.")


def render() -> None:
    data = stats.load_stats()
    if data is None:
        st.markdown('<div class="empty">No statistics exported yet.<br>Run <code>python tools/export_stats.py &lt;notebook.ipynb&gt;</code> '
                    f'and reload. Expected file: <code>{html.escape(str(stats.STATS_JSON))}</code></div>', unsafe_allow_html=True)
        return
    _kpis(data)
    label = choice("Topic", [l for _, l in stats.GROUPS], "stats_view")
    gid = next(k for k, l in stats.GROUPS if l == label)
    st.write("")
    if gid == "overview":
        _overview(data)
    elif gid == "method":
        _method(data)
    else:
        secs = [s for s in data["sections"] if s["group"] == gid]
        if not secs:
            st.markdown('<div class="empty">Nothing in this topic.</div>', unsafe_allow_html=True)
        for s in secs:
            _section(data, s)
