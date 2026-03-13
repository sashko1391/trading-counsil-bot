"""
Tests for oil-specific Pydantic models: OilRiskScore, OilForecast, MarketEvent
"""

import pytest
from datetime import datetime
from src.models.schemas import (
    Signal,
    MarketEvent,
    OilRiskScore,
    OilForecast,
    CouncilResponse,
    RiskCheck,
)


# ============================================================
# OilRiskScore
# ============================================================

class TestOilRiskScore:
    def test_create_valid(self):
        score = OilRiskScore(
            geopolitical=0.8,
            supply=0.6,
            demand=0.4,
            financial=0.3,
            seasonal=0.2,
            technical=0.5,
        )
        assert score.geopolitical == 0.8
        assert score.supply == 0.6

    def test_composite_weighted(self):
        score = OilRiskScore(
            geopolitical=1.0,
            supply=1.0,
            demand=1.0,
            financial=1.0,
            seasonal=1.0,
            technical=1.0,
        )
        assert score.composite == pytest.approx(1.0)

    def test_composite_zero(self):
        score = OilRiskScore(
            geopolitical=0, supply=0, demand=0,
            financial=0, seasonal=0, technical=0,
        )
        assert score.composite == pytest.approx(0.0)

    def test_composite_partial(self):
        score = OilRiskScore(
            geopolitical=0.8,  # * 0.25 = 0.20
            supply=0.6,        # * 0.25 = 0.15
            demand=0.4,        # * 0.20 = 0.08
            financial=0.2,     # * 0.10 = 0.02
            seasonal=0.1,      # * 0.10 = 0.01
            technical=0.5,     # * 0.10 = 0.05
        )
        expected = 0.20 + 0.15 + 0.08 + 0.02 + 0.01 + 0.05
        assert score.composite == pytest.approx(expected)

    def test_invalid_range(self):
        with pytest.raises(Exception):
            OilRiskScore(
                geopolitical=1.5, supply=0, demand=0,
                financial=0, seasonal=0, technical=0,
            )

    def test_negative_value(self):
        with pytest.raises(Exception):
            OilRiskScore(
                geopolitical=-0.1, supply=0, demand=0,
                financial=0, seasonal=0, technical=0,
            )


# ============================================================
# MarketEvent (oil event types)
# ============================================================

class TestMarketEvent:
    @pytest.mark.parametrize("event_type", [
        "price_spike", "volume_surge", "spread_change",
        "news_event", "eia_report", "opec_event",
        "geopolitical_alert", "weather_event", "scheduled_event",
    ])
    def test_all_oil_event_types(self, event_type):
        event = MarketEvent(
            event_type=event_type,
            instrument="BZ=F",
            data={"price": 80.5},
            severity=0.7,
        )
        assert event.event_type == event_type

    def test_invalid_event_type(self):
        with pytest.raises(Exception):
            MarketEvent(
                event_type="funding_extreme",  # crypto, not valid
                instrument="BZ=F",
                data={},
                severity=0.5,
            )

    def test_headline_default_empty(self):
        event = MarketEvent(
            event_type="eia_report",
            instrument="BZ=F",
            data={"draw": -7.2},
            severity=0.8,
        )
        assert event.headline == ""

    def test_headline_custom(self):
        event = MarketEvent(
            event_type="geopolitical_alert",
            instrument="BZ=F",
            data={},
            severity=0.9,
            headline="Hormuz strait tensions escalate",
        )
        assert "Hormuz" in event.headline


# ============================================================
# OilForecast
# ============================================================

class TestOilForecast:
    def _make_risk_score(self):
        return OilRiskScore(
            geopolitical=0.5, supply=0.5, demand=0.5,
            financial=0.3, seasonal=0.2, technical=0.4,
        )

    def test_create_bullish(self):
        fc = OilForecast(
            instrument="BZ=F",
            direction="BULLISH",
            confidence=0.75,
            timeframe_hours=48,
            current_price=80.0,
            target_price=82.5,
            drivers=["EIA draw", "OPEC compliance"],
            risks=["USD rally"],
            risk_score=self._make_risk_score(),
        )
        assert fc.direction == "BULLISH"
        assert fc.instrument == "BZ=F"

    def test_expected_move_pct(self):
        fc = OilForecast(
            instrument="BZ=F",
            direction="BULLISH",
            confidence=0.7,
            timeframe_hours=24,
            current_price=80.0,
            target_price=82.0,
            drivers=["test"],
            risks=["test"],
            risk_score=self._make_risk_score(),
        )
        assert fc.expected_move_pct == pytest.approx(2.5)

    def test_expected_move_bearish(self):
        fc = OilForecast(
            instrument="LGO",
            direction="BEARISH",
            confidence=0.6,
            timeframe_hours=72,
            current_price=100.0,
            target_price=95.0,
            drivers=["warm winter"],
            risks=["cold snap"],
            risk_score=self._make_risk_score(),
        )
        assert fc.expected_move_pct == pytest.approx(-5.0)

    def test_expected_move_zero_price(self):
        fc = OilForecast(
            instrument="BZ=F",
            direction="NEUTRAL",
            confidence=0.5,
            timeframe_hours=24,
            current_price=0.0,
            target_price=0.0,
            drivers=[],
            risks=[],
            risk_score=self._make_risk_score(),
        )
        assert fc.expected_move_pct == 0.0

    def test_invalid_timeframe(self):
        with pytest.raises(Exception):
            OilForecast(
                instrument="BZ=F",
                direction="BULLISH",
                confidence=0.7,
                timeframe_hours=0,  # min is 1
                current_price=80.0,
                target_price=82.0,
                drivers=[],
                risks=[],
                risk_score=self._make_risk_score(),
            )


# ============================================================
# RiskCheck (updated)
# ============================================================

class TestRiskCheck:
    def test_with_oil_risk_score(self):
        score = OilRiskScore(
            geopolitical=0.9, supply=0.7, demand=0.5,
            financial=0.3, seasonal=0.2, technical=0.4,
        )
        check = RiskCheck(
            allowed=False,
            reason="High geopolitical risk",
            oil_risk_score=score,
            daily_alerts_count=8,
            cooldown_remaining_sec=120,
        )
        assert not check.allowed
        assert check.oil_risk_score.geopolitical == 0.9

    def test_without_oil_risk_score(self):
        check = RiskCheck(allowed=True, reason="OK")
        assert check.oil_risk_score is None
        assert check.daily_alerts_count == 0


# ============================================================
# Signal (unchanged, sanity check)
# ============================================================

class TestSignal:
    def test_valid_signal(self):
        sig = Signal(
            action="LONG",
            confidence=0.8,
            thesis="EIA draw supports bullish move",
            risk_notes="USD could rally",
            sources=["https://eia.gov/report"],
        )
        assert sig.action == "LONG"

    def test_invalid_url_filtered(self):
        """Non-URL sources are silently filtered out (not rejected)"""
        sig = Signal(
            action="WAIT",
            confidence=0.5,
            thesis="test",
            risk_notes="test",
            sources=["not-a-url", "https://valid.com"],
        )
        assert sig.sources == ["https://valid.com"]
