from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import CACHE_PATH, DELIVERY_END, DELIVERY_START, LONDON, PUBLISH_FROM, PUBLISH_TO
from .elexon import fetch_wind_actuals, fetch_wind_forecasts, parse_iso
from .metrics import by_day, by_hour, by_wind_level, summarise, trading_implications
from .processing import (
    aligned_pairs,
    available_vintages_for_day,
    decision_cutoff_utc,
    decision_vintage,
    hourly_actuals,
    series_for_vintage,
)


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"Processed cache missing at {CACHE_PATH}. Run: python -m app.ingest"
        )
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


async def build_cache() -> dict[str, Any]:
    import httpx

    delivery_from = date.fromisoformat(DELIVERY_START)
    delivery_to = date.fromisoformat(DELIVERY_END)
    publish_from = parse_iso(PUBLISH_FROM)
    publish_to = parse_iso(PUBLISH_TO)

    async with httpx.AsyncClient(headers={"Accept": "application/json"}) as client:
        actuals = await fetch_wind_actuals(client, delivery_from, delivery_to)
        forecasts = await fetch_wind_forecasts(client, publish_from, publish_to)

    hourly = hourly_actuals(actuals)
    pairs = aligned_pairs(forecasts, hourly, delivery_from, delivery_to)
    summary = summarise(pairs)

    payload = {
        "meta": {
            "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "Elexon BMRS",
            "actualDataset": "FUELHH fuelType=WIND",
            "forecastDataset": "WINDFOR",
            "deliveryFrom": DELIVERY_START,
            "deliveryTo": DELIVERY_END,
            "decisionRule": (
                "For delivery day D, use the latest WINDFOR publishTime strictly "
                "before 09:20 Europe/London on D-1 (EPEX SPOT GB 60-min DA gate)."
            ),
            "alignment": (
                "WINDFOR is hourly. FUELHH is 30-minute; two settlement periods "
                "are averaged to the hour beginning HH:00 UTC."
            ),
            "errorSign": "error = forecast - actual; positive means wind was over-forecast.",
            "actualPoints": len(actuals),
            "forecastPoints": len(forecasts),
            "alignedHours": len(pairs),
        },
        "actualsHalfHourly": actuals,
        "forecasts": forecasts,
        "pairs": pairs,
        "summary": summary,
        "byHour": by_hour(pairs),
        "byDay": by_day(pairs),
        "byWindLevel": by_wind_level(pairs),
        "implications": trading_implications(summary),
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def dashboard(cache: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": cache["meta"],
        "summary": cache["summary"],
        "byHour": cache["byHour"],
        "byDay": cache["byDay"],
        "byWindLevel": cache["byWindLevel"],
        "implications": cache["implications"],
    }


def decision_view(cache: dict[str, Any], delivery: date) -> dict[str, Any]:
    forecasts = cache["forecasts"]
    hourly = hourly_actuals(cache["actualsHalfHourly"])
    vintage = decision_vintage(forecasts, delivery)
    cutoff = decision_cutoff_utc(delivery)
    curve: list[dict[str, Any]] = []
    if vintage:
        for point in series_for_vintage(forecasts, vintage, delivery):
            actual = hourly.get(point["startTime"])
            actual_mw = actual["generationMw"] if actual else None
            forecast_mw = point["forecastMw"]
            curve.append(
                {
                    "startTime": point["startTime"],
                    "hourUk": parse_iso(point["startTime"]).astimezone(LONDON).hour,
                    "forecastMw": round(forecast_mw, 1),
                    "actualMw": None if actual_mw is None else round(actual_mw, 1),
                    "errorMw": None
                    if actual_mw is None
                    else round(forecast_mw - actual_mw, 1),
                }
            )
    day_pairs = [p for p in cache["pairs"] if p["deliveryDate"] == delivery.isoformat()]
    p90 = cache["summary"].get("p90AbsErrorMw") or 0
    for point in curve:
        if p90:
            point["bandLowMw"] = round(max(0.0, point["forecastMw"] - p90), 1)
            point["bandHighMw"] = round(point["forecastMw"] + p90, 1)
    energy_forecast = sum(p["forecastMw"] for p in curve) / 1000.0 if curve else 0
    actual_points = [p["actualMw"] for p in curve if p["actualMw"] is not None]
    energy_actual = sum(actual_points) / 1000.0 if actual_points else 0
    return {
        "deliveryDate": delivery.isoformat(),
        "decisionDate": (delivery - timedelta(days=1)).isoformat(),
        "decisionCutoffUk": cutoff.astimezone(LONDON).isoformat(),
        "publishTimeUsed": vintage,
        "vintages": available_vintages_for_day(forecasts, delivery),
        "curve": curve,
        "daySummary": summarise(day_pairs),
        "forecastEnergyGwh": round(energy_forecast, 2),
        "actualEnergyGwh": round(energy_actual, 2),
        "uncertaintyBandMw": p90,
        "peakForecastMw": max((p["forecastMw"] for p in curve), default=None),
        "troughForecastMw": min((p["forecastMw"] for p in curve), default=None),
    }
