import mimetypes
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from golden_hour import __version__, scoring
from golden_hour.config import settings
from golden_hour.describe import describe
from golden_hour.hobbies import categories_for
from golden_hour.llm import OllamaClient
from golden_hour.models import (
    DescribeRequest,
    Forecast,
    OsmFallback,
    Place,
    PlaceLines,
    PlacesFromOsmRequest,
    PlacesRequest,
    PlacesResponse,
    Plan,
    PlanRequest,
    Suggestion,
    SuggestionContext,
    TimeRange,
)
from golden_hour.places import (
    OverpassClient,
    parse_elements,
    query_for,
    radius_for,
    within_walk,
)
from golden_hour.ranking import rank_places
from golden_hour.suggest import suggest
from golden_hour.weather import WeatherClient, WeatherError

STATIC_DIR = Path(__file__).parent / "static"

Planner = Callable[[list[TimeRange], Forecast, datetime], Plan]

# Some Windows registries map .js to text/plain, which browsers refuse to run as a module.
mimetypes.add_type("text/javascript", ".js")

app = FastAPI(title="Golden Hour", version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Dependencies — overridden in tests so nothing touches the network or the real clock.


@lru_cache
def get_weather() -> WeatherClient:
    return WeatherClient()


@lru_cache
def get_llm() -> OllamaClient:
    return OllamaClient(
        settings.ollama_url,
        settings.model,
        settings.llm_timeout_s,
        num_thread=settings.llm_num_thread,
    )


@lru_cache
def get_overpass() -> OverpassClient:
    # One instance per process, so its in-memory place cache is shared (R10.3).
    return OverpassClient(settings.overpass_urls, settings.overpass_budget_s)


def get_clock() -> Callable[[], datetime]:
    return lambda: datetime.now(UTC)


def get_planner() -> Planner:
    return scoring.plan_day


# Routes


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "model": settings.model}


@app.get("/api/geocode", response_model=list[Place])
def geocode(
    q: str = Query(min_length=2, max_length=100),
    weather: WeatherClient = Depends(get_weather),
) -> list[Place]:
    try:
        return weather.geocode(q)
    except WeatherError as e:
        raise HTTPException(502, "weather unavailable") from e


@app.post("/api/plan", response_model=Plan)
def plan(
    req: PlanRequest,
    weather: WeatherClient = Depends(get_weather),
    clock: Callable[[], datetime] = Depends(get_clock),
    planner: Planner = Depends(get_planner),
) -> Plan:
    # Coordinates live only for this request: never logged or stored (R1.3).
    try:
        forecast = weather.fetch_forecast(req.lat, req.lon)
    except WeatherError as e:
        raise HTTPException(502, "weather unavailable") from e
    now_local = (clock() + timedelta(seconds=forecast.utc_offset_seconds)).replace(tzinfo=None)
    return planner(req.free_ranges, forecast, now_local)


@app.post("/api/suggest", response_model=Suggestion)
def suggestion(ctx: SuggestionContext, llm: OllamaClient = Depends(get_llm)) -> Suggestion:
    # Never fails: falls back to a curated activity if the model is down or returns junk (R4.4).
    return suggest(ctx, llm)


@app.post("/api/places", response_model=PlacesResponse)
def places(
    req: PlacesRequest, overpass: OverpassClient = Depends(get_overpass)
) -> PlacesResponse:
    # Never fails because of OSM: no places means the page falls back to /api/suggest (R10.1).
    categories = categories_for(req.hobbies)
    nearby = overpass.nearby(req.lat, req.lon, radius_for(req.window.duration_min), categories)
    if nearby is None:  # no Overpass instance answered: let the browser try (R10.5)
        return PlacesResponse(
            places=[],
            fallback=OsmFallback(
                query=query_for(req.lat, req.lon, categories), urls=settings.overpass_urls
            ),
        )
    return PlacesResponse(places=rank_places(nearby, req.hobbies, req.window))


@app.post("/api/places/from-osm", response_model=PlacesResponse)
def places_from_osm(req: PlacesFromOsmRequest) -> PlacesResponse:
    # Browser-supplied elements: parsed defensively and never cached, so they can't reach
    # anyone else (R10.5).
    spots = parse_elements(req.elements, categories_for(req.hobbies))
    nearby = within_walk(spots, req.lat, req.lon, radius_for(req.window.duration_min))
    return PlacesResponse(places=rank_places(nearby, req.hobbies, req.window))


@app.post("/api/places/describe", response_model=PlaceLines)
def place_lines(req: DescribeRequest, llm: OllamaClient = Depends(get_llm)) -> PlaceLines:
    return describe(req.window, req.places, req.hobbies, llm)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
