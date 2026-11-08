"""The actual market analysis. Every function takes a dataframe and returns numbers,
so they are easy to test and the dashboard never does its own math.
"""
import numpy as np
import pandas as pd

from .config import CONVENTIONAL, GENERATION, RENEWABLES, TZ
from .holidays import is_holiday


def prepare(hourly):
    """Add totals, renewable share and German local-time columns."""
    df = hourly.copy()

    # Germany shut down its last nuclear plants on 15 April 2023,
    # so a missing nuclear value after that really means 0
    after = df.index >= pd.Timestamp("2023-04-16", tz="UTC")
    df.loc[after, "nuclear"] = df.loc[after, "nuclear"].fillna(0)

    # min_count: if any source is missing in an hour, the total stays empty
    # instead of silently becoming too small
    df["generation"] = df[GENERATION].sum(axis=1, min_count=len(GENERATION))
    df["renewables"] = df[RENEWABLES].sum(axis=1, min_count=len(RENEWABLES))
    df["conventional"] = df[CONVENTIONAL].sum(axis=1, min_count=len(CONVENTIONAL))
    df["wind"] = df["wind_onshore"] + df["wind_offshore"]
    df["renewable_share"] = df["renewables"] / df["generation"]

    local = df.index.tz_convert(TZ)
    df["local_time"] = local
    df["date"] = local.date
    df["hour"] = local.hour
    df["weekday"] = local.dayofweek
    df["month"] = local.month
    df["holiday"] = [is_holiday(d) for d in df["date"]]
    df["day_off"] = (df["weekday"] >= 5) | df["holiday"]
    return df


def last_days(df, days, end=None):
    end = end or df.index.max()
    return df[(df.index > end - pd.Timedelta(days=days)) & (df.index <= end)]


def kpis(df):
    p = df["price"].dropna()
    if p.empty:
        return {"hours": len(df), "price_hours": 0}
    return {
        "hours": len(df),
        "price_hours": len(p),
        "coverage": len(p) / len(df),
        "avg_price": p.mean(),
        "min_price": p.min(),
        "max_price": p.max(),
        "volatility": p.std(),
        "negative_hours": int((p < 0).sum()),
        "renewable_share": df["renewables"].sum() / df["generation"].sum(),
        "avg_load_gw": df["load"].mean() / 1000,
    }


def merit_order(df):
    """How much does the price go up for each extra GW of residual load?

    Residual load = demand minus wind and solar. It is the part that coal and gas
    plants have to cover, and the more expensive plants are needed, the higher the price.
    """
    d = df[["price", "residual_load"]].dropna()
    if len(d) < 50:
        return None
    x = d["residual_load"].values / 1000  # GW
    y = d["price"].values
    a, b, c = np.polyfit(x, y, 2)
    fitted = a * x**2 + b * x + c
    r2 = 1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    slope = 2 * a * np.median(x) + b  # slope of the curve at a typical load level

    # median price per 2.5 GW band, for the chart
    band = np.floor(x / 2.5) * 2.5 + 1.25
    bands = (pd.DataFrame({"gw": band, "price": y}).groupby("gw")["price"]
             .agg(hours="count", median="median",
                  low=lambda s: s.quantile(0.1), high=lambda s: s.quantile(0.9))
             .reset_index())
    bands = bands[bands["hours"] >= 10]
    return {"slope": slope, "r2": r2, "hours": len(d), "bands": bands}


def capture_rates(df):
    """Per month: the average price solar and wind actually earned, compared to the
    normal average price. Below 1 means they mostly produce when power is cheap."""
    d = df.dropna(subset=["price"]).copy()
    d["month_start"] = d["local_time"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    rows = []
    for month, g in d.groupby("month_start"):
        avg = g["price"].mean()
        row = {"month": month, "avg_price": avg}
        for tech in ("solar", "wind"):
            mwh = g[tech].clip(lower=0)
            earned = (g["price"] * mwh).sum() / mwh.sum() if mwh.sum() > 0 else np.nan
            row[f"{tech}_capture_price"] = earned
            row[f"{tech}_capture_rate"] = earned / avg if avg > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def price_by_hour(df):
    """Average price for each hour of the day, workdays vs weekends/holidays."""
    d = df.dropna(subset=["price"])
    table = d.groupby(["hour", "day_off"])["price"].mean().unstack()
    return table.rename(columns={False: "workday", True: "weekend_holiday"}).reset_index()


def negative_prices(df):
    d = df.dropna(subset=["price"])
    neg = d[d["price"] < 0]
    month = d["local_time"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    return {
        "count": len(neg),
        "lowest": neg["price"].min() if len(neg) else np.nan,
        "by_hour": neg.groupby("hour").size().reindex(range(24), fill_value=0),
        "by_month": (d["price"] < 0).groupby(month).sum(),
        "renewable_share_when_negative": neg["renewable_share"].mean() if len(neg) else np.nan,
        "renewable_share_otherwise": d.loc[d["price"] >= 0, "renewable_share"].mean(),
    }


def battery_value(df, hours=2, efficiency=0.88):
    """What could a 1 MW battery earn per day by charging in the cheapest hours and
    selling in the most expensive ones? This is a best case: it assumes you know the
    prices in advance (true for day-ahead) and ignores fees and battery wear."""
    rows = []
    for day, g in df.dropna(subset=["price"]).groupby("date"):
        if len(g) < 20:  # skip days with missing data
            continue
        p = np.sort(g["price"].values)
        revenue = p[-hours:].sum() * efficiency - p[:hours].sum()
        rows.append({"date": pd.Timestamp(day), "spread": p[-1] - p[0], "revenue": revenue})
    return pd.DataFrame(rows)


def generation_mix(df, freq="W"):
    """Generation per source in TWh, per week (or day)."""
    mix = df[GENERATION].copy()
    mix.index = df["local_time"].dt.tz_localize(None)
    return mix.resample(freq).sum(min_count=1) / 1e6