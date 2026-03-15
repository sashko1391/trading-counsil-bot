"""Tests for Weight Calibrator."""

import pytest
from metrics.weight_calibrator import WeightCalibrator


@pytest.fixture
def calibrator():
    return WeightCalibrator()


class TestWeightCalibrator:
    def test_default_weights_when_no_data(self, calibrator):
        weights = calibrator.calibrate({})
        assert weights == {"grok": 0.25, "perplexity": 0.25, "claude": 0.25, "gemini": 0.25}

    def test_default_weights_when_insufficient_data(self, calibrator):
        stats = {"grok": {"hit_rate": 0.9, "avg_confidence": 0.8, "total": 3}}
        weights = calibrator.calibrate(stats)
        assert weights == {"grok": 0.25, "perplexity": 0.25, "claude": 0.25, "gemini": 0.25}

    def test_better_agent_gets_higher_weight(self, calibrator):
        stats = {
            "grok": {"hit_rate": 0.80, "avg_confidence": 0.75, "total": 20},
            "perplexity": {"hit_rate": 0.50, "avg_confidence": 0.70, "total": 20},
            "claude": {"hit_rate": 0.65, "avg_confidence": 0.65, "total": 20},
            "gemini": {"hit_rate": 0.60, "avg_confidence": 0.60, "total": 20},
        }
        weights = calibrator.calibrate(stats)
        assert weights["grok"] > weights["perplexity"]
        assert weights["grok"] > weights["gemini"]

    def test_weights_sum_to_one(self, calibrator):
        stats = {
            "grok": {"hit_rate": 0.9, "avg_confidence": 0.8, "total": 15},
            "perplexity": {"hit_rate": 0.4, "avg_confidence": 0.7, "total": 15},
            "claude": {"hit_rate": 0.7, "avg_confidence": 0.7, "total": 15},
            "gemini": {"hit_rate": 0.6, "avg_confidence": 0.6, "total": 15},
        }
        weights = calibrator.calibrate(stats)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weights_respect_floor_ceiling(self, calibrator):
        stats = {
            "grok": {"hit_rate": 1.0, "avg_confidence": 1.0, "total": 50},
            "perplexity": {"hit_rate": 0.1, "avg_confidence": 0.9, "total": 50},
            "claude": {"hit_rate": 0.5, "avg_confidence": 0.5, "total": 50},
            "gemini": {"hit_rate": 0.5, "avg_confidence": 0.5, "total": 50},
        }
        weights = calibrator.calibrate(stats)
        for w in weights.values():
            assert w >= 0.10
            assert w <= 0.45

    def test_overconfident_agent_penalized(self, calibrator):
        # Agent with high confidence but low accuracy should be penalized
        stats = {
            "grok": {"hit_rate": 0.40, "avg_confidence": 0.90, "total": 20},
            "perplexity": {"hit_rate": 0.60, "avg_confidence": 0.60, "total": 20},
            "claude": {"hit_rate": 0.50, "avg_confidence": 0.50, "total": 20},
            "gemini": {"hit_rate": 0.50, "avg_confidence": 0.50, "total": 20},
        }
        weights = calibrator.calibrate(stats)
        # Well-calibrated perplexity should outweigh overconfident grok
        assert weights["perplexity"] > weights["grok"]

    def test_format_report(self, calibrator):
        stats = {
            "grok": {"hit_rate": 0.7, "avg_confidence": 0.7, "total": 20},
        }
        old = {"grok": 0.25, "perplexity": 0.25, "claude": 0.25, "gemini": 0.25}
        new = {"grok": 0.30, "perplexity": 0.23, "claude": 0.24, "gemini": 0.23}
        report = calibrator.format_report(stats, old, new)
        assert "grok" in report
        assert "Weight Calibration" in report
