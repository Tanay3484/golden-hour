"""Nearby named places from OpenStreetMap via the Overpass API (spec 002, design §4.2).

Privacy (R10.2): Overpass only ever sees the centre of the user's ~1 km grid cell. The precise
location is used here, server-side, to compute walking times, and is never logged or cached.
"""

import logging
import math
import time
from collections import OrderedDict
from collections.abc import Callable

import httpx

from golden_hour import __version__
from golden_hour.hobbies import CATEGORIES, classify
from golden_hour.models import Spot

log = logging.getLogger(__name__)

WALK_M_PER_MIN = 80
CELL_DECIMALS = 2  # ~1.1 km grid
CELL_SLACK_M = 800  # half-diagonal of a cell, so a cell-centre query covers every user in it
MAX_WINDOW_MIN = 40
QUERY_RADIUS_M = round(MAX_WINDOW_MIN / 3 * WALK_M_PER_MIN) + CELL_SLACK_M  # ≈ 1.9 km
PER_CATEGORY = 40
USER_AGENT = f"golden-hour/{__version__} (+https://github.com/Tanay3484/golden-hour)"
FACT_TAGS = ("description", "inscription", "artist_name", "artwork_type", "memorial", "sport")


def radius_for(duration_min: int) -> int:
    """Walking radius for a window: a third of it each way (R8.1)."""
    return round(duration_min / 3 * WALK_M_PER_MIN)


def cell_of(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, CELL_DECIMALS), round(lon, CELL_DECIMALS)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (
        math.sin((lat2 - lat1) * p / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    )
    return 12_742_000 * math.asin(math.sqrt(a))


def build_query(
    lat: float, lon: float, categories: list[str], radius_m: int = QUERY_RADIUS_M
) -> str:
    # A small maxsize gets admitted on a busy server; the default 512 MiB was rejected with 504s.
    parts = ["[out:json][timeout:25][maxsize:67108864];"]
    for key in categories:
        for rule in CATEGORIES[key].rules:
            parts.append(
                f'nwr(around:{radius_m},{lat},{lon}){rule.selector()}["name"];'
                f"out center tags {PER_CATEGORY};"
            )
    return "\n".join(parts)


def _facts(tags: dict) -> list[str]:
    facts = []
    for key in FACT_TAGS:
        value = tags.get(key)
        if value:
            value = value.strip()
            if len(value) > 100:
                value = value[:99].rstrip() + "…"
            facts.append(f"{key.replace('_', ' ')}: {value}")
    return facts[:3]


def _name_key(name: str) -> str:
    # "Shaniwarwada" and "Shaniwar Wada" are the same place.
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def parse_elements(elements: list[dict], categories: list[str]) -> list[Spot]:
    """Named, classifiable places with coordinates, deduplicated by (name, category)."""
    spots: dict[tuple[str, str], Spot] = {}
    for e in elements:
        tags = e.get("tags") or {}
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        point = e.get("center") or e
        if not name or "lat" not in point or "lon" not in point:
            continue
        found = classify(tags, categories)
        if not found:
            continue
        category, kind = found
        spots.setdefault(
            (_name_key(name), category),
            Spot(
                id=f"{e['type']}/{e['id']}",
                name=name,
                category=category,
                kind=kind,
                lat=point["lat"],
                lon=point["lon"],
                covered=CATEGORIES[category].covered,
                facts=_facts(tags),
                osm_url=f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
            ),
        )
    return list(spots.values())


def within_walk(spots: list[Spot], lat: float, lon: float, radius_m: int) -> list[Spot]:
    """Spots within `radius_m` of the user's precise location, with walk_min filled in."""
    out = []
    for s in spots:
        d = haversine_m(lat, lon, s.lat, s.lon)
        if d <= radius_m:
            out.append(s.model_copy(update={"walk_min": max(1, math.ceil(d / WALK_M_PER_MIN))}))
    return out


class PlaceCache:
    """In-memory only, keyed by grid cell + categories (R10.3). Holds public place data."""

    def __init__(
        self, ttl_s: float = 6 * 3600, max_entries: int = 256, clock: Callable = time.monotonic
    ):
        self.ttl_s, self.max_entries, self.clock = ttl_s, max_entries, clock
        self._data: OrderedDict[tuple, tuple[float, list[Spot]]] = OrderedDict()

    def get(self, key: tuple) -> list[Spot] | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        stored_at, spots = hit
        if self.clock() - stored_at > self.ttl_s:
            del self._data[key]
            return None
        return spots

    def put(self, key: tuple, spots: list[Spot]) -> None:
        self._data[key] = (self.clock(), spots)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)


class OverpassClient:
    def __init__(
        self,
        urls: list[str],
        budget_s: float = 25,
        http: httpx.Client | None = None,
        cache: PlaceCache | None = None,
        clock: Callable = time.monotonic,
    ):
        self.urls, self.budget_s, self.clock = urls, budget_s, clock
        self._http = http or httpx.Client(headers={"User-Agent": USER_AGENT})
        self.cache = cache or PlaceCache()

    def nearby(self, lat: float, lon: float, radius_m: int, categories: list[str]) -> list[Spot]:
        """Places within `radius_m` walk of (lat, lon). Returns [] if OSM can't be reached."""
        cell = cell_of(lat, lon)
        key = (*cell, tuple(sorted(categories)))
        spots = self.cache.get(key)
        if spots is None:
            spots = self._fetch(*cell, categories)
            if spots:
                self.cache.put(key, spots)
        return within_walk(spots, lat, lon, radius_m)

    def _fetch(self, cell_lat: float, cell_lon: float, categories: list[str]) -> list[Spot]:
        query = build_query(cell_lat, cell_lon, categories)
        deadline = self.clock() + self.budget_s
        for url in self.urls:
            remaining = deadline - self.clock()
            if remaining < 2:
                break
            try:
                resp = self._http.post(url, data={"data": query}, timeout=remaining)
                resp.raise_for_status()
                return parse_elements(resp.json().get("elements", []), categories)
            except (httpx.HTTPError, ValueError) as e:
                # Host and error only: never the query, which contains the (coarse) location.
                log.warning("overpass %s failed: %s", httpx.URL(url).host, type(e).__name__)
        return []
