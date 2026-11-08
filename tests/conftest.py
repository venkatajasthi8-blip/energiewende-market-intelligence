import pandas as pd
import pytest

from emi import analysis
from emi.demo_data import make_demo_data


@pytest.fixture(scope="session")
def demo_df():
    """About 4 months of demo data, prepared like the real pipeline does it."""
    data = make_demo_data("2026-01-01", end="2026-05-10", seed=1)
    hourly = pd.concat({k: v.set_index("ts_utc")["value"] for k, v in data.items()}, axis=1)
    hourly = hourly[hourly["price"] < 4000]  # remove the deliberately broken value
    return analysis.prepare(hourly)