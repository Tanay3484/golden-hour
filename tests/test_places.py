import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from golden_hour.hobbies import CATEGORIES
from golden_hour.places import (
    QUERY_RADIUS_M,
    USER_AGENT,
    OverpassClient,
    PlaceCache,
    build_query,
    cell_of,
    haversine_m,
    parse_elements,
    query_for,
    radius_for,
    within_walk,
)

FIXTURES = Path(__file__).parent / "fixtures"
ALL = list(CATEGORIES)
PUNE = (18.5204, 73.8567)
BERLIN = (52.5200, 13.4050)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# pure helpers


def test_radius_is_a_third_of_the_window_each_way():
    assert radius_for(40) == 1067
    assert radius_for(20) == 533
    assert QUERY_RADIUS_M == 1067 + 800


def test_cell_rounds_to_two_decimals():
    assert cell_of(18.5204, 73.8567) == (18.52, 73.86)


def test_haversine_known_distance():
    # Brandenburg Gate -> Alexanderplatz is about 2.5 km
    assert haversine_m(52.5163, 13.3777, 52.5219, 13.4132) == pytest.approx(2470, abs=50)


def test_build_query_uses_cell_centre_and_every_rule():
    q = build_query(18.52, 73.86, ["park", "water"])
    assert q.startswith("[out:json][timeout:25][maxsize:67108864];")
    assert f"around:{QUERY_RADIUS_M},18.52,73.86" in q
    assert q.count("out center tags 40;") == 3  # park: 1 rule, water: 2 rules
    assert '["leisure"~"^(park|garden|nature_reserve|common)$"]["name"]' in q
    assert "18.5204" not in q


# parsing real responses


@pytest.mark.parametrize(
    "fixture,origin,expect_min",
    [("overpass_pune.json", PUNE, 20), ("overpass_berlin.json", BERLIN, 80)],
)
def test_parse_real_fixtures(fixture, origin, expect_min):
    spots = parse_elements(load(fixture)["elements"], ALL)
    near = within_walk(spots, *origin, radius_for(40))
    assert len(near) >= expect_min
    assert all(1 <= s.walk_min <= 14 for s in near)
    assert all(s.osm_url.startswith("https://www.openstreetmap.org/") for s in near)
    assert len({s.id for s in spots}) == len(spots)


def test_dedupe_ignores_spaces_and_case():
    els = [
        {
            "type": "way",
            "id": 1,
            "center": {"lat": 1, "lon": 1},
            "tags": {"name": "Shaniwarwada", "historic": "fort"},
        },
        {
            "type": "node",
            "id": 2,
            "lat": 1,
            "lon": 1,
            "tags": {"name": "Shaniwar Wada", "historic": "fort"},
        },
    ]
    assert len(parse_elements(els, ["history"])) == 1


def test_parse_skips_unnamed_unclassified_and_coordinate_less():
    els = [
        {"type": "node", "id": 1, "lat": 1, "lon": 1, "tags": {"leisure": "park"}},
        {"type": "node", "id": 2, "lat": 1, "lon": 1, "tags": {"name": "Shop", "shop": "bakery"}},
        {"type": "way", "id": 3, "tags": {"name": "No centre", "leisure": "park"}},
        {"type": "node", "id": 4, "lat": 1, "lon": 1, "tags": {"name": "Ok", "leisure": "park"}},
    ]
    assert [s.name for s in parse_elements(els, ["park"])] == ["Ok"]


def test_facts_come_only_from_osm_tags_and_are_capped():
    el = {
        "type": "node",
        "id": 5,
        "lat": 1,
        "lon": 1,
        "tags": {
            "name": "Kesha",
            "tourism": "artwork",
            "artist_name": "Innokenti Baranov",
            "artwork_type": "sculpture",
            "description": "x" * 300,
            "inscription": "hi",
        },
    }
    (spot,) = parse_elements([el], ["art"])
    assert spot.facts[0].startswith("description: ")
    assert len(spot.facts[0]) <= 115
    assert len(spot.facts) == 3


def test_prefers_english_name():
    el = {
        "type": "node",
        "id": 6,
        "lat": 1,
        "lon": 1,
        "tags": {"name": "Fernsehturm", "name:en": "TV Tower", "tourism": "viewpoint"},
    }
    assert parse_elements([el], ["view"])[0].name == "TV Tower"


