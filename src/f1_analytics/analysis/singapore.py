"""Albon's grid-to-finish change at the 2026 Singapore GP (pre-race analysis, R1-R16 data)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from f1_analytics.analysis import simulation
from f1_analytics.analysis.formatting import estimate_text, pct, signed, span
from f1_analytics.analysis.results import (
    change_summary,
    field_non_finish_rate,
    race_label,
    race_mask,
    season_rows,
    with_change,
)


SEASON = 2026
DRIVER_ID = "albon"
LAST_ROUND = 16  # the data the pre-race report used
RACE_ROUND = 17  # the 2026 Singapore Grand Prix


def season_data(results: pd.DataFrame, season: int = SEASON, last_round: int = LAST_ROUND) -> pd.DataFrame:
    """Every car's `with_change` row, `season` R1 to `last_round` (the simulation's inputs)."""
    return season_rows(results, season, last_round)


def driver_rounds(season: pd.DataFrame, driver_id: str = DRIVER_ID) -> pd.DataFrame:
    """The driver's grid, finish, change and note for each round."""
    rows = season[season["driver_id"] == driver_id].sort_values("round")
    return pd.DataFrame(
        {
            "round": rows["round"].astype(int).to_numpy(),
            "race": [race_label(name) for name in rows["race_name"]],
            "race_name": rows["race_name"].to_numpy(),
            "grid": rows["grid"].astype(int).to_numpy(),
            "finish": rows["position"].astype(int).to_numpy(),
            "change": rows["change"].astype(int).to_numpy(),
            "status": rows["status"].to_numpy(),
            "finished": rows["finished"].to_numpy(),
            "note": ["" if done else status for done, status in zip(rows["finished"], rows["status"])],
        }
    )


def driver_summary(season: pd.DataFrame, driver_id: str = DRIVER_ID) -> dict[str, float]:
    """`change_summary` of the driver plus the field non-finish rate (all cars, in %)."""
    summary = change_summary(season[season["driver_id"] == driver_id])
    summary["field_non_finish_pct"] = field_non_finish_rate(season) * 100
    return summary


def driver_at_race(
    results: pd.DataFrame, race: str = "singapore", driver_id: str = DRIVER_ID, before_season: int = SEASON
) -> pd.DataFrame:
    """The driver's grid, finish, change and note at every running of `race` before `before_season`."""
    rows = with_change(
        results[
            race_mask(results["race_name"], race)
            & (results["driver_id"] == driver_id)
            & (results["season"] < before_season)
        ]
    )
    rows = rows.sort_values("season")
    return pd.DataFrame(
        {
            "season": rows["season"].astype(int).to_numpy(),
            "grid": rows["grid"].astype(int).to_numpy(),
            "finish": rows["position"].astype(int).to_numpy(),
            "change": rows["change"].astype(int).to_numpy(),
            "note": ["" if done else status for done, status in zip(rows["finished"], rows["status"])],
        }
    )


def actual_result(
    results: pd.DataFrame, season: int = SEASON, round_: int = RACE_ROUND, driver_id: str = DRIVER_ID
) -> dict[str, object]:
    """The driver's real result at the race, or `raced: False` when it has no results yet."""
    rows = with_change(
        results[(results["season"] == season) & (results["round"] == round_) & (results["driver_id"] == driver_id)]
    )
    if rows.empty:
        return {"raced": False, "text": "not yet raced"}
    row = rows.iloc[0]
    return {
        "raced": True,
        "race_name": row["race_name"],
        "grid": int(row["grid"]),
        "finish": int(row["position"]),
        "change": int(row["change"]),
        "status": row["status"],
        "finished": bool(row["finished"]),
    }


@dataclass(frozen=True)
class SimulationReport:
    """Everything the Singapore report shows from the simulation."""

    inputs: simulation.SimInputs
    base: simulation.ScenarioResult
    run_table: pd.DataFrame
    sensitivity: pd.DataFrame
    grid_slots: pd.DataFrame
    revise: pd.DataFrame
    histogram: pd.DataFrame
    running_means: pd.DataFrame

    @property
    def pooled(self) -> dict[str, object]:
        return self.base.pooled

    @property
    def runs(self) -> int:
        return len(self.base.changes)

    @property
    def races_per_run(self) -> int:
        return len(self.base.changes[0])

    def scenario(self, assumption: str) -> dict[str, object]:
        """One row of the sensitivity table as a dict."""
        rows = self.sensitivity[self.sensitivity["assumption"] == assumption]
        if rows.empty:
            raise KeyError(assumption)
        return rows.iloc[0].to_dict()


