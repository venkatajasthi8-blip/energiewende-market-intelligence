import pandas as pd

from emi.quality import missing_hours, run_checks, split_bad_rows


def frame(values):
    ts = pd.date_range("2026-01-01", periods=len(values), freq="h", tz="UTC")
    return pd.DataFrame({"ts_utc": ts, "value": values})


def test_impossible_prices_are_rejected_but_negative_prices_are_fine():
    good, bad = split_bad_rows(frame([50.0, -600.0, 99_999.0, -20.0]), "price")
    assert good["value"].tolist() == [50.0, -20.0]
    assert bad["reason"].tolist() == ["below -500", "above 4000"]


def test_solar_cannot_be_negative():
    _, bad = split_bad_rows(frame([100.0, -1.0]), "solar")
    assert len(bad) == 1


def test_missing_hours():
    ts = pd.Series(pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")).drop([3, 4])
    assert missing_hours(ts) == (10, 2)


def test_check_statuses():
    ts = pd.date_range("2026-01-01", periods=1000, freq="h", tz="UTC")
    full = pd.DataFrame({"series_key": "load", "ts_utc": ts, "value": 1.0})
    gaps = full.assign(series_key="solar").drop(range(100, 300))  # 20% missing
    now = ts.max() + pd.Timedelta(hours=1)
    result = {(c["series_key"], c["check"]): c["status"] for c in run_checks(pd.concat([full, gaps]), now)}
    assert result[("load", "completeness")] == "pass"
    assert result[("solar", "completeness")] == "fail"
    assert result[("load", "freshness")] == "pass"

    later = now + pd.Timedelta(days=5)
    result = {(c["series_key"], c["check"]): c["status"] for c in run_checks(full, later)}
    assert result[("load", "freshness")] == "warn"