from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.scrapers import WeeklyMenuService


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Weekly Lunch Menu Aggregator")
service = WeeklyMenuService()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/menu")
def read_menu() -> dict:
    """Return the aggregated weekly menu for both restaurants."""

    return service.get_menu()


@app.get("/")
def index() -> FileResponse:
    """Serve the frontend as a single static page."""

    return FileResponse(STATIC_DIR / "index.html")
