from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from .config import ELEXON_BASE


class ElexonError(RuntimeError):
    pass


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    url = f"{ELEXON_BASE}{path}"
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            response = await client.get(url, params=params, timeout=60.0)
            if response.status_code == 429:
                await _sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            await _sleep(1.5 * (attempt + 1))
    raise ElexonError(f"Failed GET {path}: {last_exc}")


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def fetch_wind_actuals(
    client: httpx.AsyncClient,
    settlement_from: date,
    settlement_to: date,
) -> list[dict[str, Any]]:
    """FUELHH WIND outturn, half-hourly MW averages."""
    rows: list[dict[str, Any]] = []
    cursor = settlement_from
    while cursor <= settlement_to:
        chunk_end = min(cursor + timedelta(days=6), settlement_to)
        payload = await _get_json(
            client,
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": cursor.isoformat(),
                "settlementDateTo": chunk_end.isoformat(),
                "fuelType": "WIND",
            },
        )
        if not isinstance(payload, list):
            raise ElexonError("Unexpected FUELHH payload")
        rows.extend(payload)
        cursor = chunk_end + timedelta(days=1)
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("fuelType") != "WIND":
            continue
        start = row.get("startTime")
        if not start or start in seen:
            continue
        seen.add(start)
        cleaned.append(
            {
                "startTime": _norm(start),
                "generation": float(row["generation"]),
                "settlementDate": row.get("settlementDate"),
                "settlementPeriod": row.get("settlementPeriod"),
                "publishTime": _norm(row["publishTime"]) if row.get("publishTime") else None,
            }
        )
    cleaned.sort(key=lambda r: r["startTime"])
    return cleaned


async def fetch_wind_forecasts(
    client: httpx.AsyncClient,
    publish_from: datetime,
    publish_to: datetime,
) -> list[dict[str, Any]]:
    """WINDFOR stream records for a publish-time window."""
    rows: list[dict[str, Any]] = []
    cursor = publish_from
    while cursor < publish_to:
        chunk_end = min(cursor + timedelta(hours=12), publish_to)
        payload = await _get_json(
            client,
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": _fmt(cursor),
                "publishDateTimeTo": _fmt(chunk_end),
            },
        )
        if not isinstance(payload, list):
            raise ElexonError("Unexpected WINDFOR payload")
        rows.extend(payload)
        cursor = chunk_end

    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        start = row.get("startTime")
        published = row.get("publishTime")
        generation = row.get("generation")
        if start is None or published is None or generation is None:
            continue
        key = (published, start)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "publishTime": _norm(published),
                "startTime": _norm(start),
                "generation": float(generation),
            }
        )
    cleaned.sort(key=lambda r: (r["publishTime"], r["startTime"]))
    return cleaned


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return _parse_dt(value)


def _norm(value: str) -> str:
    return _parse_dt(value).strftime("%Y-%m-%dT%H:%M:%SZ")
