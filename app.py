# """Streamlit dashboard.   Run with:  streamlit run app.py"""
# import sqlite3
# import time
# import urllib.request

# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import streamlit as st

# from emi import analysis as A
# from emi import db
# from emi.config import DATA_URL, DB_PATH, GENERATION, SERIES
# from emi.forecast import MODEL_NAMES

# st.set_page_config(page_title="Energiewende Market Intelligence", page_icon="⚡", layout="wide")

# RED, GREEN = "#C1121F", "#2A9D8F"
# COLORS = {"solar": "#F2B705", "wind_onshore": "#2E86AB", "wind_offshore": "#1B4F72",
#           "biomass": "#6A994E", "hydro": "#48CAE4", "other_renewables": "#A7C957",
#           "lignite": "#7F5539", "hard_coal": "#3D3D3D", "gas": "#E76F51", "nuclear": "#9B5DE5",
#           "other_conventional": "#ADB5BD", "pumped_storage": "#00B4D8"}


# def get_database():
#     # Online, the app downloads the database that GitHub Actions publishes every night.
#     # It downloads again when its copy is older than 12 hours.
#     old = not DB_PATH.exists() or time.time() - DB_PATH.stat().st_mtime > 12 * 3600
#     if DATA_URL and old:
#         with st.spinner("Downloading latest data..."):
#             gz = DB_PATH.with_suffix(".db.gz")
#             DB_PATH.parent.mkdir(exist_ok=True)
#             urllib.request.urlretrieve(DATA_URL, gz)
#             db.import_gz(gz, DB_PATH)
#             gz.unlink()
#     return DB_PATH if DB_PATH.exists() else None


# @st.cache_data(ttl=3600)
# def load(path, modified):  # `modified` makes the cache refresh when the file changes
#     con = sqlite3.connect(path)
#     sql = lambda q: pd.read_sql(q, con)  # noqa: E731
#     data = {
#         "df": A.prepare(db.read_hourly(con)),
#         "runs": sql("SELECT * FROM runs ORDER BY run_id DESC"),
#         "checks": sql("SELECT * FROM quality_checks WHERE run_id = (SELECT MAX(run_id) FROM quality_checks)"),
#         "bad_rows": sql("SELECT * FROM bad_rows ORDER BY ts_utc DESC LIMIT 500"),
#         "results": sql("SELECT * FROM forecast_results"),
#         "scores": sql("SELECT * FROM forecast_scores WHERE run_id = (SELECT MAX(run_id) FROM forecast_scores)"),
#         "briefs": sql("SELECT * FROM briefs ORDER BY rowid DESC LIMIT 20"),
#     }
#     con.close()
#     data["results"]["ts_utc"] = pd.to_datetime(data["results"]["ts_utc"], utc=True)
#     return data


# path = get_database()
# if path is None:
#     st.title("⚡ Energiewende Market Intelligence")
#     st.info("No data yet. Run `python -m emi.pipeline` (real data) or "
#             "`python -m emi.pipeline --demo` (offline demo) first.")
#     st.stop()

# data = load(str(path), path.stat().st_mtime)
# everything = data["df"]
# runs = data["runs"]

# # ---------------- sidebar
# st.sidebar.title("⚡ Energiewende")
# first_day, last_day = everything["date"].min(), everything["date"].max()
# default_start = max(first_day, last_day - pd.Timedelta(days=90))
# picked = st.sidebar.date_input("Period", (default_start, last_day), min_value=first_day, max_value=last_day)
# start, end = picked if len(picked) == 2 else (default_start, last_day)
# df = everything[(everything["date"] >= start) & (everything["date"] <= end)]
# days = (end - start).days + 1
# before = everything[(everything["date"] < start) & (everything["date"] >= start - pd.Timedelta(days=days))]

# if not runs.empty:
#     r = runs.iloc[0]
#     st.sidebar.write(f"Last update: {r['finished'] or r['started']} UTC")
#     st.sidebar.write(f"Status: `{r['status']}`")
# st.sidebar.caption("Data: Bundesnetzagentur | SMARD.de (CC BY 4.0)")

# st.title("Energiewende Market Intelligence")
# st.caption("How wind, solar and demand drive German electricity prices.")
# if not runs.empty and runs.iloc[0]["source"] == "demo":
#     st.warning("This is **demo data**. Run `python -m emi.pipeline` to load the real data.")
# if df.empty:
#     st.error("No data in this period.")
#     st.stop()

# tabs = st.tabs(["Overview", "Merit order", "Solar & wind value", "Negative prices & batteries",
#                 "Forecast", "Data quality", "Weekly brief"])

# # ---------------- overview
# with tabs[0]:
#     k = A.kpis(df)
#     k0 = A.kpis(before) if not before.empty else {}

