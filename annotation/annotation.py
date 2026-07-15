"""
Professional match annotation — single file by design.

Broadcast-style layout (Opta/FIFA-graphics style), so a crowd of ~20-25
players/gk/ref stays fully visible instead of getting covered by markers:
  - A thin foot-level ellipse (not filled, not a box) — reads as "player
    standing here" without covering any part of the body.
  - A small ID badge floating ABOVE the player's head, connected to the
    bbox top by a hairline — the badge never overlaps the player at all,
    unlike a pill label sitting on the torso.
  - Team colors for players, a distinct color for goalkeepers, yellow for
    referees — consistent across the whole match.
  - Ball marker: solid ring for a normal-confidence detection, a lighter
    dashed ring when the detection is flagged low_confidence.

No possession/ball-carrier logic here — that's a separate concern.
"""

from __future__ import annotations

import colorsys

import cv2
import numpy as np

# ---------------------------------------------------------------------- #
#  Palette                                                                #
# ---------------------------------------------------------------------- #

TEAM_COLORS = {
    0: (255, 120, 0),      # BGR — team 0, blue-ish
    1: (0, 60, 220),       # BGR — team 1, red-ish
}
GOALKEEPER_COLOR = (0, 165, 255)    # orange
REFEREE_COLOR = (0, 230, 255)       # yellow — distinct from both team colors
UNASSIGNED_COLOR = (180, 180, 180)  # gray fallback if a track has no team yet

BALL_COLOR = (0, 220, 255)
BALL_LOW_CONF_COLOR = (0, 150, 210)

FRAME_LABEL_COLOR = (0, 255, 255)
BADGE_TEXT_COLOR = (255, 255, 255)


def _id_to_color(track_id: int) -> tuple[int, int, int]:
    """Deterministic distinct color per track id — used only as a fallback
    when no team/role color applies (e.g. debugging unassigned tracks)."""
    hue = (track_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.95)
    return (int(b * 255), int(g * 255), int(r * 255))


def get_track_color(track_id: int, role: str, team_by_id: dict) -> tuple[int, int, int]:
    if role == "referee":
        return REFEREE_COLOR
    if role == "goalkeeper":
        return GOALKEEPER_COLOR
    team = team_by_id.get(track_id)
    if team is not None:
        return TEAM_COLORS.get(team, UNASSIGNED_COLOR)
    return UNASSIGNED_COLOR


# ---------------------------------------------------------------------- #
#  Primitives                                                             #
# ---------------------------------------------------------------------- #

def bbox_foot_point(bbox: list[float]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return int((x1 + x2) / 2), int(y2)


def bbox_top_point(bbox: list[float]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return int((x1 + x2) / 2), int(y1)


def draw_foot_ellipse(frame: np.ndarray, bbox: list[float], color: tuple[int, int, int], thickness: int = 2) -> None:
    """Thin open ellipse at the player's feet — never fills, never covers
    the body above it."""
    x1, _, x2, _ = bbox
    cx, cy = bbox_foot_point(bbox)
    width = max(int((x2 - x1) * 0.5), 12)
    cv2.ellipse(frame, (cx, cy), (width, 6), 0, -40, 220, color, thickness, cv2.LINE_AA)


def draw_id_badge(
    frame: np.ndarray, bbox: list[float], text: str, color: tuple[int, int, int],
    font_scale: float = 0.42, thickness: int = 1, gap_above_head: int = 14,
) -> None:
    """
    Small filled circular/pill badge floating ABOVE the player's head,
    joined to the bbox top by a thin hairline. Positioned entirely outside
    the bbox, so it never occludes any part of the player — this is what
    keeps a dense crowd of players fully visible instead of getting
    papered over by labels.
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)

    top_x, top_y = bbox_top_point(bbox)
    badge_cy = top_y - gap_above_head - th // 2
    badge_cx = top_x

    pad_x, pad_y = 6, 4
    box_w = tw + 2 * pad_x
    box_h = th + 2 * pad_y
    x1 = int(badge_cx - box_w / 2)
    y1 = int(badge_cy - box_h / 2)
    x2 = x1 + box_w
    y2 = y1 + box_h
    r = box_h // 2

    # hairline connector from badge down to the top of the bbox (stops
    # exactly at the bbox edge — never crosses into the player)
    cv2.line(frame, (top_x, y2), (top_x, top_y), color, 1, cv2.LINE_AA)

    # filled rounded pill badge
    cv2.rectangle(frame, (x1 + r, y1), (x2 - r, y2), color, -1, cv2.LINE_AA)
    cv2.circle(frame, (x1 + r, y1 + r), r, color, -1, cv2.LINE_AA)
    cv2.circle(frame, (x2 - r, y1 + r), r, color, -1, cv2.LINE_AA)

    cv2.putText(frame, text, (x1 + pad_x, y2 - pad_y), font, font_scale, BADGE_TEXT_COLOR, thickness, cv2.LINE_AA)


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
        cv2.circle(frame, (cx, cy), radius, BALL_COLOR, 2, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 1, BALL_COLOR, -1, cv2.LINE_AA)


# ---------------------------------------------------------------------- #
#  Frame-level orchestration                                              #
# ---------------------------------------------------------------------- #

def annotate_frame(
    frame: np.ndarray,
    tracks: list[dict],
    ball_det: dict | None,
    locked_class_by_id: dict,
    team_by_id: dict,
    show_frame_number: int | None = None,
) -> np.ndarray:
    """
    Draws every player/goalkeeper/referee (foot-ellipse + floating ID badge
    above the head, team/role colored) and the ball onto frame, in place.
    Nothing overlaps a player's body. Returns frame for convenient chaining.
    """
    for t in tracks:
        tid = t["track_id"]
        role = locked_class_by_id.get(tid, t["class"])
        color = get_track_color(tid, role, team_by_id)

        draw_foot_ellipse(frame, t["bbox"], color)

        if role == "referee":
            label = f"REF"
        elif role == "goalkeeper":
            team = team_by_id.get(tid)
            label = f"GK{tid}" if team is None else f"GK{tid}-T{team}"
        else:
            team = team_by_id.get(tid)
            label = f"{tid}" if team is None else f"{tid}-T{team}"

        draw_id_badge(frame, t["bbox"], label, color)

    draw_ball(frame, ball_det)

    if show_frame_number is not None:
        cv2.putText(frame, f"frame={show_frame_number}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, FRAME_LABEL_COLOR, 2, cv2.LINE_AA)

    return frame