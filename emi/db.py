"""Everything that reads from or writes to the SQLite database."""
import gzip
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

from .config import ROOT, SERIES

FMT = "%Y-%m-%d %H:%M:%S"


def to_text(ts):
    return list(pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).strftime(FMT))


def now():
    return pd.Timestamp.now(tz="UTC").strftime(FMT)


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript((ROOT / "sql" / "schema.sql").read_text())
    con.executemany(
        "INSERT OR REPLACE INTO series VALUES (?, ?, ?, ?)",
        [(key, v[0], v[1], v[2]) for key, v in SERIES.items()],
    )
    con.commit()
    return con


def start_run(con, source):
    cur = con.execute("INSERT INTO runs (started, status, source) VALUES (?, 'running', ?)",
                      (now(), source))
    con.commit()
    return cur.lastrowid


def finish_run(con, run_id, status, loaded=0, bad=0, message=""):
    con.execute("UPDATE runs SET finished=?, status=?, rows_loaded=?, rows_bad=?, message=? "
                "WHERE run_id=?", (now(), status, loaded, bad, message[:2000], run_id))
    con.commit()


def last_timestamp(con, key):
    row = con.execute("SELECT MAX(ts_utc) FROM observations WHERE series_key=?", (key,)).fetchone()
    return pd.Timestamp(row[0], tz="UTC") if row[0] else None


def save_observations(con, key, df, run_id):
    # ON CONFLICT = if the hour already exists, update it instead of adding a duplicate.
    # That makes it safe to run the pipeline as often as you like.
    rows = [(key, ts, float(v), run_id) for ts, v in zip(to_text(df["ts_utc"]), df["value"])]
    con.executemany(
        """INSERT INTO observations (series_key, ts_utc, value, run_id) VALUES (?, ?, ?, ?)
           ON CONFLICT(series_key, ts_utc) DO UPDATE SET value=excluded.value, run_id=excluded.run_id""",
        rows,
    )
    return len(rows)


def save_bad_rows(con, key, bad, run_id):
    rows = [(run_id, key, ts, v, r)
            for ts, v, r in zip(to_text(bad["ts_utc"]), bad["value"], bad["reason"])]
    con.executemany("INSERT INTO bad_rows VALUES (?, ?, ?, ?, ?)", rows)
    return len(rows)


def save_checks(con, run_id, checks):
    con.executemany("INSERT INTO quality_checks VALUES (?, ?, ?, ?, ?)",
                    [(run_id, c["check"], c["series_key"], c["status"], c["detail"]) for c in checks])


def read_long(con):
    df = pd.read_sql("SELECT series_key, ts_utc, value FROM observations", con)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


def read_hourly(con):
    df = pd.read_sql("SELECT * FROM hourly ORDER BY ts_utc", con)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df.set_index("ts_utc")


def export_gz(db_path, out_path):
    """Copy the database into a .gz file (this is what gets uploaded to GitHub)."""
    tmp = Path(db_path).with_suffix(".copy")
    src, dst = sqlite3.connect(db_path), sqlite3.connect(tmp)
    src.backup(dst)
    src.close()
    dst.close()
    with open(tmp, "rb") as f, gzip.open(out_path, "wb") as out:
        shutil.copyfileobj(f, out)
    tmp.unlink()


def import_gz(gz_path, db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(gz_path, "rb") as f, open(db_path, "wb") as out:
        shutil.copyfileobj(f, out)