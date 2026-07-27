"""
Professional match annotation — broadcast-minimal, crowd-aware.

Design principles (this is a rewrite, not a tweak — the old floating-badge
layout broke down exactly where it mattered: dense duels):

  1. Everything lives at the FEET, not the head. Feet are farther apart than
     heads in a crowd, so markers collide far less than floating badges did.
  2. Identity is shape + color, not just color. Ellipse = player,
     diamond = goalkeeper, square = referee — legible even at a glance,
     even for something like partial color blindness, even at small size.
  3. Crowd-aware auto-declutter: each frame, every player's local density
     (how many other players are within CROWD_RADIUS_PX) is measured, same
     idea as the crowd-gating already used in ball_tracker. Players in a
     duel/scramble automatically drop to a small color dot with no number;
     isolated players get the full marker with their number inside it.
     This is the actual fix for "too crowded, not clear" — the annotation
     simplifies itself precisely where a human eye would otherwise get lost.
  4. The ball-carrier highlight is a tight pulsing ring sized to the
     carrier's own marker, not a big halo — reads as "possession" without
     washing out the pitch around it.

No possession/ball-carrier logic here — that's computed elsewhere
(ball_tracker.carrier); this file only draws whatever carrier_track_id
it's handed.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

# ---------------------------------------------------------------------- #
#  Palette                                                                #
# ---------------------------------------------------------------------- #

TEAM_COLORS = {
    0: (255, 90, 30),       # BGR — team 0, vivid blue
    1: (40, 40, 255),       # BGR — team 1, vivid red
}
GOALKEEPER_COLOR = (0, 165, 255)    # orange — fallback ONLY for a GK with no team assigned yet
REFEREE_COLOR = (0, 255, 255)       # pure yellow — distinct enough from CARRIER_COLOR's gold
                                     # (0, 215, 255) to tell apart at a glance, and backed by the
                                     # "REF" text label below so shape+color+text all disambiguate it
                                     # from the carrier arrow, which has no text at all
UNASSIGNED_COLOR = (180, 180, 180)  # gray fallback if a track has no team yet

BALL_COLOR = (0, 220, 255)
BALL_LOW_CONF_COLOR = (0, 150, 210)

FRAME_LABEL_COLOR = (0, 255, 255)
MARKER_TEXT_COLOR = (255, 255, 255)
MARKER_OUTLINE_COLOR = (20, 20, 20)

CARRIER_COLOR = (0, 215, 255)       # BGR gold

# ---------------------------------------------------------------------- #
#  Crowd-aware declutter                                                  #
# ---------------------------------------------------------------------- #
# Same idea as ball_tracker's crowd gating: a player isn't judged in
# isolation, they're judged relative to who's standing near them this
# frame. Below the threshold -> full marker with number. At/above it ->
# every player in that cluster drops to a compact dot, so a 6-man scramble
# reads as "a cluster of dots", not six overlapping labels fighting for
# the same patch of grass.

CROWD_RADIUS_PX = 45.0
CROWD_MIN_NEARBY = 3   # this many OTHER players within CROWD_RADIUS_PX triggers compact mode

FULL_MARKER_RADIUS = 10
COMPACT_MARKER_RADIUS = 5


def bbox_foot_point(bbox: list[float]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return int((x1 + x2) / 2), int(y2)


def _local_crowd_count(track, all_tracks, radius_px: float) -> int:
    """How many OTHER player/goalkeeper tracks have their foot point within
    radius_px of this track's foot point this frame."""
    fx, fy = bbox_foot_point(track["bbox"])
    count = 0
    for other in all_tracks:
        if other is track:
            continue
        if other.get("_role") not in ("player", "goalkeeper"):
            continue
        ox, oy = bbox_foot_point(other["bbox"])
        if (ox - fx) ** 2 + (oy - fy) ** 2 <= radius_px ** 2:
            count += 1
    return count


# ---------------------------------------------------------------------- #
#  Marker primitives                                                      #
# ---------------------------------------------------------------------- #

