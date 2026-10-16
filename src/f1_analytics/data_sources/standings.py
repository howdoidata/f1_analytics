"""Shared cumulative-standings logic reused by every curated standings table (AC 2)."""

from __future__ import annotations

import pandas as pd

# Stands in for a missing cumulative total when testing rows for a tie. Points
# and wins are counts, so no real total is negative and nothing genuine can
# collide with this value — it only ever makes two missing totals compare
# equal to each other.
_TIED_NAN_SENTINEL = -1.0


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
    # Standard competition ranking ("1224"): a row's rank is one plus the
    # number of rows strictly ahead of it, so two drivers tied for 2nd consume
    # positions 2 and 3 and the next driver is 4th.
    #
    # That rank is derived from each row's position within its already-sorted
    # group, NOT from `rank()` over the two cumulative columns: ranking the
    # columns independently and combining the results is not the same as
    # ordering on the pair, and gave two drivers on different points totals
    # (50 and 40) the same rank while leaving rank 1 unassigned. Deriving it
    # from position also stays shape-stable at every group count, including
    # the single-group case described above.
    #
    # `cumcount()` is that position, 0-based. Tied rows then take the smallest
    # position in their run of equal totals, which both produces the "1224"
    # skip and makes the count of skipped positions exactly the number of rows
    # tied above. Equality is computed on a NaN-filled copy so that two rows
    # equally placed on a missing total compare as tied — under raw `.ne()`,
    # NaN != NaN scored them as distinct and handed them different ranks.
    position_in_group = ranked.groupby(group_columns, dropna=False).cumcount()
    totals = ranked[["cumulative_points", "cumulative_wins"]]
    filled_totals = totals.fillna(_TIED_NAN_SENTINEL)
    is_first_in_group = position_in_group == 0
    breaks_tie = filled_totals.ne(filled_totals.shift()).any(axis=1)
    starts_new_rank = breaks_tie | is_first_in_group
    ranked["standing_rank"] = (
        position_in_group.where(starts_new_rank)
        .groupby([ranked[column] for column in group_columns], dropna=False)
        .ffill()
        .astype("int64")
        + 1
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
