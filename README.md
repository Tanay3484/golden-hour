# Golden Hour

[![CI](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml/badge.svg)](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml)

> Your best 20–40 minutes outside today — planned by an open-weight model running on your own machine.

Golden Hour looks at today's weather, sunset time, and the free time you have, then uses a locally-running
[Gemma](https://ai.google.dev/gemma) model (via [Ollama](https://ollama.com)) to suggest one small, specific
outdoor activity and the best moment to do it.

Built for the [DEV Hacktoberfest 2026 Open-Source AI Challenge — Week 1: "Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## Quick start

```bash
ollama pull gemma3:4b
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn golden_hour.main:app --reload
```

Open http://localhost:8000.

## Development

```bash
pytest
ruff check .
```

Specs live in [`specs/`](specs/) — see [`specs/README.md`](specs/README.md) for the workflow.

## License

MIT
