"""Data quality checks.

Bad rows are not deleted or "fixed" - they are moved to a separate table with
the reason, so you can always see what was thrown out and why.
"""
import pandas as pd

from .config import SERIES


def split_bad_rows(df, key):
    """Split rows into (good, bad). Bad rows get a 'reason' column."""
    _, _, _, low, high = SERIES[key]
    too_low = df["value"] < low
    is_bad = too_low | (df["value"] > high)
    bad = df[is_bad].copy()
    bad["reason"] = [f"below {low}" if t else f"above {high}" for t in too_low[is_bad]]
    return df[~is_bad], bad


def missing_hours(timestamps):
    """Return (expected hours, missing hours) between the first and last timestamp."""
    if len(timestamps) == 0:
        return 0, 0
    ts = pd.to_datetime(timestamps, utc=True)
    expected = int((ts.max() - ts.min()) / pd.Timedelta(hours=1)) + 1
    return expected, expected - ts.nunique()


def run_checks(obs, now=None):
    """obs has columns series_key, ts_utc, value. Returns a list of dicts."""
    now = now or pd.Timestamp.now(tz="UTC")
    results = []
    for key, g in obs.groupby("series_key"):
        expected, missing = missing_hours(g["ts_utc"])
        share = missing / expected if expected else 1
        if missing == 0:
            status = "pass"
        elif share < 0.01:
            status = "warn"
        else:
            status = "fail"
        results.append({"check": "completeness", "series_key": key, "status": status,
                        "detail": f"{missing} of {expected} hours missing"})

        dups = int(g["ts_utc"].duplicated().sum())
        results.append({"check": "duplicates", "series_key": key,
                        "status": "pass" if dups == 0 else "fail",
                        "detail": f"{dups} duplicate hours"})

        latest = pd.to_datetime(g["ts_utc"], utc=True).max()
        age = (now - latest) / pd.Timedelta(hours=1)
        results.append({"check": "freshness", "series_key": key,
                        "status": "pass" if age <= 48 else "warn",
                        "detail": f"latest value {latest:%Y-%m-%d %H:%M} UTC"})
    return results