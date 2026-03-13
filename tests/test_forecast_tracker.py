"""
Tests for ForecastTracker — record, outcome, metrics, persistence.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from metrics.forecast_tracker import ForecastTracker
from models.schemas import OilForecast, OilRiskScore


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_risk_score(**kw):
    defaults = dict(
        geopolitical=0.3, supply=0.3, demand=0.3,
        financial=0.2, seasonal=0.4, technical=0.2,
    )
    defaults.update(kw)
    return OilRiskScore(**defaults)


def _make_forecast(
    direction="BULLISH",
    confidence=0.75,
    current_price=80.0,
    target_price=85.0,
    instrument="BZ=F",
    timestamp=None,
):
    return OilForecast(
        timestamp=timestamp or datetime.now(),
        instrument=instrument,
        direction=direction,
        confidence=confidence,
        timeframe_hours=24,
        current_price=current_price,
        target_price=target_price,
        drivers=["Strong demand"],
        risks=["OPEC surprise"],
        risk_score=_make_risk_score(),
    )


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def tmp_path_tracker(tmp_path):
    """Tracker with a temp JSON path."""
    return ForecastTracker(path=tmp_path / "forecasts.json")


# ==============================================================================
# RECORD + RETRIEVE
# ==============================================================================

def test_record_forecast(tmp_path_tracker):
    fc = _make_forecast()
    fid = tmp_path_tracker.record_forecast(fc)

    assert isinstance(fid, str)
    assert len(fid) == 12

    summary = tmp_path_tracker.get_summary()
    assert summary["total_forecasts"] == 1
    assert summary["resolved"] == 0


def test_record_outcome_bullish_correct(tmp_path_tracker):
    fc = _make_forecast(direction="BULLISH", current_price=80.0, target_price=85.0)
    fid = tmp_path_tracker.record_forecast(fc)
    ok = tmp_path_tracker.record_outcome(fid, actual_price=83.0)  # went up

    assert ok is True
    assert tmp_path_tracker.get_hit_rate() == 1.0


def test_record_outcome_bullish_wrong(tmp_path_tracker):
    fc = _make_forecast(direction="BULLISH", current_price=80.0, target_price=85.0)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=78.0)  # went down

    assert tmp_path_tracker.get_hit_rate() == 0.0


def test_record_outcome_bearish(tmp_path_tracker):
    fc = _make_forecast(direction="BEARISH", current_price=80.0, target_price=75.0)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=77.0)

    assert tmp_path_tracker.get_hit_rate() == 1.0


def test_record_outcome_neutral_correct(tmp_path_tracker):
    fc = _make_forecast(direction="NEUTRAL", current_price=80.0, target_price=80.0, confidence=0.5)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=80.5)  # <1% move

    assert tmp_path_tracker.get_hit_rate() == 1.0


def test_record_outcome_not_found(tmp_path_tracker):
    ok = tmp_path_tracker.record_outcome("nonexistent", 100.0)
    assert ok is False


# ==============================================================================
# HIT RATE
# ==============================================================================

def test_hit_rate_multiple(tmp_path_tracker):
    # 2 correct, 1 wrong => 66.67%
    for _ in range(2):
        fid = tmp_path_tracker.record_forecast(
            _make_forecast(direction="BULLISH", current_price=80.0)
        )
        tmp_path_tracker.record_outcome(fid, actual_price=82.0)

    fid = tmp_path_tracker.record_forecast(
        _make_forecast(direction="BULLISH", current_price=80.0)
    )
    tmp_path_tracker.record_outcome(fid, actual_price=78.0)

    assert abs(tmp_path_tracker.get_hit_rate() - 2 / 3) < 0.01


def test_hit_rate_no_outcomes(tmp_path_tracker):
    tmp_path_tracker.record_forecast(_make_forecast())
    assert tmp_path_tracker.get_hit_rate() == 0.0


# ==============================================================================
# BRIER SCORE
# ==============================================================================

def test_brier_score_perfect(tmp_path_tracker):
    """Confidence=1.0 and correct => Brier=0.0"""
    fc = _make_forecast(confidence=1.0, direction="BULLISH", current_price=80.0)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=85.0)

    assert tmp_path_tracker.get_brier_score() == pytest.approx(0.0, abs=1e-6)


def test_brier_score_worst(tmp_path_tracker):
    """Confidence=1.0 but wrong => Brier=1.0"""
    fc = _make_forecast(confidence=1.0, direction="BULLISH", current_price=80.0)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=75.0)

    assert tmp_path_tracker.get_brier_score() == pytest.approx(1.0, abs=1e-6)


def test_brier_score_calibrated(tmp_path_tracker):
    """Confidence=0.7, correct => (0.7 - 1.0)^2 = 0.09"""
    fc = _make_forecast(confidence=0.7, direction="BULLISH", current_price=80.0)
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=85.0)

    assert tmp_path_tracker.get_brier_score() == pytest.approx(0.09, abs=0.001)


def test_brier_score_no_outcomes(tmp_path_tracker):
    assert tmp_path_tracker.get_brier_score() == 0.0


# ==============================================================================
# SUMMARY
# ==============================================================================

def test_get_summary(tmp_path_tracker):
    fc1 = _make_forecast(confidence=0.8, direction="BULLISH", current_price=80.0)
    fc2 = _make_forecast(confidence=0.6, direction="BEARISH", current_price=80.0, target_price=75.0)

    fid1 = tmp_path_tracker.record_forecast(fc1)
    fid2 = tmp_path_tracker.record_forecast(fc2)

    tmp_path_tracker.record_outcome(fid1, actual_price=85.0)  # correct
    tmp_path_tracker.record_outcome(fid2, actual_price=82.0)  # wrong (bearish but went up)

    s = tmp_path_tracker.get_summary()
    assert s["total_forecasts"] == 2
    assert s["resolved"] == 2
    assert s["hit_rate"] == 0.5
    assert s["avg_confidence"] == pytest.approx(0.7, abs=0.01)
    assert s["brier_score"] > 0


# ==============================================================================
# WEEKLY REPORT
# ==============================================================================

def test_weekly_report_generation(tmp_path_tracker):
    fc = _make_forecast(timestamp=datetime.now())
    fid = tmp_path_tracker.record_forecast(fc)
    tmp_path_tracker.record_outcome(fid, actual_price=85.0)

    report = tmp_path_tracker.generate_weekly_report()

    assert "Weekly Forecast Report" in report
    assert "Hit rate" in report
    assert "Brier" in report
    assert "BZ=F" in report


def test_weekly_report_empty(tmp_path_tracker):
    report = tmp_path_tracker.generate_weekly_report()
    assert "Weekly Forecast Report" in report
    assert "Total forecasts: 0" in report


# ==============================================================================
# PERSISTENCE
# ==============================================================================

def test_persistence_write_read(tmp_path):
    path = tmp_path / "persist_test.json"

    tracker1 = ForecastTracker(path=path)
    fc = _make_forecast()
    fid = tracker1.record_forecast(fc)
    tracker1.record_outcome(fid, actual_price=82.0)

    # Verify file exists
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["actual_price"] == 82.0

    # Load in a new tracker
    tracker2 = ForecastTracker(path=path)
    assert tracker2.get_summary()["total_forecasts"] == 1
    assert tracker2.get_hit_rate() == 1.0


def test_persistence_empty_file(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("[]")

    tracker = ForecastTracker(path=path)
    assert tracker.get_summary()["total_forecasts"] == 0


def test_persistence_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{bad json")

    tracker = ForecastTracker(path=path)
    assert tracker.get_summary()["total_forecasts"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
