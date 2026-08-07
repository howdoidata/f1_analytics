"""Combined-cutoff championship leader analysis.

Builds on the scoped, precedence-ruled combined Kaggle+Jolpica dataset
(`combined_results`, `combined_driver_standings_by_round`,
`combined_constructor_standings_by_round`) to find the true current-season
cutoff and answer the leader-conversion questions at that cutoff, alongside
the existing Kaggle-only-cutoff answer. See `docs/decisions.md`
(2026-07-09 combined-dataset decision) for the precedence rule.
"""

from __future__ import annotations

import pandas as pd

from f1_analytics.analysis.championship_leaders import build_conversion_table, current_leaders


def determine_cutoff_round(standings: pd.DataFrame, target_season: int) -> int:
    """Return the max round present for `target_season` in a standings-by-round table.

    Works for any table shaped like `driver_standings_by_round` /
    `constructor_standings_by_round` or their combined-dataset counterparts,
    so the same helper derives both the existing Kaggle-only cutoff and the
    new combined cutoff. Raises ValueError if the target season has no rows.
    """
    season_rounds = standings.loc[standings["season"] == target_season, "round"]
    if season_rounds.empty:
        raise ValueError(f"No combined standings rows found for season {target_season}.")
    return int(season_rounds.max())


def build_combined_current_leaders(
    driver_standings_combined: pd.DataFrame,
    constructor_standings_combined: pd.DataFrame,
    target_season: int,
    combined_cutoff_round: int,
) -> pd.DataFrame:
    """Return current-season driver and constructor leader rows at the combined cutoff."""
    return pd.concat(
        [
            current_leaders(
                driver_standings_combined,
                target_season,
                combined_cutoff_round,
                "driver_id",
                "driver_name",
                "driver",
            ),
            current_leaders(
                constructor_standings_combined,
                target_season,
                combined_cutoff_round,
                "constructor_id",
                "constructor",
                "constructor",
            ),
        ],
        ignore_index=True,
    )


def build_combined_conversion_tables(
    driver_standings_combined: pd.DataFrame,
    constructor_standings_combined: pd.DataFrame,
    driver_final: pd.DataFrame,
    constructor_final: pd.DataFrame,
    combined_cutoff_round: int,
    target_season: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recompute the historical leader-conversion tables at the combined-cutoff round.

    Reuses `build_conversion_table` (already parameterized by cutoff round)
    against the combined standings tables instead of a second, parallel
    implementation. Historical (pre-target-season) rows in the combined
    standings tables are Kaggle-derived only, since Jolpica gap-fill is
    scoped to the current season, so this only changes which round number
    historical seasons are compared at.
    """
    driver_conversion = build_conversion_table(
        driver_standings_combined,
        driver_final,
        combined_cutoff_round,
        target_season,
        id_column="driver_id",
        name_column="driver_name",
    )
    constructor_conversion = build_conversion_table(
        constructor_standings_combined,
        constructor_final,
        combined_cutoff_round,
        target_season,
        id_column="constructor_id",
        name_column="constructor",
    )
    return driver_conversion, constructor_conversion


def extract_current_season_deviations(coverage: pd.DataFrame, target_season: int) -> pd.DataFrame:
    """Return `kaggle_jolpica_coverage` rows for `target_season` that are not a clean match.

    Reuses the existing coverage view's output rather than re-deriving
    overlap/gap status.
    """
    season_coverage = coverage[coverage["season"] == target_season].copy()
    return season_coverage[season_coverage["results_coverage_status"] != "match"].sort_values("round")
