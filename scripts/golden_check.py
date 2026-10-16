#!/usr/bin/env python3
"""Print every golden value from the local DuckDB next to its baseline.

The baselines are the two PDF reports in `reports/golden/`. Each stage PR runs
this script and pastes its output, explaining every DEVIATION row: which value,
from what to what, and why. A deviation is not a failure, so the script exits 0
whenever the database could be read. It is not a pytest test.

The Singapore simulation code was never kept. Its method is reconstructed from
the PDF's text:

- Grid slot: Albon's 2026 grid slots, weighted 0.5 ** ((last_round - round) / 6).
- Retirement: per race p ~ Beta(n_nf + 8f, n_fin + 8(1 - f)), where n_nf / n_fin
  are Albon's non-finishes / finishes and f is the field non-finish rate
  (2026 R1-R16, all cars, Albon included).
- Finishing change: a coin flip between one of Albon's own finishing changes
  and a 2026 non-Albon finisher whose grid is within 2 of the drawn slot.
- Retirement change: a 2026 non-finish whose grid is within 2 of the slot.
- RNG: numpy.random.default_rng(seed), seeds 0-24, 20,000 races per seed.

The database is opened read-only and no network is used.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.database.duckdb_io import connect_duckdb


FINISHED_STATUSES = ("Finished", "Lapped")
SEASON = 2026

ZANDVOORT_LAST_ROUND = 11
SINGAPORE_LAST_ROUND = 16

SEEDS = tuple(range(25))
RACES_PER_RUN = 20_000
RECENCY_HALF_LIFE = 6
PRIOR_STRENGTH = 8
PEER_WINDOW = 2
OWN_FINISH_SHARE = 0.5

# A judgement made in the Zandvoort PDF (section 5), not a computed answer.
ZANDVOORT_ESTIMATE = 31
ZANDVOORT_ESTIMATE_RANGE = (29, 33)


# --------------------------------------------------------------------------
# Tolerances and comparison
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tolerance:
    kind: str  # "exact" | "abs" | "ends"
    amount: float = 0.0
    label: str = "exact"


EXACT = Tolerance("exact")
WITHIN_2PP = Tolerance("abs", 2.0, "±2 pp")
WITHIN_0_1 = Tolerance("abs", 0.1, "±0.1")
ENDS_WITHIN_1 = Tolerance("ends", 1.0, "±1 each end")

_EPS = 1e-9


def within_tolerance(regenerated, baseline, tolerance: Tolerance) -> bool:
    """True when `regenerated` matches `baseline` under `tolerance`.

    Exact values are compared as given, so callers round to the baseline's
    displayed precision first.
    """
    if tolerance.kind == "exact":
        if isinstance(regenerated, float) or isinstance(baseline, float):
            return abs(float(regenerated) - float(baseline)) <= _EPS
        return regenerated == baseline
    if tolerance.kind == "abs":
        return abs(float(regenerated) - float(baseline)) <= tolerance.amount + _EPS
    if tolerance.kind == "ends":
        return all(
            abs(float(r) - float(b)) <= tolerance.amount + _EPS
            for r, b in zip(regenerated, baseline, strict=True)
        )
    raise ValueError(f"unknown tolerance kind: {tolerance.kind!r}")


def signed(value, decimals: int | None = None) -> str:
    """+3 / −3 / 0, using a real minus sign as the reports do.

    Integers print whole; floats print with `decimals` places (default 2).
    """
    if isinstance(value, (float, np.floating)):
        text = f"{abs(value):.{2 if decimals is None else decimals}f}"
    else:
        text = f"{abs(int(value))}"
    if text.strip("0.") == "":
        return text
    return ("+" if value > 0 else "−") + text


def signed1(value) -> str:
    return signed(value, 1)


def pct(value) -> str:
    return f"{value:.1f}%"


def plain(value) -> str:
    return str(value)


def span(value) -> str:
    lo, hi = value
    return f"{signed(lo)} to {signed(hi)}"


class Report:
    """Prints `name · regenerated · baseline · tolerance · OK/DEVIATION` rows."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str, bool]] = []

    def section(self, title: str) -> None:
        print()
        print(f"== {title}")

    def note(self, text: str) -> None:
        print(f"   {text}")

    def check(
        self,
        name: str,
        regenerated,
        baseline,
        tolerance: Tolerance = EXACT,
        fmt: Callable[[object], str] = plain,
        baseline_fmt: Callable[[object], str] | None = None,
    ) -> bool:
        ok = within_tolerance(regenerated, baseline, tolerance)
        row = (
            name,
            fmt(regenerated),
            (baseline_fmt or fmt)(baseline),
            tolerance.label,
            ok,
        )
        self.rows.append(row)
        print(" · ".join([*row[:4], "OK" if ok else "DEVIATION"]))
        return ok

    def summary(self) -> int:
        deviations = [row for row in self.rows if not row[4]]
        print()
        print(f"{len(self.rows)} values compared · {len(self.rows) - len(deviations)} OK · {len(deviations)} DEVIATION")
        for row in deviations:
            print(f"  DEVIATION: {row[0]}: {row[2]} -> {row[1]} ({row[3]})")
        return len(deviations)


