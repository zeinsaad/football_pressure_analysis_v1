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
        track_team_segments=team_assignment["track_team_segments"],
        team_colors=team_assignment["team_colors"],
        ball_carrier_cache=ball_carrier_cache,
    )

Team resolution: team_by_id alone is a flat, lossy fallback -- wrong for
roughly half the frames of any track flagged in the team assigner's
switch_suspects. track_team_segments is the real per-window history; render
resolves each track's team PER FRAME via team_for_track_at_frame, not once
per track, so a switch_suspect track visibly shows the correct color at
each point in the video instead of one (possibly wrong, for part of its
life) team throughout.

Team colors: team_colors is the team assigner's auto-detected real average
kit color per cluster (extracted from calibration torso-crop pixels), not
a hardcoded guess -- passed straight through to annotate_frame so colors
always match each team's real kit regardless of which numeric cluster
label KMeans happened to assign that run.
"""

from __future__ import annotations

import os
import subprocess

import cv2
import imageio_ffmpeg
from tqdm.auto import tqdm

from .config import RenderConfig
from annotation import annotate_frame
from team_assigner import team_for_track_at_frame


class RenderPipeline:
    def __init__(self, config: RenderConfig):
        self.config = config

    def render(
        self,
        tracking_cache: dict,
        locked_class_by_id: dict,
        team_by_id: dict,
        track_team_segments: dict | None = None,
        team_colors: dict | None = None,
        ball_carrier_cache: dict | None = None,
        video_path: str | None = None,
        output_path: str | None = None,
        force_rerender: bool = False,
    ) -> str:
        """Renders the annotated video and returns the output path. Skips
        rendering (and returns immediately) if output_path already exists,
        unless force_rerender=True.

        track_team_segments (optional but strongly recommended): the team
        assigner's per-window team history. When provided, each track's
        team color is resolved per-frame via team_for_track_at_frame
        instead of the flat team_by_id lookup, so switch_suspect tracks
        render correctly on both sides of a flip. If omitted (e.g. an
        older team assignment cache with no segments), falls back to
        team_by_id for every track -- same behavior as before this fix,
        with the same lossiness for any flip track.

        team_colors (optional): the team assigner's auto-detected real kit
        color per cluster label. If omitted, annotate_frame falls back to
        its own module-level default palette.

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

        if track_team_segments is None:
            print("⚠️ No track_team_segments provided -- falling back to flat team_by_id "
                  "for every track. Any track flagged in the team assigner's switch_suspects "
                  "will render with the wrong color for part of its life.")
        if team_colors is None:
            print("⚠️ No team_colors provided -- falling back to annotation.py's default palette.")

        cap = cv2.VideoCapture(video_path)
        assert cap.isOpened(), f"Could not open video: {video_path}"

        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        raw_path = output_path + ".raw.mp4"
        writer = cv2.VideoWriter(raw_path, cv2.VideoWriter_fourcc(*cfg.fourcc), fps, (w, h))

        frame_idx = 0
        with tqdm(total=total, desc="Rendering annotated video", unit="frame") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                data = tracking_cache.get(frame_idx, {"ball": None, "tracks": []})

                carrier_entry = ball_carrier_cache.get(frame_idx) if ball_carrier_cache else None
                carrier_track_id = carrier_entry["track_id"] if carrier_entry else None

                # Resolve team PER FRAME for only the tracks present this frame --
                # annotate_frame expects a flat team_by_id dict, so this builds a
                # frame-scoped snapshot from track_team_segments (falling back to
                # the flat team_by_id if segments weren't provided at all).
                frame_team_by_id = {}
                for t in data.get("tracks", []):
                    tid = t["track_id"]
                    if track_team_segments is not None:
                        team = team_for_track_at_frame(
                            track_team_segments, tid, frame_idx, default=team_by_id.get(tid)
                        )
                    else:
                        team = team_by_id.get(tid)
                    if team is not None:
                        frame_team_by_id[tid] = team

                annotate_frame(
                    frame,
                    tracks=data.get("tracks", []),
                    ball_det=data.get("ball"),
                    locked_class_by_id=locked_class_by_id,
                    team_by_id=frame_team_by_id,
                    #team_colors=team_colors,
                    team_colors={0: (179, 0, 0), 1: (110, 238, 255)},
                    show_frame_number=frame_idx if cfg.show_frame_number else None,
                    carrier_track_id=carrier_track_id,
                    frame_idx=frame_idx,
                )

                writer.write(frame)
                frame_idx += 1
                pbar.update(1)

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
