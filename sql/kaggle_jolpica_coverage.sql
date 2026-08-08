-- kaggle_jolpica_coverage: the single arbiter for Kaggle-vs-Jolpica
-- per-(season, round) coverage (AD-2, Story 1.7).
--
-- Tags every season/round on the curated race calendar (`races`) plus any
-- season/round that has rows in either source but is somehow missing from
-- the calendar (defensive -- never silently drops a row a source actually
-- reported) with exactly one of the five AD-2 statuses:
--   match               -- both sources have rows, counts equal
--   kaggle_only         -- Kaggle has rows, Jolpica has none
--   jolpica_only        -- Jolpica has rows, Kaggle has none
--   row_count_diverges  -- both sources have rows, counts differ
--   no_data             -- neither source has rows
--
-- `combined_results`/combined standings read these status tags; this view
-- is the ONLY place the Kaggle-vs-Jolpica row-count comparison is computed
-- (AD-2's single-arbiter rule) -- never recomputed downstream.
--
-- Prerequisites: curated `results`/`races` (Story 1.5) and the landed
-- `raw_jolpica_results` table (Story 1.7's `jolpica_loader.py`) must exist
-- before this view is created -- `scripts/build_combined_dataset.py`
-- enforces that ordering.

CREATE OR REPLACE VIEW kaggle_jolpica_coverage AS
WITH kaggle_counts AS (
    SELECT season, round, COUNT(*) AS kaggle_row_count
    FROM results
    GROUP BY season, round
),
jolpica_counts AS (
    SELECT season, round, COUNT(*) AS jolpica_row_count
    FROM raw_jolpica_results
    GROUP BY season, round
),
season_rounds AS (
    -- The race calendar is the primary universe (it carries rounds that
    -- have no results yet at all -> no_data); the UNIONs below are a
    -- defensive backstop so a season/round either source actually reports
    -- rows for is never dropped just because it is absent from `races`.
    SELECT DISTINCT season, round FROM races
    UNION
    SELECT DISTINCT season, round FROM kaggle_counts
    UNION
    SELECT DISTINCT season, round FROM jolpica_counts
)
SELECT
    sr.season,
    sr.round,
    COALESCE(k.kaggle_row_count, 0) AS kaggle_row_count,
    COALESCE(j.jolpica_row_count, 0) AS jolpica_row_count,
    CASE
        WHEN COALESCE(k.kaggle_row_count, 0) = 0 AND COALESCE(j.jolpica_row_count, 0) = 0 THEN 'no_data'
        WHEN COALESCE(k.kaggle_row_count, 0) = 0 THEN 'jolpica_only'
        WHEN COALESCE(j.jolpica_row_count, 0) = 0 THEN 'kaggle_only'
        WHEN k.kaggle_row_count = j.jolpica_row_count THEN 'match'
        ELSE 'row_count_diverges'
    END AS status
FROM season_rounds sr
LEFT JOIN kaggle_counts k ON sr.season = k.season AND sr.round = k.round
LEFT JOIN jolpica_counts j ON sr.season = j.season AND sr.round = j.round
ORDER BY sr.season, sr.round;
