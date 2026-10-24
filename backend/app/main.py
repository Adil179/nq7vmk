from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import DELIVERY_END, DELIVERY_START
from .store import dashboard, decision_view, load_cache

app = FastAPI(
    title="Day-ahead wind desk",
    description="GB national wind forecast vs outturn for January 2026 DA decisions.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache = None


def cache():
    global _cache
    if _cache is None:
        _cache = load_cache()
    return _cache


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/overview")
def overview():
    return dashboard(cache())


@app.get("/api/series")
def series():
    data = cache()
    return {
        "pairs": data["pairs"],
        "byDay": data["byDay"],
        "byHour": data["byHour"],
    }


@app.get("/api/decision")
def decision(
    deliveryDate: str = Query(..., description="Delivery day YYYY-MM-DD in January 2026"),
):
    try:
        delivery = date.fromisoformat(deliveryDate)
    except ValueError as exc:
        raise HTTPException(400, "deliveryDate must be YYYY-MM-DD") from exc
    start = date.fromisoformat(DELIVERY_START)
    end = date.fromisoformat(DELIVERY_END)
    if delivery < start or delivery > end:
        raise HTTPException(400, f"deliveryDate must be between {DELIVERY_START} and {DELIVERY_END}")
    return decision_view(cache(), delivery)


_here = Path(__file__).resolve().parent
static_candidates = [
    _here.parent / "static",
    _here.parent.parent / "frontend" / "dist",
]
static_dir = next((path for path in static_candidates if path.exists()), None)
if static_dir is not None:
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")