#     def change(key, scale=1, fmt="{:+.1f}"):
#         return fmt.format((k[key] - k0[key]) * scale) if key in k0 else None

#     c = st.columns(5)
#     c[0].metric("Average price", f"€{k['avg_price']:.2f}/MWh", change("avg_price"), delta_color="inverse")
#     c[1].metric("Volatility", f"{k['volatility']:.1f} €/MWh", change("volatility"), delta_color="inverse")
#     c[2].metric("Negative-price hours", k["negative_hours"], change("negative_hours", fmt="{:+.0f}"), delta_color="off")
#     c[3].metric("Renewable share", f"{k['renewable_share']:.1%}", change("renewable_share", 100, "{:+.1f} pp"))
#     c[4].metric("Average load", f"{k['avg_load_gw']:.1f} GW", change("avg_load_gw"), delta_color="off")
#     st.caption(f"Compared with the {days} days before. Price data for {k['coverage']:.1%} of hours.")

#     daily = df.groupby("date").agg(price=("price", "mean"), ren=("renewables", "sum"),
#                                    gen=("generation", "sum")).reset_index()
#     fig = go.Figure()
#     fig.add_bar(x=daily["date"], y=daily["ren"] / daily["gen"] * 100, name="Renewable share %",
#                 marker_color=GREEN, opacity=0.35, yaxis="y2")
#     fig.add_scatter(x=daily["date"], y=daily["price"], name="Average price €/MWh", line={"color": RED})
#     fig.update_layout(title="More renewables, lower prices", height=420,
#                       yaxis={"title": "€/MWh"},
#                       yaxis2={"title": "%", "overlaying": "y", "side": "right", "range": [0, 100]})
#     st.plotly_chart(fig, use_container_width=True)

#     mix = A.generation_mix(df, "W" if days > 60 else "D").reset_index(names="period")
#     mix = mix.melt(id_vars="period", var_name="source", value_name="TWh")
#     fig = px.area(mix, x="period", y="TWh", color="source", title="Generation by source",
#                   color_discrete_map=COLORS)
#     st.plotly_chart(fig, use_container_width=True)

# # ---------------- merit order
# with tabs[1]:
#     st.subheader("Merit order: why demand left after wind and solar sets the price")
#     st.write("Power plants are used from cheapest to most expensive. Residual load "
#              "(demand minus wind and solar) decides how expensive the last plant needed is.")
#     mo = A.merit_order(df)
#     if mo is None:
#         st.info("Not enough data in this period.")
#     else:
#         c = st.columns(3)
#         c[0].metric("Price per extra GW", f"€{mo['slope']:.2f}/MWh")
#         c[1].metric("R²", f"{mo['r2']:.2f}")
#         c[2].metric("Hours", f"{mo['hours']:,}")
#         dots = df.dropna(subset=["price", "residual_load"])
#         dots = dots.sample(min(len(dots), 4000), random_state=1)
#         fig = px.scatter(x=dots["residual_load"] / 1000, y=dots["price"], opacity=0.25,
#                          labels={"x": "Residual load (GW)", "y": "Price (€/MWh)"})
#         b = mo["bands"]
#         fig.add_scatter(x=b["gw"], y=b["high"], line={"width": 0}, showlegend=False)
#         fig.add_scatter(x=b["gw"], y=b["low"], fill="tonexty", line={"width": 0},
#                         fillcolor="rgba(193,18,31,0.15)", name="10-90% of hours")
#         fig.add_scatter(x=b["gw"], y=b["median"], name="Median price", line={"color": RED, "width": 3})
#         fig.update_layout(height=500, title="Each dot is one hour")
#         st.plotly_chart(fig, use_container_width=True)

# # ---------------- capture rates
# with tabs[2]:
#     st.subheader("What is solar and wind power actually worth?")
#     st.write("The capture rate is the price solar or wind actually earned divided by the average price. "
#              "Because all solar panels produce at the same time, they push the price down exactly "
#              "when they produce, so solar usually earns less than average.")
#     cr = A.capture_rates(df)
#     fig = go.Figure()
#     fig.add_scatter(x=cr["month"], y=cr["solar_capture_rate"], name="Solar", line={"color": COLORS["solar"], "width": 3})
#     fig.add_scatter(x=cr["month"], y=cr["wind_capture_rate"], name="Wind", line={"color": COLORS["wind_onshore"], "width": 3})
#     fig.add_hline(y=1, line_dash="dot", annotation_text="average price")
#     fig.update_layout(title="Capture rate per month", height=420)
#     st.plotly_chart(fig, use_container_width=True)

