"""Picks the top places for a window (spec 002, design §4.3). Pure and deterministic.

Code ranks, the model only describes: in the spike, Gemma's "ranking" was just list order.
"""

from golden_hour.hobbies import HOBBIES
from golden_hour.models import Hobby, Spot, Window

RAINY_PERCENT = 50
HOT_C = 28
MAX_PER_CATEGORY = 2
MIN_PLACES = 3
OPEN_AIR_AT_GOLDEN_HOUR = {"view", "water", "park"}
COOL_WHEN_HOT = {"park", "water"}


def score_spot(spot: Spot, hobbies: list[Hobby], window: Window) -> float:
    score = 0.0

    if not hobbies:
        score += 1
    elif any(HOBBIES[h][0] == spot.category for h in hobbies):
        score += 3
    elif any(spot.category in HOBBIES[h] for h in hobbies):
        score += 2

    score -= 0.25 * spot.walk_min

    w = window.weather
    if w.precip_prob >= RAINY_PERCENT:
        score += 3 if spot.covered else -2
    if "golden hour" in window.reasons and spot.category in OPEN_AIR_AT_GOLDEN_HOUR:
        score += 2
    if w.temp_c > HOT_C and spot.category in COOL_WHEN_HOT:
        score += 1

    if spot.facts:
        score += 0.5  # gives the model something real to say
    return score


def rank_places(spots: list[Spot], hobbies: list[Hobby], window: Window, k: int = 5) -> list[Spot]:
    """Top `k` with at most 2 per category; [] if fewer than 3 qualify (→ 001 fallback, R10.1)."""
    ranked = sorted(spots, key=lambda s: (-score_spot(s, hobbies, window), s.walk_min, s.name))
    picked: list[Spot] = []
    per_category: dict[str, int] = {}
    for s in ranked:
        if per_category.get(s.category, 0) < MAX_PER_CATEGORY:
            picked.append(s)
            per_category[s.category] = per_category.get(s.category, 0) + 1
            if len(picked) == k:
                break
    return picked if len(picked) >= MIN_PLACES else []
