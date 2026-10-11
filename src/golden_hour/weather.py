"""Open-Meteo client (keyless, open data). https://open-meteo.com/en/docs"""

from datetime import date, datetime

import httpx

from golden_hour.models import DayLight, Forecast, HourlyWeather, Place

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
HOURLY_VARS = "temperature_2m,precipitation_probability,wind_speed_10m,uv_index,cloud_cover"


class WeatherError(Exception):
    """Upstream weather/geocoding failure."""


class WeatherClient:
    def __init__(self, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=10)

    def fetch_forecast(self, lat: float, lon: float) -> Forecast:
        data = self._get(
            FORECAST_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": HOURLY_VARS,
                "daily": "sunrise,sunset",
                "timezone": "auto",
                "forecast_days": 2,
            },
        )
        try:
            return parse_forecast(data)
        except (KeyError, TypeError, ValueError) as e:
            raise WeatherError(f"unexpected forecast payload: {e}") from e

    def geocode(self, q: str, limit: int = 5) -> list[Place]:
        # Ask for extra rows: Open-Meteo sometimes repeats a place, and duplicates are dropped
        # (R1.4).
        params = {"name": q, "count": limit * 2, "language": "en", "format": "json"}
        data = self._get(GEOCODE_URL, params)
        places: dict[tuple, Place] = {}
        for r in data.get("results", []):
            place = Place(
                name=r["name"],
                admin1=r.get("admin1"),
                country=r.get("country"),
                lat=r["latitude"],
                lon=r["longitude"],
            )
            places.setdefault((place.name, place.admin1, place.country), place)
        return list(places.values())[:limit]

    def _get(self, url: str, params: dict) -> dict:
        try:
            resp = self._http.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise WeatherError(str(e)) from e


def parse_forecast(data: dict) -> Forecast:
    h = data["hourly"]
    hours = [
        HourlyWeather(
            time=datetime.fromisoformat(t),
            temp_c=temp,
            # Open-Meteo returns null for some variables at the far end of the range.
            precip_prob=precip or 0,
            wind_kmh=wind or 0,
            uv=uv or 0,
            cloud_cover=cloud or 0,
        )
        for t, temp, precip, wind, uv, cloud in zip(
            h["time"],
            h["temperature_2m"],
            h["precipitation_probability"],
            h["wind_speed_10m"],
            h["uv_index"],
            h["cloud_cover"],
            strict=True,
        )
        if temp is not None
    ]
    d = data["daily"]
    days = [
        DayLight(
            date=date.fromisoformat(day),
            sunrise=datetime.fromisoformat(rise),
            sunset=datetime.fromisoformat(set_),
        )
        for day, rise, set_ in zip(d["time"], d["sunrise"], d["sunset"], strict=True)
    ]
    return Forecast(
        timezone=data["timezone"],
        utc_offset_seconds=data["utc_offset_seconds"],
        hours=hours,
        days=days,
    )
