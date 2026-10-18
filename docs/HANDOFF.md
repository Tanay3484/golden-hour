# Golden Hour — handoff for a new agent session

Everything a fresh Claude Code session (local or claude.ai/code) needs to continue this project without
the original chat. Read this, then `CLAUDE.md`, then `specs/README.md`. Last updated 2026-10-18.

## 1. Status in one paragraph

Golden Hour was built 2026-10-07 → 2026-10-11 for the DEV Hacktoberfest 2026 Open-Source AI Challenge,
Week 1 ("Touch Grass"), submitted on time, and **won Best Use of Render** (featured category, announced
2026-10-16). It is live, all PRs (#1–#14) are merged into `main`, and CI is green. Nothing is in flight.
The remaining items are optional (§8).

| What | Where |
|---|---|
| Live app | https://golden-hour-ahl6.onrender.com |
| DEV post (submission) | https://dev.to/tanay_singh_1005/golden-hour-an-open-model-that-finds-your-40-minutes-outside-and-where-to-spend-them-5fe8 |
| Winners announcement | https://dev.to/devteam/congrats-to-the-hacktoberfest-open-source-ai-challenge-touch-grass-winners-152c |
| Specs (source of truth) | `specs/001-golden-hour-mvp`, `specs/002-nearby-places`, `specs/003-visual-redesign` |

## 2. What the app does

1. Location from the browser, or a city search that shows results as you type (R1.4).
2. Free-time ranges (or "now until sunset"), and up to 3 hobbies.
3. **Plain Python picks the window** (`scoring.py`): every 20–40 min quarter-hour slot inside the free
   time and daylight gets the worst weather of the hours it touches, then a score of 0–100 (rain −0.8/%,
   temp −3/°C outside 15–24, wind −2/km/h above 20, UV −5/point above 6, +15 for golden hour). Top 3
   non-overlapping slots; ties prefer golden hour.
4. **Top 5 real places** within walking distance from OpenStreetMap (Overpass), ranked by plain code
   (`ranking.py`): hobby match, walking time, weather fit, at most 2 per category.
5. **Gemma writes one line per place** (`describe.py`). Lines are validated, and templates replace any
   that fail. If there are no places, Gemma writes one activity instead (`suggest.py`).
6. Countdown and an `.ics` calendar invite with a 10-minute alarm (`static/time.js`).

Design rule throughout: **code decides, the model only writes**, and every model output has a
deterministic fallback, so the page never breaks.

## 3. Architecture and deployment

```
Browser ─▶ FastAPI (Render web, 0.5c-512mb, Singapore) ─▶ Open-Meteo (forecast, geocoding)
                     │                                  ─▶ Overpass (OSM places), browser fallback
                     └─ private network ─▶ Ollama + gemma3:1b (Render pserv, 1c-2g, Singapore)
```

- `render.yaml` is a Blueprint for both services. The web app gets `GH_OLLAMA_URL` from
  `fromService … hostport` (no scheme; `config.py` adds `http://`). Env: `GH_MODEL=gemma3:1b`,
  `GH_LLM_TIMEOUT_S=90`, `GH_LLM_NUM_THREAD=1`.
- `ollama/Dockerfile` pins `ollama/ollama:0.40.2` and pulls `gemma3:1b` at build time;
  `ollama/start.sh` warms the model up.
- Cost: about $32/month for both services, paid from a ~$50 Render credit **shared with later weeks**.
- The Blueprint needed one **Manual Sync** on first apply; the first deploy was mistakenly a plain web
  service with no Ollama and no env vars (symptom: `/api/health` showed `gemma3:4b`, suggestions all
  fell back in 0.3 s).

## 4. Hard-won lessons (all in the spec changelogs too)

| Problem | Fix |
|---|---|
| Gemma invented places ("Elm Street") | Prompt forbids naming real places; the city is passed as "region, for climate only" |
| Gemma ignored rain | When rain ≥ 50%, the first step must say how to stay dry |
| Asked to rank 13 places, both sizes returned list order; 4B invented "Frauenkirche" | Code ranks; the model only describes, using OSM facts only |
| 1B attached lines to the wrong place / borrowed other places' facts | Schema makes the model echo each place's name; lines that don't match, name another place, or borrow its facts → template |
| Overpass 504 "server too busy" for Pune | Declare `[maxsize:67108864]` (64 MiB); busy servers reject the default 512 MiB |
| Live: Overpass rate-limits Render's shared outbound IP (0 places, 12 tries) | Browser fallback (R10.5): server returns the cell-centre query, the browser asks Overpass, `/api/places/from-osm` parses untrusted input, never cached |
| Live: 38–80 s per Gemma call | Ollama sized threads from the host's cores on a 1-CPU plan; `num_thread=1` → 16–30 s |
| Perfect-day bug: golden-hour bonus lost to the 100 cap | `pick_windows` tie-break prefers golden hour |
| CSS `display` overrode `[hidden]` (skeletons never vanished) | Global `[hidden] { display: none !important; }` |
| Browser kept old `app.js` after a deploy | `Cache-Control: no-cache` on `/` and `/static/*` (ETag → 304) |

**Known gap (R9.2, partial):** gemma3:1b still adds the odd plausible detail to place lines ("a pastry"
at a café). gemma3:4b doesn't, but it's ~5× slower; production stays on 1B by choice.

## 5. Working agreements with the owner (Tanay)

- **AI-PDLC, spec first.** Phases are gated: requirements → design → tasks → implement. Draft one phase,
  stop, ask for review. Code only for specs whose `tasks.md` says `Status: Approved`. If the spec is wrong,
  edit the spec (with a changelog line) before the code.
- **Branch + PR for every change.** `main` is protected (1 approval, CI check `test`, conversations
  resolved). Tanay reviews and merges. **The agent must not admin-merge or push to `main`**; that was
  refused once and is off-limits.
- Commit messages cite task and requirement IDs, and end with the co-author line the harness provides.
- `@human` tasks are Tanay's to write by hand; offer hints, tests-first stubs and reviews. Tanay may hand
  a task over explicitly; under deadline, offer to take tasks over rather than insisting.
- Explanations for Tanay work best concrete and small (one rule, a worked example with real numbers)
  rather than full interface specs up front.
- Never publish on DEV or post anywhere on Tanay's behalf. Drafts live in `drafts/` (git-ignored).
- Be honest in public writing: the outdoor field test hasn't happened, and the post says so.

## 6. Running and testing

- Local setup is Windows + PowerShell/Git Bash: `python -m venv .venv`, `.venv/Scripts/pip install -e ".[dev]"`.
  On Linux/macOS (e.g. claude.ai/code) use `.venv/bin/…` instead.
- Tests: `pytest` (157 tests, no network), `ruff check .`, `node tests/js/time.test.mjs`. CI runs all three.
- Running the app needs Ollama with `gemma3:1b` or `gemma3:4b`. Without Ollama it still works, using the
  template/curated fallbacks.
- Browser end-to-end checks (Playwright driving Edge) were run from a scratch environment and are **not**
  in the repo. Journeys used: Pune via geolocation with 3 hobbies; Berlin via city search in dark mode;
  Overpass blocked → single-suggestion fallback; city search-as-you-type ("Pun" → Pune, Maharashtra,
  India without Enter). Reproduce them with Playwright if UI work is done.

## 7. Map of the code

| File | Role | Spec |
|---|---|---|
| `scoring.py` | window scoring and picking | 001 §4.2 |
| `weather.py` | Open-Meteo forecast and geocoding (region + dedupe) | 001 |
| `llm.py`, `prompts.py`, `suggest.py`, `fallbacks.py` | Ollama client, prompts, single activity + curated fallback | 001 §4.3 |
| `hobbies.py`, `places.py`, `ranking.py`, `describe.py` | OSM categories, Overpass client + cache + fallback, ranking, place lines | 002 |
| `main.py` | routes, dependency injection, static files + cache header | 001/002 |
| `static/` | vanilla HTML/CSS/JS (no build step), SVG sprite, light/dark | 003 |

## 8. Open items (all optional)

1. **Suspend both Render services** (`golden-hour`, `golden-hour-ollama`) now that judging is over, to
   save the shared credit. Render's CLI can't suspend: use the dashboard. The Blueprint recreates them.
2. **T12 / T23 / T26 (@human):** use it outside once, take a photo, check it on a phone; optionally add a
   short update to the DEV post.
3. **R9.2:** fewer embellished place lines on 1B (better prompt, or 4B on a bigger plan).
4. Ideas raised but not specced: an installable PWA with local notifications; on-device Gemma.
