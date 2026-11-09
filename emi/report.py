"""Print the key numbers as a Markdown table to paste into the README.

    python -m emi.report
"""
import sqlite3

import pandas as pd

from . import analysis as A
from . import db
from .config import DB_PATH


def key_findings(db_path=DB_PATH):
    con = sqlite3.connect(db_path)
    df = A.prepare(db.read_hourly(con))
    source = con.execute("SELECT source FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0]
    scores = pd.read_sql("SELECT * FROM forecast_scores WHERE run_id = "
                         "(SELECT MAX(run_id) FROM forecast_scores)", con).set_index("model")
    con.close()

    year = A.last_days(df, 365)
    k = A.kpis(df)
    mo = A.merit_order(year)
    cr = A.capture_rates(df)
    neg = A.negative_prices(df)
    battery = A.battery_value(year)

    lines = []
    if source == "demo":
        lines.append("> ⚠️ DEMO DATA - run the real pipeline before using these numbers.\n")
    lines.append(f"Data from {df['local_time'].min():%d %b %Y} to {df['local_time'].max():%d %b %Y}, "
                 f"{k['price_hours']:,} hourly prices.\n")
    lines.append("| Finding | Value |")
    lines.append("|---|---|")
    lines.append(f"| Average day-ahead price | €{k['avg_price']:.2f}/MWh |")
    lines.append(f"| Renewable share of generation | {k['renewable_share']:.1%} |")
    lines.append(f"| Hours with negative prices | {neg['count']:,}, most often at "
                 f"{neg['by_hour'].idxmax()}:00 |")
    lines.append(f"| Price increase per extra GW of residual load (last 12 months) | "
                 f"€{mo['slope']:.2f}/MWh (R² {mo['r2']:.2f}) |")
    lines.append(f"| Average solar capture rate | {cr['solar_capture_rate'].mean():.2f} |")
    lines.append(f"| Average wind capture rate | {cr['wind_capture_rate'].mean():.2f} |")
    lines.append(f"| 1 MW / 2 MWh battery, last 12 months (best case) | €{battery['revenue'].sum():,.0f} |")
    if not scores.empty:
        diff = (1 - scores.loc["gradient_boosting", "rmae"]) * 100
        word = "lower" if diff >= 0 else "higher"
        lines.append(f"| Forecast error vs 'same as yesterday' | {abs(diff):.0f}% {word} "
                     f"(€{scores.loc['gradient_boosting', 'mae']:.1f} vs "
                     f"€{scores.loc['same_as_yesterday', 'mae']:.1f}/MWh) |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(key_findings())