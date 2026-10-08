from datetime import datetime

from conftest import make_ctx

from golden_hour.prompts import build_messages, time_of_day


def test_messages_contain_window_weather_and_constraints(ctx):
    system, user = build_messages(ctx)
    assert system["role"] == "system" and user["role"] == "user"
    assert "Walking distance only" in system["content"]
    assert "nothing to buy" in system["content"]
    assert "1 to 3" in system["content"]
    text = user["content"]
    assert "Never name a real street" in system["content"]
    for fact in ["18:00–18:40", "40 minutes", "evening", "18°C", "10% chance of rain", "Berlin"]:
        assert fact in text, fact
    assert "golden hour" in text


def test_no_golden_hour_or_place_when_absent():
    ctx = make_ctx(start=datetime(2026, 10, 8, 9, 15), reasons=["dry (0% rain)"], place=None)
    text = build_messages(ctx)[1]["content"]
    assert "golden hour" not in text
    assert "Region" not in text
    assert "morning" in text


def test_time_of_day():
    assert [time_of_day(h) for h in (7, 12, 15, 19)] == [
        "morning",
        "midday",
        "afternoon",
        "evening",
    ]


def test_rain_is_called_out():
    text = build_messages(make_ctx(rain=70))[1]["content"]
    assert "Rain is likely" in text
    assert "Rain is likely" not in build_messages(make_ctx(rain=20))[1]["content"]
