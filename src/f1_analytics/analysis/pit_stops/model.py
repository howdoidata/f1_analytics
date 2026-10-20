"""The pit-stop count model: a team's race stop total, red-flag stops included.

`fit_count_model(tables, season, round)` fits a Poisson GLM of each car's stops
(every `stop_type`) on races before `(season, round)`; `forecast` turns
it into a team total over `DRAWS` seeded draws. Every rate and every fit row
uses only races before the target, and each fit row's own rates use only
races before that row's race.

Model terms:

- Fit rows: every `car_races` row of a race before the target with a start
  compound and an air temperature, except cars out before their first stop
  (no stop and not finished, the `car_out_rate` rule), so the GLM models the
  stops of running cars. Target: all of the car's Jolpica stops (normal,
  sc_vsc, red_flag and unknown).
- Covariates: the circuit history rate (all stops per car at the circuit from
  2011), the team rate (the team's stops per car, all stops, in the season's
  earlier rounds; the previous season's when the season has no earlier round), the car's mean air temperature, the race's
  weather category (story 4's `_weather_category`) and the car's start compound.
  A circuit or team with no history uses the field mean: stops per car (all
  stops) over the fit races (for a fit row, the fit races before its race).
  A covariate with one value across the fit rows, or one the others already
  explain, is left out of that fit.
- A draw: one GLM coefficient vector from their estimated normal (`params`,
  `cov_params`), shared by the team's cars; weather from the weights; then
  per car, the car out before its first stop with probability
  `car_out_rate` (0 stops), else Poisson(mu). The
  team total is the sum over its cars; red-flag stops are inside mu, with no
  separate red-flag part.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, Sequence

import numpy as np
import pandas as pd

from f1_analytics.analysis.pit_stops.history import (
    HISTORY_START_SEASON,
    UnknownInputError,
    _before,
    _stop_counts,
    _stops_per_car,
    _weather_category,
    check_inputs,
)
from f1_analytics.analysis.pit_stops.weather import WEATHER_CATEGORIES
from f1_analytics.analysis.results import FINISHED_STATUSES

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


SEED = 20261025
DRAWS = 10_000
COMPOUNDS = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")
REFERENCE_COMPOUND = "MEDIUM"
REFERENCE_WEATHER = "dry"
# Nearest levels first: a level the fit never saw uses the first one it did.
WEATHER_FALLBACK = {"dry": ("mixed", "wet"), "mixed": ("dry", "wet"), "wet": ("mixed", "dry")}
COMPOUND_FALLBACK = {
    "SOFT": ("MEDIUM", "HARD", "INTERMEDIATE", "WET"),
    "MEDIUM": ("SOFT", "HARD", "INTERMEDIATE", "WET"),
    "HARD": ("MEDIUM", "SOFT", "INTERMEDIATE", "WET"),
    "INTERMEDIATE": ("WET", "MEDIUM", "SOFT", "HARD"),
    "WET": ("INTERMEDIATE", "MEDIUM", "SOFT", "HARD"),
}
NUMERIC_TERMS = ("circuit_rate", "team_rate", "air_temp")

MODEL_NOTES = [
    "Penalty stops with no tyre change cannot be told apart from other stops in the data, "
    "so they are counted as normal stops.",
    "The wet and mixed ranges rest on few races, so they are wider: every draw samples the "
    "model's coefficients from their estimated uncertainty, and a level seen in few races is uncertain.",
    "The start-tyre effect is a pattern in past races, not cause and effect: teams choose "
    "their start tyres for reasons that also change how often they stop.",
    "A circuit or team with no stop history before the race uses the field mean: stops per car, "
    "all stops, over the races the model is fitted on.",
    "An unseen weather or start-tyre level uses its nearest seen level "
    "(wet → mixed → dry; WET → INTERMEDIATE).",
    "The model counts the stops of cars that keep running; a car out before its first stop "
    "is drawn separately, at the share of such cars in the season's earlier races.",
    "Race weather comes from Open-Meteo's Historical Forecast API, because its Previous Runs API "
    "has rain probability for only two of 2026's first 17 rounds (Miami and Canada): the rain "
    "chance p is the higher precipitation probability of the race-start hour and the next, and "
    "the weights are dry 1 - p, mixed p/2 and wet p/2.",
    "That API keeps the latest forecast for each hour, fetched after the races, not the forecast "
    "made the day before, so the backtest's weather is better than a real day-before forecast "
    "and its scores are optimistic.",
    "Tyre wear is not a model input: the race wear slope is often negative, because the car "
    "getting lighter as fuel burns outweighs the wear.",
]


# --------------------------------------------------------------------------
# Stop rates, all as of a race
# --------------------------------------------------------------------------


class _History:
    """Per-race stop counts of all cars and of each team, for the rate lookups.

    Every lookup filters to races before the `(season, round)` it is given.
    """

    def __init__(self, tables: PitStopTables) -> None:
        self.tables = tables
        held = tables.results[["season", "round"]].drop_duplicates().astype("int64")
        self.keys = held.sort_values(["season", "round"]).reset_index(drop=True)
        counts = _stop_counts(self.keys, tables.results, tables.pit_stops)
        circuits = tables.races[["season", "round", "circuit_id"]].astype({"season": "int64", "round": "int64"})
        self.races = counts.merge(circuits, on=["season", "round"], how="left")
        fit = tables.car_races[["season", "round"]].drop_duplicates().astype("int64")
        self.fit_races = self.races.merge(fit, on=["season", "round"])
        self._teams: dict[str, pd.DataFrame] = {}
        self._rates: dict[tuple, tuple[float, float]] = {}

    def team_counts(self, constructor_id: str) -> pd.DataFrame:
        if constructor_id not in self._teams:
            results = self.tables.results[self.tables.results["constructor_id"] == constructor_id]
            pit_stops = self.tables.pit_stops[self.tables.pit_stops["constructor_id"] == constructor_id]
            keys = self.keys.merge(results[["season", "round"]].drop_duplicates().astype("int64"), on=["season", "round"])
            self._teams[constructor_id] = _stop_counts(keys, results, pit_stops)
        return self._teams[constructor_id]

    def circuit_rate(self, circuit_id: str, season: int, round: int) -> float:
        races = self.races
        keep = (races["circuit_id"] == circuit_id) & (races["season"] >= HISTORY_START_SEASON) & _before(races, season, round)
        return _stops_per_car(races[keep])

    def team_rate(self, constructor_id: str, season: int, round: int) -> float:
        """The team's earlier rounds this season; the previous season when the season has no earlier round."""
        races = self.races
        earlier = (races["season"] == season) & (races["round"] < round)
        counts = self.team_counts(constructor_id)
        if earlier.any():
            rows = counts[(counts["season"] == season) & (counts["round"] < round)]
        else:
            rows = counts[counts["season"] == season - 1]
        return _stops_per_car(rows)

    def field_rate(self, season: int, round: int) -> float:
        """Stops per car (all stops) over the fit races (races with `car_races` rows) before the race."""
        return _stops_per_car(self.fit_races[_before(self.fit_races, season, round)])

    def rates(self, constructor_id: str, circuit_id: str, season: int, round: int) -> tuple[float, float]:
        """(circuit rate, team rate), each falling back to the field mean."""
        key = (constructor_id, circuit_id, season, round)
        if key not in self._rates:
            self._rates[key] = self._uncached_rates(constructor_id, circuit_id, season, round)
        return self._rates[key]

    def _uncached_rates(self, constructor_id: str, circuit_id: str, season: int, round: int) -> tuple[float, float]:
        field_mean = self.field_rate(season, round)
        circuit = self.circuit_rate(circuit_id, season, round)
        team = self.team_rate(constructor_id, season, round)
        return (field_mean if np.isnan(circuit) else circuit), (field_mean if np.isnan(team) else team)


