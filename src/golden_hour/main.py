from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from golden_hour import __version__
from golden_hour.config import settings

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Golden Hour", version=__version__)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "model": settings.model}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
