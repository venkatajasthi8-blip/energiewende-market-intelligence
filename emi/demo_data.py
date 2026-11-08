"""Fake but realistic-looking market data, so the project runs without internet.

Runs that use this are saved with source = 'demo' and the dashboard shows a
warning, so demo numbers never get mixed up with real ones.
"""
import numpy as np
import pandas as pd

from .config import TZ


def make_demo_data(start, end=None, seed=42):
    rng = np.random.default_rng(seed)
    if end is None:
        end = pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=1)
    else:
        end = pd.Timestamp(end, tz="UTC")
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), end, freq="h")
    local = idx.tz_convert(TZ)
    n = len(idx)

    hour = np.asarray(local.hour)
    weekend = np.asarray(local.dayofweek) >= 5
    # +1 in mid January, -1 in mid July
    winter = np.cos(2 * np.pi * (np.asarray(local.dayofyear) - 15) / 365)

    # demand: higher during the day, on weekdays and in winter
    day_shape = 1 + 0.18 * np.sin(np.pi * np.clip(hour - 5, 0, 16) / 16)
    load = 47_000 * day_shape * np.where(weekend, 0.84, 1) * (1 + 0.08 * winter)
    load += rng.normal(0, 900, n)

    # solar: bell curve during daylight, stronger in summer, random cloudy days
    daylight = 12 - 4 * winter
    pos = np.clip((hour + 0.5 - (12 - daylight / 2)) / daylight, 0, 1)
    clouds = np.repeat(rng.beta(4, 2, n // 24 + 2), 24)[:n]
    solar = 52_000 * (0.55 - 0.45 * winter) * np.sin(np.pi * pos) ** 1.6 * clouds

    # wind: changes slowly over days, windier in winter
    cf = np.empty(n)
    cf[0] = 0.3
    noise = rng.normal(0, 0.035, n)
    for i in range(1, n):
        cf[i] = 0.97 * cf[i - 1] + 0.03 * (0.24 + 0.1 * winter[i]) + noise[i]
    cf = np.clip(cf, 0.02, 0.85)
    wind_on = 50_000 * cf
    wind_off = 9_000 * np.clip(cf * 1.25 + rng.normal(0, 0.03, n), 0.02, 0.95)

    biomass = 4_400 + rng.normal(0, 120, n)
    hydro = 1_700 - 300 * winter + rng.normal(0, 80, n)
    other_ren = 180 + rng.normal(0, 15, n)
    residual = load - wind_on - wind_off - solar

    # whatever is left is covered by lignite, then coal, then gas
    rest = np.clip(residual - biomass - hydro - other_ren, 0, None)
    lignite = np.minimum(rest * 0.5, 15_000)
    coal = np.minimum((rest - lignite) * 0.4, 12_000)
    gas = np.clip(rest - lignite - coal, 0, None) * 0.85
    pumped = np.clip((residual - 40_000) / 8, 0, 6_000)

    # price rises with residual load and gets steep at the top (merit order)
    gw = residual / 1000
    price = 42 + 2.1 * (gw - 28) + 0.05 * np.clip(gw - 42, 0, None) ** 2
    price = price * (1 + 0.15 * winter) + rng.normal(0, 7, n)

    values = {
        "price": price, "load": load, "residual_load": residual,
        "wind_onshore": wind_on, "wind_offshore": wind_off, "solar": solar,
        "biomass": biomass, "hydro": hydro, "other_renewables": other_ren,
        "lignite": lignite, "hard_coal": coal, "gas": gas, "nuclear": np.zeros(n),
        "other_conventional": 2_100 + rng.normal(0, 100, n), "pumped_storage": pumped,
    }
    data = {k: pd.DataFrame({"ts_utc": idx, "value": np.round(v, 2)}) for k, v in values.items()}

    # break a few things on purpose so the quality checks have something to find
    if n > 500:
        gap = n // 3
        data["wind_offshore"] = data["wind_offshore"].drop(range(gap, gap + 5)).reset_index(drop=True)
        data["price"].loc[n // 2, "value"] = 99_999.0
    return data