# 001 — Golden Hour MVP: Design

- **Status:** Approved (2026-10-08)
- **Implements:** [requirements.md](requirements.md)

## 1. Architecture

```
 Browser (static HTML/JS)                 Render
 ┌──────────────────────┐   HTTPS   ┌───────────────────────────┐  private net  ┌──────────────────────┐
 │ geolocation / city   │──────────▶│ golden-hour  (web, Docker)│──────────────▶│ golden-hour-ollama   │
 │ free-time inputs     │           │ FastAPI                    │  /api/chat    │ (pserv, Docker)      │
 │ plan + suggestion UI │◀──────────│  /api/geocode /plan        │               │ ollama + gemma3:1b   │
 │ countdown, .ics      │           │  /api/suggest              │               └──────────────────────┘
 └──────────────────────┘           └─────────────┬─────────────┘
                                                  │ HTTPS (keyless, open data)
                                                  ▼
                                     Open-Meteo forecast + geocoding APIs
```

The design splits the work in two:

- **Deterministic core:** weather → candidate windows → score → pick. It's pure Python, fast, and fully
  unit-tested. It always works, even with no model.
- **Generative edge:** the model only writes the *activity* for an already-chosen window. Output is small and
  JSON-schema constrained. If the model fails, a curated fallback is used.

This keeps latency for the window under 2 s (N1), keeps CPU inference cheap on Render, and makes the AI part
easy to explain in the post.

## 2. Request flow

1. The page gets coordinates from `navigator.geolocation`. If that's denied, it calls `GET /api/geocode?q=…`
   (R1.1, R1.2).
2. The page sends `POST /api/plan` with `{lat, lon, free_ranges}`. The server fetches the Open-Meteo forecast
   (2 days, `timezone=auto`), runs the scorer and returns `best` + `alternates`. The page renders right away
   (R3, R4.5).
3. The page sends `POST /api/suggest` with `{window, place_name}` and shows progress while it waits (R4.5).
   The server prompts Gemma with a JSON schema, validates the reply and falls back to the curated list if
   needed (R4.1–R4.4).
4. The page shows a countdown to `best.start` and builds the `.ics` file client-side (R5).

Coordinates are used only inside the `/api/plan` request and are never logged or stored (R1.3, N2).
`/api/suggest` never receives coordinates.

## 3. Time handling

Open-Meteo with `timezone=auto` returns **local, offset-less** timestamps plus `utc_offset_seconds`. The whole
backend works in **naive local datetimes for the forecast location**:

- `now_local = datetime.now(UTC) + utc_offset` (with the offset tag dropped). This is injected as a dependency
  so tests can freeze time.
- `free_ranges` are local `HH:MM` times for that location's "today".
- API responses use local ISO strings without an offset, plus the `timezone` name for display and `.ics`.

## 4. Modules & interfaces

```
src/golden_hour/
  config.py      settings (GH_OLLAMA_URL, GH_MODEL, GH_LLM_TIMEOUT_S)           [exists]
  models.py      pydantic domain + API models                                    @ai
  weather.py     Open-Meteo client: fetch_forecast(), geocode()                   @ai
  scoring.py     weather_for(), score_window(), candidate_windows(),
                 pick_windows(), plan_day()                                       @human
  llm.py         OllamaClient.chat_json(messages, schema) -> dict                 @ai
  prompts.py     build_messages(ctx) -> list[dict]                                @human
  fallbacks.py   FALLBACKS list + pick_fallback(ctx) -> Suggestion                @human
  suggest.py     suggest(ctx, client) -> Suggestion  (validate + fallback)        @ai
  main.py        routes + dependency wiring                                       @ai
  static/        index.html, app.js, style.css                                    @ai
                 time.js  (countdown + .ics builder)                              @human
```

### 4.1 Models (`models.py`)

