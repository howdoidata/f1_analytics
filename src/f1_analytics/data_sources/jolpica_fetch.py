"""Jolpica (Ergast-compatible) client, response flatteners and the incremental update.

Everything Jolpica-shaped lives here:

- `JolpicaClient` -- paced, retrying, optionally page-cached GETs against
  `https://api.jolpi.ca/ergast/f1/`. The HTTP call itself is an injectable
  `getter(url, params) -> dict` so tests can replay recorded responses with
  no network. Requests never carry credentials.
- Flatteners that turn Ergast `MRData` pages into the plain CSVs committed
  under `data/raw/jolpica/` (see `RAW_COLUMNS`). Column names are Ergast's
  own field names; `jolpica_loader.py` shapes them into curated tables.
- `update_raw_dir` -- the incremental per-round update `uv run refresh` runs:
  it appends exactly the rounds whose results have been published since the
  last update, and refreshes the season-end standings of that season.

Rate limits (Jolpica's published ceiling): 4 req/s burst and 500 req/hour
sustained. `MIN_REQUEST_INTERVAL_SECONDS` paces every real request at 3600/500
seconds, so a long run never crosses the hourly cap; a sliding one-hour
window is enforced on top as a guard.
"""

from __future__ import annotations

import collections
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd


BASE_URL = "https://api.jolpi.ca/ergast/f1/"
# Jolpica clamps `limit` to 100 server-side regardless of what is requested.
PAGE_LIMIT = 100
HOURLY_REQUEST_CAP = 500
MIN_REQUEST_INTERVAL_SECONDS = 3600 / HOURLY_REQUEST_CAP  # 7.2 s
RETRY_CAP = 5
BACKOFF_BASE_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 30
# Sprints exist from 2021; earlier seasons are not queried for them.
SPRINT_FIRST_SEASON = 2021
FIRST_SEASON = 1950

Getter = Callable[[str, dict], dict]

RAW_COLUMNS: dict[str, list[str]] = {
    "races": ["season", "round", "raceName", "circuitId", "date", "time", "url"],
    "circuits": ["circuitId", "circuitName", "locality", "country", "lat", "long", "url"],
    "drivers": [
        "driverId",
        "givenName",
        "familyName",
        "dateOfBirth",
        "nationality",
        "permanentNumber",
        "code",
        "url",
    ],
    "constructors": ["constructorId", "name", "nationality", "url"],
    "results": [
        "season",
        "round",
        "raceName",
        "number",
        "driverId",
        "givenName",
        "familyName",
        "constructorId",
        "constructorName",
        "grid",
        "position",
        "positionText",
        "points",
        "laps",
        "status",
        "totalRaceTime",
        "millis",
        "fastestLapNumber",
        "fastestLapRank",
        "fastestLapTime",
    ],
    "qualifying": [
        "season",
        "round",
        "raceName",
        "number",
        "driverId",
        "constructorId",
        "position",
        "Q1",
        "Q2",
        "Q3",
    ],
    "final_driver_standings": [
        "season",
        "round",
        "position",
        "positionText",
        "points",
        "wins",
        "driverId",
        "constructorIds",
    ],
    "final_constructor_standings": [
        "season",
        "round",
        "position",
        "positionText",
        "points",
        "wins",
        "constructorId",
        "constructorName",
    ],
}
RAW_COLUMNS["sprint_results"] = RAW_COLUMNS["results"]

RAW_FILES = {name: f"{name}.csv" for name in RAW_COLUMNS}

REFERENCE_KEYS = {"circuits": "circuitId", "drivers": "driverId", "constructors": "constructorId"}
NUMERIC_SORT_COLUMNS = {"season", "round"}


class JolpicaRequestError(RuntimeError):
    """A Jolpica request failed after the retry cap, or returned a non-retryable error."""


class TransientJolpicaError(RuntimeError):
    """A retryable Jolpica failure: HTTP 429, 5xx, or a network error."""


class IncompleteJolpicaFetchError(RuntimeError):
    """Paged rows do not add up to the source's own reported total."""


