"""Export the stats notebook into the folder the app's "Stats" tab reads (data/stats/).

Run it again whenever you re-run the notebook (the notebook must be saved WITH its outputs):

    python tools/export_stats.py "path/to/pressure_stats_metrics_frames_only.ipynb"

Writes, next to the app:
    data/stats/stats.json        every section: definition, tables, key findings, figures, real-frame captions
    data/stats/frames/*.jpg      the real photo frames (1600 px wide JPEG, much smaller than the notebook PNGs)
    data/stats/thumbs/*.jpg      grid thumbnails of the same frames
    data/stats/figures/*.png     the matplotlib charts (heatmaps, grids, time series)
    data/stats/csv/*.csv         every table as CSV
Needs only Pillow (already installed with Streamlit). Nothing here touches the match video.
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
import datetime as dt
import io
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

FRAME_W, THUMB_W = 1600, 720
TEAM_CODES = {"BAR", "ATM"}

# which tab of the app a section belongs to
GROUP_OF = {"2": "pressing", "3": "pressing", "4": "pressing", "5": "pressing", "7": "pressing", "12": "pressing", "13": "pressing", "14": "pressing",
            "1": "shape", "9": "shape", "10": "shape", "11": "shape",
            "6": "passing", "8": "passing", "8b": "passing",
            "15": "players", "16": "players"}

# captions for tables that the notebook does not label itself (in the order the tables appear)
TABLE_CAPTIONS = {
    "1": ["Back-three depth while out of possession"], "2": ["Pressing intensity by team"], "3": ["Pressure frames by third"],
    "4": ["Heatmap summary by team"], "5": ["Pressing % in each 5-minute block"], "6": ["PPDA by team (own third excluded)"],
    "7": ["Time-to-press after losing the ball"], "8": ["Pass success rate, under pressure vs not"],
    "8b": ["Pass length and direction by pressure state", "Retention, duel losses counted as failures"],
    "9": ["Line height, outliers removed (1.5 x IQR)"], "10": ["Team compactness out of possession"], "11": ["Compactness while pressing vs not"],
    "12": ["Share of each team's pressure by third and channel"], "13": ["Zone intensity per time in zone"],
    "16": ["Where each player presses (% of his pressing frames)"],
}
FIGURE_CAPTIONS = {
    "m04": ["Pressure density in each team's own attacking direction (both attack left to right)"],
    "m05": ["Pressing intensity per 5-minute block"],
    "m12": ["Third x channel grid: % of each team's pressure frames"],
    "m13": ["Zone intensity: % of ball-in-cell time spent pressing"],
    "m16": ["Barcelona: where each player presses (% of his pressing frames)", "Atletico Madrid: where each player presses (% of his pressing frames)"],
}
FRAME_GROUP_TITLES = [("Metric 17", "On the pitch: share of each player's pressing by zone")]


# ------------------------------------------------------------------ html table -> rows
class _Tbl(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._sec, self._row, self._cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("thead", "tbody"):
            self._sec = tag
        elif tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self._cell = dict(tag=tag, text="", rowspan=int(a.get("rowspan", 1)))

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append(self._cell); self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append((self._sec, self._row)); self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data


def parse_table(html: str) -> dict | None:
    p = _Tbl(); p.feed(html)
    head = [r for s, r in p.rows if s == "thead"]; body = [r for s, r in p.rows if s == "tbody"]
    if not head or not body:
        return None
    n_idx = 0
    for c in body[0]:                                   # leading <th> cells of the first body row = index levels
        if c["tag"] == "th":
            n_idx += 1
        else:
            break
    n_cols = len(head[0]) - n_idx
    cols = [c["text"].strip() for c in head[0][n_idx:]]
    names = [c["text"].strip() for c in head[1][:n_idx]] if len(head) > 1 else [""] * n_idx
    rows, carry = [], {}
    for r in body:
        it, out, pos = iter(r), [], 0
        while pos < n_idx + n_cols:
            if pos in carry:
                txt, left = carry[pos]; out.append(txt)
                if left > 1:
                    carry[pos] = (txt, left - 1)
                else:
                    del carry[pos]
            else:
                c = next(it, None)
                txt = c["text"].strip() if c else ""
                out.append(txt)
                if c and c["rowspan"] > 1:
                    carry[pos] = (txt, c["rowspan"] - 1)
            pos += 1
        rows.append(out)
    return dict(header=names + cols, n_index=n_idx, rows=rows)


# ------------------------------------------------------------------ small helpers
def clean_md(t: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", t.replace("\r\n", "\n")).strip()


def save_jpeg(png_b64: str, out: Path, width: int, quality: int) -> tuple[int, int]:
    im = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return im.size


def save_png(png_b64: str, out: Path) -> tuple[int, int]:
    im = Image.open(io.BytesIO(base64.b64decode(png_b64)))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG", optimize=True)
    return im.size


FRAME_RE = re.compile(r"\*\*Frame\s+(\d+)/(\d+)\*\*:\s*(.*?)\s*\n?`frame\s+(\d+)\s+\(([^)]*)\)`", re.S)


def parse_summary(text: str) -> tuple[list[str], list[dict]]:
    """(notes before SUMMARY, [{text, kind}] after it). Deeper-indented lines continue the bullet above."""
    pre, _, post = text.partition("SUMMARY")
    notes = [l.strip() for l in pre.splitlines() if l.strip()]
    items: list[dict] = []
    for raw in post.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent >= 4 and items:
            items[-1]["text"] += "\n" + line
            continue
        kind = "note" if re.match(r"(CAUTION|NOTE|Wide intervals|There is no baseline|A larger std|If the pressed)", line) else "insight"
        items.append(dict(text=line, kind=kind))
    return notes, items


def parse_setup(text: str) -> dict:
    meta: dict = {}
    if m := re.search(r"([\d.]+) fps \| pitch (\d+) x (\d+) m", text):
        meta.update(fps=float(m[1]), pitch=[int(m[2]), int(m[3])])
    if m := re.search(r"= ([\d.]+) min \| match clock up to ([\d.]+) min", text):
        meta.update(possession_minutes=float(m[1]), match_minutes=float(m[2]))
    if m := re.search(r"out-of-possession frames per team \(def_team\): (\{.*?\})", text):
        meta["out_of_possession_frames"] = ast.literal_eval(m[1])
    if m := re.search(r"zone boundaries.*?: ([\d.]+) ([\d.]+)", text):
        meta["thirds_m"] = [float(m[1]), float(m[2])]
    if m := re.search(r"own-zone pressure not counted.*?(\{.*?\}) frames", text):
        meta["own_third_pressure_not_counted"] = ast.literal_eval(m[1])
    if m := re.search(r"teams: (\{.*?\})", text):
        meta["teams"] = ast.literal_eval(m[1])
    return meta


# ------------------------------------------------------------------ main
def export(nb_path: Path, out: Path) -> None:
    print(f"reading {nb_path} ({nb_path.stat().st_size / 1e6:.0f} MB) ...")
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    for d in ("frames", "thumbs", "figures", "csv"):
        (out / d).mkdir(parents=True, exist_ok=True)

    data = dict(generated=dt.datetime.now().isoformat(timespec="seconds"), source_notebook=nb_path.name, overview_md="", meta={}, sections=[])
    cur, intro, n_fig = None, None, 0

    for cell in nb["cells"]:
        src = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            if src.startswith("# Pressing metrics"):
                data["overview_md"] = clean_md(src)
            elif m := re.match(r"##\s+(\d+b?)\.\s+(.+?)\s*(?:\n|$)", src):
                sid = m[1]
                cur = dict(id=f"m{int(re.sub('b', '', sid)):02d}{'b' if sid.endswith('b') else ''}", number=sid, title=m[2].strip(), group=GROUP_OF.get(sid, "other"),
                           intro_md=clean_md(src[m.end():]), tables=[], figures=[], summary=[], notes=[], frame_groups=[])
                data["sections"].append(cur)
            elif src.startswith("#### Real frames"):
                intro = clean_md(src.split("\n", 1)[1]) if "\n" in src else ""
            continue

        outs = cell.get("outputs", [])
        if cur is None:                                            # setup cells: only the match meta is kept
            for o in outs:
                if o["output_type"] == "stream" and "possession frames" in "".join(o["text"]):
                    data["meta"] = parse_setup("".join(o["text"]))
            continue
        is_frames = any(o["output_type"] == "display_data" and "**Frame" in "".join(o["data"].get("text/markdown", "")) for o in outs)

        if is_frames:
            first = next(("".join(o["text"]) for o in outs if o["output_type"] == "stream"), "")
            m = re.search(r"(Metric \d+ \|[^\n]*?):\s*\d+ real frame", first)
            title = m[1] if m else "Real frames"
            for key, nice in FRAME_GROUP_TITLES:
                if title.startswith(key):
                    title = nice
            if not (m and not intro_used_for(cur, intro)) and title.startswith("Metric"):
                title = "Real frames"
            gid = f"g{len(cur['frame_groups']) + 1}"
            grp = dict(id=gid, title="Real frames" if intro and not title.startswith(("On the pitch",)) else title, intro_md=intro or "", frames=[])
            if title.startswith("On the pitch"):
                grp["intro_md"] = ("Each photo shows the player pressing, with the pitch grid drawn on the grass. "
                                   "Each cell shows the share of that player's pressing frames that happened there (as seen by his own team, attacking the opponent's goal).")
            intro = None
            pending = None
            k = 0
            for o in outs:
                if o["output_type"] != "display_data":
                    continue
                d = o["data"]
                if "text/markdown" in d and "**Frame" in "".join(d["text/markdown"]):
                    pending = FRAME_RE.search("".join(d["text/markdown"]))
                elif "image/png" in d and pending:
                    k += 1
                    base = f"{cur['id']}_{gid}_{k:02d}"
                    save_jpeg(d["image/png"], out / "frames" / f"{base}.jpg", FRAME_W, 82)
                    save_jpeg(d["image/png"], out / "thumbs" / f"{base}.jpg", THUMB_W, 78)
                    cap = pending[3].strip()
                    tm = re.match(r"^(BAR|ATM)\s+([^:]+):", cap)
                    team = tm[1] if tm else next((c for c in re.findall(r"\b(BAR|ATM)\b", cap)), None)
                    grp["frames"].append(dict(file=f"frames/{base}.jpg", thumb=f"thumbs/{base}.jpg", caption=cap, frame=int(pending[4]), clock=pending[5],
                                              team=team, player=tm[2].strip() if tm else None))
                    pending = None
            cur["frame_groups"].append(grp)
            print(f"  m{cur['number']:>3}  {len(grp['frames'])} frames  ({grp['title']})")
            continue

        # tables, figures, text of an ordinary metric cell
        label = None
        for i, o in enumerate(outs):
            t = o["output_type"]
            if t == "stream":
                txt = "".join(o["text"])
                nxt_html = i + 1 < len(outs) and outs[i + 1]["output_type"] in ("display_data", "execute_result") and "text/html" in outs[i + 1]["data"]
                if "SUMMARY" in txt:
                    notes, items = parse_summary(txt)
                    cur["notes"] += notes; cur["summary"] += items
                elif nxt_html and txt.strip():
                    lines = [l.strip() for l in txt.splitlines() if l.strip()]
                    if re.search(r":\s*$", lines[-1]) or re.match(r"^(BAR|ATM)\s+\(", lines[-1]):
                        label = lines[-1]; cur["notes"] += lines[:-1]
                    else:
                        cur["notes"] += lines
                elif txt.strip():
                    cur["notes"] += [l.strip() for l in txt.splitlines() if l.strip()]
            elif t in ("display_data", "execute_result"):
                d = o["data"]
                if "text/html" in d and "<table" in "".join(d["text/html"]):
                    tb = parse_table("".join(d["text/html"]))
                    if tb:
                        idx = len(cur["tables"])
                        caps = TABLE_CAPTIONS.get(cur["number"], [])
                        cap = (re.sub(r":\s*$", "", label) if label else (caps[idx] if idx < len(caps) else None))
                        if cap:
                            cap = re.sub(r"^\d\)\s*", "", cap).strip()
                            cap = re.sub(r"\s{2,}", " ", cap)
                            cap = cap[0].upper() + cap[1:]
                        if len(tb["header"]) > 1 and tb["header"][1] == "all":      # artefact of the notebook's groupby key
                            tb["header"][1] = "scope"
                        tb.update(id=f"{cur['id']}_t{idx + 1}", caption=cap)
                        cur["tables"].append(tb)
                        with open(out / "csv" / f"{tb['id']}.csv", "w", newline="", encoding="utf-8-sig") as f:
                            w = csv.writer(f); w.writerow(tb["header"]); w.writerows(tb["rows"])
                    label = None
                elif "image/png" in d:
                    n_fig += 1
                    name = f"{cur['id']}_f{len(cur['figures']) + 1}.png"
                    save_png(d["image/png"], out / "figures" / name)
                    caps_ = FIGURE_CAPTIONS.get(cur["id"], [])
                    k_ = len(cur["figures"])
                    cur["figures"].append(dict(file=f"figures/{name}", caption=caps_[k_] if k_ < len(caps_) else ""))
        print(f"  m{cur['number']:>3}  {len(cur['tables'])} tables, {len(cur['figures'])} figures, {len(cur['summary'])} findings")

    # sections with the same id appear once per cell: merge them (a metric can have several cells)
    merged: dict[str, dict] = {}
    for s in data["sections"]:
        merged[s["id"]] = s
    data["sections"] = list(merged.values())
    (out / "stats.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n_fr = sum(len(g["frames"]) for s in data["sections"] for g in s["frame_groups"])
    n_tb = sum(len(s["tables"]) for s in data["sections"])
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"\ndone: {len(data['sections'])} sections, {n_tb} tables, {n_fig} figures, {n_fr} frames -> {out} ({size:.1f} MB)")


def intro_used_for(cur, intro):                                    # tiny helper: a frame cell with an intro paragraph is a plain "Real frames" group
    return bool(intro)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("notebook", type=Path, help="the executed stats notebook (.ipynb, saved with outputs)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "stats")
    a = ap.parse_args()
    export(a.notebook, a.out)