def _finished(status: pd.Series) -> pd.Series:
    """`Finished`, `Lapped` (the repo's `FINISHED_STATUSES`) or `+N Laps`."""
    status = status.fillna("").astype(str)
    return status.isin(FINISHED_STATUSES) | status.str.startswith("+")


def car_out_rate(tables: PitStopTables, season: int, round: int) -> float:
    """The share of cars with no stop that did not finish, in the season's rounds before `round`.

    `Did not start` counts as out. When the season has no earlier round with
    results it is the previous season's rate; 0.0 when that has none either.
    """
    results = tables.results
    earlier = results[(results["season"] == season) & (results["round"] < round)]
    if earlier.empty:
        earlier = results[results["season"] == season - 1]
    if earlier.empty:
        return 0.0
    stopped = tables.pit_stops[["season", "round", "driver_id"]].drop_duplicates().assign(stopped=True)
    cars = earlier[["season", "round", "driver_id", "status"]].merge(stopped, on=["season", "round", "driver_id"], how="left")
    out = cars["stopped"].isna() & ~_finished(cars["status"])
    return float(out.mean())


# --------------------------------------------------------------------------
# Fit
# --------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class CountModel:
    """A fitted count model for one target race."""

    season: int
    round: int
    columns: tuple[str, ...]
    params: np.ndarray
    cov_params: np.ndarray
    dropped: tuple[str, ...]
    weather_levels: tuple[str, ...]
    compound_levels: tuple[str, ...]
    field_rate: float
    car_out_rate: float
    n_rows: int
    n_races: int
    fit_rows: pd.DataFrame = field(repr=False)
    history: _History = field(repr=False, compare=False)


