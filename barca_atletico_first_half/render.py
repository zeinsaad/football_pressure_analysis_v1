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

import cv2
from tqdm.auto import tqdm

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

        Writes browser-playable H.264 directly via OpenCV's VideoWriter
        (cfg.fourcc, e.g. 'avc1') -- no intermediate mp4v file, no ffmpeg
        transcode pass. This depends on the local OpenCV build actually
        having H.264 encoder support; if VideoWriter fails to open, this
        raises immediately with a clear error rather than silently writing
        a broken/empty file. If that happens, the previous raw-mp4v +
        ffmpeg-transcode approach is the fallback -- ffmpeg's bundled
        static binary works regardless of the local OpenCV build, at the
        cost of a temp file and a second (invisible-progress) pass."""
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

        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*cfg.fourcc), fps, (w, h))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(
                f"VideoWriter failed to open with fourcc='{cfg.fourcc}' -- this local OpenCV "
                f"build likely lacks H.264 encoder support. Fall back to writing mp4v to a "
                f".raw.mp4 temp file and transcoding with imageio_ffmpeg's bundled ffmpeg "
                f"binary instead (the approach this replaced)."
            )

        frame_idx = 0
        with tqdm(total=total, desc="Rendering annotated video", unit="frame") as pbar:
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
                frame_idx += 1
                pbar.update(1)

        cap.release()
        writer.release()

        print(f"\nDone. Annotated video saved to '{output_path}' ({frame_idx} frames).")
        return output_path