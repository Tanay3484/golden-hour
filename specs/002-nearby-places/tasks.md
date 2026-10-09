# 002 — Nearby places for your hobbies: Tasks

- **Status:** Approved (2026-10-09)
- **Implements:** [design.md](design.md)
- **Owners:** `@ai` builds (handover of 2026-10-09 still applies); `@human` approves and field-tests

Same rules as 001: one task ≈ one commit, commit messages carry task and requirement IDs, tick the box when
"Done when" passes. Branch: stacked on `t10-render`, one PR for all of 002.

## Tasks

- [x] **T15 @ai: Hobbies + categories** (R7.1, R7.2)
  `hobbies.py` with the two tables from design §3, `categories_for(hobbies)`, and a template line per
  category.
  *Done when:* tests cover every hobby mapping and the "no hobbies → all categories" case.

- [x] **T16 @ai: Overpass client + cache** (R8.1, R10.1–R10.3, N7)
  `places.py`: `build_query`, `parse_elements`, `haversine_m`, `OverpassClient.nearby` with endpoint
  failover, 25 s budget, User-Agent and `PlaceCache`. Record a fresh Pune fixture when Overpass allows it.
  *Done when:* `MockTransport` tests pass (504 → failover, both down → `[]`, cache hit makes 0 requests),
  and one live call each for Pune and Berlin succeeds or degrades to `[]` within 25 s.

- [x] **T17 @ai: Ranking** (R8.2)
  `ranking.py` `rank_places` per design §4.3.
  *Done when:* table-driven tests for hobby match, rain → covered, golden hour, the variety cap, tie-breaks
  and < 3 → `[]`.

- [x] **T18 @ai: Describe with Gemma** (R9.1–R9.3) _(1B still embellishes; bar met by 4B only, see design changelog)_
  `prompts.build_place_messages`, `describe.py` with validation and templates.
  *Done when:* unit tests pass, and a local run on the Berlin fixture with gemma3:1b and 4b invents no
  facts in 3 tries each (checked by hand; findings go in the design changelog).

- [x] **T19 @ai: API routes** (R8, R9, R10.1)
  `POST /api/places`, `POST /api/places/describe` with dependency overrides.
  *Done when:* API tests pass, including OSM down → `places: []` with status 200.

- [x] **T20 @ai: Frontend** (R7.1–R7.3, R8.3–R8.5, R10.1, R10.4)
  Hobby chips, "Top 5 near you" card with line skeletons, attribution, map links, fallback to the
  single suggestion, updated privacy note.
  *Done when:* the Playwright run passes at 360 px in light and dark (Pune via geolocation, Berlin via
  search, Overpass blocked → fallback card); no console errors; page still < 200 KB.

- [x] **T21 @ai: Docs + spec updates** (R10.3 amendment)
  Amend 001 R1.3 / N2 for the place cache if decision 3 is approved; README "How it works"; update the
  post draft's "How I Built It".
  *Done when:* specs, README and draft agree with the code.

- [ ] **T22 @ai: Live acceptance on Render** (all of 002)
  After deploy, run the checklist below against the live URL.

- [ ] **T23 @human: Use it outside once** (D4, shared with 001 T12)
  Pick a hobby, go to one of the 5 places, take a photo for the post.

## Acceptance checklist (T22)

| AC | Check | ✓ |
|----|-------|---|
| R7.1–R7.3 | Pick 3 hobbies → reload → still picked; 4th can't be added; none picked works | |
| R8.1 | All places within ~⅓ of the window's walk; longer window → wider radius | |
| R8.2 | Photography at golden hour → views/water first; rain ≥ 50% → covered places first; ≤ 2 per kind | |
| R8.3 / R8.5 | Name, kind, minutes, Map link opens the right place; attribution visible | |
| R8.4 / N6 | List appears before the lines; list ≤ 25 s, lines ≤ 60 s | |
| R9.2 | Lines don't state facts that aren't in OSM data (spot-check 10) | |
| R9.3 | Ollama stopped → template lines, list still shown | |
| R10.1 | Overpass unreachable → single suggestion with note, within 25 s | |
| R10.2 | Request to Overpass uses 3-decimal coordinates and the Golden Hour User-Agent | |
| R10.3 | Second request for the same area makes no Overpass call; nothing written to disk or logs | |
| R10.4 | Footer privacy text updated | |

## Estimate

About 5–6 hours for T15–T21, plus T22 after deploy. With approval tonight it can be on the live URL by
Saturday, inside the ship gate (requirements decision 4).
