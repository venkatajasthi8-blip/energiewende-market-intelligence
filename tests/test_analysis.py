from datetime import date

import numpy as np
import pandas as pd
import pytest

from emi import analysis as A
from emi.holidays import easter, is_holiday


def one_day(prices, solar):
    # 23:00 UTC is midnight in Berlin in winter, so these 24 hours are exactly one German day
    idx = pd.date_range("2026-03-01 23:00", periods=24, freq="h", tz="UTC")
    zero = np.zeros(24)
    df = pd.DataFrame({
        "price": prices, "load": 50_000.0, "residual_load": 30_000.0, "solar": solar,
        "wind_onshore": zero, "wind_offshore": zero, "biomass": 100.0, "hydro": zero,
        "other_renewables": zero, "lignite": 100.0, "hard_coal": zero, "gas": zero,
        "nuclear": zero, "other_conventional": zero, "pumped_storage": zero,
    }, index=idx)
    return A.prepare(df)


def test_easter_and_holidays():
    assert easter(2025) == date(2025, 4, 20)
    assert easter(2026) == date(2026, 4, 5)
    assert is_holiday(date(2026, 4, 3))      # Good Friday
    assert is_holiday(date(2026, 10, 3))     # German Unity Day
    assert not is_holiday(date(2026, 10, 2))


def test_renewable_share():
    df = one_day(np.full(24, 50.0), np.full(24, 100.0))
    # renewables = solar 100 + biomass 100, conventional = lignite 100
    assert df["renewable_share"].iloc[0] == pytest.approx(2 / 3)


def test_missing_value_does_not_count_as_zero():
    df = one_day(np.full(24, 50.0), np.full(24, 100.0))
    raw = df[list(A.GENERATION) + ["price", "load", "residual_load"]].copy()
    raw.iloc[0, raw.columns.get_loc("gas")] = np.nan
    assert np.isnan(A.prepare(raw)["generation"].iloc[0])


def test_solar_capture_rate():
    # solar only produces in the cheap hours, so it earns less than the average price
    prices = np.array([100, 100, 10, 10] * 6, dtype=float)
    solar = np.array([0, 0, 50, 50] * 6, dtype=float)
    cr = A.capture_rates(one_day(prices, solar))
    assert cr["solar_capture_price"].iloc[0] == pytest.approx(10)
    assert cr["solar_capture_rate"].iloc[0] == pytest.approx(10 / 55)


def test_battery_value():
    prices = np.r_[np.full(22, 50.0), 0.0, 100.0]
    bv = A.battery_value(one_day(prices, np.zeros(24)), hours=1, efficiency=1.0)
    assert bv["revenue"].iloc[0] == pytest.approx(100)  # buy at 0, sell at 100


def test_merit_order_on_demo_data(demo_df):
    mo = A.merit_order(demo_df)
    assert mo["slope"] > 0
    assert mo["r2"] > 0.5


def test_negative_prices_add_up(demo_df):
    neg = A.negative_prices(demo_df)
    assert neg["count"] == A.kpis(demo_df)["negative_hours"]
    assert neg["by_hour"].sum() == neg["count"]