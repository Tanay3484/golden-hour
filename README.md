# 🌅 Golden Hour

[![CI](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml/badge.svg)](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Tanay3484/golden-hour)

> Your best 20–40 minutes outside today, and one small thing to do with them.

Tell Golden Hour when you're free. It checks the hourly forecast and sunset for where you are, picks the
nicest window to be outside, and asks an open-weight model ([Gemma](https://ai.google.dev/gemma), served by
[Ollama](https://ollama.com)) for one specific, walking-distance thing to do. You get a countdown and a
calendar invite with a 10-minute reminder.

Built for the DEV [Hacktoberfest 2026 Open-Source AI Challenge, Week 1: "Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## How it works

```
Browser ──▶ FastAPI ──▶ Open-Meteo (forecast + sunset, open data, no key)
                │
                ├─ scoring.py   deterministic: every 20–40 min slot in your free time, scored 0–100
                │               (rain, temperature, wind, UV, +15 for golden hour)
                │
                └─ Ollama ──▶ Gemma writes ONE activity for the chosen slot (JSON-schema output)
                              └─ curated fallback if the model is slow, down, or returns junk
```

- **Picking the time is plain, tested Python**, so it's fast, explainable and always works.
- **The model only does the creative part**: turning "18:00–18:40, 14 °C, 45% rain, golden hour" into
  something worth getting up for. Its output is constrained to a JSON schema and validated; if anything
  goes wrong you still get a hand-written activity.
- **Privacy:** no accounts, no analytics. Coordinates are used for one forecast lookup and never logged or
  stored; the model never sees them.

## Why open models

- **It runs where you choose.** Locally on a laptop, or on a single small CPU server on Render. No API key,
  no per-request bill, no third party reading where you are and when you're free.
- **It's inspectable.** The prompt, the scoring rules and the model weights are all open, so you can see
  exactly why it picked 18:00.
- **It's swappable.** `GH_MODEL=gemma3:4b` locally for better suggestions, `gemma3:1b` in production to fit
  a 2 GB instance. Any Ollama model works.

## Run it locally

Needs Python 3.11+ and [Ollama](https://ollama.com/download).

```bash
ollama pull gemma3:4b
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn golden_hour.main:app --reload
```

Open http://localhost:8000. Settings (env vars or `.env`, see [`.env.example`](.env.example)):

| Variable | Default | |
|----------|---------|---|
| `GH_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `GH_MODEL` | `gemma3:4b` | any Ollama model with JSON output |
| `GH_LLM_TIMEOUT_S` | `60` | after this the curated fallback is used |

## Deploy to Render

Click **Deploy to Render** above (or *New → Blueprint* in the dashboard). [`render.yaml`](render.yaml)
creates two services in one region:

- `golden-hour`: the public web app (`0.5c-512mb`)
- `golden-hour-ollama`: a private Ollama server with `gemma3:1b` baked into the image (`1c-2g`)

The web app finds Ollama over Render's private network; nothing else needs configuring. On a shared CPU
`gemma3:1b` answers in a few seconds to about 30 s, and the page shows progress while it thinks.

## Development

```bash
pytest                       # 79 Python tests, no network needed
ruff check .
node tests/js/time.test.mjs  # countdown + calendar export
```

This project was built spec-first: requirements → design → tasks, each approved before code. See
[`specs/`](specs/) for the full trail, including what changed along the way and why.

## License

MIT
