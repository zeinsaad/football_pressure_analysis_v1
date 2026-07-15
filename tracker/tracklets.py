"""
Tracklet construction: group raw per-frame tracker output into tracklets,
then deliberately split at every same-class contact (bbox overlap) so no
identity is ever trusted to survive an occlusion just because the raw
tracker ID didn't change.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from .geometry import iou, bbox_center


def make_tracklet(entries: list[tuple]) -> dict:
    """entries: list of (frame_idx, bbox, conf, cls, embedding), sorted by frame_idx."""
    frames = [e[0] for e in entries]
    bbox_by_frame = {e[0]: e[1] for e in entries}
    conf_by_frame = {e[0]: e[2] for e in entries}
    class_by_frame = {e[0]: e[3] for e in entries}
    embedding_by_frame = {e[0]: e[4] for e in entries}
    classes = [e[3] for e in entries]
    majority_class = max(set(classes), key=classes.count)
    return {
        "frames": frames, "bbox_by_frame": bbox_by_frame, "conf_by_frame": conf_by_frame,
        "class_by_frame": class_by_frame, "embedding_by_frame": embedding_by_frame,
        "class": majority_class,
    }


def build_initial_tracklets(raw_tracks_by_frame: dict) -> list[dict]:
    """Groups raw per-frame tracker output by raw_track_id. A raw ID's lifespan
    is already 'one continuous stretch with no ambiguity according to the
    tracker' — exactly what a tracklet should be before contact-based splitting."""
    raw_entries_by_id = defaultdict(list)
    for frame_idx, dets in raw_tracks_by_frame.items():
        for d in dets:
            raw_entries_by_id[d["raw_track_id"]].append(
                (frame_idx, d["bbox"], d["conf"], d["class"], d["embedding"])
            )

    tracklets = []
    for raw_id, entries in raw_entries_by_id.items():
        entries.sort(key=lambda e: e[0])
        segments, current = [], [entries[0]]
        for e in entries[1:]:
            if e[0] == current[-1][0] + 1:
                current.append(e)
            else:
                segments.append(current)
                current = [e]
        segments.append(current)
        for seg in segments:
            tracklets.append(make_tracklet(seg))
    return tracklets


def find_contact_split_points(tracklets: list[dict], iou_thresh: float, merge_gap: int = 1) -> dict:
    """Returns {tracklet_index: set of cut-boundary frames}. A cut boundary at
    frame f means 'end a chunk after frame f' — so the tracklet is split right
    before and right after each contact event, isolating the ambiguous contact
    frames into their own short segment instead of leaving them attached to a
    clean pre/post segment.

    Contact frames are grouped into contiguous runs (allowing gaps of up to
    merge_gap frames to still count as one run) before computing boundaries —
    otherwise an extended contact would get a cut point at EVERY overlapping
    frame, shredding the tracklet into single-frame fragments that then get
    dropped entirely by min_tracklet_len, silently deleting real player data.
    """
    overlap_frames_by_pair = defaultdict(set)
    frame_to_tracklets = defaultdict(list)
    for idx, tl in enumerate(tracklets):
        for f in tl["frames"]:
            frame_to_tracklets[f].append(idx)

    for f, idxs in frame_to_tracklets.items():
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a, b = tracklets[idxs[i]], tracklets[idxs[j]]
                if a["class"] != b["class"]:
                    continue
                if iou(a["bbox_by_frame"][f], b["bbox_by_frame"][f]) >= iou_thresh:
                    pair = tuple(sorted((idxs[i], idxs[j])))
                    overlap_frames_by_pair[pair].add(f)

    split_points = defaultdict(set)
    for (i, j), frames in overlap_frames_by_pair.items():
        frames = sorted(frames)
        runs, current = [], [frames[0]]
        for f in frames[1:]:
            if f - current[-1] <= merge_gap:
                current.append(f)
            else:
                runs.append(current)
                current = [f]
        runs.append(current)
        for run in runs:
            split_points[i].add(run[0] - 1)
            split_points[i].add(run[-1])
            split_points[j].add(run[0] - 1)
            split_points[j].add(run[-1])
    return split_points


def slice_tracklet(tl: dict, frames: list[int]) -> dict:
    return {
        "frames": frames,
        "bbox_by_frame": {f: tl["bbox_by_frame"][f] for f in frames},
        "conf_by_frame": {f: tl["conf_by_frame"][f] for f in frames},
        "class_by_frame": {f: tl["class_by_frame"][f] for f in frames},
        "embedding_by_frame": {f: tl["embedding_by_frame"][f] for f in frames},
        "class": tl["class"],
    }


def apply_splits(tracklets: list[dict], split_points: dict) -> list[dict]:
    new_tracklets = []
    for idx, tl in enumerate(tracklets):
        cuts = set(split_points.get(idx, []))
        if not cuts:
            new_tracklets.append(tl)
            continue
        chunks, current = [], []
        for f in tl["frames"]:
            current.append(f)
            if f in cuts:
                chunks.append(current)
                current = []
        if current:
            chunks.append(current)
        for chunk in chunks:
            if chunk:
                new_tracklets.append(slice_tracklet(tl, chunk))
    return new_tracklets


def fit_velocity(frames: list[int], bbox_by_frame: dict) -> np.ndarray | None:
    if len(frames) < 2:
        return None
    farr = np.array(frames, dtype=np.float64)
    centers = np.array([bbox_center(bbox_by_frame[f]) for f in frames])
    A = np.vstack([farr, np.ones_like(farr)]).T
    vx, _ = np.linalg.lstsq(A, centers[:, 0], rcond=None)[0]
    vy, _ = np.linalg.lstsq(A, centers[:, 1], rcond=None)[0]
    return np.array([vx, vy])


def compute_tracklet_features(tl: dict, window: int) -> None:
    """Mutates tl in place, adding head/tail embedding + velocity + position."""
    frames = tl["frames"]
    head_frames = frames[:window]
    tail_frames = frames[-window:]

    head_embs = [tl["embedding_by_frame"][f] for f in head_frames if tl["embedding_by_frame"].get(f) is not None]
    tail_embs = [tl["embedding_by_frame"][f] for f in tail_frames if tl["embedding_by_frame"].get(f) is not None]
    tl["head_emb"] = np.mean(head_embs, axis=0) if head_embs else None
    tl["tail_emb"] = np.mean(tail_embs, axis=0) if tail_embs else None

    tl["head_vel"] = fit_velocity(head_frames, tl["bbox_by_frame"])
    tl["tail_vel"] = fit_velocity(tail_frames, tl["bbox_by_frame"])
    tl["head_pos"] = bbox_center(tl["bbox_by_frame"][frames[0]])
    tl["tail_pos"] = bbox_center(tl["bbox_by_frame"][frames[-1]])