```python
class TimeRange(BaseModel):          # local wall-clock, today
    start: time
    end: time                        # validator: end > start

class HourlyWeather(BaseModel):
    time: datetime                   # local, naive, on the hour
    temp_c: float
    precip_prob: int                 # 0–100
    wind_kmh: float
    uv: float
    cloud_cover: int                 # 0–100

class DayLight(BaseModel):
    date: date
    sunrise: datetime
    sunset: datetime

class Forecast(BaseModel):
    timezone: str
    utc_offset_seconds: int
    hours: list[HourlyWeather]       # 48 entries (today + tomorrow)
    days: list[DayLight]             # 2 entries

class WindowWeather(BaseModel):      # worst case across the hours a window overlaps
    temp_c: float
    precip_prob: int
    wind_kmh: float
    uv: float
    cloud_cover: int

class Window(BaseModel):
    start: datetime
    end: datetime
    duration_min: int
    day: Literal["today", "tomorrow"]
    score: int                       # 0–100
    reasons: list[str]               # 1–3 short phrases, most important first
    weather: WindowWeather

class Plan(BaseModel):
    timezone: str
    sunrise: datetime
    sunset: datetime
    best: Window | None
    alternates: list[Window]         # 0–2
    note: str | None                 # e.g. "No 20-min gap left today — here's tomorrow."

class Suggestion(BaseModel):
    title: str                       # ≤ 60 chars
    steps: list[str]                 # 1–3
    what_to_notice: str
    bring: list[str]                 # 0–3
    source: Literal["model", "fallback"] = "model"   # set by the server; not part of the LLM schema

class SuggestionContext(BaseModel):
    window: Window
    place_name: str | None

class Place(BaseModel):              # /api/geocode result item
    name: str
    country: str | None
    lat: float
    lon: float

class PlanRequest(BaseModel):        # /api/plan body
    lat: float                       # -90..90
    lon: float                       # -180..180
    free_ranges: list[TimeRange] = []
```

### 4.2 Scoring (`scoring.py`): @human

Signatures (the contract the routes depend on):

```python
def weather_for(forecast: Forecast, start: datetime, end: datetime) -> WindowWeather
def score_window(w: WindowWeather, start: datetime, end: datetime, sunset: datetime) -> tuple[int, list[str]]
def candidate_windows(free: list[TimeRange], forecast: Forecast, day: date, now: datetime) -> list[Window]
def pick_windows(candidates: list[Window], k: int = 3) -> list[Window]
def plan_day(free: list[TimeRange], forecast: Forecast, now: datetime) -> Plan
```

Baseline rules. You can tune the numbers, but update this section when you do:

- **Candidates:** starts on the quarter hour (:00/:15/:30/:45), from `max(range.start, now rounded up to
  the next quarter, sunrise)`. Duration = `min(40, available)` where `available` = minutes until
  `min(range.end, sunset + 15 min)`. Discard if duration < 20.
- **`weather_for`:** worst case over the overlapped hours: max `precip_prob`, max `wind_kmh`, max `uv`,
  max `cloud_cover`, and the `temp_c` furthest from 19.5 °C.
- **`score_window`:** start at 100, then
  - −0.8 × `precip_prob`
  - −3 per °C below 15 or above 24
  - −2 per km/h of wind above 20
  - −5 per UV point above 6
  - +15 if the window overlaps `[sunset − 60 min, sunset]` (golden hour)
  - clamp to 0–100 and round. `reasons` = the largest-magnitude factors as short phrases, e.g.
    `"dry (5% rain)"`, `"golden hour"`, `"breezy (28 km/h)"`.
- **`pick_windows`:** sort by score (desc), then golden-hour windows first (the +15 bonus can be
  lost to the 100 cap on a perfect day), then by start (asc); greedily take non-overlapping windows; return
  up to `k`.
- **`plan_day`:**
  - Empty `free` means `[now, sunset]` (R2.2).
  - No candidate today means re-run for tomorrow with the whole daylight as free, set `day="tomorrow"` and
    set `note` (R2.3).
  - Otherwise `best = picks[0]`, `alternates = picks[1:]`.

### 4.3 LLM (`llm.py`, `prompts.py`, `fallbacks.py`, `suggest.py`)

- `OllamaClient.chat_json` → `POST {GH_OLLAMA_URL}/api/chat` with
  `{"model": GH_MODEL, "messages": …, "format": <JSON schema>, "stream": false, "options": {"temperature": 0.7}}`.
  Timeout `GH_LLM_TIMEOUT_S` (default 60). Parses `message.content` as JSON.
- The schema is `Suggestion.model_json_schema()` with `source` excluded.
- **`prompts.build_messages(ctx)` (@human)** returns `[{"role": "system", …}, {"role": "user", …}]`. It must
  state duration, local time of day, weather, golden hour (if relevant), the walking-distance / no-purchase
  constraint (R4.3) and the field limits (R4.2).
- **`fallbacks` (@human)** holds at least 8 curated activities. Each has tags (`min_duration`, `ok_in_rain`,
  `golden_hour`). `pick_fallback(ctx)` picks the best match deterministically.
