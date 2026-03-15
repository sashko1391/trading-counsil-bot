"""Tests for Macro Correlations Watcher."""

import pytest
from watchers.macro_watcher import MacroSnapshot, MacroWatcher


class TestMacroSnapshot:
    def test_empty_snapshot_returns_empty_text(self):
        snap = MacroSnapshot()
        assert snap.to_prompt_text() == ""

    def test_basic_snapshot_text(self):
        snap = MacroSnapshot(
            dxy_current=104.50,
            dxy_20d_avg=103.80,
            dxy_change_5d_pct=0.65,
            dxy_trend="strengthening",
            usd_cny=7.25,
            eur_usd=1.0850,
            dollar_oil_signal="bearish_for_oil",
        )
        text = snap.to_prompt_text()
        assert "Макро-кореляції" in text
        assert "104.50" in text
        assert "ЗМІЦНЮЄТЬСЯ" in text
        assert "7.25" in text
        assert "1.0850" in text
        assert "ВЕДМЕЖИЙ для нафти" in text

    def test_weakening_dollar(self):
        snap = MacroSnapshot(
            dxy_current=101.00,
            dxy_20d_avg=103.00,
            dxy_change_5d_pct=-1.2,
            dxy_trend="weakening",
            dollar_oil_signal="bullish_for_oil",
        )
        text = snap.to_prompt_text()
        assert "СЛАБШАЄ" in text
        assert "БИЧАЧИЙ для нафти" in text

    def test_stable_dollar(self):
        snap = MacroSnapshot(
            dxy_current=103.00,
            dxy_20d_avg=103.10,
            dxy_change_5d_pct=0.05,
            dxy_trend="stable",
            dollar_oil_signal="neutral",
        )
        text = snap.to_prompt_text()
        assert "СТАБІЛЬНИЙ" in text
        assert "НЕЙТРАЛЬНИЙ" in text

    def test_has_correlation_note(self):
        snap = MacroSnapshot(dxy_current=104.0, dxy_20d_avg=103.5)
        text = snap.to_prompt_text()
        assert "-0.6" in text


class TestMacroWatcherClassification:
    def test_strengthening_trend(self):
        assert MacroWatcher._classify_trend(105.0, 104.0, 0.8) == "strengthening"

    def test_weakening_trend(self):
        assert MacroWatcher._classify_trend(101.0, 103.0, -1.0) == "weakening"

    def test_stable_trend(self):
        assert MacroWatcher._classify_trend(103.5, 103.5, 0.1) == "stable"


class TestMacroWatcherDeriveSignal:
    def test_strong_dollar_bearish(self):
        snap = MacroSnapshot(dxy_trend="strengthening")
        assert MacroWatcher._derive_signal(snap) == "bearish_for_oil"

    def test_weak_dollar_bullish(self):
        snap = MacroSnapshot(dxy_trend="weakening")
        assert MacroWatcher._derive_signal(snap) == "bullish_for_oil"

    def test_stable_neutral(self):
        snap = MacroSnapshot(dxy_trend="stable")
        assert MacroWatcher._derive_signal(snap) == "neutral"
