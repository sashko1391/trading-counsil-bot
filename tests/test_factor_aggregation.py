"""Tests for Factor-Based Aggregation (drivers analysis)."""

import pytest
from models.schemas import Signal, MarketEvent
from council.aggregator import Aggregator


@pytest.fixture
def aggregator():
    return Aggregator()


@pytest.fixture
def event():
    return MarketEvent(
        event_type="price_spike", instrument="BZ=F",
        severity=0.8, data={"price_change_pct": 3.1},
    )


class TestDriverAnalysis:
    def test_bullish_drivers_scored(self, aggregator, event):
        sig = Signal(
            action="LONG", confidence=0.8, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["opec_cut", "supply_disruption"],
        )
        resp = aggregator.aggregate(event, sig, sig, sig, sig, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["bull_score"] > 0
        assert dc["factor_bias"] == "bullish"

    def test_bearish_drivers_scored(self, aggregator, event):
        sig = Signal(
            action="SHORT", confidence=0.7, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["demand_destruction", "inventory_build"],
        )
        resp = aggregator.aggregate(event, sig, sig, sig, sig, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["bear_score"] > 0
        assert dc["factor_bias"] == "bearish"

    def test_mixed_drivers_neutral(self, aggregator, event):
        bull = Signal(
            action="LONG", confidence=0.6, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["opec_cut"],
        )
        bear = Signal(
            action="SHORT", confidence=0.6, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["demand_destruction"],
        )
        resp = aggregator.aggregate(event, bull, bear, bull, bear, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["factor_bias"] == "neutral"

    def test_driver_agreement_high_when_same(self, aggregator, event):
        sig = Signal(
            action="LONG", confidence=0.8, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["opec_cut", "geopolitical_risk"],
        )
        resp = aggregator.aggregate(event, sig, sig, sig, sig, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["driver_agreement"] == 1.0

    def test_driver_agreement_low_when_different(self, aggregator, event):
        sigs = [
            Signal(action="LONG", confidence=0.7, thesis="T", risk_notes="R",
                   sources=[], drivers=["opec_cut"]),
            Signal(action="LONG", confidence=0.7, thesis="T", risk_notes="R",
                   sources=[], drivers=["china_demand_up"]),
            Signal(action="LONG", confidence=0.7, thesis="T", risk_notes="R",
                   sources=[], drivers=["seasonal_demand"]),
            Signal(action="LONG", confidence=0.7, thesis="T", risk_notes="R",
                   sources=[], drivers=["usd_weakness"]),
        ]
        resp = aggregator.aggregate(event, *sigs, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["driver_agreement"] < 0.5

    def test_empty_drivers_handled(self, aggregator, event):
        sig = Signal(
            action="WAIT", confidence=0.5, thesis="Test",
            risk_notes="Risk", sources=[], drivers=[],
        )
        resp = aggregator.aggregate(event, sig, sig, sig, sig, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert dc["bull_score"] == 0
        assert dc["bear_score"] == 0

    def test_top_drivers_limited(self, aggregator, event):
        sig = Signal(
            action="LONG", confidence=0.8, thesis="Test",
            risk_notes="Risk", sources=[],
            drivers=["opec_cut", "supply_disruption", "china_demand_up",
                     "geopolitical_risk", "inventory_draw"],
        )
        resp = aggregator.aggregate(event, sig, sig, sig, sig, "h1")
        dc = resp.recommendation.get("driver_consensus", {})
        assert len(dc["top_drivers"]) <= 5
