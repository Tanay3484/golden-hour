"""Picks the best outdoor windows from a forecast.

Owned by @human. See specs/001-golden-hour-mvp/design.md §4.2.
"""

from datetime import date, datetime

from golden_hour.models import Forecast, Plan, TimeRange, Window, WindowWeather


def weather_for(forecast: Forecast, start: datetime, end: datetime) -> WindowWeather:
    """Worst-case weather across the forecast hours that [start, end) overlaps."""
    raise NotImplementedError("T3 @human")


def score_window(
    w: WindowWeather, start: datetime, end: datetime, sunset: datetime
) -> tuple[int, list[str]]:
    """Score 0-100 and up to 3 short reasons, most important first."""
    raise NotImplementedError("T3 @human")


def candidate_windows(
    free: list[TimeRange], forecast: Forecast, day: date, now: datetime
) -> list[Window]:
    """All quarter-hour-aligned 20-40 min windows inside the free ranges and daylight on `day`."""
    raise NotImplementedError("T3 @human")


def pick_windows(candidates: list[Window], k: int = 3) -> list[Window]:
    """Up to k non-overlapping windows, best score first (ties: earlier start)."""
    raise NotImplementedError("T3 @human")


def plan_day(free: list[TimeRange], forecast: Forecast, now: datetime) -> Plan:
    """Best window + alternates for today, falling back to tomorrow (R2.2, R2.3)."""
    raise NotImplementedError("T3 @human")
