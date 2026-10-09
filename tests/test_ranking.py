import json
from datetime import datetime, timedelta
from pathlib import Path

from golden_hour.hobbies import CATEGORIES
from golden_hour.models import Spot, Window, WindowWeather
from golden_hour.places import parse_elements, radius_for, within_walk
from golden_hour.ranking import rank_places, score_spot


def window(rain=0, temp=20.0, golden=False, minutes=40) -> Window:
    start = datetime(2026, 10, 9, 17, 30)
    return Window(
        start=start,
        end=start + timedelta(minutes=minutes),
        duration_min=minutes,
        day="today",
        score=80,
        reasons=["golden hour"] if golden else ["dry (0% rain)"],
        weather=WindowWeather(temp_c=temp, precip_prob=rain, wind_kmh=5, uv=1, cloud_cover=20),
    )


def spot(name, category, walk=5, facts=()) -> Spot:
    return Spot(
        id=f"node/{abs(hash(name)) % 10_000}",
        name=name,
        category=category,
        kind=category,
        lat=0,
        lon=0,
        walk_min=walk,
        covered=CATEGORIES[category].covered,
        facts=list(facts),
        osm_url="https://www.openstreetmap.org/node/1",
    )


MIX = [
    spot("Park A", "park", 3),
    spot("Park B", "park", 4),
    spot("Park C", "park", 5),
    spot("Lookout", "view", 9),
    spot("Canal", "water", 6),
    spot("Museum", "museum", 4),
    spot("Library", "library", 2),
    spot("Statue", "art", 5),
    spot("Memorial", "history", 7),
]


def names(spots):
    return [s.name for s in spots]


def test_hobby_first_category_wins():
    top = rank_places(MIX, ["history"], window())
    assert top[0].name == "Memorial"  # history's first category, despite a 7-min walk
    assert "Museum" in names(top[:2])


def test_no_hobbies_prefers_short_walks():
    assert names(rank_places(MIX, [], window()))[:3] == ["Library", "Park A", "Museum"]


def test_rain_puts_covered_places_first():
    top = rank_places(MIX, ["nature"], window(rain=70))
    assert {top[0].category, top[1].category} <= {"museum", "library", "cafe"}


def test_golden_hour_lifts_open_air_places():
    plain = score_spot(MIX[3], ["photography"], window())
    golden = score_spot(MIX[3], ["photography"], window(golden=True))
    assert golden == plain + 2


def test_heat_lifts_parks_and_water():
    assert score_spot(MIX[4], [], window(temp=33)) == score_spot(MIX[4], [], window()) + 1


def test_facts_bonus():
    plain, with_facts = spot("A", "art", 5), spot("B", "art", 5, facts=["artist name: X"])
    assert score_spot(with_facts, [], window()) == score_spot(plain, [], window()) + 0.5


def test_at_most_two_per_category_and_five_total():
    top = rank_places(MIX, ["nature"], window())
    assert len(top) == 5
    assert names(top).count("Park C") == 0
    assert sum(s.category == "park" for s in top) == 2


def test_tie_breaks_on_walk_then_name():
    a, b, c = spot("Bravo", "art", 4), spot("Alpha", "art", 4), spot("Zed", "art", 3)
    assert names(rank_places([a, b, c, spot("x", "park", 9)], ["art"], window()))[:2] == [
        "Zed",
        "Alpha",
    ]


def test_fewer_than_three_means_fallback():
    assert (
        rank_places(
            [spot("Park A", "park"), spot("Park B", "park"), spot("Park C", "park")], [], window()
        )
        == []
    )
    assert rank_places(MIX[:2], [], window()) == []


def test_real_pune_data_for_photography_at_golden_hour():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "overpass_pune.json").read_text("utf-8")
    )
    near = within_walk(
        parse_elements(data["elements"], list(CATEGORIES)), 18.5204, 73.8567, radius_for(40)
    )
    top = rank_places(near, ["photography", "history"], window(golden=True))
    assert len(top) == 5
    assert all(s.walk_min <= 14 for s in top)
    assert len({s.name for s in top}) == 5