# --------------------------------------------------------------------------
# Exact helpers
# --------------------------------------------------------------------------


def with_change(results: pd.DataFrame) -> pd.DataFrame:
    """Add `change` (grid - position; positive = places gained) and `finished`."""
    out = results.copy()
    out["change"] = out["grid"].astype(int) - out["position"].astype(int)
    out["finished"] = out["status"].isin(FINISHED_STATUSES)
    return out


def change_summary(driver_rows: pd.DataFrame) -> dict[str, float]:
    """Means of the change over finishes, non-finishes and all starts, plus mean grid."""
    finished = driver_rows["finished"]
    return {
        "starts": int(len(driver_rows)),
        "finishes": int(finished.sum()),
        "non_finishes": int((~finished).sum()),
        "mean_change_finished": float(driver_rows.loc[finished, "change"].mean()),
        "mean_change_non_finished": float(driver_rows.loc[~finished, "change"].mean()),
        "mean_change_all": float(driver_rows["change"].mean()),
        "mean_grid": float(driver_rows["grid"].mean()),
    }


def combined_by_round(team_rows: pd.DataFrame) -> pd.DataFrame:
    """Per round: combined classified position (plain sum, no exclusion), grid sum, best finish, any non-finish."""
    grouped = team_rows.groupby("round")
    return pd.DataFrame(
        {
            "combined": grouped["position"].sum().astype(int),
            "grid_sum": grouped["grid"].sum().astype(int),
            "cars": grouped.size(),
            "best": grouped["position"].min().astype(int),
            "any_non_finish": grouped["status"].apply(lambda s: bool((~s.isin(FINISHED_STATUSES)).any())),
        }
    ).sort_index()


