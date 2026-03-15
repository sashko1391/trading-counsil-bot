"""Tests for OVX Volatility Watcher."""

import pytest
from watchers.volatility_watcher import VolatilitySnapshot, VolatilityWatcher


class TestVolatilitySnapshot:
    def test_empty_snapshot_returns_empty_text(self):
        snap = VolatilitySnapshot()
        assert snap.to_prompt_text() == ""

    def test_basic_snapshot_text(self):
        snap = VolatilitySnapshot(
            ovx_current=32.5,
            ovx_20d_avg=30.0,
            ovx_60d_high=45.0,
            ovx_60d_low=22.0,
            ovx_percentile=45.7,
            regime="normal",
        )
        text = snap.to_prompt_text()
        assert "OVX" in text
        assert "32.5" in text
        assert "30.0" in text
        assert "НОРМАЛЬНА" in text

    def test_extreme_regime_has_warning(self):
        snap = VolatilitySnapshot(
            ovx_current=55.0,
            ovx_20d_avg=40.0,
            ovx_60d_high=55.0,
            ovx_60d_low=25.0,
            ovx_percentile=98.0,
            regime="extreme",
        )
        text = snap.to_prompt_text()
        assert "ЕКСТРЕМАЛЬНА" in text
        assert "розворот" in text

    def test_low_vol_has_warning(self):
        snap = VolatilitySnapshot(
            ovx_current=18.0,
            ovx_20d_avg=20.0,
            ovx_60d_high=30.0,
            ovx_60d_low=17.0,
            ovx_percentile=8.0,
            regime="low",
        )
        text = snap.to_prompt_text()
        assert "НИЗЬКА" in text
        assert "каталізатор" in text


class TestVolatilityWatcherClassification:
    def test_extreme_by_level(self):
        assert VolatilityWatcher._classify_regime(55.0, 50.0) == "extreme"

    def test_extreme_by_percentile(self):
        assert VolatilityWatcher._classify_regime(30.0, 96.0) == "extreme"

    def test_elevated(self):
        assert VolatilityWatcher._classify_regime(40.0, 70.0) == "elevated"

    def test_elevated_by_percentile(self):
        assert VolatilityWatcher._classify_regime(28.0, 85.0) == "elevated"

    def test_normal(self):
        assert VolatilityWatcher._classify_regime(30.0, 50.0) == "normal"

    def test_low(self):
        assert VolatilityWatcher._classify_regime(20.0, 15.0) == "low"
