from datetime import date

from app.metrics import summarise
from app.processing import decision_cutoff_utc, decision_vintage, hourly_actuals


def test_gate_is_0920_uk_on_d_minus_1():
    cutoff = decision_cutoff_utc(date(2026, 1, 15))
    assert cutoff.isoformat() == "2026-01-14T09:20:00+00:00"


def test_vintages_list_only_decision_day_and_hides_post_gate():
    from app.processing import available_vintages_for_day

    forecasts = [
        {
            "publishTime": "2026-01-13T07:30:00Z",
            "startTime": "2026-01-15T12:00:00Z",
            "generation": 1,
        },
        {
            "publishTime": "2026-01-14T07:30:00Z",
            "startTime": "2026-01-15T12:00:00Z",
            "generation": 1,
        },
        {
            "publishTime": "2026-01-14T09:30:00Z",
            "startTime": "2026-01-15T12:00:00Z",
            "generation": 1,
        },
    ]
    vintages = available_vintages_for_day(forecasts, date(2026, 1, 15))
    assert [v["publishTime"] for v in vintages] == [
        "2026-01-14T07:30:00Z",
        "2026-01-14T09:30:00Z",
    ]
    assert vintages[0]["usableAtDaGate"] is True
    assert vintages[1]["usableAtDaGate"] is False


def test_vintage_ignores_post_gate_forecasts():
    forecasts = [
        {
            "publishTime": "2026-01-14T07:30:00Z",
            "startTime": "2026-01-15T12:00:00Z",
            "generation": 1000,
        },
        {
            "publishTime": "2026-01-14T09:30:00Z",
            "startTime": "2026-01-15T12:00:00Z",
            "generation": 2000,
        },
    ]
    assert decision_vintage(forecasts, date(2026, 1, 15)) == "2026-01-14T07:30:00Z"


def test_hourly_average_of_two_half_hours():
    actuals = [
        {"startTime": "2026-01-01T00:00:00Z", "generation": 100.0},
        {"startTime": "2026-01-01T00:30:00Z", "generation": 200.0},
    ]
    hourly = hourly_actuals(actuals)
    assert hourly["2026-01-01T00:00:00Z"]["generationMw"] == 150.0


def test_summarise_bias_and_mae():
    pairs = [
        {"errorMw": 10, "absErrorMw": 10, "forecastMw": 110, "actualMw": 100},
        {"errorMw": -4, "absErrorMw": 4, "forecastMw": 96, "actualMw": 100},
    ]
    summary = summarise(pairs)
    assert summary["n"] == 2
    assert summary["biasMw"] == 3.0
    assert summary["maeMw"] == 7.0
