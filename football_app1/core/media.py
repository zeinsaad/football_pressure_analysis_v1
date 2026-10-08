"""Video helpers: codec check, browser-friendly conversion, thumbnails, basic info.

Browsers only play H.264 (avc1) in MP4. Clips written by OpenCV with the "mp4v" codec
open in VLC but show a blank player in a browser, so they are converted once with ffmpeg
and the result is cached in CACHE_DIR.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import streamlit as st

import config

try:
    import cv2
except ImportError:  # the app still works, just without thumbnails / codec detection
    cv2 = None

BROWSER_CODECS = {"avc1", "h264", "x264", "avc3"}


# ------------------------------------------------------------------ ffmpeg
def ffmpeg_exe() -> Optional[str]:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _key(path: Path, extra: str = "") -> str:
    s = path.stat()
    raw = f"{path.resolve()}|{s.st_mtime_ns}|{s.st_size}|{extra}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ------------------------------------------------------------------ info
@st.cache_data(show_spinner=False)
def video_info(path_str: str, mtime: float) -> dict:
    """Codec, duration, resolution, size. `mtime` only exists to invalidate the cache."""
    p = Path(path_str)
    info = dict(codec="unknown", duration=None, width=None, height=None, fps=None,
                size_mb=round(p.stat().st_size / 1e6, 1))
    if cv2 is None:
        return info
    cap = cv2.VideoCapture(path_str)
    try:
        if cap.isOpened():
            fcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            info["codec"] = fcc.to_bytes(4, "little").decode(errors="ignore").strip().lower() or "unknown"
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            info.update(fps=round(fps, 2) if fps else None,
                        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None,
                        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None,
                        duration=(n / fps) if fps and n else None)
    finally:
        cap.release()
    return info


def info_of(path: Path) -> dict:
    return video_info(str(path), path.stat().st_mtime)


def is_browser_ready(path: Path) -> bool:
    return info_of(path)["codec"] in BROWSER_CODECS


# ------------------------------------------------------------------ conversion
DEFAULT_CRF = 23


def web_copy_path(src: Path, max_height: Optional[int] = None, crf: int = DEFAULT_CRF) -> Path:
    extra = str(max_height) if crf == DEFAULT_CRF else f"{max_height}_crf{crf}"      # clips keep their existing cache names
    return config.CACHE_DIR / "web" / f"{src.stem}_{_key(src, extra)}.mp4"


def cached_web_copy(src: Path, max_height: Optional[int] = None, crf: int = DEFAULT_CRF) -> Optional[Path]:
    """Path to the playable file if it already exists (the original if it is already H.264)."""
    if max_height is None and is_browser_ready(src):
        return src
    dst = web_copy_path(src, max_height, crf)
    return dst if dst.exists() else None


def convert_for_browser(src: Path, max_height: Optional[int] = None,
                        on_progress: Optional[Callable[[float], None]] = None, crf: int = DEFAULT_CRF) -> Path:
    """H.264 + faststart copy of `src`, optionally capped at `max_height` pixels. Cached."""
    ready = cached_web_copy(src, max_height, crf)
    if ready:
        return ready
    exe = ffmpeg_exe()
    if exe is None:
        raise RuntimeError("ffmpeg was not found. Run:  pip install imageio-ffmpeg")

    dst = web_copy_path(src, max_height, crf)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part.mp4")
    duration = info_of(src)["duration"]

    cmd = [exe, "-y", "-loglevel", "error", "-i", str(src), "-map", "0:v:0", "-map", "0:a?"]
    if max_height:
        cmd += ["-vf", f"scale=-2:'min({max_height},ih)'"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(tmp)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if on_progress and duration and line.startswith("out_time_us="):
            try:
                on_progress(min(int(line.split("=")[1]) / 1e6 / duration, 1.0))
            except ValueError:
                pass
    _, err = proc.communicate()
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed: {err.strip()[-400:]}")
    tmp.replace(dst)
    if on_progress:
        on_progress(1.0)
    return dst


# ------------------------------------------------------------------ thumbnails
def thumbnail(path: Path, at: float = 0.35, width: int = 560) -> Optional[Path]:
    """JPEG still taken `at` (0-1) of the way through the clip. Cached; None if it cannot be made."""
    if cv2 is None:
        return None
    out = config.CACHE_DIR / "thumbs" / f"{path.stem}_{_key(path)}.jpg"
    if out.exists():
        return out
    cap = cv2.VideoCapture(str(path))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * at))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        return None
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return out


def fmt_duration(seconds: Optional[float]) -> str:
    if not seconds:
        return "-"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"