#     by_hour = A.price_by_hour(df)
#     fig = px.line(by_hour, x="hour", y=[c for c in ("workday", "weekend_holiday") if c in by_hour],
#                   markers=True, title="Average price by hour of the day",
#                   labels={"value": "€/MWh", "variable": ""})
#     st.plotly_chart(fig, use_container_width=True)

# # ---------------- negative prices and batteries
# with tabs[3]:
#     neg = A.negative_prices(df)
#     c = st.columns(3)
#     c[0].metric("Negative-price hours", neg["count"])
#     c[1].metric("Lowest price", "-" if pd.isna(neg["lowest"]) else f"€{neg['lowest']:.2f}")
#     if neg["count"]:
#         c[2].metric("Renewable share in those hours", f"{neg['renewable_share_when_negative']:.0%}",
#                     f"vs {neg['renewable_share_otherwise']:.0%} otherwise", delta_color="off")
#     left, right = st.columns(2)
#     left.plotly_chart(px.bar(x=neg["by_hour"].index, y=neg["by_hour"].values, title="At what time?",
#                              labels={"x": "Hour", "y": "Hours"}, color_discrete_sequence=[RED]),
#                       use_container_width=True)
#     right.plotly_chart(px.bar(x=neg["by_month"].index, y=neg["by_month"].values, title="Per month",
#                               labels={"x": "", "y": "Hours"}, color_discrete_sequence=[RED]),
#                        use_container_width=True)

#     st.subheader("Battery: buy cheap, sell expensive")
#     c = st.columns(2)
#     hours = c[0].select_slider("Battery size (hours of storage)", [1, 2, 4], value=2)
#     eff = c[1].slider("Efficiency", 0.70, 0.95, 0.88)
#     bv = A.battery_value(df, hours, eff)
#     if not bv.empty:
#         st.metric(f"1 MW / {hours} MWh battery, whole period (best case)", f"€{bv['revenue'].sum():,.0f}")
#         st.plotly_chart(px.bar(bv, x="date", y="revenue", title="Revenue per day",
#                                color_discrete_sequence=[GREEN]), use_container_width=True)
#     st.caption("Best case: one charge/discharge per day, prices known in advance, no fees or battery wear.")

# # ---------------- forecast
# with tabs[4]:
#     st.subheader("Forecasting tomorrow's prices")
#     scores = data["scores"]
#     if scores.empty:
#         st.info("No forecast yet (needs about 4 months of data).")
#     else:
#         scores["description"] = scores["model"].map(MODEL_NAMES)
#         st.dataframe(scores[["model", "description", "mae", "rmse", "rmae"]].round(2), hide_index=True)
#         st.caption("MAE = average error in €/MWh. rMAE below 1 = better than copying yesterday's price. "
#                    "Each week is predicted by a model trained only on earlier data. "
#                    "The oracle sees the real weather, so it is only an upper limit, not a forecast.")
#         res = data["results"]
#         recent = res[res["ts_utc"] >= res["ts_utc"].max() - pd.Timedelta(days=14)]
#         chosen = st.multiselect("Show", list(MODEL_NAMES), default=["gradient_boosting", "same_as_yesterday"])
#         actual = recent.drop_duplicates("ts_utc").sort_values("ts_utc")
#         fig = go.Figure()
#         fig.add_scatter(x=actual["ts_utc"], y=actual["actual"], name="Actual", line={"color": "black"})
#         for m in chosen:
#             s = recent[recent["model"] == m].sort_values("ts_utc")
#             fig.add_scatter(x=s["ts_utc"], y=s["predicted"], name=m)
#         fig.update_layout(title="Last 14 days: forecast vs actual", yaxis_title="€/MWh", height=440)
#         st.plotly_chart(fig, use_container_width=True)

# # ---------------- data quality
# with tabs[5]:
#     st.subheader("Data quality")
#     checks = data["checks"]
#     if not checks.empty:
#         st.dataframe(checks.pivot(index="series_key", columns="check", values="status"))
#         problems = checks[checks["status"] != "pass"]
#         if not problems.empty:
#             st.write("**Problems found**")
#             st.dataframe(problems[["series_key", "check", "status", "detail"]], hide_index=True)
#     complete = df[["price", "load", "residual_load"] + GENERATION].notna().mean() * 100
#     complete.index = [SERIES[k][1] for k in complete.index]
#     st.plotly_chart(px.bar(x=complete.values, y=complete.index, orientation="h", range_x=[0, 100],
#                            title="% of hours with data", labels={"x": "%", "y": ""},
#                            color_discrete_sequence=[GREEN]), use_container_width=True)
#     st.write("**Rows rejected by the plausibility check** (kept here, not used in the analysis)")
#     st.dataframe(data["bad_rows"], hide_index=True)
#     st.write("**Pipeline runs**")
#     st.dataframe(runs, hide_index=True)

