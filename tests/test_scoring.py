import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from golden_hour.models import DayLight, Forecast, HourlyWeather, TimeRange, Window, WindowWeather
from golden_hour.scoring import (
    candidate_windows,
    pick_windows,
    plan_day,
    score_window,
    weather_for,
)
from golden_hour.weather import parse_forecast

DAY = date(2026, 10, 8)
SUNRISE = datetime(2026, 10, 8, 7, 19)
SUNSET = datetime(2026, 10, 8, 18, 27)


def at(hh: int, mm: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm)


def make_forecast(temp=20.0, rain=0, wind=5.0, uv=1.0, cloud=20, overrides=None) -> Forecast:
    """48 hours of identical weather starting DAY 00:00; `overrides` maps hour index -> fields."""
    hours = []
    for i in range(48):
        fields = dict(temp_c=temp, precip_prob=rain, wind_kmh=wind, uv=uv, cloud_cover=cloud)
        fields.update((overrides or {}).get(i, {}))
        hours.append(HourlyWeather(time=at(0) + timedelta(hours=i), **fields))
    days = [
        DayLight(date=DAY, sunrise=SUNRISE, sunset=SUNSET),
        DayLight(
            date=DAY + timedelta(days=1),
            sunrise=SUNRISE + timedelta(days=1, minutes=2),
            sunset=SUNSET + timedelta(days=1, minutes=-2),
        ),
    ]
    return Forecast(timezone="Europe/Berlin", utc_offset_seconds=7200, hours=hours, days=days)


def free(*ranges: str) -> list[TimeRange]:
    return [TimeRange(start=r.split("-")[0], end=r.split("-")[1]) for r in ranges]


def W(**kw) -> WindowWeather:
    base = {"temp_c": 20, "precip_prob": 0, "wind_kmh": 5, "uv": 1, "cloud_cover": 20}
    return WindowWeather(**(base | kw))


# weather_for


def test_weather_for_takes_worst_case_across_overlapped_hours():
    fc = make_forecast(
        overrides={
            13: {"temp_c": 16.6, "precip_prob": 58, "wind_kmh": 8.7, "uv": 0.75},
            14: {"temp_c": 17.4, "precip_prob": 60, "wind_kmh": 14.8, "uv": 0.25},
        }
    )
    w = weather_for(fc, at(13, 30), at(14, 10))
    assert w.precip_prob == 60
    assert w.wind_kmh == 14.8
    assert w.uv == 0.75
    assert w.temp_c == 16.6  # furthest from 19.5


def test_weather_for_window_inside_one_hour_ignores_next_hour():
    fc = make_forecast(overrides={14: {"precip_prob": 90}})
    assert weather_for(fc, at(13, 0), at(13, 40)).precip_prob == 0
    assert weather_for(fc, at(13, 30), at(14, 0)).precip_prob == 0  # end is exclusive


def test_weather_for_outside_forecast_raises():
    with pytest.raises(ValueError):
        weather_for(make_forecast(), at(10, day=DAY + timedelta(days=5)), at(11))


# score_window


NOON = (at(13), at(13, 40))
GOLDEN = (at(18), at(18, 40))


@pytest.mark.parametrize(
    "weather,window,expected",
    [
        (W(temp_c=13.1, precip_prob=45, wind_kmh=19.2, uv=0.05), NOON, 58),
        (W(temp_c=13.1, precip_prob=45, wind_kmh=19.2, uv=0.05), GOLDEN, 73),
        (W(temp_c=20, precip_prob=5, wind_kmh=8, uv=3), NOON, 96),
        (W(temp_c=9, precip_prob=90, wind_kmh=45), NOON, 0),  # clamped from -25
        (W(temp_c=20, precip_prob=0), GOLDEN, 100),  # clamped from 115
        (W(temp_c=26, precip_prob=0, uv=9), NOON, 79),
    ],
)
def test_score_window(weather, window, expected):
    score, _ = score_window(weather, *window, SUNSET)
    assert score == expected
    assert isinstance(score, int)


def test_score_reasons_ordered_by_effect_and_capped():
    _, reasons = score_window(W(temp_c=9, precip_prob=90, wind_kmh=45, uv=8), *GOLDEN, SUNSET)
    assert reasons == ["rain likely (90%)", "windy (45 km/h)", "chilly (9°C)"]


def test_score_reasons_positive_on_a_nice_day():
    _, reasons = score_window(W(precip_prob=5), *NOON, SUNSET)
    assert reasons == ["dry (5% rain)", "comfortable 20°C"]


@pytest.mark.parametrize(
    "start,end,bonus",
    [
        (at(18), at(18, 40), True),
        (at(17), at(17, 40), True),
        (at(17), at(17, 27), False),  # ends exactly as golden hour starts
        (at(18, 27), at(18, 42), False),  # starts at sunset
    ],
)
def test_golden_hour_boundaries(start, end, bonus):
    _, reasons = score_window(W(), start, end, SUNSET)
    assert ("golden hour" in reasons) is bonus


