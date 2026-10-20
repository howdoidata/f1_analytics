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
