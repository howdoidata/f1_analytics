"""Monte Carlo of a driver's grid-to-finish change (the Singapore report).

The Singapore simulation code was never kept. Its method is reconstructed from
the PDF's text (`reports/golden/singapore-albon-grid-to-finish-2026-10-08.pdf`):

- Grid slot: Albon's 2026 grid slots, weighted 0.5 ** ((last_round - round) / 6).
- Retirement: per race p ~ Beta(n_nf + 8f, n_fin + 8(1 - f)), where n_nf / n_fin
  are Albon's non-finishes / finishes and f is the field non-finish rate
  (2026 R1-R16, all cars, Albon included).
- Finishing change: a coin flip between one of Albon's own finishing changes
  and a 2026 non-Albon finisher whose grid is within 2 of the drawn slot.
- Retirement change: a 2026 non-finish whose grid is within 2 of the slot.
- RNG: numpy.random.default_rng(seed), seeds 0-24, 20,000 races per seed.

Every function takes `with_change` season rows (see `analysis.results`) and
never reads the database.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from f1_analytics.analysis.results import field_non_finish_rate


SEEDS = tuple(range(25))
RACES_PER_RUN = 20_000
RECENCY_HALF_LIFE = 6
PRIOR_STRENGTH = 8
PEER_WINDOW = 2
OWN_FINISH_SHARE = 0.5

# The assumption changes the report's sensitivity table runs: label, build_sim_inputs kwargs.
SENSITIVITY_SCENARIOS = (
    ("Base case", {}),
    ("Exclude round 16", {"exclude_rounds": (16,)}),
    ("No recency weighting on grid slots", {"recency": False}),
    ("Finishing change from field peers only", {"own_share": 0.0}),
    ("Finishing change from Albon's own finishes only", {"own_share": 1.0}),
    ("Retirement rate = field average", {"retirement": "field"}),
    ("Retirement rate = Albon's own record", {"retirement": "own"}),
)

GRID_SLOTS = tuple(range(11, 21))

# Qualifying bands of the "revise once qualifying lands" table: label, grid slots.
QUALIFYING_BANDS = (
    ("15th or better", tuple(range(11, 16))),
    ("16th to 19th", tuple(range(16, 20))),
    ("20th or worse", (20,)),
)


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


@dataclass(frozen=True)
class ScenarioResult:
    """The runs of one scenario: pooled stats, per-run stats and the raw draws."""

    pooled: dict[str, object]
    per_run: list[dict[str, object]]
    changes: list[np.ndarray]
    retired: list[np.ndarray]


def run_scenario_detail(inputs: SimInputs, seeds=SEEDS, n: int = RACES_PER_RUN) -> ScenarioResult:
    """One run per seed, keeping the draws (for the histogram and running-mean figures)."""
    runs = [simulate(inputs, n, seed) for seed in seeds]
    changes = [c for c, _ in runs]
    retired = [r for _, r in runs]
    per_run = [outcome_stats(c, r) for c, r in runs]
    pooled = outcome_stats(np.concatenate(changes), np.concatenate(retired))
    return ScenarioResult(pooled, per_run, changes, retired)


def run_scenario(inputs: SimInputs, seeds=SEEDS, n: int = RACES_PER_RUN):
    """25 runs; returns (pooled stats, per-run stats)."""
    result = run_scenario_detail(inputs, seeds, n)
    return result.pooled, result.per_run


def run_table(per_run: list[dict[str, object]]) -> pd.DataFrame:
    """Average, lowest and highest run for each headline measure."""
    rows = []
    for measure, key in (
        ("Median change", "median"),
        ("Most common change", "mode"),
        ("Mean change", "mean"),
        ("Chance of gaining places", "gains"),
        ("Chance of losing places", "loses"),
    ):
        values = [run[key] for run in per_run]
        rows.append(
            {"measure": measure, "key": key, "average": float(np.mean(values)), "lowest": min(values), "highest": max(values)}
        )
    return pd.DataFrame(rows)


def sensitivity_table(
    season_rows: pd.DataFrame,
    base_pooled: dict[str, object] | None = None,
    seeds=SEEDS,
    n: int = RACES_PER_RUN,
    driver_id: str = "albon",
) -> pd.DataFrame:
    """Pooled stats under each assumption change in `SENSITIVITY_SCENARIOS`.

    `base_pooled` reuses an already-run base case.
    """
    rows = []
    for label, kwargs in SENSITIVITY_SCENARIOS:
        if not kwargs and base_pooled is not None:
            stats = base_pooled
        else:
            stats = run_scenario(build_sim_inputs(season_rows, driver_id, **kwargs), seeds, n)[0]
        rows.append({"assumption": label, **{k: stats[k] for k in ("retire", "median", "mean", "gains", "level", "loses")}})
    return pd.DataFrame(rows)


def grid_slot_table(base_inputs: SimInputs, slots=GRID_SLOTS, seeds=SEEDS, n: int = RACES_PER_RUN) -> pd.DataFrame:
    """Pooled stats with the grid slot fixed at each of `slots`."""
    rows = []
    for slot in slots:
        stats = run_scenario(replace(base_inputs, fixed_slot=slot), seeds, n)[0]
        rows.append(
            {
                "slot": slot,
                "median": stats["median"],
                "middle_80_low": stats["middle_80"][0],
                "middle_80_high": stats["middle_80"][1],
                "gains": stats["gains"],
                "level": stats["level"],
                "loses": stats["loses"],
            }
        )
    return pd.DataFrame(rows)


def revise_on_qualifying(grid_table: pd.DataFrame, bands=QUALIFYING_BANDS) -> pd.DataFrame:
    """The estimate for each qualifying band: the grid-slot median, or every distinct median if they differ."""
    medians = grid_table.set_index("slot")["median"]
    rows = []
    for label, slots in bands:
        band = sorted({int(medians[s]) for s in slots})
        rows.append({"qualifies": label, "estimate": band[0] if len(band) == 1 else tuple(band)})
    return pd.DataFrame(rows)


def outcome_histogram(result: ScenarioResult) -> pd.DataFrame:
    """Share of all simulated races at each change, split into finishes and retirements."""
    change = np.concatenate(result.changes)
    retired = np.concatenate(result.retired)
    frame = pd.DataFrame({"change": change, "outcome": np.where(retired, "Retires", "Finishes the race")})
    counts = frame.groupby(["change", "outcome"]).size().unstack("outcome", fill_value=0)
    for column in ("Finishes the race", "Retires"):
        if column not in counts:
            counts[column] = 0
    shares = counts[["Finishes the race", "Retires"]] / len(change) * 100
    return shares.reset_index().rename_axis(columns=None)


def running_means(result: ScenarioResult, points: int = 40, start: int = 50) -> pd.DataFrame:
    """Running mean change of each run at log-spaced race counts (long format: run, races, mean)."""
    n = len(result.changes[0])
    marks = np.unique(np.round(np.geomspace(min(start, n), n, points)).astype(int))
    rows = []
    for i, change in enumerate(result.changes, start=1):
        cumulative = np.cumsum(change)
        for m in marks:
            rows.append({"run": i, "races": int(m), "mean": float(cumulative[m - 1] / m)})
    return pd.DataFrame(rows)
