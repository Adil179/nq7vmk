from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .config import DA_GATE_HOUR, DA_GATE_MINUTE, LONDON
from .elexon import parse_iso


def london_day(dt: datetime) -> date:
    return dt.astimezone(LONDON).date()


def decision_cutoff_utc(delivery_day: date) -> datetime:
    """Latest instant a DA 60-min bid can be submitted for `delivery_day`."""
    decision_day = delivery_day - timedelta(days=1)
    local = datetime.combine(
        decision_day,
        time(DA_GATE_HOUR, DA_GATE_MINUTE),
        tzinfo=LONDON,
    )
    return local.astimezone(timezone.utc)


def hourly_actuals(actual_hh: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Average two 30-minute FUELHH periods into an hour beginning at HH:00."""
    buckets: dict[str, list[float]] = defaultdict(list)
    meta: dict[str, dict[str, Any]] = {}
    for row in actual_hh:
        start = parse_iso(row["startTime"])
        hour = start.replace(minute=0, second=0, microsecond=0)
        key = hour.strftime("%Y-%m-%dT%H:%M:%SZ")
        buckets[key].append(float(row["generation"]))
        meta[key] = {
            "startTime": key,
            "settlementDate": london_day(hour).isoformat(),
        }
    out: dict[str, dict[str, Any]] = {}
    for key, values in buckets.items():
        out[key] = {
            **meta[key],
            "generationMw": sum(values) / len(values),
            "halfHourCount": len(values),
        }
    return out


def decision_vintage(
    forecasts: list[dict[str, Any]],
    delivery_day: date,
) -> str | None:
    """Latest WINDFOR publishTime strictly before the D-1 09:20 UK gate."""
    cutoff = decision_cutoff_utc(delivery_day)
    eligible: list[datetime] = []
    for row in forecasts:
        published = parse_iso(row["publishTime"])
        start = parse_iso(row["startTime"])
        if london_day(start) != delivery_day:
            continue
        if published < cutoff:
            eligible.append(published)
    if not eligible:
        return None
    latest = max(eligible)
    return latest.strftime("%Y-%m-%dT%H:%M:%SZ")


def series_for_vintage(
    forecasts: list[dict[str, Any]],
    publish_time: str,
    delivery_day: date,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in forecasts
        if row["publishTime"] == publish_time
        and london_day(parse_iso(row["startTime"])) == delivery_day
    ]
    rows.sort(key=lambda r: r["startTime"])
    # Keep one value per hour (first if duplicates).
    by_hour: dict[str, dict[str, Any]] = {}
    for row in rows:
        start = parse_iso(row["startTime"]).replace(minute=0, second=0, microsecond=0)
        key = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        by_hour.setdefault(
            key,
            {
                "startTime": key,
                "forecastMw": float(row["generation"]),
                "publishTime": publish_time,
            },
        )
    return [by_hour[k] for k in sorted(by_hour)]


def aligned_pairs(
    forecasts: list[dict[str, Any]],
    actuals_hourly: dict[str, dict[str, Any]],
    delivery_from: date,
    delivery_to: date,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    day = delivery_from
    while day <= delivery_to:
        vintage = decision_vintage(forecasts, day)
        cutoff = decision_cutoff_utc(day)
        if vintage is None:
            day += timedelta(days=1)
            continue
        for point in series_for_vintage(forecasts, vintage, day):
            actual = actuals_hourly.get(point["startTime"])
            if actual is None or actual.get("halfHourCount", 0) < 2:
                continue
            forecast_mw = point["forecastMw"]
            actual_mw = actual["generationMw"]
            error = forecast_mw - actual_mw
            pairs.append(
                {
                    "deliveryDate": day.isoformat(),
                    "startTime": point["startTime"],
                    "hourUk": parse_iso(point["startTime"]).astimezone(LONDON).hour,
                    "forecastMw": round(forecast_mw, 1),
                    "actualMw": round(actual_mw, 1),
                    "errorMw": round(error, 1),
                    "absErrorMw": round(abs(error), 1),
                    "publishTime": vintage,
                    "decisionCutoff": cutoff.astimezone(LONDON).isoformat(),
                }
            )
        day += timedelta(days=1)
    return pairs


def available_vintages_for_day(
    forecasts: list[dict[str, Any]],
    delivery_day: date,
) -> list[dict[str, Any]]:
    cutoff = decision_cutoff_utc(delivery_day)
    decision_day = delivery_day - timedelta(days=1)
    by_pub: dict[str, int] = defaultdict(int)
    usable: dict[str, bool] = {}
    for row in forecasts:
        start = parse_iso(row["startTime"])
        if london_day(start) != delivery_day:
            continue
        published = parse_iso(row["publishTime"])
        # Only D-1 files — older horizons clutter the gate-time story.
        if london_day(published) != decision_day:
            continue
        pub = row["publishTime"]
        by_pub[pub] += 1
        usable[pub] = published < cutoff
    out = []
    for pub in sorted(by_pub):
        published = parse_iso(pub)
        out.append(
            {
                "publishTime": pub,
                "pointCount": by_pub[pub],
                "usableAtDaGate": usable[pub],
                "hoursBeforeGate": round(
                    (cutoff - published).total_seconds() / 3600.0, 2
                ),
            }
        )
    return out
