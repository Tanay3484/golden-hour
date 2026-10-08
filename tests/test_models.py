from datetime import datetime, time

import pytest
from pydantic import ValidationError

from golden_hour.models import Suggestion, TimeRange, Window, WindowWeather


def test_time_range_accepts_valid():
    r = TimeRange(start="12:30", end="13:15")
    assert r.start == time(12, 30)


@pytest.mark.parametrize("start,end", [("13:00", "12:00"), ("12:00", "12:00")])
def test_time_range_rejects_end_not_after_start(start, end):
    with pytest.raises(ValidationError):
        TimeRange(start=start, end=end)


def test_suggestion_limits():
    with pytest.raises(ValidationError):
        Suggestion(title="x", steps=["a", "b", "c", "d"], what_to_notice="y")
    with pytest.raises(ValidationError):
        Suggestion(title="x" * 61, steps=["a"], what_to_notice="y")
    assert Suggestion(title="x", steps=["a"], what_to_notice="y").source == "model"


def test_window_roundtrip():
    w = Window(
        start=datetime(2026, 10, 8, 17, 30),
        end=datetime(2026, 10, 8, 18, 10),
        duration_min=40,
        day="today",
        score=88,
        reasons=["golden hour"],
        weather=WindowWeather(temp_c=18, precip_prob=5, wind_kmh=10, uv=1, cloud_cover=20),
    )
    assert Window.model_validate_json(w.model_dump_json()) == w