def requests_getter(url: str, params: dict) -> dict:
    """The production getter: one unauthenticated GET, parsed as JSON."""
    import requests

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        raise TransientJolpicaError(f"{type(error).__name__}: {error}") from error
    if response.status_code == 429 or response.status_code >= 500:
        raise TransientJolpicaError(f"HTTP {response.status_code} for {response.url}")
    if response.status_code != 200:
        raise JolpicaRequestError(f"HTTP {response.status_code} for {response.url}")
    return response.json()


class JolpicaClient:
    """Paced, retrying Jolpica GETs with an optional on-disk page cache.

    A cached page is returned without a request and without pacing, which is
    what makes the one-time dump resumable.
    """

    def __init__(
        self,
        getter: Getter | None = None,
        *,
        cache_dir: Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        hourly_cap: int = HOURLY_REQUEST_CAP,
        retry_cap: int = RETRY_CAP,
        backoff_base: float = BACKOFF_BASE_SECONDS,
        base_url: str = BASE_URL,
    ) -> None:
        self.getter = getter or requests_getter
        self.cache_dir = cache_dir
        self.sleep = sleep
        self.clock = clock
        self.min_interval = min_interval
        self.hourly_cap = hourly_cap
        self.retry_cap = retry_cap
        self.backoff_base = backoff_base
        self.base_url = base_url
        self.request_count = 0
        self._recent: collections.deque[float] = collections.deque()
        self._last_request: float | None = None

    def _cache_path(self, path: str, offset: int) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / path.replace("/", "_") / f"offset_{offset:05d}.json"

    def _pace(self) -> None:
        now = self.clock()
        if self._last_request is not None:
            wait = self._last_request + self.min_interval - now
            if wait > 0:
                self.sleep(wait)
                now = self.clock()
        while self._recent and now - self._recent[0] >= 3600:
            self._recent.popleft()
        if len(self._recent) >= self.hourly_cap:
            wait = 3600 - (now - self._recent[0])
            if wait > 0:
                self.sleep(wait)
                now = self.clock()
            self._recent.popleft()
        self._last_request = now
        self._recent.append(now)

    def _request(self, url: str, params: dict) -> dict:
        attempt = 0
        while True:
            self._pace()
            self.request_count += 1
            try:
                return self.getter(url, params)
            except TransientJolpicaError as error:
                if attempt >= self.retry_cap:
                    raise JolpicaRequestError(
                        f"retry cap ({self.retry_cap}) exhausted for {url}: {error}"
                    ) from error
                self.sleep(self.backoff_base * (2**attempt))
                attempt += 1

    def get_page(self, path: str, offset: int = 0) -> dict:
        """Return one page's `MRData` for `path` (e.g. `2024/results`)."""
        cache_path = self._cache_path(path, offset)
        if cache_path is not None and cache_path.is_file():
            return json.loads(cache_path.read_text())["MRData"]
        url = f"{self.base_url}{path}.json"
        payload = self._request(url, {"limit": PAGE_LIMIT, "offset": offset})
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload))
            tmp.replace(cache_path)
        return payload["MRData"]

    def get_all(self, path: str) -> list[dict]:
        """Every page of `path`, following `offset` until the reported `total`."""
        pages = [self.get_page(path, 0)]
        total = int(pages[0]["total"])
        offset = int(pages[0].get("limit", PAGE_LIMIT))
        while offset < total:
            page = self.get_page(path, offset)
            pages.append(page)
            offset += int(page.get("limit", PAGE_LIMIT))
        return pages


# --------------------------------------------------------------------------
# Flatteners
# --------------------------------------------------------------------------

RACE_ROW_KEYS = {"results": "Results", "sprint_results": "SprintResults", "qualifying": "QualifyingResults"}


def merge_race_pages(pages: Iterable[dict], row_key: str | None = None) -> list[dict]:
    """Merge `RaceTable.Races` across pages; a race split across pages is joined."""
    merged: dict[tuple[int, int], dict] = {}
    for page in pages:
        for race in page["RaceTable"]["Races"]:
            key = (int(race["season"]), int(race["round"]))
            if key not in merged:
                merged[key] = dict(race)
                if row_key is not None:
                    merged[key][row_key] = list(race.get(row_key, []))
            elif row_key is not None:
                merged[key][row_key].extend(race.get(row_key, []))
    return [merged[key] for key in sorted(merged)]


