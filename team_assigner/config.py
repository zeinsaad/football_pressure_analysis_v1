"""
Team assigner configuration. Paths come from the project-root paths.py —
fill them in there, not here. Only thresholds/runtime knobs live in this file.
"""

from dataclasses import dataclass

import torch

try:
    from paths import TRACKING_CACHE_PATH, VIDEO_PATH, HOMOGRAPHY_CACHE_PATH, TEAM_CACHE_PATH
except ImportError:
    print("⚠️ Could not import path constants from paths.py — using empty defaults. "
          "Fill in TRACKING_CACHE_PATH / VIDEO_PATH / HOMOGRAPHY_CACHE_PATH / TEAM_CACHE_PATH "
          "in the project-root paths.py.")
    TRACKING_CACHE_PATH = ""
    VIDEO_PATH = ""
    HOMOGRAPHY_CACHE_PATH = ""
    TEAM_CACHE_PATH = ""


@dataclass
class TeamAssignerConfig:
    # ---- paths (sourced from paths.py) ----
    tracking_cache_path: str = TRACKING_CACHE_PATH
    video_path: str = VIDEO_PATH
    homography_cache_path: str = HOMOGRAPHY_CACHE_PATH
    output_cache_path: str = TEAM_CACHE_PATH

    # ---- torso crop: avoid shorts/socks/skin/head, focus on the jersey ----
    torso_top_ratio: float = 0.15      # skip the top 15% of the box (head/neck)
    torso_bottom_ratio: float = 0.50   # keep only up to 50% of box height (avoid shorts)
    torso_side_margin: float = 0.20    # crop in 20% from each side (avoid arms/background)
    min_bbox_area: int = 900           # px^2, filters out small/distant crops from calibration

    # ---- calibration sampling ----
    calibration_frame_stride: int = 15     # frames sampled to FIT the KMeans clusters
    classification_frame_stride: int = 8   # frames sampled to CLASSIFY each track
    max_calibration_samples: int = 6000    # cap AFTER collecting across the whole match

    # ---- smoothing ----
    weak_majority_threshold: float = 0.7   # below this fraction, flag the track/window for manual review

    # ---- windowed team voting (switch-robust) ----
    # A same-team ID switch is invisible to team assignment by definition (both
    # segments vote for the same team) -- only a CROSS-team switch corrupts a
    # team label, and the tracking pipeline's own team veto already guards
    # against most of those upstream. This windows per-track voting along the
    # track's own timeline instead of one whole-track majority vote, so any
    # cross-team switch that DOES survive is detected (see switch_suspects in
    # the pipeline result) and each segment gets the correct team, rather than
    # one team silently winning a global vote and mislabeling part of the
    # track. 500 frames: at classification_frame_stride=8 that's ~62 sampled
    # votes/window, vs. ~31 for a 250-frame window -- more votes per window
    # matters most when clustering separation (see the silhouette-score check
    # in calibration.py) is only weak-to-moderate, since fewer votes per
    # window means individual misclassified frames more easily flip a
    # window's majority, producing false switch_suspects that are classifier
    # noise rather than real switches.
    team_vote_window_frames: int = 500

    # ---- auto team-color extraction ----
    # Real average kit color per KMeans cluster, extracted from the actual
    # torso-crop pixels used for calibration -- self-corrects across reruns
    # even if KMeans' cluster label 0/1 assignment flips, unlike a
    # hardcoded color-per-label mapping. Both knobs below were tuned
    # against real debugging on broadcast footage: small/distant bboxes
    # have only a few pixels of margin even after the torso-crop side
    # margins, so grass bleed at the crop edge disproportionately skews a
    # tiny crop's average -- color_extraction_min_area_percentile restricts
    # extraction to only the larger, cleaner bboxes, computed from this
    # match's own candidate sizes (not a fixed absolute area, which can end
    # up above every bbox a given clip ever produces). Even after that and
    # after grass-pixel filtering, real broadcast footage still produced
    # muted/desaturated colors (confirmed empirically -- filtering barely
    # moved the values), so a saturation boost is applied afterward to make
    # the result usable as a render color without changing which cluster
    # maps to which color.
    color_extraction_min_area_percentile: float = 75.0   # keep only the largest ~25% of bboxes
    color_grass_dominance_thresh: float = 1.15            # ratio: green > other channels * this
    color_saturation_boost_factor: float = 2.2
    color_min_lightness: float = 0.25
    color_max_lightness: float = 0.75

    # ---- pitch projection (for goalkeeper assignment) ----
    px_per_meter: int = 10
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0
    gk_position_sample_stride: int = 10    # frames sampled when computing a track's pitch-space centroid

    # ---- SigLIP ----
    siglip_model_name: str = "google/siglip-base-patch16-224"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    log_every_n_frames: int = 300
