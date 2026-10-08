"""Curated activities used when the model is unreachable or returns junk (R4.4)."""

from dataclasses import dataclass

from golden_hour.models import Suggestion, SuggestionContext

RAINY_PERCENT = 50


@dataclass(frozen=True)
class Fallback:
    suggestion: Suggestion
    min_duration: int = 20
    ok_in_rain: bool = False
    golden_hour: bool = False


def _s(title: str, steps: list[str], notice: str, bring: list[str] | None = None) -> Suggestion:
    return Suggestion(
        title=title, steps=steps, what_to_notice=notice, bring=bring or [], source="fallback"
    )


FALLBACKS: list[Fallback] = [
    Fallback(
        _s(
            "Chase the last light",
            [
                "Walk west, toward the sunset, for 10 minutes.",
                "Find a spot where you can see the sky.",
                "Stay until the light changes colour, then walk back.",
            ],
            "How long your shadow gets, and which buildings catch the light last.",
            ["phone (camera only)"],
        ),
        golden_hour=True,
    ),
    Fallback(
        _s(
            "Golden-hour photo walk",
            [
                "Walk any loop near home.",
                "Take exactly five photos of things lit by the low sun.",
                "Pick your favourite on the way back.",
            ],
            "Backlit leaves and grass glowing at the edges.",
            ["phone"],
        ),
        golden_hour=True,
    ),
    Fallback(
        _s(
            "Rain sounds under cover",
            [
                "Walk to the nearest covered spot: a bus shelter, porch or awning.",
                "Stand for five minutes and just listen.",
                "Take the long way home.",
            ],
            "How rain sounds different on metal, leaves and pavement.",
            ["umbrella", "jacket"],
        ),
        ok_in_rain=True,
    ),
    Fallback(
        _s(
            "Puddle-reflection hunt",
            [
                "Walk your street and the next one over.",
                "Find three puddles with a clear reflection of something above.",
            ],
            "The smell of wet earth (petrichor) right after the rain eases.",
            ["umbrella"],
        ),
        ok_in_rain=True,
    ),
    Fallback(
        _s(
            "Three-colour leaf hunt",
            [
                "Walk to the nearest street with trees.",
                "Find leaves in three different colours.",
                "Line them up on a bench and take one photo.",
            ],
            "Which trees change colour first, and which stay green.",
        ),
    ),
    Fallback(
        _s(
            "Ten-minute sit spot",
            [
                "Walk to the nearest patch of green, even a small one.",
                "Sit for ten minutes without your phone.",
                "Count how many different birds you hear.",
            ],
            "Birds call more when you stop moving for a few minutes.",
            ["something to sit on"],
        ),
    ),
    Fallback(
        _s(
            "Walk a street you've never walked",
            [
                "Pick a turn you never take, within ten minutes of home.",
                "Walk it to the end and come back a different way.",
            ],
            "One building, garden or door you'd never noticed before.",
        ),
        min_duration=30,
    ),
    Fallback(
        _s(
            "Cloud-shape break",
            [
                "Step outside and find a spot with open sky.",
                "Watch the clouds for five minutes and name two shapes.",
            ],
            "How fast the clouds move compared with the wind at ground level.",
        ),
    ),
    Fallback(
        _s(
            "Loop the block, slowly",
            [
                "Walk around your block at half your normal speed.",
                "Stop once for anything that's alive and growing.",
            ],
            "Plants growing in cracks in the pavement.",
        ),
    ),
]


def pick_fallback(ctx: SuggestionContext) -> Suggestion:
    """Deterministic best match: fits the duration, suits the rain, prefers golden hour."""
    w = ctx.window
    rainy = w.weather.precip_prob >= RAINY_PERCENT
    golden = "golden hour" in w.reasons

    fits = [
        f for f in FALLBACKS if f.min_duration <= w.duration_min and (f.ok_in_rain or not rainy)
    ]
    if rainy:
        preferred = [f for f in fits if f.ok_in_rain]
    elif golden:
        preferred = [f for f in fits if f.golden_hour]
    else:
        preferred = [f for f in fits if not f.ok_in_rain and not f.golden_hour]
    pool = preferred or fits or FALLBACKS
    # Vary by day so it isn't the same suggestion every time, but stay deterministic.
    return pool[w.start.toordinal() % len(pool)].suggestion