def _check_race(tables: PitStopTables, season: int, round: int) -> None:
    """Story 4's season and round messages, for the calls that take no team or circuit."""
    rounds = tables.races.loc[tables.races["season"] == season, "round"]
    if rounds.empty:
        raise UnknownInputError(f"no races in season {season}")
    if round not in set(rounds):
        raise UnknownInputError(f"no round {round} in season {season}")


def _fit_rows(tables: PitStopTables, history: _History, season: int, round: int) -> pd.DataFrame:
    """One row per car of each race before the target with a known start compound and air temperature.

    A car out before its first stop (no stop and a status `_finished` rejects)
    is left out: the forecast draws it separately. A row whose circuit and team rates stay unknown (no earlier fit race to
    take a field mean from) is left out.
    """
    cars = tables.car_races[_before(tables.car_races, season, round)]
    weather = {(int(s), int(r)): _weather_category(group) for (s, r), group in cars.groupby(["season", "round"])}
    rows = cars[cars["start_compound"].isin(COMPOUNDS) & cars["air_temp_mean"].notna()]
    rows = rows[["season", "round", "circuit_id", "driver_id", "constructor_id", "start_compound", "air_temp_mean"]]
    rows = rows.astype({"season": "int64", "round": "int64"}).rename(columns={"air_temp_mean": "air_temp"})
    stops = tables.pit_stops.groupby(["season", "round", "driver_id"]).size().rename("stops").reset_index()
    rows = rows.merge(stops.astype({"season": "int64", "round": "int64"}), on=["season", "round", "driver_id"], how="left")
    stopped = tables.pit_stops[["season", "round", "driver_id"]].drop_duplicates().astype({"season": "int64", "round": "int64"})
    status = tables.results[["season", "round", "driver_id", "status"]].astype({"season": "int64", "round": "int64"})
    rows = rows.merge(stopped.assign(stopped=True), on=["season", "round", "driver_id"], how="left") \
        .merge(status, on=["season", "round", "driver_id"], how="left")
    out = rows["stopped"].isna() & ~_finished(rows["status"])
    rows = rows[~out].drop(columns=["stopped", "status"])
    rates = [
        history.rates(team, circuit, s, r)
        for s, r, circuit, team in rows[["season", "round", "circuit_id", "constructor_id"]].itertuples(index=False)
    ]
    rows = rows.assign(
        stops=rows["stops"].fillna(0).astype("int64"),
        circuit_rate=[c for c, _ in rates],
        team_rate=[t for _, t in rates],
        weather=[weather[(s, r)] for s, r in zip(rows["season"], rows["round"])],
    )
    rows = rows.dropna(subset=["circuit_rate", "team_rate"])
    return rows.astype({"circuit_rate": "float64", "team_rate": "float64", "air_temp": "float64"}) \
        .sort_values(["season", "round", "driver_id"]).reset_index(drop=True)


