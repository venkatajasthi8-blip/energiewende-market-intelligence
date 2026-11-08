"""Tests for the SMARD download code, using a fake server so no internet is needed."""
import pandas as pd
import pytest

from emi import smard

HOUR = 3_600_000
WEEKS = [1_700_000_000_000, 1_700_000_000_000 + 168 * HOUR]


class FakeResponse:
    def __init__(self, status, data=None):
        self.status_code = status
        self.data = data

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class FakeServer:
    def __init__(self, fail_first=0):
        self.calls = []
        self.fail_first = fail_first

    def get(self, url, timeout):
        self.calls.append(url)
        if len(self.calls) <= self.fail_first:
            return FakeResponse(503)
        if "/9999/" in url:
            return FakeResponse(404)
        if url.endswith("index_hour.json"):
            return FakeResponse(200, {"timestamps": WEEKS})
        week = int(url.split("_")[-1].replace(".json", ""))
        values = [[week + i * HOUR, float(i)] for i in range(168)]
        values[-1][1] = None  # last hour not published yet
        return FakeResponse(200, {"series": values})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(smard.time, "sleep", lambda s: None)


def test_downloads_from_the_right_week_and_skips_empty_hours():
    server = FakeServer()
    since = pd.Timestamp(WEEKS[0] + 10 * HOUR, unit="ms", tz="UTC")
    df, skipped = smard.fetch_series(4169, since, session=server)
    assert len(server.calls) == 3          # index + 2 weeks
    assert skipped == 2
    assert df["ts_utc"].min() == since
    assert df["ts_utc"].is_monotonic_increasing


def test_retries_when_server_is_busy():
    server = FakeServer(fail_first=2)
    assert smard.get_json(server, "x/index_hour.json") == {"timestamps": WEEKS}
    assert len(server.calls) == 3


def test_gives_up_eventually():
    with pytest.raises(smard.SmardError):
        smard.get_json(FakeServer(fail_first=99), "x/index_hour.json", retries=2)


def test_404_is_not_retried():
    server = FakeServer()
    with pytest.raises(smard.SmardError):
        smard.get_json(server, "/9999/DE/index_hour.json")
    assert len(server.calls) == 1