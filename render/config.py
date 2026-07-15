"""
Render configuration. Paths come from the project-root paths.py — fill
them in there, not here.
"""

from dataclasses import dataclass

try:
    from paths import VIDEO_PATH, TRACKING_CACHE_PATH, OUTPUT_VIDEO_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in VIDEO_PATH / TRACKING_CACHE_PATH / OUTPUT_VIDEO_PATH "
          "in the project-root paths.py.")
    VIDEO_PATH = ""
    TRACKING_CACHE_PATH = ""
    OUTPUT_VIDEO_PATH = ""


@dataclass
class RenderConfig:
    video_path: str = VIDEO_PATH
    tracking_cache_path: str = TRACKING_CACHE_PATH   # only used if pipeline.run() is called standalone
    output_video_path: str = OUTPUT_VIDEO_PATH

    show_frame_number: bool = False
    log_every_n_frames: int = 200
    fourcc: str = "mp4v"
