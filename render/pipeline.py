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
    )
"""

from __future__ import annotations

import os

import cv2

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
        video_path: str | None = None,
        output_path: str | None = None,
        force_rerender: bool = False,
    ) -> str:
        """Renders the annotated video and returns the output path. Skips
        rendering (and returns immediately) if output_path already exists,
        unless force_rerender=True."""
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

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            data = tracking_cache.get(frame_idx, {"ball": None, "tracks": []})

            annotate_frame(
                frame,
                tracks=data.get("tracks", []),
                ball_det=data.get("ball"),
                locked_class_by_id=locked_class_by_id,
                team_by_id=team_by_id,
                show_frame_number=frame_idx if cfg.show_frame_number else None,
            )

            writer.write(frame)
            if frame_idx % cfg.log_every_n_frames == 0:
                print(f"rendered {frame_idx}/{total}")
            frame_idx += 1

        cap.release()
        writer.release()
        print(f"\nDone. Annotated video saved to '{output_path}' ({frame_idx} frames).")
        return output_path