def season_summary(values: pd.Series) -> dict[str, float]:
    """n, min, max, mean, median and sample stdev."""
    return {
        "n": int(values.count()),
        "min": int(values.min()),
        "max": int(values.max()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "stdev": float(values.std(ddof=1)),
    }


def lap_text(td: pd.Timedelta) -> str:
    total = td.total_seconds()
    minutes = int(total // 60)
    return f"{minutes}:{total - 60 * minutes:06.3f}"


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SimInputs:
    grids: np.ndarray
    grid_weights: np.ndarray
    own_finish_changes: np.ndarray
    peer_grid: np.ndarray
    peer_change: np.ndarray
    retire_grid: np.ndarray
    retire_change: np.ndarray
    beta_a: float
    beta_b: float
    fixed_p: float | None = None
    fixed_slot: int | None = None
    own_share: float = OWN_FINISH_SHARE


def build_sim_inputs(
    season_rows: pd.DataFrame,
    driver_id: str = "albon",
    *,
    exclude_rounds: tuple[int, ...] = (),
    recency: bool = True,
    own_share: float = OWN_FINISH_SHARE,
    retirement: str = "blend",  # "blend" | "field" | "own"
    fixed_slot: int | None = None,
) -> SimInputs:
    rows = season_rows[~season_rows["round"].isin(exclude_rounds)]
    driver = rows[rows["driver_id"] == driver_id].sort_values("round")
    field = rows[rows["driver_id"] != driver_id]
    non_finish = rows[~rows["finished"]]

    last_round = int(driver["round"].max())
    if recency:
        weights = 0.5 ** ((last_round - driver["round"].to_numpy()) / RECENCY_HALF_LIFE)
    else:
        weights = np.ones(len(driver))
    weights = weights / weights.sum()

    f = field_non_finish_rate(rows)
    n_nf = int((~driver["finished"]).sum())
    n_fin = int(driver["finished"].sum())
    fixed_p = {"blend": None, "field": f, "own": n_nf / (n_nf + n_fin)}[retirement]

    peers = field[field["finished"]]
    return SimInputs(
        grids=driver["grid"].to_numpy(dtype=int),
        grid_weights=weights,
        own_finish_changes=driver.loc[driver["finished"], "change"].to_numpy(dtype=int),
        peer_grid=peers["grid"].to_numpy(dtype=int),
        peer_change=peers["change"].to_numpy(dtype=int),
        retire_grid=non_finish["grid"].to_numpy(dtype=int),
        retire_change=non_finish["change"].to_numpy(dtype=int),
        beta_a=n_nf + PRIOR_STRENGTH * f,
        beta_b=n_fin + PRIOR_STRENGTH * (1 - f),
        fixed_p=fixed_p,
        fixed_slot=fixed_slot,
        own_share=own_share,
    )


def field_non_finish_rate(season_rows: pd.DataFrame) -> float:
    """Non-finish rate over every car in `season_rows` (the PDF's "field rate of 21%")."""
    return float((~season_rows["finished"]).mean())


def _draw_near(rng, slots, pool_grid, pool_change) -> np.ndarray:
    out = np.empty(len(slots), dtype=int)
    for slot in np.unique(slots):
        idx = np.flatnonzero(slots == slot)
        pool = pool_change[np.abs(pool_grid - slot) <= PEER_WINDOW]
        if pool.size == 0:
            raise ValueError(f"no rows within {PEER_WINDOW} of grid slot {slot}")
        out[idx] = rng.choice(pool, size=idx.size)
    return out


def simulate(inputs: SimInputs, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """One run of `n` races. Returns (change per race, retired per race)."""
    rng = np.random.default_rng(seed)
    if inputs.fixed_slot is None:
        slots = rng.choice(inputs.grids, size=n, p=inputs.grid_weights)
    else:
        slots = np.full(n, inputs.fixed_slot, dtype=int)
    if inputs.fixed_p is None:
        p = rng.beta(inputs.beta_a, inputs.beta_b, size=n)
    else:
        p = np.full(n, inputs.fixed_p)
    retired = rng.random(n) < p
    use_own = rng.random(n) < inputs.own_share

    change = np.empty(n, dtype=int)
    own = ~retired & use_own
    peer = ~retired & ~use_own
    change[own] = rng.choice(inputs.own_finish_changes, size=int(own.sum()))
    change[peer] = _draw_near(rng, slots[peer], inputs.peer_grid, inputs.peer_change)
    change[retired] = _draw_near(rng, slots[retired], inputs.retire_grid, inputs.retire_change)
    return change, retired


def outcome_stats(change: np.ndarray, retired: np.ndarray) -> dict[str, object]:
    values, counts = np.unique(change, return_counts=True)
    shares = counts / change.size * 100
    q = lambda p: int(np.quantile(change, p, method="inverted_cdf"))  # noqa: E731
    return {
        "retire": float(retired.mean() * 100),
        "median": q(0.5),
        "mode": int(values[np.argmax(counts)]),
        "mean": float(change.mean()),
        "gains": float((change > 0).mean() * 100),
        "level": float((change == 0).mean() * 100),
        "loses": float((change < 0).mean() * 100),
        "middle_half": (q(0.25), q(0.75)),
        "middle_80": (q(0.10), q(0.90)),
        "share_of": {int(v): float(s) for v, s in zip(values, shares)},
    }


def run_scenario(inputs: SimInputs, seeds=SEEDS, n: int = RACES_PER_RUN):
    """25 runs; returns (pooled stats, per-run stats)."""
    runs = [simulate(inputs, n, seed) for seed in seeds]
    per_run = [outcome_stats(c, r) for c, r in runs]
    pooled = outcome_stats(np.concatenate([c for c, _ in runs]), np.concatenate([r for _, r in runs]))
    return pooled, per_run


# --------------------------------------------------------------------------
# Baselines, transcribed from the PDFs in reports/golden/
# --------------------------------------------------------------------------

SINGAPORE_ROUNDS = [
    # round, label, grid, finish, change, note
    (1, "Australian", 15, 12, 3, ""),
    (2, "Chinese", 22, 22, 0, "Did not start"),
    (3, "Japanese", 17, 20, -3, ""),
    (4, "Miami", 15, 10, 5, ""),
    (5, "Canadian", 18, 21, -3, "Retired"),
    (6, "Monaco", 11, 8, 3, ""),
    (7, "Barcelona", 18, 18, 0, ""),
    (8, "Austrian", 18, 17, 1, ""),
    (9, "British", 16, 21, -5, "Retired"),
    (10, "Belgian", 15, 15, 0, ""),
    (11, "Hungarian", 19, 17, 2, ""),
    (12, "Dutch", 16, 17, -1, "Retired"),
    (13, "Italian", 20, 17, 3, ""),
    (14, "Spanish", 16, 15, 1, ""),
    (15, "Azerbaijan", 12, 20, -8, "Retired"),
    (16, "Bahrain in Malaysia", 18, 21, -3, "Retired"),
]

ALBON_AT_SINGAPORE = [
    # season, grid, finish, change, note
    (2019, 6, 6, 0, ""),
    (2022, 18, 17, 1, ""),
    (2023, 14, 11, 3, ""),
    (2024, 11, 20, -9, "Retired"),
    (2025, 20, 14, 6, ""),
]

RUN_TABLE = [
    # measure, key, average, lowest, highest, tolerance, fmt
    ("Median change", "median", 1, 1, 1, EXACT, signed),
    ("Most common change", "mode", 3, 3, 3, EXACT, signed),
    ("Mean change", "mean", 0.73, 0.68, 0.80, WITHIN_0_1, signed),
    ("Chance of gaining places", "gains", 54.5, 53.9, 55.1, WITHIN_2PP, pct),
    ("Chance of losing places", "loses", 34.0, 33.2, 34.5, WITHIN_2PP, pct),
]

SENSITIVITY = [
    # label, build_sim_inputs kwargs, retire, median, mean, gains, level, loses
    ("Base case", {}, 32, 1, 0.73, 54, 12, 34),
    ("Exclude round 16", {"exclude_rounds": (16,)}, 29, 1, 0.83, 56, 12, 32),
    ("No recency weighting on grid slots", {"recency": False}, 32, 1, 0.80, 55, 12, 33),
    ("Finishing change from field peers only", {"own_share": 0.0}, 32, 1, 1.31, 57, 7, 36),
    ("Finishing change from Albon's own finishes only", {"own_share": 1.0}, 32, 1, 0.17, 52, 16, 32),
    ("Retirement rate = field average", {"retirement": "field"}, 22, 1, 1.23, 61, 12, 27),
    ("Retirement rate = Albon's own record", {"retirement": "own"}, 37, 1, 0.47, 51, 11, 38),
]

GRID_TABLE = [
    # slot, median, middle 80%, gains, level, loses
    (11, 0, (-11, 3), 44, 11, 45),
    (12, 0, (-10, 4), 45, 12, 43),
    (13, 0, (-9, 5), 46, 11, 43),
    (14, 0, (-5, 5), 47, 11, 42),
    (15, 0, (-4, 5), 49, 10, 40),
    (16, 1, (-3, 5), 51, 10, 39),
    (17, 1, (-3, 5), 54, 10, 36),
    (18, 1, (-3, 5), 59, 11, 31),
    (19, 1, (-2, 6), 60, 14, 26),
    (20, 2, (-2, 7), 67, 15, 18),
]

REVISE_ON_QUALIFYING = [
    # label, slots, estimate
    ("15th or better", range(11, 16), 0),
    ("16th to 19th", range(16, 20), 1),
    ("20th or worse", range(20, 21), 2),
]


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


def _load(conn) -> dict[str, pd.DataFrame]:
    results = conn.execute(
        "SELECT season, round, race_name, driver_id, constructor_id, grid, position, status "
        "FROM combined_results"
    ).df()
    standings = conn.execute(
        "SELECT season, round, constructor_id, standing_rank, cumulative_points "
        "FROM combined_constructor_standings_by_round WHERE season = ?",
        [SEASON],
    ).df()
    laps = conn.execute(
        "SELECT season, round, race_label, Driver, driver_id, constructor_id, LapTime "
        "FROM raw_fastf1_laps WHERE season = ?",
        [SEASON],
    ).df()
    return {"results": results, "standings": standings, "laps": laps}


def check_zandvoort(report: Report, data: dict[str, pd.DataFrame]) -> None:
    results = data["results"]
    season = with_change(results[(results["season"] == SEASON) & (results["round"] <= ZANDVOORT_LAST_ROUND)])
    williams = season[season["constructor_id"].str.contains("williams", case=False, na=False)]
    by_round = combined_by_round(williams)

    report.section("Zandvoort PDF: validation answers")
    report.check("Miami (R4) Williams combined finish", int(by_round.loc[4, "combined"]), 19)
    report.check("Canada (R5) best Williams finish", f"P{by_round.loc[5, 'best']}", "P9")
    laps = data["laps"]
    mel = laps[(laps["round"] == 1) & laps["constructor_id"].str.contains("williams", case=False, na=False)].copy()
    mel["lap"] = pd.to_timedelta(mel["LapTime"])
    best = mel.loc[mel["lap"].idxmin()]
    report.check("Melbourne (R1) fastest Williams lap", f"{lap_text(best['lap'])} ({best['driver_id']})", "1:23.590 (sainz)")

    report.section(f"Zandvoort PDF: Williams combined finish per round, {SEASON} R1–R{ZANDVOORT_LAST_ROUND}")
    report.note(
        "per round: " + ", ".join(f"R{r} {v}" for r, v in by_round["combined"].items())
    )
    s = season_summary(by_round["combined"])
    report.check("season n", s["n"], 11)
    report.check("season min", s["min"], 19)
    report.check("season max", s["max"], 38)
    report.check("season mean", round(s["mean"], 1), 30.6)
    report.check("season median", round(s["median"], 1), 31.0)
    report.check("season stdev (sample)", round(s["stdev"], 1), 5.7)
    report.check("last 6 rounds mean", round(by_round["combined"].tail(6).mean(), 1), 32.5)
    report.check("last 4 rounds mean", round(by_round["combined"].tail(4).mean(), 1), 35.2)

    report.section("Zandvoort PDF: Zandvoort 2021–25 history (all teams, grid > 0)")
    dutch = results[
        results["race_name"].str.contains("dutch", case=False, na=False)
        & results["season"].between(2021, 2025)
        & (results["grid"] > 0)
    ]
    moved = (dutch["position"] - dutch["grid"]).abs()
    report.check("starts", int(len(dutch)), 97)
    report.check("median |position change|", float(moved.median()), 3.0)
    report.check("starts moving 5 or more places", int((moved >= 5).sum()), 30)

    report.section("Zandvoort PDF: estimate (section 5)")
    lo, hi = ZANDVOORT_ESTIMATE_RANGE
    report.note(
        f"STATED CONSTANT (a judgement, not computed): estimate {ZANDVOORT_ESTIMATE}, range {lo}–{hi}."
    )
    report.note("Inputs it was weighed from, each compared exactly:")
    report.check("input: season median", round(s["median"], 1), 31.0)
    report.check("input: last 4 rounds mean", round(by_round["combined"].tail(4).mean(), 1), 35.2)
    report.check(
        "input: rounds with a DNF or DNS",
        f"{int(by_round['any_non_finish'].sum())} of {len(by_round)}",
        "5 of 11",
    )
    report.check("input: mean grid, season (both cars)", round(williams["grid"].mean(), 1), 16.5)
    last4 = williams[williams["round"] > ZANDVOORT_LAST_ROUND - 4]
    report.check("input: mean grid, last 4 rounds (both cars)", round(last4["grid"].mean(), 1), 17.0)
    st = data["standings"]
    st = st[st["round"] == ZANDVOORT_LAST_ROUND]
    w = st[st["constructor_id"].str.contains("williams", case=False, na=False)].iloc[0]
    report.check(
        f"input: constructors' standings after R{ZANDVOORT_LAST_ROUND}",
        f"P{int(w['standing_rank'])} of {len(st)}, {float(w['cumulative_points']):g} pts",
        "P9 of 11, 11 pts",
    )
    report.check("input: Zandvoort median position change", float(moved.median()), 3.0)
    z2025 = results[
        results["race_name"].str.contains("dutch", case=False, na=False)
        & (results["season"] == 2025)
        & results["constructor_id"].str.contains("williams", case=False, na=False)
    ]
    report.check("input: 2025 Zandvoort combined total", int(z2025["position"].sum()), 18)


def check_singapore_exact(report: Report, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    results = data["results"]
    season = with_change(results[(results["season"] == SEASON) & (results["round"] <= SINGAPORE_LAST_ROUND)])
    albon = season[season["driver_id"] == "albon"].set_index("round")

    report.section(f"Singapore PDF: Albon {SEASON} grid, finish and change per round")
    for rnd, label, grid, finish, change, note in SINGAPORE_ROUNDS:
        row = albon.loc[rnd]
        got_note = "" if row["finished"] else row["status"]
        report.check(
            f"R{rnd} {label} (grid, finish, change, note)",
            (int(row["grid"]), f"P{int(row['position'])}", signed(int(row["change"])), got_note),
            (grid, f"P{finish}", signed(change), note),
        )

    report.section("Singapore PDF: summaries")
    s = change_summary(albon)
    report.check("non-finishes in starts", f"{s['non_finishes']} in {s['starts']}", "6 in 16")
    report.check("finishes", s["finishes"], 10)
    report.check("mean change over finishes", round(s["mean_change_finished"], 1), 1.5, fmt=signed1)
    report.check("mean change over non-finishes", round(s["mean_change_non_finished"], 1), -3.3, fmt=signed1)
    report.check("mean change over all starts", round(s["mean_change_all"], 1), -0.3, fmt=signed1)
    report.check("mean grid slot", round(s["mean_grid"], 1), 16.6)
    report.note("(The PDF's method text says +2.3 / −2.7; the baseline is its table and summary row.)")
    all_rate = field_non_finish_rate(season)
    report.note(f"field non-finish rate, all 22 cars: {pct(all_rate * 100)} (simulation input f)")
    report.check("field retirement rate (all cars)", round(all_rate * 100), 21, fmt=lambda v: f"{v}%")

    report.section("Singapore PDF: Albon at Singapore")
    sg = with_change(
        results[results["race_name"].str.contains("singapore", case=False, na=False) & (results["driver_id"] == "albon")]
    ).sort_values("season")
    for season_year, grid, finish, change, note in ALBON_AT_SINGAPORE:
        row = sg[sg["season"] == season_year]
        got = None
        if len(row):
            first = row.iloc[0]
            got = (
                int(first["grid"]),
                f"P{int(first['position'])}",
                signed(int(first["change"])),
                "" if first["finished"] else first["status"],
            )
        report.check(f"{season_year} (grid, finish, change, note)", got, (grid, f"P{finish}", signed(change), note))
    return season


def check_singapore_simulation(report: Report, season: pd.DataFrame) -> None:
    base_inputs = build_sim_inputs(season)
    report.section(
        f"Singapore PDF: simulation ({len(SEEDS)} runs × {RACES_PER_RUN:,} races, seeds "
        f"{SEEDS[0]}–{SEEDS[-1]}, numpy default_rng)"
    )
    f = field_non_finish_rate(season)
    report.note(
        f"inputs: f = {f:.4f}; retirement p ~ Beta({base_inputs.beta_a:.3f}, {base_inputs.beta_b:.3f}) "
        f"(mean {base_inputs.beta_a / (base_inputs.beta_a + base_inputs.beta_b):.4f})"
    )
    pooled, per_run = run_scenario(base_inputs)

    report.check("blended retirement chance", pooled["retire"], 32, WITHIN_2PP, pct, lambda v: f"{v}%")
    report.check("median change", pooled["median"], 1, fmt=signed)
    report.check("most common change", pooled["mode"], 3, fmt=signed)
    report.check("mean change", pooled["mean"], 0.73, WITHIN_0_1, signed)
    report.check("gains places", pooled["gains"], 54, WITHIN_2PP, pct, lambda v: f"{v}%")
    report.check("no change", pooled["level"], 12, WITHIN_2PP, pct, lambda v: f"{v}%")
    report.check("loses places", pooled["loses"], 34, WITHIN_2PP, pct, lambda v: f"{v}%")
    for outcome, share in ((3, 14.4), (1, 13.5), (0, 11.5)):
        report.check(
            f"share at {signed(outcome)}", pooled["share_of"].get(outcome, 0.0), share, WITHIN_2PP, pct
        )
    report.check("middle half", pooled["middle_half"], (-2, 3), ENDS_WITHIN_1, span)
    report.check("middle 80%", pooled["middle_80"], (-4, 5), ENDS_WITHIN_1, span)

    report.section("Singapore PDF: 25 runs × 20,000 races")
    for measure, key, avg, lowest, highest, tol, fmt in RUN_TABLE:
        values = [run[key] for run in per_run]
        mean = float(np.mean(values))
        if tol is EXACT:
            mean = round(mean, 2)
        report.check(f"{measure}: average of 25 runs", mean, avg, tol, fmt)
        report.check(f"{measure}: lowest run", min(values), lowest, tol, fmt)
        report.check(f"{measure}: highest run", max(values), highest, tol, fmt)

    report.section("Singapore PDF: sensitivity")
    whole = lambda v: f"{v}%"  # noqa: E731
    for label, kwargs, retire, median, mean, gains, level, loses in SENSITIVITY:
        stats = pooled if not kwargs else run_scenario(build_sim_inputs(season, **kwargs))[0]
        report.check(f"{label}: retire", stats["retire"], retire, WITHIN_2PP, pct, whole)
        report.check(f"{label}: median", stats["median"], median, fmt=signed)
        report.check(f"{label}: mean", stats["mean"], mean, WITHIN_0_1, signed)
        report.check(f"{label}: gains", stats["gains"], gains, WITHIN_2PP, pct, whole)
        report.check(f"{label}: level", stats["level"], level, WITHIN_2PP, pct, whole)
        report.check(f"{label}: loses", stats["loses"], loses, WITHIN_2PP, pct, whole)

    report.section("Singapore PDF: grid slot")
    medians: dict[int, int] = {}
    for slot, median, middle_80, gains, level, loses in GRID_TABLE:
        stats = run_scenario(replace(base_inputs, fixed_slot=slot))[0]
        medians[slot] = stats["median"]
        report.check(f"P{slot}: median", stats["median"], median, fmt=signed)
        report.check(f"P{slot}: middle 80%", stats["middle_80"], middle_80, ENDS_WITHIN_1, span)
        report.check(f"P{slot}: gains", stats["gains"], gains, WITHIN_2PP, pct, whole)
        report.check(f"P{slot}: level", stats["level"], level, WITHIN_2PP, pct, whole)
        report.check(f"P{slot}: loses", stats["loses"], loses, WITHIN_2PP, pct, whole)

    report.section("Singapore PDF: revise on qualifying (from the grid-slot medians)")
    for label, slots, estimate in REVISE_ON_QUALIFYING:
        band = sorted({medians[s] for s in slots})
        got = band[0] if len(band) == 1 else tuple(band)
        report.check(f"qualifies {label}", got, estimate, fmt=lambda v: signed(v) if isinstance(v, int) else str(v))


def main(db_path: Path = DUCKDB_PATH) -> int:
    if not db_path.exists():
        print(
            f"golden_check: no DuckDB file at {db_path}. Build the local database first "
            "(scripts/build_f1_dataset.py, scripts/build_combined_dataset.py).",
            file=sys.stderr,
        )
        return 1

    with connect_duckdb(db_path, read_only=True) as conn:
        data = _load(conn)

    print(f"Golden check against {db_path}")
    print("Columns: name · regenerated · baseline · tolerance · OK/DEVIATION")
    report = Report()
    check_zandvoort(report, data)
    season = check_singapore_exact(report, data)
    check_singapore_simulation(report, season)
    report.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