def verify_total(pages: list[dict], row_key: str, label: str) -> None:
    """Landed rows must equal the source's own `total`, never more or fewer."""
    total = int(pages[0]["total"])
    landed = sum(len(race.get(row_key, [])) for page in pages for race in page["RaceTable"]["Races"])
    if landed != total:
        raise IncompleteJolpicaFetchError(f"{label}: landed {landed} row(s), source reported {total}")


def _frame(rows: list[dict], table: str) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=RAW_COLUMNS[table])


def flatten_races(races: list[dict]) -> pd.DataFrame:
    rows = [
        {
            "season": int(race["season"]),
            "round": int(race["round"]),
            "raceName": race.get("raceName"),
            "circuitId": race.get("Circuit", {}).get("circuitId"),
            "date": race.get("date"),
            "time": race.get("time"),
            "url": race.get("url"),
        }
        for race in races
    ]
    return _frame(rows, "races")


def flatten_circuits(races: list[dict]) -> pd.DataFrame:
    rows = []
    for race in races:
        circuit = race.get("Circuit")
        if not circuit:
            continue
        location = circuit.get("Location", {})
        rows.append(
            {
                "circuitId": circuit.get("circuitId"),
                "circuitName": circuit.get("circuitName"),
                "locality": location.get("locality"),
                "country": location.get("country"),
                "lat": location.get("lat"),
                "long": location.get("long"),
                "url": circuit.get("url"),
            }
        )
    return _frame(rows, "circuits")


def _driver_row(driver: dict) -> dict:
    return {
        "driverId": driver.get("driverId"),
        "givenName": driver.get("givenName"),
        "familyName": driver.get("familyName"),
        "dateOfBirth": driver.get("dateOfBirth"),
        "nationality": driver.get("nationality"),
        "permanentNumber": driver.get("permanentNumber"),
        "code": driver.get("code"),
        "url": driver.get("url"),
    }


def _constructor_row(constructor: dict) -> dict:
    return {
        "constructorId": constructor.get("constructorId"),
        "name": constructor.get("name"),
        "nationality": constructor.get("nationality"),
        "url": constructor.get("url"),
    }


def flatten_results(races: list[dict], row_key: str = "Results") -> pd.DataFrame:
    """Race or sprint classification rows (`Results` / `SprintResults`)."""
    table = "sprint_results" if row_key == "SprintResults" else "results"
    rows = []
    for race in races:
        for result in race.get(row_key, []):
            driver = result.get("Driver", {})
            constructor = result.get("Constructor", {})
            fastest = result.get("FastestLap", {})
            race_time = result.get("Time", {})
            rows.append(
                {
                    "season": int(race["season"]),
                    "round": int(race["round"]),
                    "raceName": race.get("raceName"),
                    "number": result.get("number"),
                    "driverId": driver.get("driverId"),
                    "givenName": driver.get("givenName"),
                    "familyName": driver.get("familyName"),
                    "constructorId": constructor.get("constructorId"),
                    "constructorName": constructor.get("name"),
                    "grid": result.get("grid"),
                    "position": result.get("position"),
                    "positionText": result.get("positionText"),
                    "points": result.get("points"),
                    "laps": result.get("laps"),
                    "status": result.get("status"),
                    "totalRaceTime": race_time.get("time"),
                    "millis": race_time.get("millis"),
                    "fastestLapNumber": fastest.get("lap"),
                    "fastestLapRank": fastest.get("rank"),
                    "fastestLapTime": fastest.get("Time", {}).get("time"),
                }
            )
    return _frame(rows, table)


