# 001 — Golden Hour MVP: Tasks

- **Status:** Approved (2026-10-08)
- **Implements:** [design.md](design.md)
- **Owners:** `@human` = Tanay writes it by hand · `@ai` = Claude · `@human+ai` = pair

Each task is one commit. The commit message starts with the task ID and requirement IDs, e.g.
`T3 (R3.2): score_window baseline`. Tick the box when the "Done when" check passes.

## Ownership change (2026-10-09)

Tanay is studying for the GRE (Monday) and handed the build over to the AI to hit the Sunday deadline. The
original plan had T3, T6 and T9 as `@human`. Tanay wrote the first `score_window` rules, and they're now
`@ai`. Still human-only: **T12** (going outside) and the final edit and submission of **T13** (the post).

| Who | Tasks |
|-----|-------|
| @ai | T1–T11, T14, T13 draft |
| @human | T12, T13 final edit + submit, Render "Apply" click in T10 |

## Schedule (revised)

| Day | @ai | @human |
|-----|-----|--------|
| Thu 10-08 | T1, T2, T4, T11 ✅ | — |
| Fri 10-09 | T3, T5–T10, T13 draft | Render Apply click (2 min) |
| Sat 10-10 | T14 against live URL | GRE prep (optional: T12 as a study break) |
| Sun 10-11 | fixes | T13 review + submit |

## Tasks

### Foundation

- [x] **T1 @ai: Domain models** (R2.1, R3.3, R4.2)
  `models.py` exactly as design §4.1, including the `TimeRange` end > start validator.
  *Done when:* model tests pass. `scoring.py` exists with the five signatures from §4.2, each raising
  `NotImplementedError`.

- [x] **T2 @ai: Open-Meteo client** (R1.2, R3.1)
  `weather.py`: `fetch_forecast(lat, lon) -> Forecast` (2 days, hourly temp/precip-prob/wind/UV/cloud,
  daily sunrise/sunset, `timezone=auto`) and `geocode(q) -> list[Place]`. Recorded fixtures go in
  `tests/fixtures/`.
  *Done when:* tests against `MockTransport` pass and one manual call against the live API succeeds.

- [x] **T11 @ai: CI** (N5)
  GitHub Actions: Python 3.11, `pip install -e .[dev]`, `ruff check .`, `pytest`.
  *Done when:* the badge in the README is green.

### Picking the window

- [x] **T3 @ai (was @human): Scoring** (R2.2, R2.3, R3.2, R3.3)
  Implement `scoring.py` per design §4.2. Suggested order, one commit each:
  1. `weather_for` + tests
  2. `score_window` + table-driven tests (rainy, hot, windy, perfect, golden hour)
  3. `candidate_windows` + tests (quarter-hour alignment, `now` mid-range, range shorter than 20 min,
     sunset cut-off)
  4. `pick_windows` + test (non-overlap, tie → earlier)
  5. `plan_day` + tests (empty ranges, the "tomorrow" fallback)

  Ask the AI for hints, a review, or test scaffolding whenever you like. It won't write the implementation.
  *Done when:* all scoring tests pass and the §4.2 numbers match the code, or the spec is updated to match.

- [x] **T4 @ai: `/api/geocode` + `/api/plan` routes** (R1.2, R1.3, R2, R3) _(live real-plan check done 2026-10-09)_
  Wire the routes with `get_weather` / `get_now` dependencies; 502 on upstream failure. Before T3 lands,
  tests override the scoring dependency with a fake.
  *Done when:* API tests pass, and `/api/plan` returns a real plan locally once T3 is merged.

### The suggestion

- [x] **T5 @ai: Ollama client** (R4.2, R6.2, R6.3)
  `llm.py` `OllamaClient.chat_json`; the schema comes from `Suggestion` minus `source`; `GH_OLLAMA_URL`
  normalization in `config.py`; `GH_LLM_TIMEOUT_S` setting.
  *Done when:* `MockTransport` tests pass and a manual call against local `gemma3:4b` returns valid JSON.

- [x] **T6 @ai (was @human): Prompt + fallbacks** (R4.1, R4.3, R4.4)
  `prompts.build_messages(ctx)` and `fallbacks.py` (≥ 8 activities with tags, `pick_fallback`). Try the
  prompt against both `gemma3:1b` and `gemma3:4b` locally and note the differences. That's material for
  the post.
  *Done when:* the prompt test asserts that duration, weather, time of day and constraints appear in the
  messages; the fallback test covers rain, short windows and golden hour.

- [x] **T7 @ai: Suggest service + `/api/suggest`** (R4.1–R4.4)
  `suggest.py` (validate, truncate, fall back, log without context) and the route.
  *Done when:* tests cover valid output, malformed JSON, timeout and over-long lists.

### Frontend

- [ ] **T8 @ai: Page shell** (R1.1, R1.2, R2.1, R3.3, R3.4, R4.5, N3)
  `index.html`, `app.js`, `style.css`: location with city fallback, free-range inputs, plan card +
  alternates, suggestion loading/progress, °C/°F toggle. Leaves mount points for T9.
  *Done when:* the full flow works locally at 360 px wide; page weight < 200 KB.

- [ ] **T9 @ai (was @human): Countdown + calendar** (R5.1, R5.2)
  `static/time.js` per design §4.5, hooked into the mount points from T8.
  *Done when:* the countdown passes through "in Xm" → "now — go!" → "done", and the downloaded `.ics`
  imports correctly into Google Calendar and your phone's calendar at the right local time.

### Ship

- [ ] **T10 @ai: Render deployment** (R6.1, R6.2, N4)
  `ollama/Dockerfile` (model baked in at build time), the two-service `render.yaml`, deploy via Blueprint.
  You click "Apply" in the Render dashboard; the AI can't log in for you.
  *Done when:* the live URL's health check is OK and a suggestion comes back with `source: "model"` in
  ≤ 45 s.

- [ ] **T14 @ai: Acceptance check** (all)
  Run the checklist below against the live URL and fix or log anything that fails.

- [ ] **T12 @human: Touch grass** (D4)
  Use the deployed app for real at least once: screenshot the plan and suggestion, do the activity, take
  photos, and note what the model got right or wrong.

- [ ] **T13 @human+ai: DEV post + submit** (D1–D4)
  Template sections: What I Built, Demo, Code, How I Built It, **Why Open Innovation Matters**. Tag the
  Render + Gemma categories. The AI drafts the outline and edits; the voice and the outdoor story are yours.
  Submit before 2026-10-11 end of day.

## Acceptance checklist (T14)

| AC | Check | ✓ |
|----|-------|---|
| R1.1 / R1.2 | Allow location → plan works; deny → city search works | |
| R1.3 / N2 | Server logs contain no coordinates | |
| R2.1 / R2.2 | Two ranges respected; no ranges → now until sunset | |
| R2.3 | Late at night → tomorrow's window with a note | |
| R3.1–R3.3 | Best + ≤ 2 alternates with reasons; matches the forecast | |
| R3.4 | °F toggle converts and persists | |
| R4.1–R4.3 | Suggestion fits the window, ≤ 3 steps, walking distance, nothing to buy | |
| R4.4 | Ollama stopped → fallback shown, window still shown | |
| R4.5 / N1 | Window ≤ 2 s; suggestion ≤ 45 s with progress | |
| R5.1 / R5.2 | `.ics` imports correctly; countdown runs | |
| R6.1–R6.3 | Blueprint deploy works; local run needs no keys | |
| N3 | Usable at 360 px | |
| N4 | Render usage dashboard is on track for under $50 | |
