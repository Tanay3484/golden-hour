# 003 — Visual redesign: Tasks

- **Status:** Approved (2026-10-10)
- **Implements:** [design.md](design.md)

- [x] **T24 @ai: Redesign** (V1–V5, V7)
  New `index.html`, `style.css`, `app.js` per design. *Prototype exists on `spike-003-redesign`; on
  approval it becomes the implementation.*
  *Done when:* screenshots at 1440 px (light) and 390 px (dark) match the design; page < 200 KB.

- [ ] **T25 @ai: Regression check** (V6)
  *Done when:* `pytest`, `ruff`, `node tests/js/time.test.mjs`, and the three browser journeys pass
  locally, then once more on the live URL after deploy.

- [ ] **T26 @human: Look at it on your own phone**
  Open the live URL on your phone and say if anything feels off.
