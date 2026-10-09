# 🌅 Golden Hour

[![CI](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml/badge.svg)](https://github.com/Tanay3484/golden-hour/actions/workflows/ci.yml)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Tanay3484/golden-hour)

> Your best 20–40 minutes outside today, and one small thing to do with them.

Tell Golden Hour when you're free. It checks the hourly forecast and sunset for where you are, picks the
nicest window to be outside, and finds the **top 5 real places within walking distance** that suit your
hobbies, from [OpenStreetMap](https://www.openstreetmap.org). An open-weight model
([Gemma](https://ai.google.dev/gemma), served by [Ollama](https://ollama.com)) writes one line for each on
what to do there right now. You get a countdown and a calendar invite with a 10-minute reminder.

Built for the DEV [Hacktoberfest 2026 Open-Source AI Challenge, Week 1: "Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## How it works

```
Browser ──▶ FastAPI ──▶ Open-Meteo (forecast + sunset, open data, no key)
                │
                ├─ scoring.py   deterministic: every 20–40 min slot in your free time, scored 0–100
                │               (rain, temperature, wind, UV, +15 for golden hour)
                │
                ├─ places.py ──▶ OpenStreetMap (Overpass): named parks, views, water, art, history…
                │   ranking.py   top 5 by your hobbies, walking time, weather and variety
                │
                └─ Ollama ──▶ Gemma writes one line per place, using only OSM facts (JSON-schema output)
                              └─ template lines if the model is slow, down, or puts a line on the wrong place
                              └─ no places found? one Gemma-written activity instead, with a curated fallback
```

- **Picking the time is plain, tested Python**, so it's fast, explainable and always works.
- **The model only does the creative part**: turning "18:00–18:40, 14 °C, 45% rain, golden hour" into
  something worth getting up for. Its output is constrained to a JSON schema and validated; if anything
  goes wrong you still get a hand-written activity.
- **Code ranks, the model describes.** In testing, small models asked to "pick the best 5" just picked the
  first five, and invented details about real places. So plain code picks, and each line is checked
  against the place it belongs to.
- **Privacy:** no accounts, no analytics. Precise coordinates are used for the forecast and walking times
  and never logged or stored. OpenStreetMap only sees the centre of your ~1 km area; nearby-place results
  are cached in memory per area for up to 6 hours. The model never sees coordinates.

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
