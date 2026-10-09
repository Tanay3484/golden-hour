# 002 — Nearby places for your hobbies: Design

- **Status:** Approved (2026-10-09)
- **Implements:** [requirements.md](requirements.md)

## 1. Flow

```
choose(window) ─┬─▶ POST /api/places   {lat, lon, window, hobbies}         ≤ 25 s, no model
                │      ├─ cache hit (rounded ~1 km cell, ≤ 6 h)  ─────────┐
                │      └─ Overpass (2 instances, in order) ─▶ parse ──────┤
                │                                         rank_places() ◀─┘
                │      ◀─ {places: [5], attribution}   or   {places: []}
                │
                ├─ places ≥ 3 ─▶ render list now (R8.4)
                │               POST /api/places/describe {window, places, hobbies}
                │               ◀─ {lines: {place_id: "…"}, source}      (Gemma, template per miss)
                │
                └─ places < 3 or error ─▶ POST /api/suggest   (001 behaviour, R10.1)
```

The places request runs first and the model call only happens after it, so there is still exactly one
model call per window choice.

## 2. Spike findings

Run 2026-10-09 ~01:00 IST; scripts and raw data are in the session scratchpad, and the Berlin response is
kept as `tests/fixtures/overpass_berlin_spike.json`.

| Test | Result |
|---|---|
| `overpass-api.de`, Berlin, 1.2 km, simple query | 200 in 2.5 s |
| `overpass-api.de`, Pune / Mumbai, `[timeout:10]` | 504 `Dispatcher_Client::request_read_and_idx::timeout. The server is probably too busy` |
| `overpass-api.de`, Pune, `[timeout:25]`, 1 category | 200, 10 parks |
| `overpass-api.de`, Pune, 7 categories | 504 after 11 s (busy) |
| `overpass.private.coffee` | 500 for every city |
| `maps.mail.ru` (VK) | 504 or read timeout for every city |
| Berlin, broad query, 300 cap | 109 cafés, 86 memorials, 61 artworks; parks crowded out → **query per category with a per-category cap** |
| gemma3:1b, rank 13 Berlin places | 7.8 s laptop; picked ids 1–5 in order; invented details ("rain-soaked") |
| gemma3:4b, same | 26.5 s laptop; mostly list order; invented "Frauenkirche" |

## 3. Hobbies → OSM categories (`hobbies.py`)

Each category is one Overpass selector, queried with its own `out … N` cap so dense categories can't
crowd out the others.

| Category | Overpass selector | Covered? |
|---|---|---|
| `park` | `leisure~"^(park|garden|nature_reserve|common)$"` | no |
| `water` | `natural=water` · `waterway~"^(river|canal)$"` | no |
| `view` | `tourism=viewpoint` · `natural=peak` | no |
| `art` | `tourism=artwork` | no |
| `history` | `historic~"^(monument|memorial|castle|fort|ruins|archaeological_site)$"` | no |
| `museum` | `tourism~"^(museum|gallery)$"` | **yes** |
| `library` | `amenity=library` | **yes** |
| `cafe` | `amenity=cafe` + `outdoor_seating=yes` | partly |
| `sport` | `leisure~"^(pitch|track|fitness_station)$"` | no |

| Hobby | Categories (first = strongest match) |
|---|---|
| photography | view, water, art, history, park |
| nature & birds | park, water, view |
| history | history, museum |
| art | art, museum |
| running & walking | park, water, sport |
| reading & sketching | park, library, cafe |
| coffee outside | cafe, park |
| sports | sport, park |

With no hobbies picked, the query uses all categories (R7.2).

## 4. Modules & interfaces

```
src/golden_hour/
  hobbies.py     HOBBIES, CATEGORIES (selector, covered, template line), categories_for(hobbies)
  places.py      OverpassClient.nearby(lat, lon, radius_m, categories) -> list[Spot]
                 build_query(), parse_elements(), haversine_m(), PlaceCache
  ranking.py     rank_places(spots, hobbies, window, k=5) -> list[Spot]        (pure)
  describe.py    describe(window, spots, hobbies, llm) -> PlaceLines            (model + templates)
  prompts.py     + build_place_messages(window, spots, hobbies)
  main.py        + POST /api/places, POST /api/places/describe
  static/        hobby chips, places card, attribution, privacy note
```

### 4.1 Models