# # ---------------- brief
# with tabs[6]:
#     briefs = data["briefs"]
#     if briefs.empty:
#         st.info("No brief yet.")
#     else:
#         st.markdown(briefs.iloc[0]["text_md"])
#         st.download_button("Download as Markdown", briefs.iloc[0]["text_md"], "weekly_brief.md")


import sqlite3
import time
import urllib.request
from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from emi import analysis as A
from emi import db
from emi.config import DATA_URL, DB_PATH, GENERATION, SERIES
from emi.forecast import MODEL_NAMES

st.set_page_config(page_title="Energiewende Market Intelligence", page_icon="⚡", layout="wide")

INK = "#1C2321"
MUTED = "#6B7280"
GRID = "#E7E5DF"
TEAL = "#0F766E"
RED = "#B91C1C"
AMBER = "#D97706"

# 12 sources is too many for one chart, so they're grouped (bottom of the stack first)
MIX = {
    "Solar": (["solar"], "#F2B705"),
    "Wind onshore": (["wind_onshore"], "#3B82C4"),
    "Wind offshore": (["wind_offshore"], "#1E4E79"),
    "Biomass & hydro": (["biomass", "hydro", "other_renewables"], "#6A994E"),
    "Gas": (["gas"], "#E76F51"),
    "Hard coal": (["hard_coal"], "#4B5563"),
    "Lignite": (["lignite"], "#8B5E3C"),
    "Other": (["nuclear", "other_conventional", "pumped_storage"], "#C9C6BD"),
}

st.markdown("""
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px;}
#MainMenu, footer {visibility: hidden;}
h1 {font-size: 2.1rem !important; letter-spacing: -0.02em;}
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E7E5DF;
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] p {color: #6B7280; font-size: 0.85rem;}
[data-testid="stMetricValue"] {font-size: 1.55rem; font-weight: 600;}
.stTabs [data-baseweb="tab-list"] {gap: 6px; border-bottom: 1px solid #E7E5DF;}
.stTabs [data-baseweb="tab"] {padding: 10px 14px; font-weight: 500;}
.subtitle {color: #6B7280; font-size: 1.05rem; margin-top: -0.8rem; margin-bottom: 1.6rem;}
.chart-title {font-weight: 600; font-size: 1.02rem; margin: 1.2rem 0 0 0;}
.chart-note {color: #6B7280; font-size: 0.88rem; margin: 0.1rem 0 0.4rem 0;}
</style>
""", unsafe_allow_html=True)


def chart_title(title, note=""):
    st.markdown(f'<p class="chart-title">{title}</p>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<p class="chart-note">{note}</p>', unsafe_allow_html=True)


