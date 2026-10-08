# 001 — Golden Hour MVP: Requirements

- **Status:** Approved (2026-10-08)
- **Owner:** @Tanay3484
- **Deadline:** submission due 2026-10-11 (DEV Hacktoberfest Week 1, "Touch Grass")

## 1. Problem

People *intend* to go outside but don't, because "when?" and "to do what?" are two small decisions that are
easy to put off. Weather apps answer "what's it like", not "go now, do this".

## 2. Product statement

Golden Hour picks **one** 20–40 minute window today when it's good to be outside, and suggests **one**
specific, low-effort activity for it. The suggestion is written by an open-weight model (Gemma) running on
infrastructure we control, using only open data.

## 3. Users

- **Primary:** a desk-bound person (student, remote worker, developer) with fragmented free time.
- **Context of use:** checks the app once in the morning or at a break, on phone or laptop.

## 4. User stories & acceptance criteria

### R1 — Location
*As a user, I want the app to know roughly where I am, so weather and sunset are correct.*

- R1.1 WHEN the user opens the app, the system SHALL request browser geolocation.
- R1.2 IF geolocation is denied or unavailable, THEN the system SHALL let the user enter a city name and
  resolve it to coordinates.
- R1.3 The system SHALL NOT store the user's location on the server beyond the lifetime of a request.

### R2 — Free time
*As a user, I want to tell the app when I'm free, so suggestions fit my day.*

- R2.1 The system SHALL let the user enter one or more free time ranges for today (e.g. 12:30–13:15).
- R2.2 IF the user enters no ranges, THEN the system SHALL assume they are free from now until sunset.
- R2.3 IF no free range of at least 20 minutes remains today, THEN the system SHALL say so and offer
  tomorrow's best window instead.

### R3 — Picking the window
*As a user, I want the best window chosen for me, so I don't have to read a forecast.*

- R3.1 The system SHALL fetch today's hourly forecast (temperature, precipitation probability, wind, UV,
  cloud cover) and sunrise/sunset for the user's location from an open, keyless weather API.
- R3.2 The system SHALL score each candidate 20–40 minute slot inside the user's free ranges using a
  deterministic, unit-tested function (dry, comfortable temperature, low wind, daylight; bonus near golden
  hour).
- R3.3 The system SHALL return the top-scoring slot plus up to two alternates, each with a one-line reason.
- R3.4 The UI SHALL display temperatures in °C by default, with a °F toggle (client-side conversion).

### R4 — The suggestion (AI)
*As a user, I want one concrete thing to do outside, so I actually go.*

- R4.1 WHEN a window is chosen, the system SHALL ask an open-weight Gemma model for a single activity that
  fits the duration, weather, and time of day.
- R4.2 The model response SHALL be constrained to a JSON schema: `title`, `steps` (≤3), `what_to_notice`,
  `bring` (≤3 items).
- R4.3 The suggestion SHALL require no purchase, booking, or travel beyond walking distance.
- R4.4 IF the model is unreachable or returns invalid output, THEN the system SHALL still show the window
  with a fallback activity from a curated list.
- R4.5 WHILE the suggestion is being generated, the system SHALL show progress, and SHALL display the
  chosen window immediately (the window is not blocked on the model).

### R5 — Going outside
*As a user, I want a nudge at the right time, so I don't forget.*

- R5.1 The system SHALL offer an "Add to calendar" (.ics download) for the chosen window.
- R5.2 The system SHALL show a countdown to the window start while the page is open.

### R6 — Deployment & openness
- R6.1 The system SHALL be deployable to Render via `render.yaml` (one-click Blueprint).
- R6.2 The deployed model SHALL be an open-weight model served by open-source software (Ollama) on our own
  Render service — no closed, third-party LLM API.
- R6.3 The system SHALL also run fully locally (`ollama` + `uvicorn`) with no account or API key.

## 5. Non-functional requirements

- N1 **Latency:** window shown ≤ 2 s after submit; AI suggestion ≤ 45 s on Render CPU (with progress shown).
- N2 **Privacy:** no accounts, no analytics, no persistence of location or schedule.
- N3 **Mobile-first:** usable at 360 px width; page weight < 200 KB excluding fonts.
- N4 **Cost:** total Render spend fits inside the $50 credit through judging (~2026-10-19).
- N5 **Quality:** `pytest` and `ruff` pass in CI on every push.

## 6. Non-goals (MVP)

- Accounts, history, streaks, social features.
- Reading the user's real calendar (Google/Outlook) or importing `.ics` files.
- Push notifications when the page is closed.
- Route/map generation.

## 7. Submission deliverables (challenge-driven)

- D1 Public repo with MIT license and run instructions.
- D2 Live demo URL on Render.
- D3 DEV post following the template: What I Built, Demo, Code, How I Built It, **Why Open Innovation Matters**.
- D4 Bonus: actually use it outside and document the experience (photos + what the model suggested).

## 8. Decisions (formerly open questions)

Resolved with the proposed defaults on 2026-10-08. Override any of them during review.

1. **Model size.** `gemma3:1b` on Render (CPU, ~2 GB instance); `gemma3:4b` locally. Switch via `GH_MODEL`.
2. **Free-time input.** Manual ranges only. `.ics` *import* is a non-goal for the MVP.
3. **Units.** Metric by default, °F toggle in the UI (→ R3.4).
4. **Partner prizes.** Target *Best Use of Render* and *Best Use of Gemma*.

## Changelog

- 2026-10-07 — Initial draft.
- 2026-10-08 — Resolved open questions with defaults; added R3.4.
