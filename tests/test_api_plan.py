import json
from datetime import UTC, datetime, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golden_hour.main import app, get_clock, get_planner, get_weather
from golden_hour.models import Place, Plan
from golden_hour.weather import WeatherError, parse_forecast

FIXTURES = Path(__file__).parent / "fixtures"
FORECAST = parse_forecast(
    json.loads((FIXTURES / "openmeteo_forecast_berlin.json").read_text(encoding="utf-8"))
)
FROZEN_UTC = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)  # 12:00 in Berlin (UTC+2)


class FakeWeather:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    def fetch_forecast(self, lat, lon):
        self.calls.append((lat, lon))
        if self.fail:
            raise WeatherError("down")
        return FORECAST

    def geocode(self, q):
        if self.fail:
            raise WeatherError("down")
        return [Place(name="Berlin", country="Germany", lat=52.52, lon=13.41)]


class FakePlanner:
    def __init__(self):
        self.args = None

    def __call__(self, free, forecast, now):
        self.args = (free, forecast, now)
        day = forecast.days[0]
        return Plan(timezone=forecast.timezone, sunrise=day.sunrise, sunset=day.sunset, best=None)


@pytest.fixture
def deps():
    weather, planner = FakeWeather(), FakePlanner()
    app.dependency_overrides[get_weather] = lambda: weather
    app.dependency_overrides[get_planner] = lambda: planner
    app.dependency_overrides[get_clock] = lambda: (lambda: FROZEN_UTC)
    yield weather, planner
    app.dependency_overrides.clear()


client = TestClient(app)


def test_plan_passes_local_now_and_ranges_to_planner(deps):
    weather, planner = deps
    resp = client.post(
        "/api/plan",
        json={"lat": 52.52, "lon": 13.41, "free_ranges": [{"start": "12:30", "end": "13:15"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Europe/Berlin"
    assert weather.calls == [(52.52, 13.41)]
    free, forecast, now = planner.args
    assert now == datetime(2026, 10, 8, 12, 0)
    assert now.tzinfo is None
    assert free[0].start == time(12, 30)
    assert forecast is FORECAST


def test_plan_free_ranges_default_empty(deps):
    _, planner = deps
    assert client.post("/api/plan", json={"lat": 1, "lon": 2}).status_code == 200
    assert planner.args[0] == []


@pytest.mark.parametrize(
    "body",
    [
        {"lat": 91, "lon": 0},
        {"lat": 0, "lon": 181},
        {"lat": 0, "lon": 0, "free_ranges": [{"start": "13:00", "end": "12:00"}]},
    ],
)
def test_plan_rejects_invalid_input(deps, body):
    assert client.post("/api/plan", json=body).status_code == 422


def test_plan_weather_failure_is_502(deps):
    deps[0].fail = True
    resp = client.post("/api/plan", json={"lat": 0, "lon": 0})
    assert resp.status_code == 502
    assert resp.json() == {"detail": "weather unavailable"}


def test_geocode(deps):
    resp = client.get("/api/geocode", params={"q": "Berlin"})
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Berlin"


def test_geocode_validation_and_failure(deps):
    assert client.get("/api/geocode", params={"q": "B"}).status_code == 422
    deps[0].fail = True
    assert client.get("/api/geocode", params={"q": "Berlin"}).status_code == 502
