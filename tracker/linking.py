"""
Global tracklet linking: one Hungarian-algorithm assignment problem PER
CLASS, over ALL tracklets of that class at once — not a sliding window.
A contact at frame 200 can be correctly resolved using appearance evidence
from frame 5000 if that's where the clearest signal happens to be; this is
what a bounded-delay online corrector structurally cannot do.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment


def link_score(ti: dict, tj: dict, motion_weight: float, motion_norm_px: float, max_gap: int) -> float | None:
    gap = tj["frames"][0] - ti["frames"][-1]
    if gap <= 0 or gap > max_gap:
        return None

    if ti["tail_emb"] is None or tj["head_emb"] is None:
        appearance_sim = 0.0
    else:
        appearance_sim = float(np.dot(ti["tail_emb"], tj["head_emb"]))

    if ti["tail_vel"] is not None:
        predicted = ti["tail_pos"] + ti["tail_vel"] * gap
    else:
        predicted = ti["tail_pos"]
    dist = float(np.linalg.norm(predicted - tj["head_pos"]))
    motion_penalty = min(dist / motion_norm_px, 1.0)

    return appearance_sim - motion_weight * motion_penalty


def link_tracklets_globally(
    tracklets: list[dict], max_gap: int, min_link_score: float,
    motion_weight: float, motion_norm_px: float, debug: bool = False,
) -> dict:
    links = {}
    by_class = defaultdict(list)
    for idx, tl in enumerate(tracklets):
        by_class[tl["class"]].append(idx)

    for cls, idxs in by_class.items():
        idxs_by_end = sorted(idxs, key=lambda i: tracklets[i]["frames"][-1])
        idxs_by_start = sorted(idxs, key=lambda i: tracklets[i]["frames"][0])
        n, m = len(idxs_by_end), len(idxs_by_start)
        if n == 0 or m == 0:
            continue

        BIG = 1e6
        cost = np.full((n, m), BIG)
        for a, i in enumerate(idxs_by_end):
            for b, j in enumerate(idxs_by_start):
                if i == j:
                    continue
                score = link_score(tracklets[i], tracklets[j], motion_weight, motion_norm_px, max_gap)
                if score is not None and score >= min_link_score:
                    cost[a, b] = -score

        row_ind, col_ind = linear_sum_assignment(cost)
        for a, b in zip(row_ind, col_ind):
            if cost[a, b] >= BIG:
                continue
            i, j = idxs_by_end[a], idxs_by_start[b]
            links[i] = j
            if debug:
                print(f"  [link] class={cls}: tracklet {i} (ends frame {tracklets[i]['frames'][-1]}) "
                      f"-> tracklet {j} (starts frame {tracklets[j]['frames'][0]}), score={-cost[a,b]:.3f}")

    return links


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry
