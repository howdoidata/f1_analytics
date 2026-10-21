"""The pit-stop count model: a team's race stop total, red-flag stops included.

`fit_count_model(tables, season, round)` fits a Poisson GLM of each car's stops
above the race minimum (every `stop_type`) on races before `(season, round)`;
`forecast` turns it into a team total over `DRAWS` seeded draws. Every rate and every fit row
uses only races before the target, and each fit row's own rates use only
races before that row's race.

Model terms:

- Fit rows: every `car_races` row of a race before the target with a start
  compound and an air temperature, except cars out before their first stop
  (no stop and not finished, the `car_out_rate` rule), so the GLM models the
  stops of running cars. Target: the car's extra stops, all of its Jolpica
  stops (normal, sc_vsc, red_flag and unknown) minus the race minimum. A
  non-finisher below the minimum counts 0 extra stops; a finisher below it
  fails the fit.
- Race minimum (`race_minimum`): in a dry race, the `stop_rules` mart's
  `dry_minimum` for the circuit at the latest `from_season` up to the season,
  or 1 with no such row; 1 in a mixed or wet race (a weather change forces a
  tyre change; no finisher in the data made none). Circuit rules live only in
  the mart's seed.
- Covariates: the circuit history rate (all stops per car at the circuit from
  2011), the team rate (the team's stops per car, all stops, in the season's
  earlier rounds; the previous season's when the season has no earlier round), the car's mean air temperature, the race's
  weather category (story 4's `_weather_category`), the car's start compound
  and the race's `incident` (1 when the `race_incidents` mart says it had a
  safety car or red flag period, VSC not counted; 0 otherwise, and for a race
  missing from the mart).
  A circuit or team with no history uses the field mean: stops per car (all
  stops) over the fit races (for a fit row, the fit races before its race).
  A covariate with one value across the fit rows, or one the others already
  explain, is left out of that fit.
- Incident chance (`incident_chance`): races with a safety car or red flag ÷
  races, over the earlier `race_incidents` races at the circuit and the earlier
  races of the season, each race counted once; with neither, all earlier
  `race_incidents` races; with none, 0.0. No tuned weight.
- Team link (`team_link`, ρ): the chance that the team's cars share one
  uniform for their extra stops. ρ = (obs − mean m_ind) ÷ (mean m_shared −
  mean m_ind), clipped to [0, 1], over the fit rows' team-races where both cars
  finished, from the season's earlier rounds (all fit rows when the season has
  none; ρ = 0 with none at all), with in-sample mu: obs is the share with equal
  extra stops, m_ind = Σₖ p₁(k)p₂(k) and m_shared the overlap of the two
  cars' Poisson CDF steps. No tuned weight.
- A draw: one GLM coefficient vector from their estimated normal (`params`,
  `cov_params`), shared by the team's cars; weather from the weights, which
  fixes the race minimum; then `incident` from the incident chance, also
  shared by the team's cars; then per car, the car out before its first stop
  with probability `car_out_rate` (0 stops); then the link (with chance ρ the
  cars share one uniform u, else each has its own) and the uniforms. A running
  car makes the minimum plus F⁻¹(u; mu), its own Poisson's inverse CDF, so the
  link moves only the team's joint spread, not either car's distribution. The
  team total is the sum over its cars; red-flag stops are inside mu, with no
  separate red-flag part.
"""

from __future__ import annotations

import math
import numbers
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import poisson

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
INCIDENT_TERM = "incident"
# The race minimum: one stop in a dry race (two compounds). In a mixed or wet race the two-compound rule
# lapses, but the weather change forces a tyre change: no finisher in the data made none (user, 2026-10-21).
DEFAULT_DRY_MINIMUM = 1
WET_MINIMUM = 1
SPLITS = ("same", "differ by 1", "differ by 2+")
# A numerical guard, not a model term: a car's mean extra stops in a draw is capped here. A level whose
# extra stops are all 0 has a coefficient near −∞ with a huge spread, and its sampled coefficients
# would overflow exp; no draw on the committed data comes near the cap.
MU_CAP = 1e6

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
    "The incident chance rests on few races: it is the share of earlier races at the circuit and "
    "earlier races of the season with a safety car or red flag (a VSC does not count), and the "
    "backtest tests it only through its season half, because no backtest round is at a circuit "
    "with earlier races in the data.",
    "A running car makes at least the race minimum of stops: 1 in a dry race, more where a "
    "circuit's rules require it, and 1 in a mixed or wet race; the model counts the stops above it.",
    "The team's two cars usually make the same number of stops: in each draw they share one random "
    "draw for their extra stops with a chance set from the season's earlier races where both finished, "
    "and each car keeps its own spread.",
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


def _race_incidents(tables: PitStopTables) -> pd.DataFrame:
    """season, round (int64) and incident (0/1) of every race in the `race_incidents` mart."""
    frame = tables.race_incidents
    return pd.DataFrame({
        "season": frame["season"].astype("int64"),
        "round": frame["round"].astype("int64"),
        "incident": frame["incident"].astype(bool).astype("int64"),
    })


def _dry_minimum(tables: PitStopTables, circuit_id: str, season: int) -> int:
    """The `stop_rules` row's `dry_minimum` at the latest `from_season` up to `season`; 1 with none."""
    rules = tables.stop_rules
    rows = rules[(rules["circuit_id"] == circuit_id) & (rules["from_season"].astype("int64") <= season)]
    if rows.empty:
        return DEFAULT_DRY_MINIMUM
    return int(rows.sort_values("from_season")["dry_minimum"].iloc[-1])


def race_minimum(tables: PitStopTables, circuit_id: str, season: int, weather: str) -> int:
    """The stops a running car makes at least: the circuit's dry minimum when `weather` is dry, else `WET_MINIMUM`."""
    return _dry_minimum(tables, circuit_id, season) if weather == "dry" else WET_MINIMUM


def incident_chance(tables: PitStopTables, circuit_id: str, season: int, round: int) -> float:
    """The chance of a safety car or red flag (not a VSC) at the race, from races before it.

    Races with an incident ÷ races, over the earlier `race_incidents` races at
    the circuit and the earlier races of the season, each race counted once.
    With neither, all earlier `race_incidents` races; with none, 0.0.

    Unlike `car_out_rate` it checks its inputs, as the subpackage's public
    functions do: an unknown circuit, season or round raises story 4's
    `UnknownInputError` message.
    """
    if circuit_id not in set(tables.circuits["circuit_id"]):
        raise UnknownInputError(f"unknown circuit_id '{circuit_id}'")
    _check_race(tables, season, round)
    incidents = _race_incidents(tables)
    circuits = tables.races[["season", "round", "circuit_id"]].astype({"season": "int64", "round": "int64"})
    earlier = incidents[_before(incidents, season, round)].merge(circuits, on=["season", "round"], how="left")
    pool = earlier[(earlier["circuit_id"] == circuit_id) | (earlier["season"] == season)]
    if pool.empty:
        pool = earlier
    if pool.empty:
        return 0.0
    return float(pool["incident"].mean())


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
    # ρ: the chance the team's cars share one uniform for their extra stops.
    team_link: float
    # The target race's minimum stops by weather (dry, mixed, wet).
    minimums: Mapping[str, int]


def _check_race(tables: PitStopTables, season: int, round: int) -> None:
    """Story 4's season and round messages, for the calls that take no team or circuit."""
    rounds = tables.races.loc[tables.races["season"] == season, "round"]
    if rounds.empty:
        raise UnknownInputError(f"no races in season {season}")
    if round not in set(rounds):
        raise UnknownInputError(f"no round {round} in season {season}")


def _fit_rows(tables: PitStopTables, history: _History, season: int, round: int) -> pd.DataFrame:
    """One row per car of each race before the target with a known start compound and air temperature.

    Each row carries its race's `incident` (0/1) from the `race_incidents` mart,
    whether the car `finished`, the race `minimum` (`race_minimum`) and its
    `extra` stops: stops − minimum, 0 for a non-finisher below the minimum.
    Raises `ValueError` for a finisher below the minimum.

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
    finished = _finished(rows["status"])
    out = rows["stopped"].isna() & ~finished
    rows = rows.assign(finished=finished)[~out].drop(columns=["stopped", "status"])
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
    # A race missing from the mart is clean.
    rows = rows.merge(_race_incidents(tables), on=["season", "round"], how="left")
    rows = rows.assign(incident=rows["incident"].fillna(0).astype("int64"))
    rows = rows.astype({"circuit_rate": "float64", "team_rate": "float64", "air_temp": "float64"}) \
        .sort_values(["season", "round", "driver_id"]).reset_index(drop=True)
    minimum = [
        race_minimum(tables, circuit, s, w)
        for s, circuit, w in rows[["season", "circuit_id", "weather"]].itertuples(index=False)
    ]
    rows = rows.assign(minimum=pd.Series(minimum, index=rows.index, dtype="int64"))
    below = rows[(rows["stops"] < rows["minimum"]) & rows["finished"]]
    if not below.empty:
        row = below.iloc[0]
        raise ValueError(
            f"{row['driver_id']} finished {row['season']} round {row['round']} with {row['stops']} stops, "
            f"below the race minimum {row['minimum']}"
        )
    return rows.assign(extra=(rows["stops"] - rows["minimum"]).clip(lower=0).astype("int64"))


def _seen(values: pd.Series, order: Sequence[str]) -> tuple[str, ...]:
    present = set(values)
    return tuple(level for level in order if level in present)


def _design(frame: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    """The design matrix of `frame` (circuit_rate, team_rate, air_temp, weather, start_compound, incident) for `columns`."""
    out = np.empty((len(frame), len(columns)))
    for j, name in enumerate(columns):
        if name == "const":
            out[:, j] = 1.0
        elif name in NUMERIC_TERMS or name == INCIDENT_TERM:
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
        INCIDENT_TERM,
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
        result = sm.GLM(rows["extra"].to_numpy(dtype=float), full[:, kept], family=sm.families.Poisson()).fit()
    params = np.asarray(result.params, dtype=float)
    mu = np.exp(full[:, kept] @ params)
    race = tables.races[(tables.races["season"] == season) & (tables.races["round"] == round)]
    circuit_id = str(race["circuit_id"].iloc[0])

    races = rows[["season", "round"]].drop_duplicates()
    return CountModel(
        season=season, round=round, columns=columns,
        params=params, cov_params=np.asarray(result.cov_params(), dtype=float),
        dropped=dropped, weather_levels=weather_levels, compound_levels=compound_levels,
        field_rate=history.field_rate(season, round),
        car_out_rate=car_out_rate(tables, season, round),
        n_rows=len(rows), n_races=len(races), fit_rows=rows, history=history,
        team_link=_team_link(_link_pairs(rows, mu, season)),
        minimums={w: race_minimum(tables, circuit_id, season, w) for w in WEATHER_CATEGORIES},
    )


# --------------------------------------------------------------------------
# Team link
# --------------------------------------------------------------------------


def _link_pairs(rows: pd.DataFrame, mu: np.ndarray, season: int) -> pd.DataFrame:
    """The fit rows' team-races where both cars finished: mu1, mu2 (in-sample) and extra1, extra2.

    From the season's earlier rounds; all fit rows when the season has none.
    """
    cars = rows.assign(mu=mu)
    groups = cars.groupby(["season", "round", "constructor_id"], sort=True)
    both = groups["finished"].transform("all") & (groups["finished"].transform("size") == 2)
    cars = cars[both].sort_values(["season", "round", "constructor_id", "driver_id"])
    first, second = cars.iloc[0::2].reset_index(drop=True), cars.iloc[1::2].reset_index(drop=True)
    pairs = pd.DataFrame({
        "season": first["season"], "round": first["round"], "constructor_id": first["constructor_id"],
        "mu1": first["mu"], "mu2": second["mu"], "extra1": first["extra"], "extra2": second["extra"],
    })
    this_season = pairs[pairs["season"] == season]
    return (this_season if not this_season.empty else pairs).reset_index(drop=True)


def _support(mu1: float, mu2: float) -> np.ndarray:
    """0..k, with k past both Poisson's mass to well below float precision."""
    top = max(mu1, mu2)
    return np.arange(int(top + 12 * math.sqrt(top) + 30))


def _match_chances(mu1: float, mu2: float) -> tuple[float, float]:
    """(m_ind, m_shared): the chance two cars' counts are equal drawn independently, and from one shared uniform.

    m_ind = Σₖ p₁(k)p₂(k); m_shared = Σₖ the overlap of the CDF steps (F₁(k−1), F₁(k)] and (F₂(k−1), F₂(k)].
    """
    k = _support(mu1, mu2)
    m_ind = float((poisson.pmf(k, mu1) * poisson.pmf(k, mu2)).sum())
    c1, c2 = poisson.cdf(k, mu1), poisson.cdf(k, mu2)
    p1, p2 = np.concatenate([[0.0], c1[:-1]]), np.concatenate([[0.0], c2[:-1]])
    m_shared = float(np.clip(np.minimum(c1, c2) - np.maximum(p1, p2), 0.0, None).sum())
    return m_ind, m_shared


def _link_parts(pairs: pd.DataFrame) -> dict[str, float]:
    """n, obs, mean m_ind, mean m_shared and the unclipped ρ of the pairs (NaN ρ with no pairs or no spread)."""
    if pairs.empty:
        return {"n": 0, "obs": math.nan, "m_ind": math.nan, "m_shared": math.nan, "rho": math.nan}
    chances = np.array([_match_chances(a, b) for a, b in zip(pairs["mu1"], pairs["mu2"])])
    obs = float((pairs["extra1"] == pairs["extra2"]).mean())
    m_ind, m_shared = float(chances[:, 0].mean()), float(chances[:, 1].mean())
    spread = m_shared - m_ind
    rho = (obs - m_ind) / spread if spread > 0 else math.nan
    return {"n": len(pairs), "obs": obs, "m_ind": m_ind, "m_shared": m_shared, "rho": rho}


def _team_link(pairs: pd.DataFrame) -> float:
    """ρ in [0, 1]; 0 with no pairs (or when sharing cannot change the match chance)."""
    rho = _link_parts(pairs)["rho"]
    return 0.0 if math.isnan(rho) else float(min(max(rho, 0.0), 1.0))


def _model_pairs(model: CountModel) -> pd.DataFrame:
    rows = model.fit_rows
    mu = np.exp(_design(rows, model.columns) @ model.params)
    return _link_pairs(rows, mu, model.season)


def team_split_check(model: CountModel) -> pd.DataFrame:
    """The model's against the observed shares of team-races whose cars made the same, 1 apart or 2+ apart stops.

    Over the team-races `team_link` is set from (both cars finished; the
    season's earlier rounds, else all fit rows), with in-sample mu and the
    link ρ. The model share is exact, not sampled: ρ times the shared-uniform
    chance plus (1 − ρ) times the independent one, averaged over team-races.
    Columns `split` (`SPLITS`), `model`, `observed`; NaN shares with no
    team-races.
    """
    pairs = _model_pairs(model)
    if pairs.empty:
        return pd.DataFrame({"split": SPLITS, "model": [math.nan] * 3, "observed": [math.nan] * 3})
    rho = model.team_link
    shares = np.zeros(3)
    for mu1, mu2 in zip(pairs["mu1"], pairs["mu2"]):
        k = _support(mu1, mu2)
        p1, p2 = poisson.pmf(k, mu1), poisson.pmf(k, mu2)
        independent = _split_shares(np.outer(p1, p2), k)
        shares += rho * _split_shares(_shared_joint(mu1, mu2, k), k) + (1 - rho) * independent
    gap = (pairs["extra1"] - pairs["extra2"]).abs().clip(upper=2)
    observed = [float((gap == g).mean()) for g in (0, 1, 2)]
    return pd.DataFrame({"split": SPLITS, "model": shares / len(pairs), "observed": observed})


def _split_shares(joint: np.ndarray, k: np.ndarray) -> np.ndarray:
    gap = np.abs(k[:, None] - k[None, :])
    return np.array([joint[gap == 0].sum(), joint[gap == 1].sum(), joint[gap >= 2].sum()])


def _shared_joint(mu1: float, mu2: float, k: np.ndarray) -> np.ndarray:
    """P(F₁⁻¹(u) = i, F₂⁻¹(u) = j) for one shared uniform u: the overlap of the two CDF steps."""
    c1, c2 = poisson.cdf(k, mu1), poisson.cdf(k, mu2)
    p1, p2 = np.concatenate([[0.0], c1[:-1]]), np.concatenate([[0.0], c2[:-1]])
    return np.clip(np.minimum(c1[:, None], c2[None, :]) - np.maximum(p1[:, None], p2[None, :]), 0.0, None)


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
    incident_chance: float


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


def _incident(incident: float | bool) -> float:
    """A chance in [0, 1] from `incident`: true/false is 1/0, a finite real number in [0, 1] is itself."""
    if isinstance(incident, (bool, np.bool_)):
        return 1.0 if incident else 0.0
    if isinstance(incident, numbers.Real):
        value = float(incident)
        if math.isfinite(value) and 0.0 <= value <= 1.0:
            return value
    raise ValueError(f"incident must be a chance in [0, 1] or true/false, got {incident!r}")


def _nearest(level: str, seen: Sequence[str], fallback: Mapping[str, Sequence[str]]) -> str:
    for candidate in (level, *fallback[level]):
        if candidate in seen:
            return candidate
    return seen[0]


def _range(totals: np.ndarray) -> StopRange:
    p10, p90 = np.percentile(totals, [10, 90])
    raw_mean = float(totals.mean())
    return StopRange(mean=round(raw_mean, 1), p10=float(p10), p90=float(p90), raw_mean=raw_mean)


