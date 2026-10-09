from datetime import datetime, timedelta

from conftest import make_ctx

from golden_hour.fallbacks import FALLBACKS, pick_fallback


def test_enough_curated_activities():
    assert len(FALLBACKS) >= 8
    assert all(f.suggestion.source == "fallback" for f in FALLBACKS)


def test_rain_picks_rain_friendly_activity():
    s = pick_fallback(make_ctx(rain=80))
    match = next(f for f in FALLBACKS if f.suggestion is s)
    assert match.ok_in_rain


def test_golden_hour_picks_golden_activity():
    s = pick_fallback(make_ctx(rain=0, reasons=["golden hour"]))
    assert next(f for f in FALLBACKS if f.suggestion is s).golden_hour


def test_short_window_never_gets_long_activity():
    for d in range(10):
        ctx = make_ctx(start=datetime(2026, 10, 8, 12) + timedelta(days=d), minutes=20, reasons=[])
        s = pick_fallback(ctx)
        assert next(f for f in FALLBACKS if f.suggestion is s).min_duration <= 20


def test_deterministic():
    assert pick_fallback(make_ctx()) is pick_fallback(make_ctx())
