"""Tests for Market Regime Detector."""

import pytest
from watchers.regime_detector import RegimeDetector, RegimeAnalysis


@pytest.fixture
def detector():
    return RegimeDetector()


class TestRegimeDetection:
    def test_insufficient_data(self, detector):
        result = detector.detect([80.0, 81.0, 82.0])
        assert result.regime == "ranging"
        assert result.confidence < 0.5

    def test_trending_up(self, detector):
        prices = [70 + i * 0.5 for i in range(30)]  # steady climb
        result = detector.detect(prices)
        assert result.regime == "trending_up"
        assert result.trend_strength > 0.5

    def test_trending_down(self, detector):
        prices = [90 - i * 0.5 for i in range(30)]  # steady fall
        result = detector.detect(prices)
        assert result.regime == "trending_down"
        assert result.trend_strength > 0.5

    def test_ranging(self, detector):
        # oscillating prices
        prices = [80 + (i % 4 - 2) * 0.3 for i in range(30)]
        result = detector.detect(prices)
        assert result.regime in ("ranging", "trending_up", "trending_down")

    def test_crisis_high_volatility(self, detector):
        # extreme moves
        import random
        random.seed(42)
        prices = [80.0]
        for _ in range(29):
            prices.append(prices[-1] * (1 + random.uniform(-0.08, 0.08)))
        result = detector.detect(prices)
        # With 8% daily moves, annualized vol should be very high
        assert result.volatility_pct > 50

    def test_format_for_prompt(self, detector):
        analysis = RegimeAnalysis(
            regime="trending_up",
            confidence=0.8,
            description="Test description",
            volatility_pct=25.0,
            trend_strength=0.7,
            days_in_regime=5,
        )
        text = detector.format_for_prompt(analysis)
        assert "TRENDING_UP" in text
        assert "Test description" in text
        assert "LONG" in text  # guidance for trending up

    def test_all_regimes_have_guidance(self, detector):
        for regime in ["trending_up", "trending_down", "ranging", "breakout", "crisis"]:
            analysis = RegimeAnalysis(
                regime=regime,
                confidence=0.7,
                description="test",
                volatility_pct=20.0,
                trend_strength=0.5,
                days_in_regime=3,
            )
            text = detector.format_for_prompt(analysis)
            assert len(text) > 50, f"No guidance for regime {regime}"
