# ============================================================================================
# inspect_caches.py -- look inside the 4 caches before annotating ball + ball carrier.
#   python inspect_caches.py          (paste the whole printed output back)
# Prints the structure of each file, then 4 checks:
#   1) frame alignment between the caches
#   2) ball cache: how many frames have a ball, which fields / statuses
#   3) carrier cache: do its carrier ids exist in the NEW match cache at the same frame?
#      (if it was computed on an older tracking, the ids will not match -> it must be remapped or recomputed)
#   4) homography: do players' feet land inside the pitch? (decides whether to use it)
# ============================================================================================
import io
import os
import pickle
from collections import Counter

import numpy as np

BASE = r"C:\Users\user\Desktop\Football_cv_project\football-pipeline (1)\project\barca_atletico_first_half\new_cache"
PATHS = {
    "match":      os.path.join(BASE, "barca_atletico_match_cache.pkl"),
    "ball":       os.path.join(BASE, "barca_atletico_first_half_ball_tracked_cache.pkl"),
    "carrier":    os.path.join(BASE, "barca_atletico_first_half_ball_carrier_cache.pkl"),
    "homography": os.path.join(BASE, "homography_cache_barca_atletico_firsthalf.pkl"),
}
PX_PER_METER = 10


class _Compat(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith("numpy._core"):
            module = module.replace("numpy._core", "numpy.core", 1)
        return super().find_class(module, name)


def load(p):
    with open(p, "rb") as fh:
        b = fh.read()
    try:
        return pickle.loads(b)
    except ModuleNotFoundError:
        return _Compat(io.BytesIO(b)).load()


def short(v, n=160):
    s = repr(v)
    return s if len(s) <= n else s[:n] + " ..."


def describe(obj, name="root", depth=0, max_depth=4):
    pad = "  " * depth
    if isinstance(obj, dict):
        keys = list(obj.keys())
        kt = Counter(type(k).__name__ for k in keys)
        print(f"{pad}{name}: dict, {len(obj)} keys {dict(kt)} | first keys: {short(keys[:8], 120)}")
        if depth >= max_depth:
            return
        if len(obj) > 50 and all(isinstance(k, (int, np.integer)) for k in keys[:50]):   # frame-indexed
            nn = [k for k in keys if obj[k] not in (None, [], {})]
            print(f"{pad}  (frame-indexed: {len(nn)} non-empty, frames {min(keys)}..{max(keys)})")
            for k in nn[:1] + nn[len(nn) // 2:len(nn) // 2 + 1]:
                describe(obj[k], f"[{k}]", depth + 1, max_depth)
        else:
            for k in keys[:12]:
                describe(obj[k], f"[{k!r}]", depth + 1, max_depth)
    elif isinstance(obj, (list, tuple)):
        print(f"{pad}{name}: {type(obj).__name__}, len {len(obj)}")
        if depth < max_depth and len(obj):
            nn = [i for i, v in enumerate(obj) if v is not None]
            print(f"{pad}  ({len(nn)} non-None)") if len(obj) > 50 else None
            for i in (nn[:1] + nn[len(nn) // 2:len(nn) // 2 + 1] if len(obj) > 50 else range(min(len(obj), 3))):
                describe(obj[i], f"[{i}]", depth + 1, max_depth)
    elif isinstance(obj, np.ndarray):
        print(f"{pad}{name}: ndarray {obj.shape} {obj.dtype} | {short(obj.ravel()[:6].tolist(), 100)}")
    elif hasattr(obj, "shape") and hasattr(obj, "columns"):
        print(f"{pad}{name}: DataFrame {obj.shape} | columns {list(obj.columns)}")
        print(obj.head(3).to_string())
    else:
        print(f"{pad}{name}: {type(obj).__name__} = {short(obj)}")


def frame_map(obj):
    """Find the frame-indexed part of a cache: returns (path, mapping) or (None, None)."""
    if isinstance(obj, dict) and len(obj) > 1000 and all(isinstance(k, (int, np.integer)) for k in list(obj)[:50]):
        return "root", obj
    if isinstance(obj, (list, tuple)) and len(obj) > 1000:
        return "root(list)", dict(enumerate(obj))
    if isinstance(obj, dict):
        for k, v in obj.items():
            p, m = frame_map(v)
            if m is not None:
                return f"[{k!r}]" + ("" if p.startswith("root") else p), m
    return None, None


data = {}
for k, p in PATHS.items():
    print("\n" + "=" * 100 + f"\n{k.upper()}: {p}")
    if not os.path.exists(p):
        print("  MISSING"); continue
    data[k] = load(p)
    print(f"  size {os.path.getsize(p) / 1e6:.1f} MB")
    describe(data[k])

print("\n" + "=" * 100 + "\nCHECKS")
tc = data["match"]["tracking_cache"] if "match" in data else {}
pinfo = data.get("match", {}).get("player_info", {})

# 1) frame alignment
for k in ("ball", "carrier"):
    if k in data:
        path, fm = frame_map(data[k])
        print(f"1) {k}: frame map at {path} -> {len(fm) if fm else 0} entries"
              + (f", frames {min(fm)}..{max(fm)} (match cache {min(tc)}..{max(tc)})" if fm else ""))

# 2) ball
if "ball" in data:
    path, fm = frame_map(data["ball"])
    if fm:
        vals = [v for v in fm.values() if v not in (None, [], {})]
        print(f"2) ball: {len(vals)} / {len(fm)} frames with a ball entry")
        if vals and isinstance(vals[0], dict):
            fields = Counter(k for v in vals[:5000] for k in v)
            print(f"   fields: {dict(fields)}")
            for key in ("status", "source", "state", "low_confidence", "is_interpolated", "smoothed"):
                if key in fields:
                    print(f"   {key}: {dict(Counter(str(v.get(key)) for v in vals))}")
    # ball also stored inside the match cache?
    nb = sum(1 for d in tc.values() if d.get("ball"))
    print(f"   (match cache has its own 'ball' on {nb} frames)")

# 3) carrier ids vs the new match cache
if "carrier" in data:
    path, fm = frame_map(data["carrier"])
    if fm:
        def carrier_id(v):
            if isinstance(v, (int, np.integer)):
                return int(v)
            if isinstance(v, dict):
                for key in ("carrier_track_id", "carrier_id", "current_carrier", "carrier", "track_id", "player_id"):
                    if key in v and isinstance(v[key], (int, np.integer)):
                        return int(v[key])
            return None
        ids = {f: carrier_id(v) for f, v in fm.items()}
        has = {f: c for f, c in ids.items() if c is not None and c >= 0}
        print(f"3) carrier: {len(has)} / {len(fm)} frames with a carrier id "
              f"(field guessed from: {list(next(iter(fm.values())).keys()) if isinstance(next(iter(fm.values())), dict) else type(next(iter(fm.values()))).__name__})")
        ok = sum(1 for f, c in has.items() if any(t["track_id"] == c for t in tc.get(int(f), {}).get("tracks", [])))
        print(f"   carrier id present in the NEW match cache at the same frame: {ok}/{len(has)} "
              f"({ok / max(len(has), 1):.1%})  -> ~100% = same ids, low = computed on an older tracking")
        top = Counter(has.values()).most_common(12)
        print("   most frequent carrier ids:", [(c, n, pinfo.get(c, {}).get("name", "NOT IN MATCH CACHE")) for c, n in top])

# 4) homography sanity: feet of players projected to the pitch
if "homography" in data:
    import cv2
    hc = data["homography"]
    get = (lambda f: hc.get(f)) if isinstance(hc, dict) else (lambda f: hc[f] if 0 <= f < len(hc) else None)
    n_h = len(hc)
    valid = sum(1 for f in (hc if isinstance(hc, dict) else range(n_h)) if get(f) is not None)
    inside, total, frames_used = 0, 0, 0
    for f in list(tc)[::200]:
        H = get(f)
        if H is None:
            continue
        frames_used += 1
        for t in tc[f]["tracks"]:
            x1, y1, x2, y2 = t["bbox"]
            p = cv2.perspectiveTransform(np.array([[[(x1 + x2) / 2, y2]]], np.float32), np.asarray(H, np.float64)).reshape(2)
            x, y = p / PX_PER_METER
            total += 1
            inside += (-5 <= x <= 110) and (-5 <= y <= 73)
    print(f"4) homography: {valid}/{n_h} frames valid | feet inside the pitch (+5 m margin): "
          f"{inside}/{total} ({inside / max(total, 1):.1%}) over {frames_used} sampled frames")
    print("   >90% = usable for pitch features (e.g. a minimap); much lower = skip it, the annotation does not need it")