def simulation_report(
    season: pd.DataFrame,
    driver_id: str = DRIVER_ID,
    seeds=simulation.SEEDS,
    n: int = simulation.RACES_PER_RUN,
) -> SimulationReport:
    """Run the base case, the sensitivity scenarios and the grid-slot runs."""
    inputs = simulation.build_sim_inputs(season, driver_id)
    base = simulation.run_scenario_detail(inputs, seeds, n)
    grid_slots = simulation.grid_slot_table(inputs, seeds=seeds, n=n)
    return SimulationReport(
        inputs=inputs,
        base=base,
        run_table=simulation.run_table(base.per_run),
        sensitivity=simulation.sensitivity_table(season, base.pooled, seeds, n, driver_id),
        grid_slots=grid_slots,
        revise=simulation.revise_on_qualifying(grid_slots),
        histogram=simulation.outcome_histogram(base),
        running_means=simulation.running_means(base),
    )


# --------------------------------------------------------------------------
# Display tables (strings, ready for `formatting.markdown_table`)
# --------------------------------------------------------------------------

# Round 16 arrived from Jolpica labelled "Bahrain Grand Prix in Malaysia" (see the caveats).
FLAGGED_ROUNDS = {16: "*"}


def rounds_display(rounds: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Round": [f"R{r}" for r in rounds["round"]],
            "Race": [f"{race}{FLAGGED_ROUNDS.get(r, '')}" for r, race in zip(rounds["round"], rounds["race"])],
            "Grid": rounds["grid"],
            "Finish": [f"P{p}" for p in rounds["finish"]],
            "Change": [signed(int(c)) for c in rounds["change"]],
            "Note": rounds["note"],
        }
    )


def history_display(history: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Season": history["season"],
            "Grid": history["grid"],
            "Finish": [f"P{p}" for p in history["finish"]],
            "Change": [signed(int(c)) for c in history["change"]],
            "Note": history["note"],
        }
    )


def _measure_text(key: str, value) -> str:
    if key in ("median", "mode"):
        value = round(float(value), 2)
        return signed(int(value)) if value == int(value) else signed(value)
    if key == "mean":
        return signed(float(value))
    return pct(float(value))


def run_table_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Measure": table["measure"],
            "Average of 25 runs": [_measure_text(k, v) for k, v in zip(table["key"], table["average"])],
            "Lowest run": [_measure_text(k, v) for k, v in zip(table["key"], table["lowest"])],
            "Highest run": [_measure_text(k, v) for k, v in zip(table["key"], table["highest"])],
        }
    )


def sensitivity_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Assumption changed": table["assumption"],
            "Retire": [pct(v) for v in table["retire"]],
            "Median": [signed(int(v)) for v in table["median"]],
            "Mean": [signed(float(v)) for v in table["mean"]],
            "Gains": [pct(v) for v in table["gains"]],
            "Level": [pct(v) for v in table["level"]],
            "Loses": [pct(v) for v in table["loses"]],
        }
    )


def grid_slots_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "If he starts": [f"P{s}" for s in table["slot"]],
            "Median": [signed(int(v)) for v in table["median"]],
            "Middle 80%": [span(lo, hi) for lo, hi in zip(table["middle_80_low"], table["middle_80_high"])],
            "Gains": [pct(v) for v in table["gains"]],
            "Level": [pct(v) for v in table["level"]],
            "Loses": [pct(v) for v in table["loses"]],
        }
    )


def revise_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"If Albon qualifies": table["qualifies"], "Then estimate": [estimate_text(v) for v in table["estimate"]]}
    )


def actual_text(actual: dict[str, object]) -> str:
    """'Grid 16 → P18, change −2 (Retired)', or 'not yet raced'."""
    if not actual["raced"]:
        return "not yet raced"
    note = "" if actual["finished"] else f" ({actual['status']})"
    return f"Grid {actual['grid']} → P{actual['finish']}, change {signed(actual['change'])}{note}"