- `suggest.suggest(ctx, client)` builds the messages, calls `chat_json` and validates with `Suggestion`
  (enforcing the list caps by truncation, not failure). On any exception or validation error it returns
  `pick_fallback(ctx)` with `source="fallback"` and logs the reason, without the context (R4.4).

### 4.4 HTTP API (`main.py`)

| Method | Path | Body / query | Response | Reqs |
|--------|------|--------------|----------|------|
| GET | `/api/health` | — | `{status, version, model}` | — |
| GET | `/api/geocode` | `q` (≥2 chars) | `[{name, country, lat, lon}]` (≤5) | R1.2 |
| POST | `/api/plan` | `{lat, lon, free_ranges: [{start, end}]}` | `Plan` | R2, R3 |
| POST | `/api/suggest` | `SuggestionContext` | `Suggestion` | R4 |

Errors: if the weather upstream fails, return `502 {"detail": "weather unavailable"}`. Validation errors use
FastAPI's standard 422. Dependencies (`get_weather`, `get_llm`, `get_now`) can be overridden in tests, so no
test touches the network.

### 4.5 Frontend (`static/`)

Vanilla JS, no build step, one page (N3). Its states are: *locating → form → planning → plan shown →
suggestion loading → suggestion shown*. The °C/°F toggle is stored in `localStorage`.

**`time.js` (@human)** exports:

```js
startCountdown(el, startIso, endIso)   // updates every second: "in 1h 12m" → "now — go!" → "done"
buildIcs({title, description, startIso, endIso, timezone})  // returns an .ics string (VCALENDAR/VEVENT)
downloadIcs(icsString, filename)       // Blob + temporary <a download>
```

## 5. Deployment (Render)

`render.yaml` defines two services:

| Service | Type | Plan | Notes |
|---------|------|------|-------|
| `golden-hour` | web, Docker (root `Dockerfile`) | Starter | Health check `/api/health`. `GH_OLLAMA_URL` comes from `fromService: golden-hour-ollama, property: hostport`. |
| `golden-hour-ollama` | private service, Docker (`ollama/Dockerfile`) | Standard (~2 GB) | `FROM ollama/ollama`. The model is pulled at **build** time, so it's baked into the image with no disk needed. `OLLAMA_KEEP_ALIVE=-1` keeps it loaded. |

- `hostport` has no scheme, so `config.py` normalizes `GH_OLLAMA_URL` by adding `http://` when it's missing.
- **Cost check (N4):** roughly $7 + $25 a month, prorated, which is well under $50 through judging. *Verify
  current Render pricing before deploying.*
- `gemma3:1b` on shared CPU is expected to take about 10–30 s per suggestion. That fits within N1, and the
  progress UI covers the wait.

## 6. Testing

- **Unit:** scoring (table-driven with hand-built `Forecast` fixtures), the fallback picker, prompt contents
  (asserts that key facts appear), `.ics` (manual check plus a validator).
- **Clients:** `weather.py` and `llm.py` are tested against `httpx.MockTransport` with recorded JSON fixtures
  in `tests/fixtures/`.
- **API:** `TestClient` with dependency overrides (fake weather, fake LLM, frozen clock).
- **CI:** GitHub Actions on push and PR runs `ruff check` + `pytest` (N5).
- **Manual:** the acceptance-criteria checklist in `tasks.md`, run against the deployed URL.

## 7. Risks

| Risk | Mitigation |
|------|-----------|
| CPU inference too slow or OOM on Render | 1b model, keep-alive, small output schema, fallback path; upgrade the plan if needed |
| Small model ignores constraints | JSON-schema `format`, server-side truncation, prompt tests, fallback |
| Open-Meteo outage or rate limit | 502 with a friendly UI message; free tier is generous for demo traffic |
| Time-zone bugs | single local-naive convention (§3), frozen-clock tests around sunset and midnight |
| Deadline (2026-10-11) | deterministic core first; AI and deploy can degrade gracefully |

## Changelog

- 2026-10-08 — Initial draft.
- 2026-10-09 — T6: local testing showed both Gemma sizes invent street/landmark names when given a
  place, and ignore rain unless told exactly what to do. The prompt now forbids naming real places
  (`place_name` is passed as "region, for climate only") and, when rain ≥ 50%, requires the first
  step to say how to stay dry. `coerce` also drops "None"-style `bring` items and rejects empty
  titles or notices (→ fallback).
- 2026-10-09 — T3: `pick_windows` tie-break prefers golden hour before earlier start.
- 2026-10-08 — T1: added `Place` and `PlanRequest` to §4.1 (they were implied by §4.4).
