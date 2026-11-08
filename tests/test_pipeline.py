import sqlite3

import pandas as pd

from emi import brief, db, forecast, pipeline, report


def test_forecast_only_uses_past_information(demo_df):
    f = forecast.add_features(demo_df)
    t = f.index[500]
    assert f.loc[t, "price_24h_ago"] == f.loc[t - pd.Timedelta(hours=24), "price"]
    assert f.loc[t, "residual_load_48h_ago"] == f.loc[t - pd.Timedelta(hours=48), "residual_load"]
    # the real forecast must never see same-hour price, wind, solar or load
    assert not {"price", "wind", "solar", "load", "residual_load"} & set(forecast.FEATURES)


def test_forecast_beats_baseline(demo_df):
    results = forecast.backtest(demo_df, test_days=14)
    s = forecast.scores(results).set_index("model")
    assert s.loc["gradient_boosting", "mae"] < s.loc["same_as_yesterday", "mae"]
    assert s.loc["oracle", "mae"] < s.loc["gradient_boosting", "mae"]


def test_brief_wording():
    assert brief.compare(10.0, 30.0, " €/MWh") == "down 20.0 €/MWh from 30.0 €/MWh the week before"
    assert brief.compare(55.0, 50.0, " pp", "%") == "up 5.0 pp from 50.0% the week before"


def test_saving_twice_does_not_create_duplicates(tmp_path):
    con = db.connect(tmp_path / "test.db")
    run_id = db.start_run(con, "demo")
    df = pd.DataFrame({"ts_utc": pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC"),
                       "value": [1.0, 2, 3, 4, 5]})
    db.save_observations(con, "load", df, run_id)
    db.save_observations(con, "load", df.assign(value=df["value"] * 10), run_id)
    assert con.execute("SELECT COUNT(*), SUM(value) FROM observations").fetchone() == (5, 150.0)


def test_whole_pipeline_with_demo_data(tmp_path):
    path = tmp_path / "test.db"
    assert pipeline.run(demo=True, start="2026-07-01", db_path=path, export=tmp_path / "copy.gz") == "success"
    # second run only adds new hours
    assert pipeline.run(demo=True, start="2026-07-01", db_path=path, do_forecast=False) == "success"

    con = sqlite3.connect(path)
    total, unique = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT series_key || ts_utc) FROM observations").fetchone()
    assert total == unique
    assert con.execute("SELECT COUNT(*) FROM bad_rows").fetchone()[0] >= 1
    assert "demo data" in con.execute("SELECT text_md FROM briefs").fetchone()[0]
    assert "DEMO DATA" in report.key_findings(path)

    db.import_gz(tmp_path / "copy.gz", tmp_path / "restored.db")
    restored = sqlite3.connect(tmp_path / "restored.db")
    assert restored.execute("SELECT COUNT(*) FROM observations").fetchone()[0] > 0