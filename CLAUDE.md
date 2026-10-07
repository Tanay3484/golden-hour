# Golden Hour — agent guide

Hacktoberfest 2026 Week 1 ("Touch Grass") entry. FastAPI + Gemma via Ollama, deployed on Render.

## Workflow (AI-PDLC) — read `specs/README.md` first

- Never write feature code for a spec whose `tasks.md` is not `Status: Approved`.
- Draft one phase at a time (requirements → design → tasks), then stop and ask for review.
- When implementing, work task-by-task from `tasks.md`; tick the box and reference task + requirement IDs in
  the commit message. If the spec is wrong, propose a spec edit before changing code.
- Tasks marked `@human` are the maintainer's to write by hand. Don't implement them; only help (hints,
  review, tests-first stubs) when asked.

## Commands

- Install: `python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"`
- Run: `.venv/Scripts/uvicorn golden_hour.main:app --reload`
- Test / lint: `.venv/Scripts/pytest` · `.venv/Scripts/ruff check .`

## Conventions

- Source in `src/golden_hour/`, tests mirror modules in `tests/`.
- Config only via `golden_hour.config.settings` (env prefix `GH_`).
- External calls (weather, Ollama) go through small client modules so tests can stub them; no network in tests.
