"""Shared cumulative-standings logic reused by every curated standings table (AC 2)."""

from __future__ import annotations

import pandas as pd


def add_standing_rank(
    df: pd.DataFrame,
    group_columns: list[str],
    id_columns: list[str],
) -> pd.DataFrame:
    """Rank rows within each group by cumulative points/wins, tying on equal totals.

    Assumes `df` already has `cumulative_points` and `cumulative_wins` columns.
    Rows that tie on both are given the same `standing_rank`; ties break only
    for sort order via `id_columns`, not for the rank value itself.
    """
    ranked = df.sort_values(
        group_columns + ["cumulative_points", "cumulative_wins"] + id_columns,
        ascending=[True] * len(group_columns) + [False, False] + [True] * len(id_columns),
    ).copy()

    tie_changed = (
        ranked.groupby(group_columns)[["cumulative_points", "cumulative_wins"]]
        .apply(lambda group: group.ne(group.shift()).any(axis=1).cumsum())
        .reset_index(level=group_columns, drop=True)
    )
    ranked["standing_rank"] = tie_changed.astype("int64")
    return ranked.sort_values(group_columns + ["standing_rank"] + id_columns).reset_index(drop=True)


def compute_cumulative_standings(
    results: pd.DataFrame,
    id_column: str,
    name_column: str,
) -> pd.DataFrame:
    """Aggregate per-round race points/wins into cumulative standings by round.

    Groups `results` by season, round, race_name, date, `id_column`, and
    `name_column`; sums points and counts wins per round; then adds a running
    per-season cumulative total and `standing_rank`. This is the single
    function every curated standings table (driver and constructor) calls —
    no parallel implementation.
    """
    grouped = (
        results.groupby(
            ["season", "round", "race_name", "date", id_column, name_column],
            dropna=False,
            as_index=False,
        )
        .agg(
            race_points=("points", "sum"),
            race_wins=("position", lambda values: int((values == 1).any())),
        )
        .sort_values(["season", id_column, "round"])
    )
    grouped["cumulative_points"] = grouped.groupby(["season", id_column])["race_points"].cumsum()
    grouped["cumulative_wins"] = grouped.groupby(["season", id_column])["race_wins"].cumsum()
    return add_standing_rank(grouped, ["season", "round"], [id_column])