# client: failover, budget, cache


ONE_PARK = {
    "elements": [
        {
            "type": "node",
            "id": 7,
            "lat": 18.5205,
            "lon": 73.8568,
            "tags": {"name": "Udyan", "leisure": "park"},
        }
    ]
}


def client(handler, **kw) -> OverpassClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})
    return OverpassClient(["https://a.example/api", "https://b.example/api"], http=http, **kw)


def test_failover_to_second_endpoint_and_privacy_of_query():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "a.example":
            return httpx.Response(504)
        return httpx.Response(200, json=ONE_PARK)

    spots = client(handler).nearby(*PUNE, radius_for(40), ["park"])
    assert [s.name for s in spots] == ["Udyan"]
    assert [r.url.host for r in seen] == ["a.example", "b.example"]
    query = parse_qs(seen[1].content.decode())["data"][0]
    assert "18.52,73.86" in query and "18.5204" not in query  # only the cell centre leaves (R10.2)
    assert seen[1].headers["User-Agent"].startswith("golden-hour/")


def test_all_endpoints_down_returns_none_not_empty():
    # None means "unreachable", so the browser can try (R10.5); [] means OSM found nothing.
    assert client(lambda r: httpx.Response(500)).nearby(*PUNE, 1000, ["park"]) is None


def test_budget_stops_trying_more_endpoints():
    t = [0.0]
    calls = []

    def handler(request):
        calls.append(request.url.host)
        t[0] += 24  # first attempt eats almost the whole budget
        return httpx.Response(504)

    assert client(handler, clock=lambda: t[0]).nearby(*PUNE, 1000, ["park"]) is None
    assert calls == ["a.example"]


def test_cache_hit_makes_no_request_and_recomputes_walk_per_user():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=ONE_PARK)

    c = client(handler)
    first = c.nearby(18.5204, 73.8567, 1000, ["park"])
    second = c.nearby(18.5230, 73.8590, 1000, ["park"])  # same cell, different user
    assert len(calls) == 1
    assert first[0].walk_min != second[0].walk_min


def test_empty_answer_is_empty_list():
    c = client(lambda r: httpx.Response(200, json={"elements": []}))
    assert c.nearby(*PUNE, 1000, ["park"]) == []


def test_empty_results_are_not_cached():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"elements": []})

    c = client(handler)
    c.nearby(*PUNE, 1000, ["park"])
    c.nearby(*PUNE, 1000, ["park"])
    assert len(calls) == 2


def test_cache_expires_and_evicts():
    now = [0.0]
    cache = PlaceCache(ttl_s=10, max_entries=2, clock=lambda: now[0])
    cache.put("a", [])
    cache.put("b", [])
    cache.put("c", [])
    assert cache.get("a") is None  # evicted (oldest)
    now[0] = 11
    assert cache.get("c") is None  # expired


@pytest.mark.parametrize(
    "junk",
    [
        "not a dict",
        {"type": "node", "id": "7", "lat": 1, "lon": 1, "tags": {"name": "X", "leisure": "park"}},
        {"type": "bogus", "id": 7, "lat": 1, "lon": 1, "tags": {"name": "X", "leisure": "park"}},
        {"type": "node", "id": 7, "lat": 999, "lon": 1, "tags": {"name": "X", "leisure": "park"}},
        {"type": "node", "id": 7, "lat": True, "lon": 1, "tags": {"name": "X", "leisure": "park"}},
        {"type": "node", "id": 7, "lat": 1, "lon": 1, "tags": ["name", "X"]},
        {"type": "way", "id": 7, "center": "x", "tags": {"name": "X", "leisure": "park"}},
    ],
)
def test_parse_ignores_untrusted_junk(junk):
    assert parse_elements([junk], ["park"]) == []


def test_parse_caps_names_and_ignores_non_string_facts():
    el = {
        "type": "node",
        "id": 8,
        "lat": 1,
        "lon": 1,
        "tags": {"name": "N" * 500, "leisure": "park", "description": 42},
    }
    (spot,) = parse_elements([el], ["park"])
    assert len(spot.name) == 120 and spot.facts == []


def test_query_for_uses_cell_centre():
    q = query_for(18.5204, 73.8567, ["park"])
    assert "18.52,73.86" in q and "18.5204" not in q