def flatten_qualifying(races: list[dict]) -> pd.DataFrame:
    rows = []
    for race in races:
        for result in race.get("QualifyingResults", []):
            rows.append(
                {
                    "season": int(race["season"]),
                    "round": int(race["round"]),
                    "raceName": race.get("raceName"),
                    "number": result.get("number"),
                    "driverId": result.get("Driver", {}).get("driverId"),
                    "constructorId": result.get("Constructor", {}).get("constructorId"),
                    "position": result.get("position"),
                    "Q1": result.get("Q1"),
                    "Q2": result.get("Q2"),
                    "Q3": result.get("Q3"),
                }
            )
    return _frame(rows, "qualifying")


def standings_lists(pages: list[dict]) -> list[dict]:
    lists: list[dict] = []
    for page in pages:
        lists.extend(page["StandingsTable"]["StandingsLists"])
    return lists


def verify_standings_total(pages: list[dict], entry_key: str, label: str) -> None:
    total = int(pages[0]["total"])
    landed = sum(len(standings.get(entry_key, [])) for standings in standings_lists(pages))
    if landed != total:
        raise IncompleteJolpicaFetchError(f"{label}: landed {landed} row(s), source reported {total}")


def merge_standings_pages(pages: list[dict], entry_key: str) -> list[dict]:
    """Join one season's standings list when it is split across pages."""
    merged: dict[tuple[int, int], dict] = {}
    for standings in standings_lists(pages):
        key = (int(standings["season"]), int(standings["round"]))
        if key not in merged:
            merged[key] = dict(standings)
            merged[key][entry_key] = list(standings.get(entry_key, []))
        else:
            merged[key][entry_key].extend(standings.get(entry_key, []))
    return [merged[key] for key in sorted(merged)]


def flatten_driver_standings(pages: list[dict]) -> pd.DataFrame:
    rows = []
    for standings in merge_standings_pages(pages, "DriverStandings"):
        for entry in standings.get("DriverStandings", []):
            rows.append(
                {
                    "season": int(standings["season"]),
                    "round": int(standings["round"]),
                    "position": entry.get("position"),
                    "positionText": entry.get("positionText"),
                    "points": entry.get("points"),
                    "wins": entry.get("wins"),
                    "driverId": entry.get("Driver", {}).get("driverId"),
                    "constructorIds": ";".join(
                        constructor.get("constructorId", "") for constructor in entry.get("Constructors", [])
                    ),
                }
            )
    return _frame(rows, "final_driver_standings")


def flatten_constructor_standings(pages: list[dict]) -> pd.DataFrame:
    rows = []
    for standings in merge_standings_pages(pages, "ConstructorStandings"):
        for entry in standings.get("ConstructorStandings", []):
            constructor = entry.get("Constructor", {})
            rows.append(
                {
                    "season": int(standings["season"]),
                    "round": int(standings["round"]),
                    "position": entry.get("position"),
                    "positionText": entry.get("positionText"),
                    "points": entry.get("points"),
                    "wins": entry.get("wins"),
                    "constructorId": constructor.get("constructorId"),
                    "constructorName": constructor.get("name"),
                }
            )
    return _frame(rows, "final_constructor_standings")


