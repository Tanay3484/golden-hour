from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from golden_hour.hobbies import CATEGORIES
from golden_hour.main import app, get_llm, get_overpass
from golden_hour.models import Spot, Window, WindowWeather

START = datetime(2026, 10, 9, 17, 30)
WINDOW = Window(
    start=START,
    end=START + timedelta(minutes=40),
    duration_min=40,
    day="today",
    score=90,
    reasons=["golden hour"],
    weather=WindowWeather(temp_c=24, precip_prob=0, wind_kmh=5, uv=2, cloud_cover=10),
)


def spot(i, category, walk):
    return Spot(
        id=f"node/{i}",
        name=f"Place {i}",
        category=category,
        kind=category,
        lat=18.52,
        lon=73.85,
        walk_min=walk,
        covered=CATEGORIES[category].covered,
        osm_url=f"https://www.openstreetmap.org/node/{i}",
    )


NEARBY = [spot(1, "park", 3), spot(2, "view", 6), spot(3, "art", 2), spot(4, "history", 5)]


class FakeOverpass:
    def __init__(self, spots):
        self.spots, self.calls = spots, []

    def nearby(self, lat, lon, radius_m, categories):
        self.calls.append((lat, lon, radius_m, categories))
        return self.spots


class FakeLLM:
    def chat_json(self, messages, schema, temperature=0.7):
        return {"lines": [{"id": 1, "name": "Place 1", "line": "Sit by the trees."}]}


@pytest.fixture
def overpass():
    fake = FakeOverpass(NEARBY)
    app.dependency_overrides[get_overpass] = lambda: fake
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    yield fake
    app.dependency_overrides.clear()


client = TestClient(app)
BODY = {"lat": 18.5204, "lon": 73.8567, "window": WINDOW.model_dump(mode="json")}


def test_places_ranked_with_attribution(overpass):
    resp = client.post("/api/places", json=BODY | {"hobbies": ["photography"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["attribution"] == "Places © OpenStreetMap contributors"
    assert data["places"][0]["category"] == "view"  # photography's first category
    lat, lon, radius, cats = overpass.calls[0]
    assert (lat, lon, radius) == (18.5204, 73.8567, 1067)
    assert cats == ["view", "water", "art", "history", "park"]


def test_no_hobbies_searches_everything(overpass):
    client.post("/api/places", json=BODY)
    assert overpass.calls[0][3] == list(CATEGORIES)


def test_osm_down_or_sparse_is_empty_not_an_error(overpass):
    overpass.spots = NEARBY[:2]
    resp = client.post("/api/places", json=BODY)
    assert resp.status_code == 200 and resp.json()["places"] == []


@pytest.mark.parametrize(
    "extra",
    [{"hobbies": ["juggling"]}, {"hobbies": ["art", "history", "nature", "coffee"]}, {"lat": 95}],
)
def test_places_validation(overpass, extra):
    assert client.post("/api/places", json=BODY | extra).status_code == 422


def test_describe_route(overpass):
    places = [s.model_dump(mode="json") for s in NEARBY[:3]]
    resp = client.post(
        "/api/places/describe",
        json={"window": WINDOW.model_dump(mode="json"), "places": places, "hobbies": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lines"]["node/1"] == "Sit by the trees."
    assert data["source"] == {"node/1": "model", "node/2": "template", "node/3": "template"}


def test_unreachable_osm_hands_the_query_to_the_browser(overpass):
    overpass.spots = None
    data = client.post("/api/places", json=BODY | {"hobbies": ["art"]}).json()
    assert data["places"] == []
    fb = data["fallback"]
    assert fb["urls"] and fb["urls"][0].startswith("https://")
    assert "18.52,73.86" in fb["query"] and "18.5204" not in fb["query"]
    assert '"tourism"="artwork"' in fb["query"]


def test_no_fallback_when_osm_answered(overpass):
    assert client.post("/api/places", json=BODY).json()["fallback"] is None


def element(i, lat, lon, tags):
    return {"type": "node", "id": i, "lat": lat, "lon": lon, "tags": tags}


def test_from_osm_parses_ranks_and_filters_by_walk(overpass):
    elements = [
        element(1, 18.5210, 73.8570, {"name": "Garden", "leisure": "garden"}),
        element(2, 18.5190, 73.8560, {"name": "Statue", "tourism": "artwork"}),
        element(3, 18.5215, 73.8580, {"name": "Lookout", "tourism": "viewpoint"}),
        element(4, 18.6000, 73.9000, {"name": "Too far", "leisure": "park"}),
        {"junk": True},
    ]
    resp = client.post("/api/places/from-osm", json=BODY | {"elements": elements})
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["places"]]
    assert set(names) == {"Garden", "Statue", "Lookout"}
    assert overpass.calls == []  # the server didn't query OSM itself


def test_from_osm_rejects_huge_payloads(overpass):
    big = [element(i, 18.52, 73.85, {"name": f"P{i}", "leisure": "park"}) for i in range(2001)]
    assert client.post("/api/places/from-osm", json=BODY | {"elements": big}).status_code == 422