def _grid(
    model: CountModel, circuit_rate: float, team_rate: float, air_temp: float, compounds: Sequence[str]
) -> np.ndarray:
    """The design rows, shape (weather category, incident 0/1, car, column)."""
    grid = pd.DataFrame(
        [
            {"circuit_rate": circuit_rate, "team_rate": team_rate, "air_temp": float(air_temp),
             "weather": _nearest(w, model.weather_levels, WEATHER_FALLBACK),
             "start_compound": _nearest(c, model.compound_levels, COMPOUND_FALLBACK),
             INCIDENT_TERM: incident}
            for w in WEATHER_CATEGORIES for incident in (0, 1) for c in compounds
        ]
    )
    return _design(grid, model.columns).reshape(len(WEATHER_CATEGORIES), 2, len(compounds), len(model.columns))


def _draw(model: CountModel, x: np.ndarray, weights: np.ndarray, chance: float) -> tuple[np.ndarray, np.ndarray]:
    """Each car's stops in each of the `DRAWS` seeded draws, and each draw's incident (True/False).

    Draw order: coefficients, weather (which fixes the race minimum), incident
    (one per draw, shared by the team's cars), car out, the link (one per draw:
    with chance `team_link` every car uses the first car's uniform), the
    uniforms. A car out gets 0; a running car the minimum plus its Poisson's
    inverse CDF at its uniform.
    """
    rng = np.random.default_rng(SEED)
    # Cholesky, not the default SVD: its factor is unique, so draws match across LAPACK builds.
    betas = rng.multivariate_normal(model.params, model.cov_params, size=DRAWS, method="cholesky")
    weather_draw = rng.choice(len(WEATHER_CATEGORIES), size=DRAWS, p=weights)
    incident_draw = rng.random(DRAWS) < chance
    eta = np.einsum("dck,dk->dc", x[weather_draw, incident_draw.astype(int)], betas)
    mu = np.exp(np.minimum(eta, math.log(MU_CAP)))
    out = rng.random((DRAWS, x.shape[2])) < model.car_out_rate
    linked = rng.random(DRAWS) < model.team_link
    u = rng.random((DRAWS, x.shape[2]))
    u = np.where(linked[:, None], u[:, :1], u)
    # ppf(0) is −1 (below the support); a uniform of exactly 0 is the smallest count, 0.
    extra = np.maximum(poisson.ppf(u, mu), 0).astype("int64")
    minimum = np.array([model.minimums[w] for w in WEATHER_CATEGORIES], dtype="int64")[weather_draw]
    stops = (minimum[:, None] + extra) * ~out
    return stops, incident_draw


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
    incident: float | bool | None = None,
    model: CountModel | None = None,
) -> Forecast:
    """The team's total stops at the race (all stops), over `DRAWS` draws seeded `SEED`.

    `weather` is a category (`dry`, `mixed`, `wet`) or weights over them;
    `start_compounds` has one compound per car. `incident` is the chance of a
    safety car or red flag in [0, 1], or true/false for a race known to have
    one or not; by default it is `incident_chance` for the race. `model`
    reuses a fit for the same `(season, round)`.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)
    compounds = tuple(str(c).upper() for c in start_compounds)
    bad = [c for c in compounds if c not in COMPOUNDS]
    if not compounds or bad:
        raise ValueError(f"start compounds must be from {', '.join(COMPOUNDS)}, got {list(start_compounds)}")
    weights = _weights(weather)
    chance = incident_chance(tables, circuit_id, season, round) if incident is None else _incident(incident)
    if model is None:
        model = fit_count_model(tables, season, round)
    elif (model.season, model.round) != (season, round):
        raise ValueError(f"model is fitted for {model.season} round {model.round}, not {season} round {round}")

    circuit_rate, team_rate = model.history.rates(constructor_id, circuit_id, season, round)
    x = _grid(model, circuit_rate, team_rate, air_temp, compounds)
    stops, _ = _draw(model, x, weights, chance)

    return Forecast(
        constructor_id=constructor_id, circuit_id=circuit_id, season=season, round=round,
        total=_range(stops.sum(axis=1)),
        weather_weights=dict(zip(WEATHER_CATEGORIES, (float(w) for w in weights))),
        start_compounds=compounds, air_temp=float(air_temp),
        circuit_rate=float(circuit_rate), team_rate=float(team_rate),
        incident_chance=chance,
    )