def _seen(values: pd.Series, order: Sequence[str]) -> tuple[str, ...]:
    present = set(values)
    return tuple(level for level in order if level in present)


def _design(frame: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    """The design matrix of `frame` (circuit_rate, team_rate, air_temp, weather, start_compound) for `columns`."""
    out = np.empty((len(frame), len(columns)))
    for j, name in enumerate(columns):
        if name == "const":
            out[:, j] = 1.0
        elif name in NUMERIC_TERMS:
            out[:, j] = frame[name].to_numpy(dtype=float)
        else:
            term, level = name.split(":", 1)
            out[:, j] = (frame[term].to_numpy() == level).astype(float)
    return out


def fit_count_model(tables: PitStopTables, season: int, round: int) -> CountModel:
    """The Poisson GLM and the car-out rate, fitted on races before `(season, round)`."""
    return _fit(tables, season, round, _History(tables))


def _fit(tables: PitStopTables, season: int, round: int, history: _History) -> CountModel:
    """`fit_count_model` with a shared `_History` (its rates are as of each race, so any target can share it)."""
    import statsmodels.api as sm

    _check_race(tables, season, round)
    rows = _fit_rows(tables, history, season, round)
    if rows.empty:
        raise ValueError(f"no fit races before {season} round {round}")

    weather_levels = _seen(rows["weather"], WEATHER_CATEGORIES)
    compound_levels = _seen(rows["start_compound"], COMPOUNDS)
    weather_ref = REFERENCE_WEATHER if REFERENCE_WEATHER in weather_levels else weather_levels[0]
    compound_ref = REFERENCE_COMPOUND if REFERENCE_COMPOUND in compound_levels else compound_levels[0]
    candidates = [
        "const", *NUMERIC_TERMS,
        *(f"weather:{level}" for level in weather_levels if level != weather_ref),
        *(f"start_compound:{level}" for level in compound_levels if level != compound_ref),
    ]
    # Keep a term only if it adds to the rank: a constant or already-explained term is dropped.
    full = _design(rows, candidates)
    kept: list[int] = []
    for j in range(len(candidates)):
        if np.linalg.matrix_rank(full[:, kept + [j]]) > len(kept):
            kept.append(j)
    columns = tuple(candidates[j] for j in kept)
    dropped = tuple(name for name in candidates if name not in columns)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = sm.GLM(rows["stops"].to_numpy(dtype=float), full[:, kept], family=sm.families.Poisson()).fit()

    races = rows[["season", "round"]].drop_duplicates()
    return CountModel(
        season=season, round=round, columns=columns,
        params=np.asarray(result.params, dtype=float), cov_params=np.asarray(result.cov_params(), dtype=float),
        dropped=dropped, weather_levels=weather_levels, compound_levels=compound_levels,
        field_rate=history.field_rate(season, round),
        car_out_rate=car_out_rate(tables, season, round),
        n_rows=len(rows), n_races=len(races), fit_rows=rows, history=history,
    )


# --------------------------------------------------------------------------
# Forecast
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StopRange:
    """A team total over the draws: mean (one decimal), 10th and 90th percentiles, and the unrounded mean."""

    mean: float
    p10: float
    p90: float
    raw_mean: float


@dataclass(frozen=True)
class Forecast:
    """The team's race stop total (all stops, red-flag stops included) and the inputs it used."""

    constructor_id: str
    circuit_id: str
    season: int
    round: int
    total: StopRange
    weather_weights: dict[str, float]
    start_compounds: tuple[str, ...]
    air_temp: float
    circuit_rate: float
    team_rate: float


def _weights(weather: str | Mapping[str, float]) -> np.ndarray:
    if isinstance(weather, str):
        if weather not in WEATHER_CATEGORIES:
            raise ValueError(f"unknown weather '{weather}'; expected one of {', '.join(WEATHER_CATEGORIES)}")
        return np.array([1.0 if level == weather else 0.0 for level in WEATHER_CATEGORIES])
    unknown = set(weather) - set(WEATHER_CATEGORIES)
    if unknown:
        raise ValueError(f"unknown weather '{sorted(unknown)[0]}'; expected one of {', '.join(WEATHER_CATEGORIES)}")
    weights = np.array([float(weather.get(level, 0.0)) for level in WEATHER_CATEGORIES])
    if (weights < 0).any() or not np.isclose(weights.sum(), 1.0):
        raise ValueError(f"weather weights must be non-negative and sum to 1, got {dict(weather)}")
    return weights / weights.sum()


def _nearest(level: str, seen: Sequence[str], fallback: Mapping[str, Sequence[str]]) -> str:
    for candidate in (level, *fallback[level]):
        if candidate in seen:
            return candidate
    return seen[0]


def _range(totals: np.ndarray) -> StopRange:
    p10, p90 = np.percentile(totals, [10, 90])
    raw_mean = float(totals.mean())
    return StopRange(mean=round(raw_mean, 1), p10=float(p10), p90=float(p90), raw_mean=raw_mean)


def forecast(
    tables: PitStopTables,
    constructor_id: str,
    circuit_id: str,
    season: int,
    round: int,
    *,
    start_compounds: Sequence[str],
    air_temp: float,
    weather: str | Mapping[str, float],
    model: CountModel | None = None,
) -> Forecast:
    """The team's total stops at the race (all stops), over `DRAWS` draws seeded `SEED`.

    `weather` is a category (`dry`, `mixed`, `wet`) or weights over them;
    `start_compounds` has one compound per car. `model` reuses a fit for the
    same `(season, round)`.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)
    compounds = tuple(str(c).upper() for c in start_compounds)
    bad = [c for c in compounds if c not in COMPOUNDS]
    if not compounds or bad:
        raise ValueError(f"start compounds must be from {', '.join(COMPOUNDS)}, got {list(start_compounds)}")
    weights = _weights(weather)
    if model is None:
        model = fit_count_model(tables, season, round)
    elif (model.season, model.round) != (season, round):
        raise ValueError(f"model is fitted for {model.season} round {model.round}, not {season} round {round}")

    circuit_rate, team_rate = model.history.rates(constructor_id, circuit_id, season, round)
    # One design row per (weather category, car).
    grid = pd.DataFrame(
        [
            {"circuit_rate": circuit_rate, "team_rate": team_rate, "air_temp": float(air_temp),
             "weather": _nearest(w, model.weather_levels, WEATHER_FALLBACK),
             "start_compound": _nearest(c, model.compound_levels, COMPOUND_FALLBACK)}
            for w in WEATHER_CATEGORIES for c in compounds
        ]
    )
    x = _design(grid, model.columns).reshape(len(WEATHER_CATEGORIES), len(compounds), len(model.columns))

    rng = np.random.default_rng(SEED)
    # Cholesky, not the default SVD: its factor is unique, so draws match across LAPACK builds.
    betas = rng.multivariate_normal(model.params, model.cov_params, size=DRAWS, method="cholesky")
    weather_draw = rng.choice(len(WEATHER_CATEGORIES), size=DRAWS, p=weights)
    mu = np.exp(np.einsum("dck,dk->dc", x[weather_draw], betas))
    out = rng.random((DRAWS, len(compounds))) < model.car_out_rate
    running = ~out
    total = (rng.poisson(mu) * running).sum(axis=1)

    return Forecast(
        constructor_id=constructor_id, circuit_id=circuit_id, season=season, round=round,
        total=_range(total),
        weather_weights=dict(zip(WEATHER_CATEGORIES, (float(w) for w in weights))),
        start_compounds=compounds, air_temp=float(air_temp),
        circuit_rate=float(circuit_rate), team_rate=float(team_rate),
    )