def reference_rows(
    race_lists: Iterable[list[dict]], standings_pages: Iterable[list[dict]] = ()
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drivers and constructors from every object embedded in results/standings responses."""
    drivers: list[dict] = []
    constructors: list[dict] = []
    for races in race_lists:
        for race in races:
            for key in RACE_ROW_KEYS.values():
                for result in race.get(key, []):
                    if result.get("Driver"):
                        drivers.append(_driver_row(result["Driver"]))
                    if result.get("Constructor"):
                        constructors.append(_constructor_row(result["Constructor"]))
    for pages in standings_pages:
        for standings in standings_lists(pages):
            for entry in standings.get("DriverStandings", []):
                if entry.get("Driver"):
                    drivers.append(_driver_row(entry["Driver"]))
                for constructor in entry.get("Constructors", []):
                    constructors.append(_constructor_row(constructor))
            for entry in standings.get("ConstructorStandings", []):
                if entry.get("Constructor"):
                    constructors.append(_constructor_row(entry["Constructor"]))
    return _frame(drivers, "drivers"), _frame(constructors, "constructors")


# --------------------------------------------------------------------------
# CSV I/O
# --------------------------------------------------------------------------


def _sort_key(series: pd.Series) -> pd.Series:
    if series.name in NUMERIC_SORT_COLUMNS:
        return pd.to_numeric(series, errors="coerce")
    return series


def normalize(frame: pd.DataFrame, table: str) -> pd.DataFrame:
    """Column order, de-duplication and a stable sort, so equal data writes equal bytes.

    Row order within a round is kept as the source returned it.
    """
    frame = frame[RAW_COLUMNS[table]].astype("string")
    if table in REFERENCE_KEYS:
        key = REFERENCE_KEYS[table]
        frame = frame.dropna(subset=[key]).drop_duplicates(subset=[key], keep="last")
        sort_by = [key]
    elif table in ("final_driver_standings", "final_constructor_standings"):
        sort_by = ["season"]
    else:
        sort_by = ["season", "round"]
    return frame.sort_values(sort_by, kind="stable", key=_sort_key).reset_index(drop=True)


def read_raw_table(raw_dir: Path, table: str) -> pd.DataFrame:
    path = raw_dir / RAW_FILES[table]
    if not path.is_file():
        raise FileNotFoundError(f"Missing Jolpica raw file: {path}")
    return pd.read_csv(path, dtype="string", keep_default_na=False, na_values=[""])


def write_raw_table(raw_dir: Path, table: str, frame: pd.DataFrame) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / RAW_FILES[table]
    tmp = path.with_name(path.name + ".tmp")
    normalize(frame, table).to_csv(tmp, index=False)
    tmp.replace(path)


# --------------------------------------------------------------------------
# Incremental update
# --------------------------------------------------------------------------


def _round_keys(frame: pd.DataFrame) -> set[tuple[int, int]]:
    if frame.empty:
        return set()
    return {(int(season), int(round_)) for season, round_ in zip(frame["season"], frame["round"])}


def _same_rows(left: pd.DataFrame, right: pd.DataFrame, table: str) -> bool:
    a = normalize(left, table).fillna("")
    b = normalize(right, table).fillna("")
    return a.shape == b.shape and bool((a.to_numpy() == b.to_numpy()).all())


def _seasons(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame["season"])


def update_raw_dir(
    raw_dir: Path,
    client: JolpicaClient,
    *,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Append every newly published round to the Jolpica CSVs under `raw_dir`.

    1. Re-fetch the latest season's schedule (one request). If every
       scheduled round already has results, fetch the next season's
       schedule; an empty one changes nothing.
    2. Walk the rounds lacking results in order. The first round whose
       results come back empty ends the walk ("up to date").
    3. For each round with results: append results, sprint and qualifying,
       and any new driver/constructor/circuit; then refresh that season's
       final standings.

    Nothing is written unless something changed. Returns
    `{"appended": [(season, round), ...], "races_changed": bool}`.
    """
    tables = {table: read_raw_table(raw_dir, table) for table in RAW_COLUMNS}
    races = tables["races"]
    loaded = _round_keys(tables["results"])

    season = int(_seasons(races).max())
    schedule_races = merge_race_pages(client.get_all(f"{season}/races"))
    new_schedule = flatten_races(schedule_races)
    races_changed = bool(schedule_races) and not _same_rows(races[_seasons(races) == season], new_schedule, "races")
    if races_changed:
        races = pd.concat([races[_seasons(races) != season], new_schedule.astype("string")], ignore_index=True)
    circuits = pd.concat([tables["circuits"], flatten_circuits(schedule_races).astype("string")], ignore_index=True)

    pending = sorted(key for key in _round_keys(new_schedule) if key not in loaded)
    if not pending and schedule_races:
        next_season = season + 1
        next_races = merge_race_pages(client.get_all(f"{next_season}/races"))
        if next_races:
            log(f"[jolpica] season {next_season} schedule published ({len(next_races)} round(s))")
            next_schedule = flatten_races(next_races)
            races = pd.concat([races, next_schedule.astype("string")], ignore_index=True)
            circuits = pd.concat([circuits, flatten_circuits(next_races).astype("string")], ignore_index=True)
            races_changed = True
            pending = sorted(_round_keys(next_schedule))

    appended: list[tuple[int, int]] = []
    new_frames: dict[str, list[pd.DataFrame]] = collections.defaultdict(list)
    for season_, round_ in pending:
        result_pages = client.get_all(f"{season_}/{round_}/results")
        verify_total(result_pages, "Results", f"{season_} round {round_} results")
        result_races = merge_race_pages(result_pages, "Results")
        if not any(race.get("Results") for race in result_races):
            break
        sprint_races: list[dict] = []
        if season_ >= SPRINT_FIRST_SEASON:
            sprint_pages = client.get_all(f"{season_}/{round_}/sprint")
            verify_total(sprint_pages, "SprintResults", f"{season_} round {round_} sprint")
            sprint_races = merge_race_pages(sprint_pages, "SprintResults")
        qualifying_pages = client.get_all(f"{season_}/{round_}/qualifying")
        verify_total(qualifying_pages, "QualifyingResults", f"{season_} round {round_} qualifying")
        qualifying_races = merge_race_pages(qualifying_pages, "QualifyingResults")

        new_frames["results"].append(flatten_results(result_races, "Results"))
        new_frames["sprint_results"].append(flatten_results(sprint_races, "SprintResults"))
        new_frames["qualifying"].append(flatten_qualifying(qualifying_races))
        drivers, constructors = reference_rows([result_races, sprint_races, qualifying_races])
        new_frames["drivers"].append(drivers)
        new_frames["constructors"].append(constructors)
        appended.append((season_, round_))
        log(f"[jolpica] {season_} round {round_}: {len(new_frames['results'][-1])} result row(s) appended")

    if not appended:
        if races_changed:
            write_raw_table(raw_dir, "races", races)
            write_raw_table(raw_dir, "circuits", circuits)
            log("[jolpica] schedule updated; no new results")
        else:
            log("[jolpica] up to date")
        return {"appended": [], "races_changed": races_changed}

    def _concat(*frames: pd.DataFrame) -> pd.DataFrame:
        return pd.concat([frame.astype("string") for frame in frames if not frame.empty] or [frames[0]], ignore_index=True)

    for table in ("results", "sprint_results", "qualifying"):
        tables[table] = _concat(tables[table], *new_frames[table])

    standings_pages = []
    for season_ in sorted({season_ for season_, _ in appended}):
        driver_pages = client.get_all(f"{season_}/driverstandings")
        constructor_pages = client.get_all(f"{season_}/constructorstandings")
        verify_standings_total(driver_pages, "DriverStandings", f"{season_} driver standings")
        verify_standings_total(constructor_pages, "ConstructorStandings", f"{season_} constructor standings")
        standings_pages.extend([driver_pages, constructor_pages])
        for table, frame in (
            ("final_driver_standings", flatten_driver_standings(driver_pages)),
            ("final_constructor_standings", flatten_constructor_standings(constructor_pages)),
        ):
            existing = tables[table]
            tables[table] = _concat(existing[_seasons(existing) != season_], frame)
    standing_drivers, standing_constructors = reference_rows([], standings_pages)

    tables["drivers"] = _concat(tables["drivers"], *new_frames["drivers"], standing_drivers)
    tables["constructors"] = _concat(tables["constructors"], *new_frames["constructors"], standing_constructors)
    tables["races"] = races
    tables["circuits"] = circuits
    for table, frame in tables.items():
        write_raw_table(raw_dir, table, frame)
    return {"appended": appended, "races_changed": races_changed}


def completed_rounds(raw_dir: Path, season: int, today: date | None = None) -> list[int]:
    """Rounds of `season` that have run (date before today) and have results."""
    today = today or date.today()
    races = read_raw_table(raw_dir, "races")
    with_results = _round_keys(read_raw_table(raw_dir, "results"))
    rounds = []
    for race_season, race_round, race_date in zip(races["season"], races["round"], races["date"]):
        key = (int(race_season), int(race_round))
        if key[0] == season and key in with_results and date.fromisoformat(str(race_date)) < today:
            rounds.append(key[1])
    return sorted(rounds)