# candidate_windows


def test_candidates_in_evening_range_respect_sunset_cutoff():
    wins = candidate_windows(free("17:30-19:00"), make_forecast(), DAY, now=at(12, 5))
    spans = [(w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) for w in wins]
    assert spans == [
        ("17:30", "18:10"),
        ("17:45", "18:25"),
        ("18:00", "18:40"),
        ("18:15", "18:42"),  # sunset 18:27 + 15 min
    ]
    assert all(w.day == "today" for w in wins)


def test_candidates_start_on_quarter_hour_after_now():
    wins = candidate_windows(free("12:00-13:30"), make_forecast(), DAY, now=at(12, 5))
    assert wins[0].start == at(12, 15)
    assert all(w.start.minute % 15 == 0 for w in wins)
    assert wins[-1].end == at(13, 30)
    assert all(20 <= w.duration_min <= 40 for w in wins)


def test_candidates_unaligned_range_start_is_rounded_up():
    wins = candidate_windows(free("12:10-13:00"), make_forecast(), DAY, now=at(8))
    assert wins[0].start == at(12, 15)


def test_candidates_skip_short_ranges_and_night():
    fc = make_forecast()
    assert candidate_windows(free("12:00-12:19"), fc, DAY, now=at(8)) == []
    assert candidate_windows(free("05:00-07:40"), fc, DAY, now=at(4)) == []  # before sunrise
    assert candidate_windows(free("19:00-21:00"), fc, DAY, now=at(8)) == []  # after sunset


def test_candidates_for_tomorrow_are_labelled():
    tomorrow = DAY + timedelta(days=1)
    wins = candidate_windows(free("10:00-11:00"), make_forecast(), tomorrow, now=at(22))
    assert wins and all(w.day == "tomorrow" for w in wins)


# pick_windows


def win(start: datetime, minutes: int, score: int) -> Window:
    return Window(
        start=start,
        end=start + timedelta(minutes=minutes),
        duration_min=minutes,
        day="today",
        score=score,
        reasons=[],
        weather=W(),
    )


def test_pick_windows_best_first_without_overlap():
    cands = [win(at(13), 40, 54), win(at(18), 40, 73), win(at(18, 15), 27, 70), win(at(15), 40, 60)]
    assert [w.score for w in pick_windows(cands)] == [73, 60, 54]


def test_pick_windows_tie_prefers_earlier_and_respects_k():
    cands = [win(at(15), 30, 80), win(at(10), 30, 80), win(at(12), 30, 80)]
    picks = pick_windows(cands, k=2)
    assert [p.start for p in picks] == [at(10), at(12)]


def test_pick_windows_tie_prefers_golden_hour():
    golden = win(at(18), 40, 100).model_copy(update={"reasons": ["golden hour"]})
    picks = pick_windows([win(at(12), 40, 100), golden], k=1)
    assert picks == [golden]


def test_pick_windows_adjacent_windows_do_not_overlap():
    picks = pick_windows([win(at(13), 30, 90), win(at(13, 30), 30, 80)])
    assert len(picks) == 2


# plan_day


def test_plan_day_prefers_golden_hour_on_uniform_day():
    plan = plan_day([], make_forecast(), now=at(12, 5))
    assert plan.best.start == at(17)  # earliest window overlapping golden hour (17:27)
    assert plan.best.score == 100
    assert len(plan.alternates) == 2
    assert plan.note is None
    assert plan.sunset == SUNSET


def test_plan_day_empty_free_means_now_until_sunset():
    plan = plan_day([], make_forecast(), now=at(16, 50))
    assert plan.best is not None
    assert all(at(17) <= w.start for w in [plan.best, *plan.alternates])
    assert all(w.end <= SUNSET for w in [plan.best, *plan.alternates])


def test_plan_day_avoids_rainy_hours():
    rainy = {h: {"precip_prob": 90} for h in range(13, 19)}
    plan = plan_day(free("11:00-18:00"), make_forecast(overrides=rainy), now=at(10))
    assert plan.best.end <= at(13)


def test_plan_day_falls_back_to_tomorrow_late_at_night():
    plan = plan_day([], make_forecast(), now=at(21, 30))
    assert plan.best.day == "tomorrow"
    assert plan.best.start.date() == DAY + timedelta(days=1)
    assert plan.note and "tomorrow" in plan.note
    assert plan.sunset.date() == DAY + timedelta(days=1)


def test_plan_day_falls_back_when_free_ranges_already_passed():
    plan = plan_day(free("09:00-10:00"), make_forecast(), now=at(15))
    assert plan.best.day == "tomorrow"


def test_plan_day_with_real_berlin_forecast():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "openmeteo_forecast_berlin.json").read_text("utf-8")
    )
    plan = plan_day(free("13:00-15:00", "17:30-19:00"), parse_forecast(data), now=at(12, 5))
    assert plan.best.start == at(18)
    assert plan.best.score == 73
    assert "golden hour" in plan.best.reasons
