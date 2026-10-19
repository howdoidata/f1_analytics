"""Synthetic frames shaped like the marts, for the analysis tests (no DuckDB)."""

from __future__ import annotations

import pandas as pd

RESULT_COLUMNS = ["season", "round", "race_name", "driver_id", "constructor_id", "grid", "position", "status"]


def results_frame(records) -> pd.DataFrame:
    """Rows of (season, round, race_name, driver_id, constructor_id, grid, position, status)."""
    return pd.DataFrame(records, columns=RESULT_COLUMNS)


def synthetic_season(season: int = 2026, rounds: int = 6, cars: int = 22, race: str = "Test Grand Prix") -> pd.DataFrame:
    """A full field each round with a mix of finishes and non-finishes at every grid slot.

    Car 0 is "albon" and cars 0-1 are Williams. Positions are a rotation of the grid, so
    changes are both positive and negative, and every third car of a round retires.
    """
    records = []
    for rnd in range(1, rounds + 1):
        for car in range(cars):
            grid = (car + rnd) % cars + 1
            position = (car + 2 * rnd) % cars + 1
            status = "Retired" if (car + rnd) % 3 == 0 else ("Lapped" if car % 2 else "Finished")
            driver = "albon" if car == 0 else f"d{car}"
            team = "williams" if car in (0, 1) else f"t{car // 2}"
            records.append((season, rnd, f"Round {rnd} {race}", driver, team, grid, position, status))
    return results_frame(records)
