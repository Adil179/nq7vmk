from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def summarise(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if not pairs:
        return {
            "n": 0,
            "maeMw": None,
            "rmseMw": None,
            "biasMw": None,
            "mapePct": None,
            "p50AbsErrorMw": None,
            "p90AbsErrorMw": None,
            "energyErrorGwh": None,
            "forecastEnergyGwh": None,
            "actualEnergyGwh": None,
            "within500MwPct": None,
            "within1000MwPct": None,
            "overforecastHoursPct": None,
        }

    errors = [p["errorMw"] for p in pairs]
    abs_errors = [p["absErrorMw"] for p in pairs]
    actuals = [p["actualMw"] for p in pairs]
    forecasts = [p["forecastMw"] for p in pairs]
    mape_terms = [
        abs(p["errorMw"]) / p["actualMw"] * 100.0
        for p in pairs
        if p["actualMw"] > 100
    ]
    sorted_abs = sorted(abs_errors)
    n = len(pairs)
    # Hourly MW average * 1 hour = MWh; /1000 = GWh
    forecast_gwh = sum(forecasts) / 1000.0
    actual_gwh = sum(actuals) / 1000.0
    return {
        "n": n,
        "maeMw": round(_mean(abs_errors), 1),
        "rmseMw": round(sqrt(_mean([e * e for e in errors])), 1),
        "biasMw": round(_mean(errors), 1),
        "mapePct": round(_mean(mape_terms), 2) if mape_terms else None,
        "p50AbsErrorMw": round(_quantile(sorted_abs, 0.5), 1),
        "p90AbsErrorMw": round(_quantile(sorted_abs, 0.9), 1),
        "energyErrorGwh": round(forecast_gwh - actual_gwh, 2),
        "forecastEnergyGwh": round(forecast_gwh, 2),
        "actualEnergyGwh": round(actual_gwh, 2),
        "within500MwPct": round(100.0 * sum(1 for a in abs_errors if a <= 500) / n, 1),
        "within1000MwPct": round(100.0 * sum(1 for a in abs_errors if a <= 1000) / n, 1),
        "overforecastHoursPct": round(
            100.0 * sum(1 for e in errors if e > 0) / n, 1
        ),
    }


def by_hour(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        groups[int(pair["hourUk"])].append(pair)
    return [
        {"hourUk": hour, **summarise(groups[hour])}
        for hour in range(24)
        if hour in groups
    ]


def by_day(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        groups[pair["deliveryDate"]].append(pair)
    return [{"deliveryDate": day, **summarise(groups[day])} for day in sorted(groups)]


def by_wind_level(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Terciles of actual wind output — accuracy often degrades at high wind."""
    if not pairs:
        return []
    actuals = sorted(p["actualMw"] for p in pairs)
    q1 = actuals[len(actuals) // 3]
    q2 = actuals[(2 * len(actuals)) // 3]
    buckets = {"Low": [], "Medium": [], "High": []}
    for pair in pairs:
        if pair["actualMw"] <= q1:
            buckets["Low"].append(pair)
        elif pair["actualMw"] <= q2:
            buckets["Medium"].append(pair)
        else:
            buckets["High"].append(pair)
    out = []
    for label, rows in buckets.items():
        if not rows:
            continue
        item = summarise(rows)
        item["level"] = label
        item["actualFromMw"] = round(min(r["actualMw"] for r in rows), 1)
        item["actualToMw"] = round(max(r["actualMw"] for r in rows), 1)
        out.append(item)
    return out


def trading_implications(summary: dict[str, Any]) -> list[str]:
    if not summary.get("n"):
        return ["Not enough aligned forecast/actual hours to quantify error."]
    notes: list[str] = []
    bias = summary["biasMw"]
    mae = summary["maeMw"]
    p90 = summary["p90AbsErrorMw"]
    energy = summary["energyErrorGwh"]
    if bias > 150:
        notes.append(
            f"Day-ahead vintages over-forecast national wind by {bias:.0f} MW on average. "
            "Treating the forecast as unbiased would leave the book short of wind and "
            "require extra DA / ID purchases (or thermal) after the fact."
        )
    elif bias < -150:
        notes.append(
            f"Day-ahead vintages under-forecast national wind by {abs(bias):.0f} MW on average. "
            "Buying the residual as if the forecast were unbiased would over-procure "
            "wholesale volume on windy days."
        )
    else:
        notes.append(
            f"Mean bias is modest ({bias:.0f} MW). Random error dominates: plan a buffer "
            f"around MAE {mae:.0f} MW rather than a large directional haircut."
        )
    notes.append(
        f"A 90th-percentile absolute error of {p90:.0f} MW is a practical uncertainty "
        "band to overlay on the DA curve when sizing thermal / market cover."
    )
    if energy is not None:
        direction = "above" if energy > 0 else "below"
        notes.append(
            f"Over January 2026 the decision-time forecast was {abs(energy):.1f} GWh "
            f"{direction} metered wind. That is the energy equivalent of the bias "
            "the desk would have carried if it had bought 1:1 against this vintage."
        )
    notes.append(
        f"{summary['within1000MwPct']}% of hours landed within ±1,000 MW of the "
        f"decision-time forecast; {summary['within500MwPct']}% within ±500 MW."
    )
    return notes