def _draw_text_with_outline(frame, text, center, font_scale, color=MARKER_TEXT_COLOR):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, 1)
    org = (int(center[0] - tw / 2), int(center[1] + th / 2))
    cv2.putText(frame, text, org, font, font_scale, MARKER_OUTLINE_COLOR, 2, cv2.LINE_AA)
    cv2.putText(frame, text, org, font, font_scale, color, 1, cv2.LINE_AA)


def _draw_text_plain(frame, text, center, font_scale, color):
    """No dark outline pass -- for text sitting on a solid, already-high-
    contrast fill (e.g. dark text on the referee's yellow square), where
    _draw_text_with_outline's outline pass (always MARKER_OUTLINE_COLOR)
    would be the same near-black as the fill color itself, rendering as one
    solid blob instead of legible letters."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, 1)
    org = (int(center[0] - tw / 2), int(center[1] + th / 2))
    cv2.putText(frame, text, org, font, font_scale, color, 1, cv2.LINE_AA)


def _blend_shape_in_roi(frame, cx, cy, half_extent, alpha, draw_shape_fn):
    """Alpha-blends a filled shape by copying/blending only the small pixel
    region around (cx, cy) -- NOT the whole frame. The original version did
    `overlay = frame.copy(); cv2.addWeighted(overlay, ...)` on the full
    frame buffer for every single marker; on a 1080p/4K frame with ~15-20
    full markers per frame that's 15-20 full-frame copies PER FRAME for
    nothing but a ~20px ellipse, which is the actual reason a pure-drawing,
    fully-cached render pass was taking minutes instead of seconds.
    draw_shape_fn(roi, local_cx, local_cy) draws the filled shape onto the
    ROI using coordinates local to that ROI (i.e. shifted by the ROI's
    top-left corner)."""
    h, w = frame.shape[:2]
    x0, x1 = max(cx - half_extent, 0), min(cx + half_extent, w)
    y0, y1 = max(cy - half_extent, 0), min(cy + half_extent, h)
    if x1 <= x0 or y1 <= y0:
        return
    roi = frame[y0:y1, x0:x1]
    overlay = roi.copy()
    draw_shape_fn(overlay, cx - x0, cy - y0)
    frame[y0:y1, x0:x1] = cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0)


def draw_player_marker(
    frame: np.ndarray, bbox: list[float], color: tuple[int, int, int],
    number: str | None, compact: bool,
) -> None:
    """Filled, translucent ellipse at the feet. Full mode shows the number
    centered inside it; compact mode (crowd-aware) is just a small solid
    dot with a thin dark outline for contrast against grass, no text."""
    cx, cy = bbox_foot_point(bbox)

    if compact:
        cv2.circle(frame, (cx, cy), COMPACT_MARKER_RADIUS, color, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), COMPACT_MARKER_RADIUS, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)
        return

    r = FULL_MARKER_RADIUS
    axes = (r, int(r * 0.72))
    _blend_shape_in_roi(
        frame, cx, cy, half_extent=r + 4, alpha=0.85,
        draw_shape_fn=lambda roi, lx, ly: cv2.ellipse(roi, (lx, ly), axes, 0, 0, 360, color, -1, cv2.LINE_AA),
    )
    cv2.ellipse(frame, (cx, cy), axes, 0, 0, 360, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)

    if number is not None:
        _draw_text_with_outline(frame, number, (cx, cy), font_scale=0.34)


def draw_goalkeeper_marker(
    frame: np.ndarray, bbox: list[float], color: tuple[int, int, int],
    label: str | None, compact: bool,
) -> None:
    """Diamond marker — a distinct silhouette from the player ellipse, so
    'who's the keeper' reads instantly even at small size or in a crowd
    near the box. label is "GK{track_id}" in full mode (None in compact) so
    a keeper reads as both role (diamond shape) and identity (id), same as
    outfield players get their number."""
    cx, cy = bbox_foot_point(bbox)

    if compact:
        r = COMPACT_MARKER_RADIUS + 2
        pts = np.array([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]], np.int32)
        cv2.fillConvexPoly(frame, pts, color, cv2.LINE_AA)
        cv2.polylines(frame, [pts], True, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)
        return

    r = FULL_MARKER_RADIUS + 2

    def _shape(roi, lx, ly):
        pts = np.array([[lx, ly - r], [lx + r, ly], [lx, ly + r], [lx - r, ly]], np.int32)
        cv2.fillConvexPoly(roi, pts, color, cv2.LINE_AA)

    _blend_shape_in_roi(frame, cx, cy, half_extent=r + 4, alpha=0.85, draw_shape_fn=_shape)

    pts = np.array([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]], np.int32)
    cv2.polylines(frame, [pts], True, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)

    if label is not None:
        # smaller than the player font_scale (0.34) -- "GK12" is wider than
        # a bare number, and the diamond's usable width is narrower than
        # the ellipse's at the same radius
        _draw_text_with_outline(frame, label, (cx, cy), font_scale=0.26)


def draw_referee_marker(frame: np.ndarray, bbox: list[float], color: tuple[int, int, int]) -> None:
    """Small solid yellow square with a "REF" label inside it -- shape
    (square, unused elsewhere: ellipse=player, diamond=goalkeeper),
    color (yellow), and text all disambiguate it from the ball-carrier
    arrow, which is a similar gold but has no text and a different shape.
    Referees are never part of the crowd-density count, so this stays
    full-size always -- there's rarely more than one on screen near any
    given duel."""
    cx, cy = bbox_foot_point(bbox)
    r = COMPACT_MARKER_RADIUS + 3
    pts = np.array([
        [cx - r, cy - r], [cx + r, cy - r], [cx + r, cy + r], [cx - r, cy + r],
    ], np.int32)
    cv2.fillConvexPoly(frame, pts, color, cv2.LINE_AA)
    cv2.polylines(frame, [pts], True, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)
    # dark text, no outline pass -- see _draw_text_plain's docstring for why
    # _draw_text_with_outline was rendering this as a solid blob
    _draw_text_plain(frame, "REF", (cx, cy), font_scale=0.24, color=(20, 20, 20))


def draw_dashed_circle(
    frame: np.ndarray, center: tuple[int, int], radius: int,
    color: tuple[int, int, int], thickness: int = 2, n_dashes: int = 16,
) -> None:
    for i in range(n_dashes):
        if i % 2 == 0:
            theta1 = 360 * i / n_dashes
            theta2 = 360 * (i + 0.6) / n_dashes
            cv2.ellipse(frame, center, (radius, radius), 0, theta1, theta2, color, thickness, cv2.LINE_AA)


def draw_ball(frame: np.ndarray, ball_det: dict | None) -> None:
    if ball_det is None:
        return
    bx1, by1, bx2, by2 = [int(v) for v in ball_det["bbox"]]
    cx, cy = (bx1 + bx2) // 2, (by1 + by2) // 2
    radius = max((bx2 - bx1) // 2, 5)
    low_conf = ball_det.get("low_confidence", False)

    if low_conf:
        draw_dashed_circle(frame, (cx, cy), radius, BALL_LOW_CONF_COLOR, thickness=1)
    else:
        cv2.circle(frame, (cx, cy), radius, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), radius - 1, BALL_COLOR, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 1, BALL_COLOR, -1, cv2.LINE_AA)


# ---------------------------------------------------------------------- #
#  Ball-carrier possession highlight                                      #
# ---------------------------------------------------------------------- #

def _pulse_alpha(frame_idx: int | None, period_frames: int = 20) -> float:
    if frame_idx is None:
        return 0.8
    phase = (frame_idx % period_frames) / period_frames
    return 0.55 + 0.45 * math.sin(2 * math.pi * phase)


CARRIER_ARROW_HALF_WIDTH = 6
CARRIER_ARROW_HEIGHT = 8
CARRIER_ARROW_GAP = 5       # clearance between the marker and the arrow tip
CARRIER_ARROW_BOB_PX = 2    # max vertical bob amplitude


def draw_carrier_indicator(
    frame: np.ndarray, bbox: list[float], compact: bool, frame_idx: int | None = None,
    color: tuple[int, int, int] = CARRIER_COLOR,
) -> None:
    """A small solid gold arrow hovering above the carrier, tip pointing
    down at their marker -- a "you are here" pin rather than a ring around
    the marker itself. Gently bobs up/down (driven by frame_idx) so it
    still reads as "live" without any extra clutter, since it's the only
    animated element on screen and never touches the marker or badge."""
    cx, cy = bbox_foot_point(bbox)
    marker_r = COMPACT_MARKER_RADIUS if compact else FULL_MARKER_RADIUS
    bob = int(round(CARRIER_ARROW_BOB_PX * _pulse_alpha(frame_idx)))
    tip_y = cy - marker_r - CARRIER_ARROW_GAP - bob

    pts = np.array([
        [cx - CARRIER_ARROW_HALF_WIDTH, tip_y - CARRIER_ARROW_HEIGHT],
        [cx + CARRIER_ARROW_HALF_WIDTH, tip_y - CARRIER_ARROW_HEIGHT],
        [cx, tip_y],
    ], np.int32)
    cv2.fillConvexPoly(frame, pts, color, cv2.LINE_AA)
    cv2.polylines(frame, [pts], True, MARKER_OUTLINE_COLOR, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------- #
#  Frame-level orchestration                                              #
# ---------------------------------------------------------------------- #

def get_track_color(track_id: int, role: str, team_by_id: dict) -> tuple[int, int, int]:
    if role == "referee":
        return REFEREE_COLOR
    # goalkeeper is marked by shape (diamond, see draw_goalkeeper_marker), not
    # by color -- so a GK reads as team-colored just like their outfield
    # teammates once assigned. Orange is only a fallback for the brief window
    # before team assignment has run.
    team = team_by_id.get(track_id)
    if team is not None:
        return TEAM_COLORS.get(team, UNASSIGNED_COLOR)
    if role == "goalkeeper":
        return GOALKEEPER_COLOR
    return UNASSIGNED_COLOR


def annotate_frame(
    frame: np.ndarray,
    tracks: list[dict],
    ball_det: dict | None,
    locked_class_by_id: dict,
    team_by_id: dict,
    show_frame_number: int | None = None,
    carrier_track_id: int | None = None,
    frame_idx: int | None = None,
) -> np.ndarray:
    """
    Draws every player/goalkeeper/referee as a feet-level marker (ellipse /
    diamond / square, team-or-role colored) plus the ball, in place.

    Markers are crowd-aware: a player standing alone gets the full marker
    with their number inside it; a player in a duel/scramble (>= 3 other
    players within CROWD_RADIUS_PX) automatically drops to a small color
    dot so a crowded scene reads as "a cluster", not overlapping labels.

    carrier_track_id: track_id of the current ball carrier (from
    ball_tracker.carrier's ball_carrier_cache), or None. Gets a thin
    pulsing ring around their own marker.

    frame_idx: drives the carrier ring's pulse; leave None for a still
    frame (falls back to a fixed near-peak ring).

    Returns frame for convenient chaining.
    """
    # tag each track with its resolved role once, up front -- used both for
    # drawing and for the crowd-density count
    for t in tracks:
        t["_role"] = locked_class_by_id.get(t["track_id"], t["class"])

    for t in tracks:
        tid = t["track_id"]
        role = t["_role"]
        color = get_track_color(tid, role, team_by_id)

        if role == "referee":
            draw_referee_marker(frame, t["bbox"], color)
            continue

        compact = _local_crowd_count(t, tracks, CROWD_RADIUS_PX) >= CROWD_MIN_NEARBY

        if role == "goalkeeper":
            label = None if compact else f"GK{tid}"
            draw_goalkeeper_marker(frame, t["bbox"], color, label, compact)
        else:
            number = None if compact else str(tid)
            draw_player_marker(frame, t["bbox"], color, number, compact)

        if tid == carrier_track_id:
            draw_carrier_indicator(frame, t["bbox"], compact, frame_idx=frame_idx)

    for t in tracks:
        t.pop("_role", None)

    draw_ball(frame, ball_det)

    if show_frame_number is not None:
        # bottom-left instead of top-left -- keeps the frame counter out of
        # the way of the pitch action, which up top competed with whatever
        # was happening near the near touchline.
        h = frame.shape[0]
        cv2.putText(frame, f"frame={show_frame_number}", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, FRAME_LABEL_COLOR, 2, cv2.LINE_AA)

    return frame