"""Run the whole thing: download -> check -> save -> analyse -> forecast -> brief.

    python -m emi.pipeline                 real data from SMARD
    python -m emi.pipeline --demo          fake data, works offline
    python -m emi.pipeline --no-forecast   skip the (slower) forecast test
    python -m emi.pipeline --export data/energy.db.gz
"""
import argparse
import logging
import sys

import pandas as pd

from . import analysis, brief, db, forecast, quality
from .config import DB_PATH, SERIES, START_DATE
from .demo_data import make_demo_data
from .smard import SmardError, fetch_series

log = logging.getLogger("pipeline")


def load_data(con, run_id, demo, start):
    loaded = bad_count = 0
    errors = []
    demo_data = make_demo_data(start) if demo else None

    for key, (smard_id, *_rest) in SERIES.items():
        try:
            # only download what's new, plus 3 days because SMARD corrects recent values
            last = db.last_timestamp(con, key)
            since = pd.Timestamp(start, tz="UTC")
            if last is not None:
                since = max(since, last - pd.Timedelta(days=3))

            if demo:
                df = demo_data[key]
                df = df[df["ts_utc"] >= since]
            else:
                df, skipped = fetch_series(smard_id, since)
                if skipped:
                    log.info("%s: %d hours not published yet", key, skipped)

            good, bad = quality.split_bad_rows(df, key)
            loaded += db.save_observations(con, key, good, run_id)
            bad_count += db.save_bad_rows(con, key, bad, run_id)
            con.commit()
            log.info("%-20s %6d rows saved, %d bad", key, len(good), len(bad))
        except SmardError as e:
            # one broken series should not stop the others
            errors.append(f"{key}: {e}")
            log.error("%s failed: %s", key, e)
    return loaded, bad_count, errors


def analyse(con, run_id, source, do_forecast):
    checks = quality.run_checks(db.read_long(con))
    db.save_checks(con, run_id, checks)
    df = analysis.prepare(db.read_hourly(con))

    table = None
    note = ""
    if do_forecast:
        try:
            results = forecast.backtest(df)
            table = forecast.scores(results)
            con.execute("DELETE FROM forecast_results")
            con.executemany("INSERT INTO forecast_results VALUES (?, ?, ?, ?)",
                            zip(results["model"], db.to_text(results["ts_utc"]),
                                results["actual"], results["predicted"]))
            con.executemany("INSERT INTO forecast_scores VALUES (?, ?, ?, ?, ?)",
                            [(run_id, r.model, r.mae, r.rmse, r.rmae) for r in table.itertuples()])
            log.info("forecast scores:\n%s", table.round(2).to_string(index=False))
        except ValueError as e:
            note = f"forecast skipped: {e}"
            log.warning(note)

    text = brief.weekly_brief(df, table, checks, source)
    con.execute("INSERT INTO briefs VALUES (?, ?, ?)", (run_id, db.now(), text))
    con.commit()
    return note


def run(demo=False, start=START_DATE, db_path=DB_PATH, do_forecast=True, export=None):
    source = "demo" if demo else "smard"
    con = db.connect(db_path)
    run_id = db.start_run(con, source)
    try:
        loaded, bad, errors = load_data(con, run_id, demo, start)
        if len(errors) == len(SERIES):
            raise RuntimeError("every series failed to download")
        note = analyse(con, run_id, source, do_forecast)
        status = "partial" if errors else "success"
        db.finish_run(con, run_id, status, loaded, bad, "; ".join(errors + [note]).strip("; "))
    except Exception as e:
        db.finish_run(con, run_id, "failed", message=repr(e))
        raise
    finally:
        con.close()

    if export:
        db.export_gz(db_path, export)
        log.info("exported database to %s", export)
    log.info("run %d finished: %s", run_id, status)
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="use fake data instead of SMARD")
    parser.add_argument("--start", default=START_DATE)
    parser.add_argument("--no-forecast", action="store_true")
    parser.add_argument("--export", help="also save a .gz copy of the database here")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(args.demo, args.start, DB_PATH, not args.no_forecast, args.export)
    except Exception:
        log.exception("pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()