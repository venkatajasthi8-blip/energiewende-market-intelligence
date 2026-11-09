"""Forecast tomorrow's 24 hourly prices, and test it honestly.

The real situation: the day-ahead auction closes at 12:00 on day D and sets the
prices for every hour of day D+1. A forecast made before that may only use what
is already known at that moment:
  - prices up to day D            -> price from 24h, 48h, 168h earlier
  - actual wind/solar/load        -> only from 48h earlier (published with a delay)
  - the calendar                  -> hour, weekday, month, holidays

To check whether the model is any good, it is compared to two simple rules
("same price as yesterday" and "same price as last week"). The test is
walk-forward: the model is trained only on the past and tested on the next
week, then the window moves on one week.

There is also an "oracle" model that is allowed to see the real wind/solar/load
of the hour it predicts. That is cheating, so it is NOT a forecast - it only shows
how much better the model could get with good weather forecasts.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

CALENDAR = ["hour", "weekday", "month", "day_off", "holiday"]
FEATURES = CALENDAR + [
    "price_24h_ago", "price_48h_ago", "price_week_ago",
    "yesterday_mean", "yesterday_min", "yesterday_max",
    "residual_load_48h_ago", "wind_48h_ago", "solar_48h_ago", "load_week_ago",
]
ORACLE_FEATURES = FEATURES + ["residual_load", "load", "wind", "solar"]

MODEL_NAMES = {
    "same_as_yesterday": "Same hour yesterday (baseline)",
    "same_as_last_week": "Same hour last week (baseline)",
    "gradient_boosting": "Gradient boosting model",
    "oracle": "Model with actual weather (not a real forecast)",
}


def add_features(df):
    # make sure every hour exists, so shift(24) really means 24 hours back
    hours = pd.date_range(df.index.min(), df.index.max(), freq="h", tz="UTC")
    df = df.reindex(hours)
    local = df.index.tz_convert("Europe/Berlin")
    df["hour"], df["weekday"], df["month"] = local.hour, local.dayofweek, local.month
    df["holiday"] = df["holiday"].astype("boolean").fillna(False).astype(int)
    df["day_off"] = ((df["weekday"] >= 5) | (df["holiday"] == 1)).astype(int)

    p = df["price"]
    df["price_24h_ago"] = p.shift(24)
    df["price_48h_ago"] = p.shift(48)
    df["price_week_ago"] = p.shift(168)
    last_24 = p.rolling(24, min_periods=20)
    df["yesterday_mean"] = last_24.mean().shift(24)
    df["yesterday_min"] = last_24.min().shift(24)
    df["yesterday_max"] = last_24.max().shift(24)
    df["residual_load_48h_ago"] = df["residual_load"].shift(48)
    df["wind_48h_ago"] = df["wind"].shift(48)
    df["solar_48h_ago"] = df["solar"].shift(48)
    df["load_week_ago"] = df["load"].shift(168)
    return df


def new_model():
    # absolute_error loss = less sensitive to extreme price spikes
    return HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.06,
                                         max_iter=350, min_samples_leaf=30, random_state=7)


def backtest(df, test_days=56, step_days=7, min_train_days=60):
    data = add_features(df).dropna(subset=["price"])
    end = data.index.max()
    # test weeks start at midnight German time, like real delivery days
    start = (end - pd.Timedelta(days=test_days)).tz_convert("Europe/Berlin").normalize()
    if start.tz_convert("UTC") - data.index.min() < pd.Timedelta(days=min_train_days):
        raise ValueError(f"need at least {min_train_days + test_days} days of data")

    results = []
    week = start
    while week.tz_convert("UTC") <= end:
        week_end = week + pd.Timedelta(days=step_days)
        train = data[data.index < week.tz_convert("UTC")]
        test = data[(data.index >= week.tz_convert("UTC")) & (data.index < week_end.tz_convert("UTC"))]
        if test.empty:
            break
        out = pd.DataFrame({"actual": test["price"]})
        out["same_as_yesterday"] = test["price_24h_ago"]
        out["same_as_last_week"] = test["price_week_ago"]
        # the models predict how much the price changes compared with yesterday,
        # not the price itself. Trees can't predict values outside what they've seen,
        # so this works much better when the price level moves.
        change = train["price"] - train["price_24h_ago"]
        ok = change.notna()
        for name, cols in (("gradient_boosting", FEATURES), ("oracle", ORACLE_FEATURES)):
            model = new_model().fit(train.loc[ok, cols], change[ok])
            out[name] = test["price_24h_ago"] + model.predict(test[cols])
        results.append(out)
        week = week_end

    wide = pd.concat(results).dropna()
    return (wide.reset_index(names="ts_utc")
            .melt(id_vars=["ts_utc", "actual"], var_name="model", value_name="predicted"))


def scores(results):
    rows = []
    for model, g in results.groupby("model"):
        err = g["predicted"] - g["actual"]
        rows.append({"model": model, "mae": err.abs().mean(), "rmse": np.sqrt((err**2).mean())})
    table = pd.DataFrame(rows).set_index("model")
    # rMAE < 1 means better than just copying yesterday's price
    table["rmae"] = table["mae"] / table.loc["same_as_yesterday", "mae"]
    return table.sort_values("mae").reset_index()