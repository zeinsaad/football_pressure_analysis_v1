"""
TrackingPipeline: orchestrates the full offline global re-linking pipeline.

    1. Raw causal BoT-SORT + OSNet pass over the video -> raw per-frame track IDs.
    2. Build initial tracklets from raw IDs, split at every same-class contact.
    3. Compute head/tail appearance + motion features per tracklet.
    4. Solve one global Hungarian assignment per class over the whole match.
    5. Union accepted links into final chains -> final global identities.
    6. Rebuild the final per-frame cache with global IDs + ball detections.
    7. Ghost-track removal + ratio-aware class locking.

Usage:

    from tracker import TrackingConfig, TrackingPipeline, get_or_build_cache

    pipeline = TrackingPipeline(TrackingConfig())
    tracking_cache = get_or_build_cache(pipeline, cfg.video_path, cfg.output_cache_path,
                                         detection_cache=detection_cache)
"""

from __future__ import annotations

import os
from collections import defaultdict

from .config import TrackingConfig
from .reid import load_osnet
from .raw_tracking import build_tracker, run_raw_tracking
from .tracklets import build_initial_tracklets, find_contact_split_points, apply_splits, compute_tracklet_features
from .linking import link_tracklets_globally, UnionFind
from .cache_io import save_cache


class TrackingPipeline:
    def __init__(self, config: TrackingConfig):
        self.config = config
        self.osnet = None
        self.tracker = None

    def check_paths(self) -> None:
        cfg = self.config
        print("Checking paths...")
        for p in [cfg.detection_cache_path, cfg.osnet_weights_path, cfg.video_path]:
            print(p, "->", "OK" if os.path.exists(p) else "MISSING")

    def load_models(self) -> None:
        """Loads the standalone OSNet backbone (informational — BoT-SORT loads
        its own copy internally from osnet_weights_path) and initializes BoT-SORT."""
        cfg = self.config
        device = "cuda" if cfg.device != "cpu" else "cpu"
        self.osnet = load_osnet(cfg.osnet_weights_path, device)
        print("OSNet ready. Embedding dim: 512")
        self.tracker = build_tracker(cfg)

    def run(self, detection_cache: dict, video_path: str | None = None, save_to: str | None = None) -> dict:
        """Runs the full pipeline and returns
        {"tracking_cache": {frame_idx: {"ball":, "tracks": [...]}}, "locked_class_by_id": {...}}."""
        cfg = self.config
        video_path = video_path or cfg.video_path

        if self.tracker is None:
            self.load_models()

        # --- 1. raw causal pass ---
        raw_tracks_by_frame = run_raw_tracking(self.tracker, detection_cache, video_path, cfg)
        total_frames = max(raw_tracks_by_frame.keys()) + 1 if raw_tracks_by_frame else 0

        # --- 2. tracklets + contact splitting ---
        initial_tracklets = build_initial_tracklets(raw_tracks_by_frame)
        print(f"Initial tracklets (from raw track IDs): {len(initial_tracklets)}")

        split_points = find_contact_split_points(initial_tracklets, cfg.contact_iou_thresh)
        split_tracklets = apply_splits(initial_tracklets, split_points)
        print(f"Tracklets after contact-based splitting: {len(split_tracklets)} "
              f"(from {len(initial_tracklets)}, {sum(len(v) for v in split_points.values())} split points applied)")

        pre_filter_count = len(split_tracklets)
        split_tracklets = [tl for tl in split_tracklets if len(tl["frames"]) >= cfg.min_tracklet_len]
        print(f"Dropped {pre_filter_count - len(split_tracklets)} tracklets shorter than "
              f"min_tracklet_len={cfg.min_tracklet_len} frames (too short for reliable linking)")
        print(f"Tracklets going into global linking: {len(split_tracklets)}")

        # --- 3. head/tail features ---
        for tl in split_tracklets:
            compute_tracklet_features(tl, cfg.embed_window)
        print(f"Computed head/tail features for {len(split_tracklets)} tracklets.")

        # --- 4. global linking ---
        accepted_links = link_tracklets_globally(
            split_tracklets, cfg.max_link_gap, cfg.min_link_score,
            cfg.motion_weight, cfg.motion_norm_px, debug=cfg.debug_linking,
        )
        print(f"\nTotal accepted links: {len(accepted_links)}")

        # --- 5. union into final identities ---
        uf = UnionFind(len(split_tracklets))
        for i, j in accepted_links.items():
            uf.union(i, j)

        chain_members = defaultdict(list)
        for idx in range(len(split_tracklets)):
            chain_members[uf.find(idx)].append(idx)

        canonical_id_of_tracklet = {}
        canonical_class = {}
        next_id = 1
        for root, members in chain_members.items():
            for m in members:
                canonical_id_of_tracklet[m] = next_id
            canonical_class[next_id] = split_tracklets[members[0]]["class"]
            next_id += 1

        chain_lengths = [len(members) for members in chain_members.values()]
        print(f"Final global identities: {len(chain_members)}")
        print(f"Chain length distribution: 1 tracklet={sum(1 for c in chain_lengths if c==1)}, "
              f"2={sum(1 for c in chain_lengths if c==2)}, 3+={sum(1 for c in chain_lengths if c>=3)}")

        by_class_counts = defaultdict(int)
        for cid, cls in canonical_class.items():
            by_class_counts[cls] += 1
        print("Identity counts by class:", dict(by_class_counts))
        for cls, expected in cfg.max_ids_per_class_expected.items():
            actual = by_class_counts.get(cls, 0)
            if actual > expected:
                print(f"  [check] {cls}: {actual} identities, expected <= {expected} -- consider raising "
                      f"max_link_gap or lowering min_link_score, or check [link] debug output")

        # --- 6. rebuild final per-frame cache with global IDs + ball ---
        final_tracking_cache = defaultdict(lambda: {"ball": None, "tracks": []})
        for idx, tl in enumerate(split_tracklets):
            cid = canonical_id_of_tracklet[idx]
            for f in tl["frames"]:
                final_tracking_cache[f]["tracks"].append({
                    "track_id": cid,
                    "bbox": tl["bbox_by_frame"][f],
                    "conf": tl["conf_by_frame"][f],
                    "class": tl["class_by_frame"][f],
                })

        for f in range(total_frames):
            ball_det = next((d for d in detection_cache.get(f, []) if d["class"] == "ball"), None)
            final_tracking_cache.setdefault(f, {"ball": ball_det, "tracks": []})
            final_tracking_cache[f]["ball"] = ball_det

        final_tracking_cache = dict(final_tracking_cache)
        print(f"Rebuilt tracking cache: {len(final_tracking_cache)} frames.")

        # --- 7. ghost-track removal + ratio-aware class locking ---
        id_frame_counts = defaultdict(int)
        for data in final_tracking_cache.values():
            for t in data["tracks"]:
                id_frame_counts[t["track_id"]] += 1

        ghost_ids = {tid for tid, count in id_frame_counts.items() if count < cfg.min_track_length}
        print(f"Ghost tracks dropped (< {cfg.min_track_length} frames): {sorted(ghost_ids)}")

        for data in final_tracking_cache.values():
            data["tracks"] = [t for t in data["tracks"] if t["track_id"] not in ghost_ids]

        class_votes = defaultdict(lambda: defaultdict(int))
        for data in final_tracking_cache.values():
            for t in data["tracks"]:
                class_votes[t["track_id"]][t["class"]] += 1

        locked_class_by_id = {}
        for tid, votes in class_votes.items():
            total = sum(votes.values())
            ref_votes = votes.get("referee", 0)
            gk_votes = votes.get("goalkeeper", 0)
            ref_confirmed = ref_votes >= cfg.min_confirm_frames_abs and (ref_votes / total) >= cfg.min_confirm_ratio
            gk_confirmed = gk_votes >= cfg.min_confirm_frames_abs and (gk_votes / total) >= cfg.min_confirm_ratio
            if ref_confirmed:
                locked_class_by_id[tid] = "referee"
            elif gk_confirmed:
                locked_class_by_id[tid] = "goalkeeper"
            else:
                locked_class_by_id[tid] = max(votes, key=votes.get)

        final_counts = defaultdict(int)
        for cls in locked_class_by_id.values():
            final_counts[cls] += 1
        print(f"\nFinal identity counts after ghost removal: {dict(final_counts)}")

        result = {"tracking_cache": final_tracking_cache, "locked_class_by_id": locked_class_by_id}

        if save_to:
            save_cache(result, save_to)

        return result
