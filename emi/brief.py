"""Weekly market summary in plain English.

Written with simple rules instead of an AI model on purpose: every sentence
comes straight from a calculated number, so nothing can be made up.
"""
import numpy as np
import pandas as pd

from . import analysis as A


def compare(new, old, unit, old_unit=None):
    """'up 5.0 €/MWh from 40.0 €/MWh the week before'. Uses absolute differences,
    because percent changes make no sense when prices go below zero."""
    old_unit = old_unit or unit
    if pd.isna(new) or pd.isna(old):
        return "no data for the week before"
    diff = new - old
    if abs(diff) < 0.5:
        return f"about the same as the week before ({old:.1f}{old_unit})"
    direction = "up" if diff > 0 else "down"
    return f"{direction} {abs(diff):.1f}{unit} from {old:.1f}{old_unit} the week before"


def weekly_brief(df, scores=None, checks=None, source="smard"):
    end = df.index.max()
    week = A.last_days(df, 7, end)
    prev = A.last_days(df, 7, end - pd.Timedelta(days=7))
    k, k0 = A.kpis(week), A.kpis(prev)
    neg = A.negative_prices(week)
    mo = A.merit_order(A.last_days(df, 90, end))
    battery = A.battery_value(week)

    first, last = week["local_time"].min(), week["local_time"].max()
    lines = [f"## Weekly market brief: {first:%d %b} to {last:%d %b %Y}"]
    if source == "demo":
        lines.append("> ⚠️ Based on **demo data**, not real market data.")
    lines.append(f"*Price data available for {k['price_hours']} of {k['hours']} hours.*")

    lines.append("\n### Prices")
    lines.append(f"- Average day-ahead price: **€{k['avg_price']:.2f}/MWh**, "
                 f"{compare(k['avg_price'], k0.get('avg_price', np.nan), ' €/MWh')}.")
    lines.append(f"- Lowest €{k['min_price']:.2f}, highest €{k['max_price']:.2f}/MWh.")
    if neg["count"]:
        lines.append(f"- **{neg['count']} hours with negative prices.** Renewables made "
                     f"{neg['renewable_share_when_negative']:.0%} of generation in those hours, "
                     f"compared with {neg['renewable_share_otherwise']:.0%} in the other hours.")
    else:
        lines.append("- No hours with negative prices.")

    lines.append("\n### Generation")
    lines.append(f"- Renewables: **{k['renewable_share']:.1%}** of generation, "
                 f"{compare(k['renewable_share'] * 100, k0.get('renewable_share', np.nan) * 100, ' pp', '%')}.")
    lines.append(f"- Average grid load: {k['avg_load_gw']:.1f} GW.")
    if mo:
        lines.append(f"- Over the last 90 days, each extra GW of residual load added about "
                     f"**€{mo['slope']:.1f}/MWh** to the price (R² {mo['r2']:.2f}).")

    if not battery.empty:
        lines.append("\n### Battery opportunity")
        lines.append(f"- A 1 MW / 2 MWh battery could have earned up to **€{battery['revenue'].sum():,.0f}** "
                     f"this week (best case: one cycle per day, no fees).")

    if scores is not None and not scores.empty:
        s = scores.set_index("model")
        better = "beats" if s.loc["gradient_boosting", "rmae"] < 1 else "does not beat"
        lines.append("\n### Forecast")
        lines.append(f"- The model {better} the 'same as yesterday' rule: average error "
                     f"€{s.loc['gradient_boosting', 'mae']:.1f} vs €{s.loc['same_as_yesterday', 'mae']:.1f}/MWh.")

    if checks:
        problems = [c for c in checks if c["status"] != "pass"]
        lines.append("\n### Data quality")
        if not problems:
            lines.append("- All checks passed.")
        for c in problems[:6]:
            lines.append(f"- {c['series_key']} ({c['check']}): **{c['status']}**, {c['detail']}.")

    return "\n".join(lines)