"""
Runs the initial tracking stage using BoT-SORT and the fine-tuned OSNet ReID
model. This stage performs a single forward pass over the video and records the
raw tracking results (track ID, bounding box, confidence, class, and embedding)
for each frame. No identity correction or track linking is performed here;
those steps are handled later in the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from boxmot import BoTSORT

from .config import TrackingConfig


# Create and configure the BoT-SORT tracker using the parameters defined in
# TrackingConfig, then initialize it on the selected CPU or GPU device.
def build_tracker(config: TrackingConfig) -> BoTSORT:
    device_str = "cpu" if config.device == "cpu" else str(config.device)
    tracker = BoTSORT(
        model_weights=Path(config.osnet_weights_path),
        device=device_str,
        fp16=False,
        track_high_thresh=config.track_high_thresh,
        track_low_thresh=config.track_low_thresh,
        new_track_thresh=config.new_track_thresh,
        track_buffer=config.track_buffer,
        match_thresh=config.match_thresh,
        proximity_thresh=config.proximity_thresh,
        appearance_thresh=config.appearance_thresh,
        cmc_method=config.cmc_method,
        frame_rate=config.frame_rate,
    )
    print(f"BoT-SORT initialized on device='{device_str}'.")
    return tracker


# Process every video frame with BoT-SORT and store the raw tracking output.
# For each tracked object, record its raw track ID, bounding box, confidence,
# detected class, and appearance embedding for use in later processing stages.
def run_raw_tracking(tracker: BoTSORT, detection_cache: dict, video_path: str, config: TrackingConfig) -> dict:
    """Returns raw_tracks_by_frame: {frame_idx: [{"raw_track_id", "bbox", "conf", "class", "embedding"}]}"""
    raw_tracks_by_frame: dict[int, list[dict]] = {}

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"Could not open video: {video_path}"
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_dets = detection_cache.get(frame_idx, [])
        person_dets = [d for d in frame_dets if d["class"] in config.class_to_id]

        dets_array = (
            np.array(
                [[*d["bbox"], d["conf"], config.class_to_id[d["class"]]] for d in person_dets],
                dtype=np.float64,
            )
            if person_dets else np.empty((0, 6), dtype=np.float64)
        )

        tracked = tracker.update(dets_array, frame)

        # Store normalized appearance embeddings for the currently active tracks.
        embedding_lookup = {}
        for strack in tracker.active_tracks:
            if strack.curr_feat is not None:
                emb = strack.curr_feat
                norm = np.linalg.norm(emb)
                embedding_lookup[strack.id] = emb / norm if norm > 0 else emb

        frame_entries = []
        for x1, y1, x2, y2, raw_tid, conf, cls_id, det_ind in tracked:
            raw_tid = int(raw_tid)
            bbox = [float(x1), float(y1), float(x2), float(y2)]
            cls = person_dets[int(det_ind)]["class"]   # Raw detection class for this frame.
            embedding = embedding_lookup.get(raw_tid)
            frame_entries.append({
                "raw_track_id": raw_tid, "bbox": bbox, "conf": float(conf),
                "class": cls, "embedding": embedding,
            })

        raw_tracks_by_frame[frame_idx] = frame_entries

        if frame_idx % config.log_every_n_frames == 0:
            print(f"frame {frame_idx}/{total_frames} | active raw tracks: {len(frame_entries)}")

        frame_idx += 1

    cap.release()
    print(f"\nDone. Processed {frame_idx} frames of raw tracking.")
    return raw_tracks_by_frame