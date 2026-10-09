from datetime import datetime

import pytest

from golden_hour.models import SuggestionContext, Window, WindowWeather


def make_ctx(
    start=datetime(2026, 10, 8, 18, 0),
    minutes=40,
    rain=10,
    reasons=("golden hour", "dry (10% rain)"),
    place="Berlin",
) -> SuggestionContext:
    from datetime import timedelta

    return SuggestionContext(
        window=Window(
            start=start,
            end=start + timedelta(minutes=minutes),
            duration_min=minutes,
            day="today",
            score=90,
            reasons=list(reasons),
            weather=WindowWeather(temp_c=17.6, precip_prob=rain, wind_kmh=12, uv=1, cloud_cover=40),
        ),
        place_name=place,
    )


@pytest.fixture
def ctx() -> SuggestionContext:
    return make_ctx()
