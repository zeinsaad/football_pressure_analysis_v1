"""
RenderPipeline: walks the source video frame-by-frame, pulls the finalized
tracking data (tracks + ball + locked classes) and team assignment for each
frame, calls annotation.annotate_frame, and writes the annotated video.

Usage:

    from render import RenderConfig, RenderPipeline

    pipeline = RenderPipeline(RenderConfig())
    pipeline.render(
        tracking_cache=tracking_cache,
        locked_class_by_id=locked_class_by_id,
        team_by_id=team_assignment["team_by_id"],
        ball_carrier_cache=ball_carrier_cache,
    )
"""

from __future__ import annotations

import os
import subprocess

import cv2
import imageio_ffmpeg

from .config import RenderConfig
from annotation import annotate_frame


class RenderPipeline:
    def __init__(self, config: RenderConfig):
        self.config = config

    def render(
        self,
        tracking_cache: dict,
        locked_class_by_id: dict,
        team_by_id: dict,
        ball_carrier_cache: dict | None = None,
        video_path: str | None = None,
        output_path: str | None = None,
        force_rerender: bool = False,
    ) -> str:
        """Renders the annotated video and returns the output path. Skips
        rendering (and returns immediately) if output_path already exists,
        unless force_rerender=True.

        Internally writes frames with OpenCV's mp4v codec (always available,
        no missing-codec surprises), then transcodes to H.264 as a final
        step -- mp4v is a completely valid video file, but it's MPEG-4
        Part 2, which browsers refuse to play through an HTML5 <video> tag
        (the file just shows as broken/blank in something like Streamlit's
        st.video, even though VLC/ffplay open it fine). This is invisible
        to callers -- output_path is always the browser-playable H.264 file;
        the intermediate mp4v file is a temp artifact that gets deleted."""
        cfg = self.config
        video_path = video_path or cfg.video_path
        output_path = output_path or cfg.output_video_path

        if os.path.exists(output_path) and not force_rerender:
            print(f"✅ Annotated video already exists at '{output_path}' — skipping render.")
            return output_path

        cap = cv2.VideoCapture(video_path)
        assert cap.isOpened(), f"Could not open video: {video_path}"

        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        raw_path = output_path + ".raw.mp4"
        writer = cv2.VideoWriter(raw_path, cv2.VideoWriter_fourcc(*cfg.fourcc), fps, (w, h))

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            data = tracking_cache.get(frame_idx, {"ball": None, "tracks": []})

            carrier_entry = ball_carrier_cache.get(frame_idx) if ball_carrier_cache else None
            carrier_track_id = carrier_entry["track_id"] if carrier_entry else None

            annotate_frame(
                frame,
                tracks=data.get("tracks", []),
                ball_det=data.get("ball"),
                locked_class_by_id=locked_class_by_id,
                team_by_id=team_by_id,
                show_frame_number=frame_idx if cfg.show_frame_number else None,
                carrier_track_id=carrier_track_id,
                frame_idx=frame_idx,
            )

            writer.write(frame)
            if frame_idx % cfg.log_every_n_frames == 0:
                print(f"rendered {frame_idx}/{total}")
            frame_idx += 1

        cap.release()
        writer.release()

        self._transcode_to_h264(raw_path, output_path, fps)
        os.remove(raw_path)

        print(f"\nDone. Annotated video saved to '{output_path}' ({frame_idx} frames).")
        return output_path

    def _transcode_to_h264(self, raw_path: str, final_path: str, fps: float) -> None:
        """imageio_ffmpeg bundles a static ffmpeg binary, so this works the
        same on Windows/Kaggle/Colab with no separate ffmpeg install.
        -movflags +faststart moves the moov atom to the front of the file
        so browsers (and Streamlit's st.video) can start playback before
        the whole file has downloaded."""
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe, "-y", "-i", raw_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            final_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg transcode to H.264 failed:\n{result.stderr[-2000:]}")