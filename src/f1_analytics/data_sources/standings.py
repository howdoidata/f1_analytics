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

    # Computed without `groupby(...).apply(...)`: when the frame holds exactly
    # ONE group, pandas unstacks that apply's result into a DataFrame instead
    # of the Series it returns for two or more groups, and assigning it to the
    # single `standing_rank` column raised `ValueError: Cannot set a DataFrame
    # with multiple columns to the single column standing_rank`. That is
    # reachable in normal operation — the first race weekend of a season, or a
    # single-round CSV extract — and it raised from this shared function, so
    # both `build_f1_dataset.py` and `build_combined_dataset.py` inherited the
    # crash (the latter's empty-frame guard caught only the zero-row case).
    #
    # The vectorized form below is shape-stable at every group count: a row
    # starts a new rank when it differs from the previous row on either
    # cumulative column, OR when it is the first row of its group. That
    # "first row" test uses a group-wise `cumcount()` rather than
    # `group_columns.shift()`, because on the frame's very first row every
    # `.shift()` is NaN and `.ne()` answers False on both comparisons — that
    # row would start no rank at all, leaving its group 0-based while every
    # later group was 1-based (reproduced live as 1950 round 1).
    is_first_in_group = ranked.groupby(group_columns, dropna=False).cumcount() == 0
    totals = ranked[["cumulative_points", "cumulative_wins"]]
    breaks_tie = totals.ne(totals.shift()).any(axis=1)
    ranked["standing_rank"] = (
        (breaks_tie | is_first_in_group)
        .groupby([ranked[column] for column in group_columns], dropna=False)
        .cumsum()
        .astype("int64")
    )
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
