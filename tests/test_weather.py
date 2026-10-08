import json
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from golden_hour.weather import WeatherClient, WeatherError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def client_returning(payload=None, status=200, seen=None) -> WeatherClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return WeatherClient(httpx.Client(transport=httpx.MockTransport(handler)))


def test_fetch_forecast_parses_fixture():
    seen = []
    fc = client_returning(load("openmeteo_forecast_berlin.json"), seen=seen).fetch_forecast(
        52.52, 13.41
    )

    assert fc.timezone == "Europe/Berlin"
    assert fc.utc_offset_seconds == 7200
    assert len(fc.hours) == 48
    assert fc.hours[0].time == datetime(2026, 10, 8, 0, 0)
    assert fc.hours[0].temp_c == 13.7
    assert [d.date for d in fc.days] == [date(2026, 10, 8), date(2026, 10, 9)]
    assert fc.days[0].sunset == datetime(2026, 10, 8, 18, 27)

    params = seen[0].url.params
    assert params["timezone"] == "auto"
    assert params["forecast_days"] == "2"


def test_fetch_forecast_tolerates_nulls():
    data = load("openmeteo_forecast_berlin.json")
    data["hourly"]["precipitation_probability"][-1] = None
    data["hourly"]["uv_index"][-1] = None
    fc = client_returning(data).fetch_forecast(52.52, 13.41)
    assert fc.hours[-1].precip_prob == 0
    assert fc.hours[-1].uv == 0


def test_geocode_parses_fixture():
    places = client_returning(load("openmeteo_geocode_berlin.json")).geocode("Berlin")
    assert 1 <= len(places) <= 5
    assert places[0].name == "Berlin"
    assert places[0].country == "Germany"
    assert places[0].lat == pytest.approx(52.52, abs=0.01)


def test_geocode_no_results():
    assert client_returning({"generationtime_ms": 0.1}).geocode("zzzz") == []


@pytest.mark.parametrize("status", [429, 500])
def test_upstream_errors_raise_weather_error(status):
    with pytest.raises(WeatherError):
        client_returning({"error": True}, status=status).fetch_forecast(0, 0)


def test_malformed_payload_raises_weather_error():
    with pytest.raises(WeatherError):
        client_returning({"timezone": "UTC"}).fetch_forecast(0, 0)
