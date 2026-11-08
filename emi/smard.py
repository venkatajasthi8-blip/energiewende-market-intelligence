"""Download data from the SMARD API (Bundesnetzagentur, public, no API key).

SMARD splits every series into weekly files. First you ask for the list of
weekly files (index), then you download the ones you need.
"""
import logging
import time

import pandas as pd
import requests

log = logging.getLogger(__name__)

BASE = "https://www.smard.de/app/chart_data"


class SmardError(Exception):
    pass


def get_json(session, url, retries=4):
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 404:
                raise SmardError(f"not found: {url}")
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"server returned {r.status_code}")
            r.raise_for_status()
            time.sleep(0.15)  # be nice to a free public API
            return r.json()
        except SmardError:
            raise
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if attempt == retries:
                raise SmardError(f"giving up on {url}: {e}") from e
            wait = 1.5 * 2**attempt
            log.warning("request failed (%s), retrying in %.0fs", e, wait)
            time.sleep(wait)


def fetch_series(filter_id, since, session=None):
    """Return (dataframe with ts_utc + value, number of empty values skipped)."""
    session = session or requests.Session()
    index = get_json(session, f"{BASE}/{filter_id}/DE/index_hour.json")
    weeks = sorted(index["timestamps"])

    # start from the week that contains `since`
    since_ms = since.timestamp() * 1000
    first = max(0, len([w for w in weeks if w <= since_ms]) - 1)

    frames, skipped = [], 0
    for week in weeks[first:]:
        url = f"{BASE}/{filter_id}/DE/{filter_id}_DE_hour_{week}.json"
        df = pd.DataFrame(get_json(session, url)["series"], columns=["ts", "value"])
        # SMARD sends null for hours that are not published yet
        skipped += int(df["value"].isna().sum())
        frames.append(df.dropna())

    if not frames:
        return pd.DataFrame(columns=["ts_utc", "value"]), 0

    df = pd.concat(frames)
    df["ts_utc"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[df["ts_utc"] >= since].drop_duplicates("ts_utc").sort_values("ts_utc")
    return df[["ts_utc", "value"]].reset_index(drop=True), skipped