def tidy(fig, height=360, legend=True, hover="x unified"):
    fig.update_layout(
        template="plotly_white",
        height=height,
        font=dict(family="Inter, -apple-system, Helvetica, Arial, sans-serif", size=13, color=INK),
        margin=dict(l=0, r=0, t=30 if legend else 10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", title=dict(text="")),
        hovermode=hover,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def get_database():
    # online the app pulls the database that the nightly GitHub Action publishes
    too_old = not DB_PATH.exists() or time.time() - DB_PATH.stat().st_mtime > 12 * 3600
    if DATA_URL and too_old:
        with st.spinner("Downloading the latest data..."):
            gz = DB_PATH.with_suffix(".db.gz")
            DB_PATH.parent.mkdir(exist_ok=True)
            urllib.request.urlretrieve(DATA_URL, gz)
            db.import_gz(gz, DB_PATH)
            gz.unlink()
    return DB_PATH if DB_PATH.exists() else None


@st.cache_data(ttl=3600)
def load(path, modified):  # modified time is only here so the cache resets when the file changes
    con = sqlite3.connect(path)
    q = lambda sql: pd.read_sql(sql, con)  # noqa: E731
    data = {
        "df": A.prepare(db.read_hourly(con)),
        "runs": q("SELECT * FROM runs ORDER BY run_id DESC"),
        "checks": q("SELECT * FROM quality_checks WHERE run_id = (SELECT MAX(run_id) FROM quality_checks)"),
        "bad_rows": q("SELECT * FROM bad_rows ORDER BY ts_utc DESC LIMIT 500"),
        "results": q("SELECT * FROM forecast_results"),
        "scores": q("SELECT * FROM forecast_scores WHERE run_id = (SELECT MAX(run_id) FROM forecast_scores)"),
        "briefs": q("SELECT * FROM briefs ORDER BY rowid DESC LIMIT 1"),
    }
    con.close()
    data["results"]["ts_utc"] = pd.to_datetime(data["results"]["ts_utc"], utc=True)
    return data


path = get_database()
if path is None:
    st.title("Energiewende Market Intelligence")
    st.info("No data yet. Run `python -m emi.pipeline` for the real data, "
            "or `python -m emi.pipeline --demo` to try it offline.")
    st.stop()

data = load(str(path), path.stat().st_mtime)
everything = data["df"]
runs = data["runs"]
last_run = runs.iloc[0] if not runs.empty else None

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## ⚡ Energiewende")
    st.caption("German day-ahead electricity market")

    first_day, last_day = everything["date"].min(), everything["date"].max()
    period = st.radio("Period", ["Last 30 days", "Last 90 days", "Last 12 months", "All data", "Custom"],
                      index=1)
    if period == "Custom":
        picked = st.date_input("From / to", (last_day - timedelta(days=90), last_day),
                               min_value=first_day, max_value=last_day)
        start, end = picked if len(picked) == 2 else (first_day, last_day)
    elif period == "All data":
        start, end = first_day, last_day
    else:
        days_back = {"Last 30 days": 30, "Last 90 days": 90, "Last 12 months": 365}[period]
        start, end = max(first_day, last_day - timedelta(days=days_back - 1)), last_day

    st.divider()
    if last_run is not None:
        updated = str(last_run["finished"] or last_run["started"])[:16]
        st.markdown(f"**Last update**  \n{updated} UTC")
        st.markdown(f"**Pipeline status**  \n`{last_run['status']}`")
    st.markdown(f"**Data range**  \n{first_day:%d %b %Y} – {last_day:%d %b %Y}")
    st.divider()
    st.caption("Data: Bundesnetzagentur | SMARD.de (CC BY 4.0). Not investment advice.")

df = everything[(everything["date"] >= start) & (everything["date"] <= end)]
days = (end - start).days + 1
before = everything[(everything["date"] < start) & (everything["date"] >= start - timedelta(days=days))]

# ---------------------------------------------------------------- header
st.title("Energiewende Market Intelligence")
st.markdown('<p class="subtitle">How wind, solar and demand set German electricity prices, '
            f'{start:%d %b %Y} to {end:%d %b %Y}.</p>', unsafe_allow_html=True)

if last_run is not None and last_run["source"] == "demo":
    st.warning("You're looking at **demo data**. Run `python -m emi.pipeline` to load the real market data.",
               icon="⚠️")
if df["price"].dropna().empty:
    st.error("No price data in this period.")
    st.stop()

tabs = st.tabs(["Overview", "Merit order", "Solar & wind", "Negative prices", "Battery value",
                "Forecast", "Data quality", "Weekly brief"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    k = A.kpis(df)
    k0 = A.kpis(before) if len(before) > 24 * 7 else {}

    def delta(key, unit="", scale=1, decimals=1):
        if key not in k0:
            return None
        return f"{(k[key] - k0[key]) * scale:+.{decimals}f}{unit}"

    c = st.columns(5)
    c[0].metric("Average price", f"€{k['avg_price']:.1f}/MWh", delta("avg_price", " €"), delta_color="inverse")
    c[1].metric("Renewable share", f"{k['renewable_share']:.1%}", delta("renewable_share", " pp", 100))
    c[2].metric("Negative-price hours", f"{k['negative_hours']:,}", delta("negative_hours", decimals=0),
                delta_color="off")
    c[3].metric("Price volatility", f"{k['volatility']:.1f} €", delta("volatility", " €"), delta_color="inverse")
    c[4].metric("Average demand", f"{k['avg_load_gw']:.1f} GW", delta("avg_load_gw", " GW"), delta_color="off")
    if k0:
        st.caption(f"Changes compared with the {days} days before.")

    daily = (df.groupby("date")
             .agg(price=("price", "mean"), ren=("renewables", "sum"), gen=("generation", "sum"))
             .reset_index())
    daily["share"] = daily["ren"] / daily["gen"].where(daily["gen"] > 0)

    chart_title("Price and renewable share per day",
                "On days with a lot of wind and sun, the average price drops.")
    fig = go.Figure()
    fig.add_bar(x=daily["date"], y=daily["share"], name="Renewable share", marker_color="#9ED8C7",
                yaxis="y2", hovertemplate="%{y:.0%}")
    fig.add_scatter(x=daily["date"], y=daily["price"], name="Average price", mode="lines",
                    line=dict(color=RED, width=2.2), hovertemplate="€%{y:.1f}/MWh")
    fig.update_layout(yaxis=dict(title="€/MWh"),
                      yaxis2=dict(overlaying="y", side="right", range=[0, 1], tickformat=".0%",
                                  showgrid=False))
    st.plotly_chart(tidy(fig, 380))

    chart_title("Where the electricity came from", "Generation per week (per day for short periods), in TWh.")
    mix = A.generation_mix(df, "W" if days > 60 else "D")
    fig = go.Figure()
    for name, (cols, color) in MIX.items():
        fig.add_scatter(x=mix.index, y=mix[cols].sum(axis=1, min_count=1), name=name, mode="lines",
                        stackgroup="one", line=dict(width=0.5, color=color), fillcolor=color,
                        hovertemplate="%{y:.2f} TWh")
    fig.update_layout(yaxis_title="TWh")
    st.plotly_chart(tidy(fig, 400))

# ---------------------------------------------------------------- merit order
with tabs[1]:
    mo = A.merit_order(df)
    st.markdown("Power plants are used from cheapest to most expensive. Wind and solar cost almost nothing to "
                "run, so what matters for the price is the **residual load**: the demand that is left for "
                "coal and gas plants after wind and solar. The more of it there is, the more expensive the "
                "last plant that has to run, and the higher the price.")
    if mo is None:
        st.info("Not enough data in this period.")
    else:
        c = st.columns(3)
        c[0].metric("Price increase per extra GW", f"€{mo['slope']:.2f}/MWh")
        c[1].metric("How well the curve fits (R²)", f"{mo['r2']:.2f}")
        c[2].metric("Hours analysed", f"{mo['hours']:,}")

        chart_title("Price vs. residual load", "Each dot is one hour. The line is the median price.")
        dots = df.dropna(subset=["price", "residual_load"])
        dots = dots.sample(min(len(dots), 5000), random_state=1)
        b = mo["bands"]
        fig = go.Figure()
        fig.add_scatter(x=dots["residual_load"] / 1000, y=dots["price"], mode="markers", name="Hours",
                        marker=dict(size=4, color="#94A3B8", opacity=0.35), hoverinfo="skip")
        fig.add_scatter(x=b["gw"], y=b["high"], mode="lines", line=dict(width=0), showlegend=False,
                        hoverinfo="skip")
        fig.add_scatter(x=b["gw"], y=b["low"], mode="lines", line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(185,28,28,0.12)", name="Middle 80% of hours", hoverinfo="skip")
        fig.add_scatter(x=b["gw"], y=b["median"], mode="lines+markers", name="Median price",
                        line=dict(color=RED, width=3), marker=dict(size=5),
                        hovertemplate="%{x:.1f} GW → €%{y:.0f}/MWh<extra></extra>")
        fig.update_layout(xaxis_title="Residual load (GW)", yaxis_title="Price (€/MWh)")
        st.plotly_chart(tidy(fig, 480, hover="closest"))

# ---------------------------------------------------------------- solar & wind
with tabs[2]:
    cr = A.capture_rates(df)
    st.markdown("The **capture rate** is the price solar or wind actually earned, divided by the average price. "
                "All solar panels produce at the same time, so they push the price down exactly when they "
                "sell. That's why solar usually earns less than the average.")
    c = st.columns(3)
    c[0].metric("Solar capture rate", f"{cr['solar_capture_rate'].mean():.0%}")
    c[1].metric("Wind capture rate", f"{cr['wind_capture_rate'].mean():.0%}")
    c[2].metric("Solar earned per MWh", f"€{cr['solar_capture_price'].mean():.1f}")

    chart_title("Capture rate per month", "100% = earned exactly the average price.")
    fig = go.Figure()
    fig.add_hline(y=1, line=dict(color=MUTED, dash="dot", width=1))
    fig.add_scatter(x=cr["month"], y=cr["solar_capture_rate"], name="Solar", mode="lines+markers",
                    line=dict(color="#E0A800", width=3), hovertemplate="%{y:.0%}")
    fig.add_scatter(x=cr["month"], y=cr["wind_capture_rate"], name="Wind", mode="lines+markers",
                    line=dict(color="#3B82C4", width=3), hovertemplate="%{y:.0%}")
    fig.update_layout(yaxis_tickformat=".0%")
    fig.update_xaxes(tickformat="%b %Y")
    st.plotly_chart(tidy(fig, 360))

    left, right = st.columns(2)
    with left:
        chart_title("Average price by hour", "Workdays vs. weekends and holidays.")
        by_hour = A.price_by_hour(df).rename(columns={"workday": "Workday", "weekend_holiday": "Weekend / holiday"})
        fig = go.Figure()
        for col, color in (("Workday", INK), ("Weekend / holiday", TEAL)):
            if col in by_hour:
                fig.add_scatter(x=by_hour["hour"], y=by_hour[col], name=col, mode="lines",
                                line=dict(color=color, width=2.5), hovertemplate="€%{y:.1f}/MWh")
        fig.update_layout(yaxis_title="€/MWh")
        fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h}:00" for h in range(0, 24, 3)])
        st.plotly_chart(tidy(fig, 340))
    with right:
        chart_title("Price by hour and day", "Blue = cheap, red = expensive. Midday dips are the solar effect.")
        grid = df.pivot_table(index="hour", columns="date", values="price", aggfunc="mean")
        fig = px.imshow(grid, aspect="auto", origin="lower", color_continuous_scale="RdYlBu_r",
                        labels=dict(x="", y="Hour", color="€/MWh"))
        fig.update_traces(hovertemplate="%{x}<br>%{y}:00 → €%{z:.0f}/MWh<extra></extra>")
        st.plotly_chart(tidy(fig, 340, legend=False, hover="closest"))

# ---------------------------------------------------------------- negative prices
with tabs[3]:
    neg = A.negative_prices(df)
    if neg["count"] == 0:
        st.info("No hours with negative prices in this period.")
    else:
        st.markdown("When there is far more wind and solar power than people need, prices can drop **below zero**: "
                    "some plants pay to keep producing because stopping costs more.")
        c = st.columns(3)
        c[0].metric("Hours with negative prices", f"{neg['count']:,}")
        c[1].metric("Lowest price", f"€{neg['lowest']:.2f}/MWh")
        c[2].metric("Renewable share in those hours", f"{neg['renewable_share_when_negative']:.0%}",
                    f"{neg['renewable_share_otherwise']:.0%} in all other hours", delta_color="off")

        left, right = st.columns(2)
        with left:
            chart_title("What time of day?")
            fig = go.Figure(go.Bar(x=neg["by_hour"].index, y=neg["by_hour"].values, marker_color=RED,
                                   hovertemplate="%{x}:00 → %{y} hours<extra></extra>"))
            fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h}:00" for h in range(0, 24, 3)])
            st.plotly_chart(tidy(fig, 320, legend=False, hover="closest"))
        with right:
            chart_title("Which months?")
            fig = go.Figure(go.Bar(x=neg["by_month"].index, y=neg["by_month"].values, marker_color=RED,
                                   hovertemplate="%{x|%b %Y} → %{y} hours<extra></extra>"))
            fig.update_xaxes(tickformat="%b %Y")
            st.plotly_chart(tidy(fig, 320, legend=False, hover="closest"))

# ---------------------------------------------------------------- battery
with tabs[4]:
    st.markdown("A battery can charge when power is cheap and sell when it's expensive. This estimates what "
                "a **1 MW battery** could have earned with one full cycle per day.")
    c = st.columns(2)
    hours = c[0].select_slider("Storage size (hours)", options=[1, 2, 4], value=2)
    efficiency = c[1].slider("Round-trip efficiency", 0.70, 0.95, 0.88, step=0.01)
    bv = A.battery_value(df, hours, efficiency)
    if bv.empty:
        st.info("Not enough complete days in this period.")
    else:
        best = bv.loc[bv["revenue"].idxmax()]
        c = st.columns(3)
        c[0].metric("Total revenue", f"€{bv['revenue'].sum():,.0f}")
        c[1].metric("Average per day", f"€{bv['revenue'].mean():,.0f}")
        c[2].metric("Best day", f"€{best['revenue']:,.0f}", f"{best['date']:%d %b %Y}", delta_color="off")

        chart_title("Revenue per day", f"1 MW / {hours} MWh battery, {efficiency:.0%} efficiency.")
        fig = go.Figure(go.Bar(x=bv["date"], y=bv["revenue"], marker_color=TEAL,
                               hovertemplate="%{x|%d %b %Y} → €%{y:,.0f}<extra></extra>"))
        fig.update_layout(yaxis_title="€")
        st.plotly_chart(tidy(fig, 340, legend=False, hover="closest"))
    st.caption("This is a best case: it assumes the prices are known in advance (true for the day-ahead market) "
               "and ignores grid fees, taxes and battery wear.")

# ---------------------------------------------------------------- forecast
with tabs[5]:
    scores = data["scores"]
    if scores.empty:
        st.info("No forecast yet. It needs about four months of data.")
    else:
        s = scores.set_index("model")
        improvement = 1 - s.loc["gradient_boosting", "rmae"]
        st.markdown("Every day at 12:00 the auction sets tomorrow's 24 hourly prices. The model predicts them "
                    "using only what's known before the auction, and is tested week by week on data it has "
                    "never seen.")
        c = st.columns(3)
        c[0].metric("Model's average error", f"€{s.loc['gradient_boosting', 'mae']:.1f}/MWh")
        c[1].metric("'Same as yesterday' error", f"€{s.loc['same_as_yesterday', 'mae']:.1f}/MWh")
        c[2].metric("Improvement", f"{improvement:.0%}", "better" if improvement > 0 else "worse",
                    delta_color="normal" if improvement > 0 else "inverse")

        res = data["results"]
        recent = res[res["ts_utc"] >= res["ts_utc"].max() - pd.Timedelta(days=14)]
        chart_title("Forecast vs. actual price, last 14 days of the test")
        lines = {
            "gradient_boosting": dict(color=TEAL, width=2.2),
            "same_as_yesterday": dict(color="#9CA3AF", width=1.5, dash="dash"),
            "oracle": dict(color=AMBER, width=1.5, dash="dot"),
        }
        show = st.multiselect("Show", list(lines), default=["gradient_boosting", "same_as_yesterday"],
                              format_func=lambda m: MODEL_NAMES[m])
        actual = recent.drop_duplicates("ts_utc").sort_values("ts_utc")
        fig = go.Figure()
        fig.add_scatter(x=actual["ts_utc"], y=actual["actual"], name="Actual price", mode="lines",
                        line=dict(color=INK, width=2.2), hovertemplate="€%{y:.1f}")
        for m in show:
            part = recent[recent["model"] == m].sort_values("ts_utc")
            fig.add_scatter(x=part["ts_utc"], y=part["predicted"], name=MODEL_NAMES[m], mode="lines",
                            line=lines[m], hovertemplate="€%{y:.1f}")
        fig.update_layout(yaxis_title="€/MWh")
        st.plotly_chart(tidy(fig, 420))

        chart_title("All models")
        table = scores.assign(model=scores["model"].map(MODEL_NAMES)).sort_values("mae")
        st.dataframe(
            table[["model", "mae", "rmse", "rmae"]],
            hide_index=True,
            column_config={
                "model": "Model",
                "mae": st.column_config.NumberColumn("Average error (€/MWh)", format="%.1f"),
                "rmse": st.column_config.NumberColumn("RMSE (€/MWh)", format="%.1f"),
                "rmae": st.column_config.NumberColumn("Error vs. 'same as yesterday'", format="%.2f"),
            },
        )
        st.caption("Below 1.00 in the last column means better than just copying yesterday's prices. "
                   "The model with actual weather sees the real wind and solar of the hour it predicts, "
                   "so it isn't a real forecast; it shows how much a weather forecast could help.")

# ---------------------------------------------------------------- data quality
with tabs[6]:
    checks = data["checks"]
    if not checks.empty:
        passed = (checks["status"] == "pass").sum()
        c = st.columns(3)
        c[0].metric("Checks passed", f"{passed} of {len(checks)}")
        c[1].metric("Warnings", int((checks["status"] == "warn").sum()))
        c[2].metric("Rows rejected", f"{len(data['bad_rows']):,}")

        chart_title("Latest checks per series")
        icons = {"pass": "✅ pass", "warn": "⚠️ warn", "fail": "❌ fail"}
        status = checks.pivot(index="series_key", columns="check", values="status").apply(lambda col: col.map(icons))
        status.index = [SERIES[k][1] for k in status.index]
        st.dataframe(status.rename(columns=str.capitalize))

        problems = checks[checks["status"] != "pass"]
        for _, p in problems.iterrows():
            st.markdown(f"- **{SERIES[p['series_key']][1]}**, {p['check']}: {p['detail']}")

    chart_title("Share of hours with data", "For the selected period.")
    complete = df[["price", "load", "residual_load"] + GENERATION].notna().mean().sort_values()
    fig = go.Figure(go.Bar(x=complete.values, y=[SERIES[k][1] for k in complete.index], orientation="h",
                           marker_color=TEAL, hovertemplate="%{x:.1%}<extra></extra>"))
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    st.plotly_chart(tidy(fig, 420, legend=False, hover="closest"))

    with st.expander("Rejected rows"):
        st.caption("Values outside the allowed range. They're kept here but not used anywhere.")
        st.dataframe(data["bad_rows"].rename(columns={"series_key": "series", "ts_utc": "hour (UTC)"}),
                     hide_index=True)
    with st.expander("Pipeline runs"):
        st.dataframe(runs[["run_id", "started", "status", "source", "rows_loaded", "rows_bad", "message"]],
                     hide_index=True)

# ---------------------------------------------------------------- weekly brief
with tabs[7]:
    briefs = data["briefs"]
    if briefs.empty:
        st.info("No weekly brief yet.")
    else:
        text = briefs.iloc[0]["text_md"]
        with st.container(border=True):
            st.markdown(text)
        st.download_button("Download as Markdown", text, file_name="weekly_brief.md")