"""Writes data/stats/cards/<n>.jpg: the 'pitch grid' real frame of every player, with the pressing-seconds text replaced.

Run from the project root after export_stats.py:  python tools/make_player_cards.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent / "data" / "stats"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:                                   # on Windows fall back to Segoe UI
        return ImageFont.truetype("segoeui.ttf", size)


def main() -> None:
    data = json.loads((ROOT / "stats.json").read_text(encoding="utf-8"))
    sec = next(s for s in data["sections"] if s["id"] == "m16")
    rows = {r[1]: r for r in sec["tables"][0]["rows"]}
    hdr = sec["tables"][0]["header"]
    out = ROOT / "cards"; out.mkdir(exist_ok=True)
    g2 = next(g for g in sec["frame_groups"] if g["id"] == "g2")
    for f in g2["frames"]:
        r = dict(zip(hdr, rows[f["player"]]))
        v = lambda k: f'{float(r[k]):.0f}%'
        im = Image.open(ROOT / f["file"]).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((8, 8, 668, 156), 10, fill=(16, 21, 31))
        d.text((26, 22), f'{f["team"]} {f["player"]}: where he presses', font=font(BOLD, 22), fill=(255, 255, 255))
        d.text((26, 62), f'middle third: left {v("mid_left")} | centre {v("mid_centre")} | right {v("mid_right")}', font=font(FONT, 18), fill=(232, 237, 245))
        d.text((26, 90), f'attacking third: left {v("att_left")} | centre {v("att_centre")} | right {v("att_right")}', font=font(FONT, 18), fill=(232, 237, 245))
        d.text((26, 124), "cells outside the camera view are not drawn", font=font(FONT, 14), fill=(141, 154, 179))
        im.save(out / Path(f["file"]).name, quality=88)
    print("wrote", len(g2["frames"]), "frames to", out)


if __name__ == "__main__":
    main()
