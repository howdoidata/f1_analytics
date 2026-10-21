# Data sources and attribution

## `jolpica/`

Race schedules, results, sprint results, qualifying, season-end standings,
and the driver, constructor and circuit tables, 1950 to the latest published
round. Pit stops (`pit_stops.csv`: lap, time of day and pit-lane duration of
every stop) from 2011 onwards, the first season Jolpica has them.

- Source: the [Jolpica F1 API](https://github.com/jolpica/jolpica-f1)
  (Ergast-compatible, `https://api.jolpi.ca/ergast/f1/`), which continues the
  Ergast Developer API's dataset.
- Licence: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
  per the [Jolpica terms of use](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md).
  Non-commercial use only; derived data must be shared under the same licence.
- Produced by `scripts/dump_jolpica.py` (one-time dump) and kept current by
  `uv run refresh`. The CSVs flatten the API responses and keep Ergast's
  field names.

## `fastf1/`

Per-lap timing and weather for selected race sessions, one folder per round:
`fastf1/<season>/<RR>-<race-slug>/{laps,weather}.csv` plus `counts.json`.

- Source: Formula 1 live-timing data, fetched with
  [FastF1](https://github.com/theOehrly/Fast-F1) by `uv run refresh`. Fetching
  requires the user's own F1TV subscription login.
- F1 timing data is the property of Formula One World Championship Limited.
  This project is unofficial and not associated with the Formula 1 companies.
  The extracts are kept here for non-commercial analysis only.

## `fastf1_summary/`

Small per-race summaries of FastF1 race sessions:

- `car_races.csv` -- one row per car per race: laps, stints, compounds, race
  weather means and rain, and a raw tyre-wear slope.
- `track_status_periods.csv` -- the safety-car, virtual-safety-car and
  red-flag periods of each race, by lap.

- Source: Formula 1 live-timing data, fetched with
  [FastF1](https://github.com/theOehrly/Fast-F1) and summarised by
  `uv run fetch-sessions`. Fetching requires the user's own F1TV subscription
  login.
- F1 timing data is the property of Formula One World Championship Limited.
  This project is unofficial and not associated with the Formula 1 companies.
  The summaries are kept here for non-commercial analysis only.

## `fastf1_practice/`

Per-stint summaries of practice sessions, one file per session:
`fastf1_practice/<season>/<RR>-<race-slug>/<FP1|FP2|FP3>_stints.csv` (one row
per car per stint: compound, laps and a raw tyre-wear slope).

- Source: Formula 1 live-timing data, fetched with
  [FastF1](https://github.com/theOehrly/Fast-F1) and summarised by
  `uv run fetch-sessions`. Fetching requires the user's own F1TV subscription
  login.
- F1 timing data is the property of Formula One World Championship Limited.
  This project is unofficial and not associated with the Formula 1 companies.
  The summaries are kept here for non-commercial analysis only.

## `open_meteo/`

Hourly weather forecasts for the race window, one file per race:
`open_meteo/day_before/<season>-<RR>.json` (the backtest's weather) and
`open_meteo/forecast/<season>-<RR>.json` (the live forecast for an upcoming
race, which the scenario file and the pit-stop forecast page read). Each holds
the endpoint, the query, the fetch time, the race start in UTC and the API
response: hourly precipitation, precipitation probability and air temperature
for the race date and the day after, at the circuit's latitude and longitude.

- Source: [Open-Meteo](https://open-meteo.com/), Historical Forecast API
  (`https://historical-forecast-api.open-meteo.com/v1/forecast`), fetched by
  `uv run fetch-weather --season <s> --round <r> --day-before`. No account or
  key is needed. The Previous Runs API has rain probability for only two of
  2026's first 17 rounds (Miami and Canada), so it is not used.
- Live forecasts: Open-Meteo's Forecast API
  (`https://api.open-meteo.com/v1/forecast`), fetched by
  `uv run fetch-weather --season <s> --round <r>` before the race. A later
  fetch replaces the file, so it holds the latest forecast fetched.
- The Historical Forecast API keeps the latest forecast for each hour, and
  these files were fetched after the races: they are not a true day-before
  forecast, so the backtest's weather is optimistic. The analysis uses p, the
  higher precipitation probability of the race-start hour and the next.
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), per the
  [Open-Meteo terms](https://open-meteo.com/en/terms), for both folders.
  Weather data by Open-Meteo.com. The pit-stop forecast page carries the same
  credit in its footer.
