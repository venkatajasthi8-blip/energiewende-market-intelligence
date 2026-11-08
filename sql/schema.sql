-- All timestamps are stored in UTC as text: 'YYYY-MM-DD HH:MM:SS'
-- (no daylight-saving problems, and text sorts correctly)

CREATE TABLE IF NOT EXISTS series (
    series_key  TEXT PRIMARY KEY,
    smard_id    INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started     TEXT NOT NULL,
    finished    TEXT,
    status      TEXT NOT NULL,      -- running / success / partial / failed
    source      TEXT NOT NULL,      -- smard / demo
    rows_loaded INTEGER DEFAULT 0,
    rows_bad    INTEGER DEFAULT 0,
    message     TEXT
);

-- one row per series per hour ("long" format: a new series needs no new column)
CREATE TABLE IF NOT EXISTS observations (
    series_key  TEXT NOT NULL REFERENCES series(series_key),
    ts_utc      TEXT NOT NULL,
    value       REAL NOT NULL,
    run_id      INTEGER REFERENCES runs(run_id),
    PRIMARY KEY (series_key, ts_utc)
);
CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations (ts_utc);

-- rows that failed the plausibility check, kept for checking later
CREATE TABLE IF NOT EXISTS bad_rows (
    run_id      INTEGER REFERENCES runs(run_id),
    series_key  TEXT NOT NULL,
    ts_utc      TEXT NOT NULL,
    value       REAL,
    reason      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_checks (
    run_id      INTEGER REFERENCES runs(run_id),
    "check"     TEXT NOT NULL,
    series_key  TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('pass', 'warn', 'fail')),
    detail      TEXT
);

-- forecast test results (replaced on every run)
CREATE TABLE IF NOT EXISTS forecast_results (
    model      TEXT NOT NULL,
    ts_utc     TEXT NOT NULL,
    actual     REAL NOT NULL,
    predicted  REAL NOT NULL,
    PRIMARY KEY (model, ts_utc)
);

CREATE TABLE IF NOT EXISTS forecast_scores (
    run_id  INTEGER REFERENCES runs(run_id),
    model   TEXT NOT NULL,
    mae     REAL,
    rmse    REAL,
    rmae    REAL      -- MAE divided by the MAE of "same hour yesterday"
);

CREATE TABLE IF NOT EXISTS briefs (
    run_id   INTEGER REFERENCES runs(run_id),
    created  TEXT NOT NULL,
    text_md  TEXT NOT NULL
);

-- one row per hour, one column per series
DROP VIEW IF EXISTS hourly;
CREATE VIEW hourly AS
SELECT
    ts_utc,
    MAX(CASE WHEN series_key = 'price'              THEN value END) AS price,
    MAX(CASE WHEN series_key = 'load'               THEN value END) AS load,
    MAX(CASE WHEN series_key = 'residual_load'      THEN value END) AS residual_load,
    MAX(CASE WHEN series_key = 'wind_onshore'       THEN value END) AS wind_onshore,
    MAX(CASE WHEN series_key = 'wind_offshore'      THEN value END) AS wind_offshore,
    MAX(CASE WHEN series_key = 'solar'              THEN value END) AS solar,
    MAX(CASE WHEN series_key = 'biomass'            THEN value END) AS biomass,
    MAX(CASE WHEN series_key = 'hydro'              THEN value END) AS hydro,
    MAX(CASE WHEN series_key = 'other_renewables'   THEN value END) AS other_renewables,
    MAX(CASE WHEN series_key = 'lignite'            THEN value END) AS lignite,
    MAX(CASE WHEN series_key = 'hard_coal'          THEN value END) AS hard_coal,
    MAX(CASE WHEN series_key = 'gas'                THEN value END) AS gas,
    MAX(CASE WHEN series_key = 'nuclear'            THEN value END) AS nuclear,
    MAX(CASE WHEN series_key = 'other_conventional' THEN value END) AS other_conventional,
    MAX(CASE WHEN series_key = 'pumped_storage'     THEN value END) AS pumped_storage
FROM observations
GROUP BY ts_utc;