```python
Hobby = Literal["photography", "nature", "history", "art", "running", "reading", "coffee", "sports"]

class Spot(BaseModel):
    id: str              # "node/123", stable OSM id
    name: str            # name:en if present, else name
    category: str        # key of CATEGORIES
    kind: str            # raw OSM value, e.g. "viewpoint", "memorial"
    lat: float
    lon: float
    walk_min: int        # straight-line distance / 80 m/min, rounded up
    covered: bool
    facts: list[str]     # ≤ 3 short facts from OSM tags only: description, artist_name, inscription (trimmed)
    osm_url: str         # https://www.openstreetmap.org/node/123

class PlacesRequest(BaseModel):
    lat: float; lon: float; window: Window; hobbies: list[Hobby] = []   # ≤ 3

class PlacesResponse(BaseModel):
    places: list[Spot]   # 0 or 3–5
    attribution: str = "Places © OpenStreetMap contributors"

class DescribeRequest(BaseModel):
    window: Window; places: list[Spot]; hobbies: list[Hobby] = []      # places: 1–5, no coordinates needed

class PlaceLines(BaseModel):
    lines: dict[str, str]                     # Spot.id -> sentence
    source: dict[str, Literal["model", "template"]]
```

`DescribeRequest` carries spots, which include coordinates. The describe step ignores `lat`/`lon` and they
are never put in the prompt, so the model still doesn't see the user's location (it only sees place names).

### 4.2 Overpass client (`places.py`)

- **Endpoints, tried in order:** `https://overpass-api.de/api/interpreter`, then
  `https://overpass.private.coffee/api/interpreter`. The second is down tonight but costs nothing to try.
  Configurable via `GH_OVERPASS_URLS`.
- **Query:** `[out:json][timeout:25];` then for each category
  `nwr(around:R,LAT,LON)[selector]["name"];out center tags 40;`. `LAT`/`LON` is the **centre of the
  user's 2-decimal grid cell** (~1.1 km; R10.2), and `R` is the radius for a 40-minute window (≈ 1.07 km)
  plus 800 m of slack for the cell's half-diagonal, ≈ 1.9 km. One query per cell + hobby set therefore
  serves every user and window in that cell. The server then filters by the user's **precise**
  distance and the window's own radius (R8.1); the precise location never leaves the server.
- **HTTP:** POST, `User-Agent: golden-hour/<version> (+https://github.com/Tanay3484/golden-hour)`, timeout
  27 s per attempt and a **25 s overall budget** across attempts (R10.1). A 429 or 504 moves to the next
  endpoint; nothing sleeps inside a user request.
- **Parse:** skip elements without a name or coordinates; dedupe by name + category (OSM often has both a
  node and a way for one park); compute `walk_min` with the haversine distance; drop anything beyond `R`.
- **Cache (R10.3):** in-process dict, key `(cell_lat, cell_lon, sorted categories)`, 6 h TTL, 256 entries,
  oldest evicted first. It stores parsed places with their own coordinates (public data); `walk_min` is
  recomputed for each user. Errors and empty results are not cached.

### 4.3 Ranking (`ranking.py`, pure)

`score = hobby + distance + weather + kind bonus`

- **hobby:** +3 if the category is a picked hobby's first category, +2 for any other category of a picked
  hobby, +1 if no hobbies were picked.
- **distance:** −0.25 per minute of walking.
- **weather:** if rain ≥ 50%: +3 for covered, −2 for not covered. If golden hour: +2 for `view`, `water`,
  `park`. If temperature > 28 °C: +1 for `park`, `water` (shade, breeze).
- **facts:** +0.5 if the spot has any `facts` (gives the model something real to say).
- **Pick:** sort by score (desc), then walk time (asc), then name; greedily take with ≤ 2 per category;
  stop at `k`. Return `[]` if fewer than 3 qualify (→ R10.1 fallback).

### 4.4 Describe (`describe.py`, `prompts.py`)

- One `chat_json` call. The schema is `{"lines": [{"id": str, "line": str}]}` with exactly `len(places)`
  items.
- Each place goes into the prompt as `id. name (kind, N min walk) — facts: …`; window facts as in 001.
  The system prompt says: one sentence ≤ 20 words per place; something to *do or notice now*; **only use
  the facts listed; never state history, features or what a place looks like unless it's in the facts**;
  match weather and golden hour.
