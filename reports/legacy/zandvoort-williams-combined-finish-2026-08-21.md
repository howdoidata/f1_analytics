---
output:
  html_document: default
  pdf_document: default
---
# Williams Combined Finishing Position — 2026 Dutch Grand Prix

**Question:** What will be the combined finishing position total for Williams Racing in the upcoming Zandvoort race?

## Answer: 31

Range 29–33.

| | |
|---|---|
| **Prepared** | 2026-08-21 |
| **Race** | 2026 Dutch Grand Prix, Zandvoort — round 12 of 22, **2026-08-23** |
| **Status** | Pre-race. Qualifying not yet run. |
| **Convention** | Plain sum of two classified finishing positions; lower is better (P1+P2=3, P4+P5=9) |
| **Data source** | `data/processed/f1_analytics.duckdb` — 30 tables, seasons 1950–2026 |
| **2026 results** | Complete through round 11 (Hungary, 2026-07-26) |

---

## 1. Method

```
  Kaggle CSVs ─┐
               ├─→ DuckDB curated layer ─→ combined_results ─→ per-round sum ─→ estimate
  Jolpica API ─┘        (30 tables)         (season 2026)      (classified pos)
```

Every figure below is a query against the committed local database. 2026 results are sourced **176 rows Jolpica + 66 rows Kaggle**. No figure is hand-entered.

**Counting rule.** A retired or non-starting car is still *classified* and its position counts normally — no exclusion, no penalty. Two 2026 rounds depend on this: China (Albon DNS, classified P22) and Canada (Albon retired, classified P21).

**Validation.** The database reproduces three independently-supplied answers exactly: Miami P9+P10=19, Canada highest finish P9, Melbourne fastest Williams lap 1:23.590 (Sainz).

---

## 2. Season to date — every round

| Round | Race | Grid sum | Result | Total | Note |
|---:|---|---:|---|---:|---|
| R1 | Australian | 36 | P12 + P15 | **27** |  |
| R2 | Chinese | 39 | P9 + P22 | **31** | Did not start |
| R3 | Japanese | 33 | P15 + P20 | **35** |  |
| R4 | Miami | 28 | P9 + P10 | **19** |  |
| R5 | Canadian | 33 | P9 + P21 | **30** | Retired |
| R6 | Monaco | 23 | P8 + P16 | **24** | Retired |
| R7 | Barcelona | 34 | P12 + P18 | **30** |  |
| R8 | Austrian | 35 | P17 + P20 | **37** | Retired |
| R9 | British | 30 | P17 + P21 | **38** | Retired |
| R10 | Belgian | 34 | P15 + P16 | **31** |  |
| R11 | Hungarian | 37 | P17 + P18 | **35** |  |

**n=11 · min 19 · max 38 · mean 30.6 · median 31 · stdev 5.7**

### Distribution

```
  19-24  ####       2
  25-29  ##         1
  30-32  ########   4
  33-35  ####       2
  36-38  ####       2
         better <───────────────> worse
```

### Trend

```
  R1  Australian  ############################             27
  R2  Chinese     ################################         31
  R3  Japanese    ####################################     35
  R4  Miami       ####################                     19
  R5  Canadian    ###############################          30
  R6  Monaco      #########################                24
  R7  Barcelona   ###############################          30
  R8  Austrian    ######################################   37
  R9  British     ######################################## 38
  R10 Belgian     ################################         31
  R11 Hungarian   ####################################     35
```

| Window | Values | Mean |
|---|---|---:|
| All 11 rounds | — | 30.6 |
| Last 6 (R6–R11) | 24, 30, 37, 38, 31, 35 | 32.5 |
| **Last 4 (R8–R11)** | 37, 38, 31, 35 | **35.2** |

Nothing under 30 since Barcelona in June. Miami's 19 is an outlier, not a baseline.

---

## 3. Zandvoort history

| Season | Grid | Result | Total |
|---:|---|---|---:|
| 2021 | 0+11 | P16 + P17 | **33** |
| 2022 | 15+20 | P12 + P18 | **30** |
| 2023 | 4+10 | P8 + P20 | **28** |
| 2024 | 19+18 | P14 + P16 | **30** |
| 2025 | 15+9 | P5 + P13 | **18** |

```
  2021  #############################      33
  2022  ##########################         30
  2023  #########################          28
  2024  ##########################         30
  2025  ################                   18
```

**Four of five land 28–33.** The 2025 outlier (18) was Albon P5 from grid 15 — same driver pairing as now, so relevant but optimistic.

### Why the circuit compresses outcomes

Zandvoort 2021–25, all teams, 97 starts: median position change **3 places**, mean 3.6. Only **30 of 97 (31%)** moved 5 or more places. Low overtaking caps both upside and disaster.

---

## 4. Competitive context

2026 constructor standings after round 11:

```
  P1   Mercedes           ########################## 332
  P2   Ferrari            ####################       268
  P3   McLaren            #############              177
  P4   Red Bull           #############              168
  P5   RB F1 Team         ####                       62
  P6   Alpine F1 Team     ####                       60
  P7   Haas F1 Team       #                          20
  P8   Audi                                          12
  P9   Williams                                      11  <--
  P10  Aston Martin                                  1
  P11  Cadillac F1 Team                              0
```

**Williams sit P9 of 11 on 11 points.** Mean grid 16.5 across the season, drifting to 17.0 over the last four rounds.

---

## 5. Reasoning

| Pulls worse (33–35) | Pulls better (28–30) |
|---|---|
| Last 4 rounds average 35.2 | Zandvoort clusters 28–33 across 5 seasons |
| P9 of 11 constructors, 11 pts | Median position change only 3 places |
| Qualifying drifted 16.5 → 17.0 | Low overtaking caps disaster scenarios |
| DNF/DNS in 5 of 11 rounds | 2025 Zandvoort was 18 with this pairing |

**31 is where they meet** — simultaneously the season median (31), inside the Zandvoort band, and a modest concession to poor current form.

### Revise when qualifying lands

| If Williams qualify | Then estimate |
|---|---|
| Both top 12 | 26–28 |
| Grid sum ~30 (typical) | **31** |
| Both 17+ again | 34–36 |

---

## 6. Caveats

1. **Qualifying has not run.** Grid position is the dominant input and it is unknown.
2. **Retirement risk is real but priced in.** DNF/DNS in 5 of 11 rounds; a single retirement costs roughly 6–8 on the total. Those rounds are already in the mean.
3. **Pre-race estimate, not a computed answer.** It will be reconciled against the source-backed result once round 12 lands.

---

## Appendix — reproduce

```sql
-- Per-round combined total, 2026
SELECT round, race_name,
       string_agg('P' || position, ' + ' ORDER BY position) AS result,
       sum(position::INT) AS combined_total
FROM combined_results
WHERE season = 2026 AND constructor_id ILIKE '%williams%'
GROUP BY round, race_name ORDER BY round;

-- Zandvoort history
SELECT cr.season, sum(cr.position::INT) AS combined_total
FROM combined_results cr
JOIN races ra ON cr.season = ra.season AND cr.round = ra.round
WHERE ra.race_name ILIKE '%dutch%' AND cr.constructor_id ILIKE '%williams%'
GROUP BY cr.season ORDER BY cr.season;
```

Catalog entry: `catalog/intake/2026-08-21-zandvoort-combined-finish.yaml`

FastF1 lap data covers Canada, Melbourne, Miami, Silverstone — not required here, since finishing position is a results-based fact.
