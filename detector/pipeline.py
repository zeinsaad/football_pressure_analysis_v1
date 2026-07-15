"""
DetectionPipeline: loads the two YOLO models and produces per-frame
detections (ball + goalkeeper + player + referee), with the ball sourced
exclusively from the dedicated ball model.

Usage (single frame, e.g. from inside a larger pipeline / main loop):

    from detector import DetectionPipeline, DetectionConfig

    pipeline = DetectionPipeline(DetectionConfig())
    pipeline.load_models()

    dets = pipeline.detect_frame(frame)   # list[dict] for this one frame

Usage (full video -> cache, load-or-build):

    from detector import get_or_build_cache
    detection_cache = get_or_build_cache(pipeline, cfg.video_path, cfg.output_cache_path)
"""

from __future__ import annotations

import os

import cv2
from ultralytics import YOLO

from .config import DetectionConfig
from .geometry import same_class_nms, cross_class_suppress_players
from .ball import process_ball_detections
from .cache_io import save_cache, print_summary


class DetectionPipeline:
    """Two independent YOLO models, fused into one per-frame detection list."""

    def __init__(self, config: DetectionConfig):
        self.config = config
        self.multi_model: YOLO | None = None
        self.ball_model: YOLO | None = None

    # ------------------------------------------------------------------ #
    #  Setup                                                              #
    # ------------------------------------------------------------------ #

    def check_paths(self) -> None:
        """Print OK/MISSING for every configured path. Does not raise."""
        cfg = self.config
        print("Checking paths...")
        for p in [cfg.multi_model_path, cfg.ball_model_path, cfg.video_path]:
            print(p, "->", "OK" if os.path.exists(p) else "MISSING")

    def load_models(self) -> None:
        """Load both YOLO models and validate the multiclass label mapping."""
        cfg = self.config
        self.multi_model = YOLO(cfg.multi_model_path)
        self.ball_model = YOLO(cfg.ball_model_path)

        print("Multiclass model classes:", self.multi_model.names)
        print("Ball model classes:", self.ball_model.names)

        if self.multi_model.names != cfg.multi_class_names:
            print(
                "\n⚠️ WARNING: config.multi_class_names does not match model.names. "
                "Update DetectionConfig.multi_class_names to match exactly before running."
            )
        else:
            print("\n✅ Class mapping matches.")

    # ------------------------------------------------------------------ #
    #  Per-frame detection (the callable used by other pipeline stages)   #
    # ------------------------------------------------------------------ #

    def detect_frame(self, frame) -> list[dict]:
        """
        Run both models on a single frame and return the fused detection list:
        at most one "ball" entry (from the ball model only) plus deduplicated
        goalkeeper/player/referee entries (from the multiclass model only).
        """
        if self.multi_model is None or self.ball_model is None:
            raise RuntimeError("Models not loaded — call load_models() first.")

        cfg = self.config

        # --- multiclass model: goalkeeper / player / referee only ---
        multi_res = self.multi_model.predict(
            frame, conf=cfg.conf_thresh_multi, device=cfg.device, verbose=False
        )[0]

        multi_dets = []
        for box in multi_res.boxes:
            cls_id = int(box.cls[0])
            cls_name = cfg.multi_class_names[cls_id]
            if cls_name == "ball":
                continue  # ball is sourced only from the dedicated ball model

            multi_dets.append({
                "bbox": box.xyxy[0].tolist(),
                "conf": float(box.conf[0]),
                "class": cls_name,
                "source": "multi",
            })

        # --- ball-only model: sole source of ball detections ---
        ball_res = self.ball_model.predict(
            frame, conf=cfg.conf_thresh_ball, device=cfg.device, verbose=False
        )[0]

        ball_model_dets = [
            {
                "bbox": box.xyxy[0].tolist(),
                "conf": float(box.conf[0]),
                "class": "ball",
                "source": "ball_model",
            }
            for box in ball_res.boxes
        ]

        fused_ball = process_ball_detections(ball_model_dets, low_conf_flag=cfg.ball_low_conf_flag)

        non_ball_dets = same_class_nms(multi_dets, iou_thresh=cfg.same_class_nms_iou)
        non_ball_dets = cross_class_suppress_players(non_ball_dets, iou_thresh=cfg.cross_class_iou_thresh)

        return fused_ball + non_ball_dets

    # ------------------------------------------------------------------ #
    #  Full-video run                                                      #
    # ------------------------------------------------------------------ #

    def run_on_video(self, video_path: str | None = None, save_to: str | None = None) -> dict:
        """
        Run detect_frame() over every frame of a video and return the
        frame-indexed detection cache: {frame_idx: [det, det, ...]}.

        If save_to is given, pickles the cache to that path as a side effect.
        """
        cfg = self.config
        video_path = video_path or cfg.video_path

        cap = cv2.VideoCapture(video_path)
        assert cap.isOpened(), f"Could not open video: {video_path}"

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"Video: {total_frames} frames @ {fps:.2f} fps")

        detection_cache: dict[int, list[dict]] = {}
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            dets = self.detect_frame(frame)
            detection_cache[frame_idx] = dets

            if frame_idx % cfg.log_every_n_frames == 0:
                ball_n = sum(1 for d in dets if d["class"] == "ball")
                gk_n = sum(1 for d in dets if d["class"] == "goalkeeper")
                ref_n = sum(1 for d in dets if d["class"] == "referee")
                player_n = sum(1 for d in dets if d["class"] == "player")
                print(f"frame {frame_idx}/{total_frames} | ball:{ball_n} gk:{gk_n} ref:{ref_n} player:{player_n}")

            frame_idx += 1

        cap.release()
        print(f"\nDone. Processed {frame_idx} frames.")

        if save_to:
            save_cache(detection_cache, save_to)
            print_summary(detection_cache)

        return detection_cache