- Validation: unknown ids are dropped; missing or empty lines are filled from that category's template;
  lines are trimmed to 140 characters. A model failure means all templates, `source` = template (R9.3).

### 4.5 API

| Method | Path | Body | Response | Reqs |
|---|---|---|---|---|
| POST | `/api/places` | `PlacesRequest` | `PlacesResponse` (never errors because of OSM: returns `places: []`) | R8, R10 |
| POST | `/api/places/describe` | `DescribeRequest` | `PlaceLines` (never fails) | R9 |

### 4.6 Frontend

- **Hobby chips** go in the "When are you free" card: "What do you enjoy? (up to 3, optional)". They're
  toggle buttons with `aria-pressed`, saved in `localStorage` (`gh-hobbies`, wrapped in try/catch) (R7).
- **"Top 5 near you" card** replaces "What to do" when there are ≥ 3 places. Each row has the name, then
  "kind · N min walk · Map ↗", then the line (a skeleton shimmer until it arrives). The attribution sits
  under the list (R8.5). Changing the window re-requests both.
- **Fallback:** when there are 0 places or an error, the existing single-suggestion card shows, with a
  small note "Couldn't reach map data right now".
- **Privacy note in the footer (R10.4):** "Your location is used for one forecast lookup and, rounded to
  about 100 m, to find nearby places on OpenStreetMap. It's never stored."

## 5. Testing

- **Unit:** `build_query` (rounding, radius, per-category caps), `parse_elements` (fixture: dedupe, names,
  walk time), `rank_places` (table-driven: hobby match, rain → covered, golden hour, variety cap, < 3 →
  `[]`), templates, `describe` validation (unknown ids, missing lines, model down).
- **Client:** `MockTransport`: first endpoint 504 → second 200; both fail → `[]`; budget exhaustion; cache
  hit makes zero requests.
- **API:** dependency overrides for the Overpass client and the LLM.
- **Manual:** the live Render URL from Pune and from a search for Berlin; one run with Ollama stopped and
  one with Overpass blocked.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Overpass busy or down (seen tonight) | two endpoints, 25 s budget, cache, fallback to the 001 suggestion |
| Render's outbound IP shared with heavy Overpass users → 429 | same fallback; `GH_OVERPASS_URLS` lets us point at another instance |
| Model invents facts about real places | facts-only prompt, ≤ 20 words, template fallback; the spike showed the risk is real, so test it |
| 5 lines too slow on 1 CPU | list shows first (R8.4); lines are capped at 20 words; expect ~30–40 s |
| Sparse OSM areas | < 3 places → 001 fallback |
| Deadline | ship gate in requirements decision 4 |

## Changelog

- 2026-10-09 — T18 results (3 runs × Pune/Berlin each): after the name and borrowed-fact checks,
  gemma3:1b put every line on the right place and stopped borrowing other places' facts, but still adds
  plausible generic detail ("the water's surface" at a park, "a pastry" at a café). gemma3:4b stayed
  grounded and used real facts well (inscriptions, the library's padlock note), but took 18–40 s on a
  laptop, i.e. minutes on Render's 1 CPU. **Production stays on 1B; T18's "invents no facts" bar is met
  by 4B only.** Accepted for the MVP of 002; revisit with a bigger Render plan or on-device inference.
- 2026-10-09 — T18: with gemma3:1b, 2 of 3 Pune runs attached lines to the wrong place (a park's line
  described a statue elsewhere on the list). The schema now makes the model echo each place's `name`;
  a line is rejected (→ template) if the echoed name doesn't match its id or the line mentions another
  listed place, or uses a fact belonging to another listed place. Temperature lowered to 0.3.
- 2026-10-09 — T17: dropped `sports_centre` from `sport`; in real Berlin data it surfaced a paid
  axe-throwing venue. Pitches, tracks and outdoor fitness stations are free to use.
- 2026-10-09 — T16: Overpass rejected the default 512 MiB `maxsize` with fast 504s on a busy server;
  declaring `[maxsize:67108864]` got Pune (3.2 s) and Mumbai (2.9 s) through on the main instance.
  Dedupe ignores spaces and punctuation in names ("Shaniwarwada" = "Shaniwar Wada").
- 2026-10-09 — §4.2: query from the cell centre with a fixed ~1.9 km radius and per-category cap 40,
  so one cached response serves the whole cell; distances recomputed per user (R10.2 tightened).
- 2026-10-09 — Initial draft.
