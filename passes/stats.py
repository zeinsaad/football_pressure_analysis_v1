"""
Reporting helpers over a pass_events cache (from
pipeline.get_or_build_pass_events). Not part of the cached pipeline output
itself -- these recompute on demand from whatever events_df you hand them.
Always filter is_turnover out before calling these; both functions assume
they're getting genuine pass attempts, not the raw events_df.
"""


def team_pass_stats(pass_events):
    """Total attempted / completed / failed per team, scored to the
    PASSER's team regardless of outcome -- an intercepted pass counts as a
    failed attempt for the passer's team, not an event credited to the
    interceptor."""
    stats = (
        pass_events.groupby("passer_team")["outcome"]
        .value_counts()
        .unstack(fill_value=0)
    )
    stats["attempted"] = stats.get("completed", 0) + stats.get("failed", 0)
    stats["completion_pct"] = (stats.get("completed", 0) / stats["attempted"] * 100).round(1)
    stats = stats.reset_index().rename(columns={"passer_team": "team"})
    for col in ["completed", "failed"]:
        if col not in stats.columns:
            stats[col] = 0
    return stats[["team", "attempted", "completed", "failed", "completion_pct"]]


def top_passers(pass_events, top_n=5):
    """Per-team ranking by completed-pass count (not completion %, so a
    40/45 passer doesn't get outranked by a flukey 2/2)."""
    grouped = (
        pass_events.groupby(["passer_team", "passer_id"])["outcome"]
        .value_counts()
        .unstack(fill_value=0)
    )
    for col in ["completed", "failed"]:
        if col not in grouped.columns:
            grouped[col] = 0
    grouped["attempted"] = grouped["completed"] + grouped["failed"]
    grouped["completion_pct"] = (grouped["completed"] / grouped["attempted"] * 100).round(1)
    grouped = grouped.reset_index().rename(columns={"passer_team": "team", "passer_id": "track_id"})
    grouped = grouped.sort_values(["team", "completed"], ascending=[True, False])
    return grouped.groupby("team").head(top_n)[
        ["team", "track_id", "attempted", "completed", "failed", "completion_pct"]
    ]
