# 002 — Nearby places for your hobbies: Requirements

- **Status:** Draft — awaiting review
- **Owner:** @Tanay3484
- **Builds on:** [001 Golden Hour MVP](../001-golden-hour-mvp/requirements.md) (requirement IDs continue from R6)
- **Deadline:** must not put the 001 submission at risk (due 2026-10-11 23:59 PDT)

## 1. Problem

The MVP's "What to do" is one generic activity written by the model ("walk to the nearest patch of green").
It doesn't know what's actually around you or what you enjoy, so it's easy to ignore. Early testing also
showed the model invents real-sounding places ("Elm Street") when it has nothing real to work with.

## 2. Product statement

Golden Hour suggests the **top 5 real places within walking distance** of you that suit your hobbies and
the chosen window. Each comes with one line from Gemma on what to do there right now. Places come from
**OpenStreetMap** (open data), so the model is grounded in real places instead of making them up.

**Places, not events.** There is no open, keyless source of local events, and event APIs are mostly
ticketed, which conflicts with the "nothing to buy" rule (R4.3). Events are out of scope.

## 3. Spike findings (2026-10-09)

Measured before writing this spec; details in [design.md §2](design.md#2-spike-findings).

- Public Overpass servers are **unreliable**: in one evening, 2 of 3 public instances failed for every
  city, and the main one returned 504 "server too busy" for Pune and Mumbai unless the query allowed
  ≥ 25 s. When it works, it takes about 2–11 s.
- Asking Gemma to *rank* places doesn't help: both sizes mostly picked the first five in list order.
  Asked for detail, they invented facts (4B called a memorial the "Frauenkirche").
  → **Code ranks; Gemma only writes the lines, using only the facts it's given.**
- gemma3:1b wrote 5 lines in 7.8 s on a laptop (about 30–40 s expected on Render's 1 CPU); 4B took 26 s
  on a laptop, which is too slow for Render.

## 4. User stories & acceptance criteria

### R7 — Hobbies
*As a user, I want to tell the app what I enjoy once, so suggestions feel like mine.*

- R7.1 The system SHALL offer a fixed list of hobbies (photography, nature & birds, history, art,
  running & walking, reading & sketching, coffee outside, sports) and let the user pick up to 3.
- R7.2 Picking hobbies SHALL be optional. IF none are picked, THEN the system SHALL treat the user as
  interested in all of them.
- R7.3 The system SHALL remember the picks on the user's device only (no accounts, nothing stored on the
  server).

### R8 — Nearby places
*As a user, I want real places near me that fit my hobbies, so I have somewhere to go.*

- R8.1 WHEN a window is chosen, the system SHALL look up named public places from OpenStreetMap within
  walking distance: a third of the window each way at 80 m/min, so there's time to walk there, spend a
  while, and walk back (a 40-minute window gives about 13 minutes' walk, roughly 1.1 km).
- R8.2 The system SHALL pick the top 5 using a deterministic, unit-tested ranking: hobby match, walking
  time, weather fit (covered places score higher when rain ≥ 50%; open views and water score higher at
  golden hour) and variety (at most 2 of the same kind).
- R8.3 Each place SHALL show its name, kind, walking time and a link to it on the OpenStreetMap map.
- R8.4 The place list SHALL appear without waiting for the model.
- R8.5 The UI SHALL show "Places © OpenStreetMap contributors" wherever OSM data is shown (ODbL licence).

### R9 — Gemma's line for each place
*As a user, I want to know why each place is worth it right now.*

- R9.1 WHEN the 5 places are shown, the system SHALL ask Gemma for one sentence per place (≤ 20 words)
  on what to do or notice there in this window.
- R9.2 The prompt SHALL tell the model to use only the facts provided and to not state history or
  features of a place that aren't in its data.
- R9.3 IF the model is unreachable or returns invalid output for a place, THEN the system SHALL show a
  template line for that kind of place instead (e.g. viewpoint: "Watch the light change over the view.").

### R10 — Reliability & privacy
- R10.1 IF OpenStreetMap is unavailable or finds fewer than 3 matching places, THEN the system SHALL show
  the MVP's single activity suggestion (R4) instead. The page SHALL never break or wait more than 25 s
  for places.
- R10.2 The system SHALL send OpenStreetMap only coordinates rounded to 3 decimals (about 110 m), with an
  identifying User-Agent as the Overpass usage policy requires.
- R10.3 The system MAY cache place results in server memory, keyed by a rounded grid cell (about 1 km),
  for at most 6 hours. The cache holds only public place data, is never written to disk or logs, and is
  cleared on restart. *(This amends R1.3 / N2; see decision 3 below.)*
- R10.4 The privacy note on the page SHALL say that the rounded location is sent to OpenStreetMap to find
  places.

## 5. Non-functional

- N6 **Latency:** place list ≤ 25 s worst case, typically ≤ 10 s; Gemma lines ≤ 60 s on Render, with
  progress shown per line.
- N7 **Load on OSM:** at most 1 Overpass request per window choice; cached repeats make 0 requests.
- N8 **Quality:** ranking, query building, response parsing and fallbacks covered by tests that don't
  touch the network.

## 6. Non-goals

- Events, opening hours, ratings and reviews; routing or turn-by-turn directions; hobby-specific
  wording beyond one line; saving favourite places.

## 7. Decisions for review

1. **Code ranks, Gemma writes the lines** (spike: Gemma's "ranking" was list order). The UI calls it
   "Top 5 near you", not "Gemma's top 5".
2. **Replace, don't add:** the 5 places *replace* the single activity in "What to do". The single
   activity stays as the fallback (R10.1). This keeps it to one model call per window, which matters on
   1 CPU.
3. **Cache vs strict no-storage:** R1.3 currently says the server keeps no location beyond a request. A
   ~1 km grid-cell cache (memory only, 6 h) means far fewer Overpass calls and survives server outages
   for repeat visits, but it does keep "someone looked near here". **Recommendation:** allow the cache
   (R10.3) and amend R1.3. The alternative is no cache: stricter privacy, more 504s.
4. **Ship gate:** 002 goes into the submission only if it passes its acceptance checks on the live
   Render URL by Saturday 2026-10-10 evening IST. Otherwise the submission ships with 001 and 002 lands
   afterwards.

## Changelog

- 2026-10-09 — Initial draft, informed by the Overpass and Gemma spike.
