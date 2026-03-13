"""
Tests for Oil Risk Governor
Verifies oil-specific risk scoring, alert limits, cooldown, and OPEC proximity.
"""

import pytest
from datetime import datetime, timedelta

from risk.risk_governor import RiskGovernor
from models.schemas import (
    Signal,
    MarketEvent,
    CouncilResponse,
    OilRiskScore,
    RiskCheck,
)
from council.aggregator import Aggregator


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_signal(action="LONG", confidence=0.8):
    return Signal(
        action=action,
        confidence=confidence,
        thesis="Test thesis",
        invalidation_price=78.0 if action != "WAIT" else None,
        risk_notes="Test risk",
        sources=[],
    )


def _make_council(signals=None, event=None):
    """Build a CouncilResponse via Aggregator."""
    if signals is None:
        signals = {"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "WAIT"}
    if event is None:
        event = MarketEvent(
            event_type="price_spike",
            instrument="BZ=F",
            severity=0.7,
            data={"price_change_pct": 3.0},
        )
    agg = Aggregator()
    return agg.aggregate(
        event=event,
        grok=_make_signal(signals.get("grok", "LONG"), 0.8),
        perplexity=_make_signal(signals.get("perplexity", "LONG"), 0.8),
        claude=_make_signal(signals.get("claude", "LONG"), 0.8),
        gemini=_make_signal(signals.get("gemini", "WAIT"), 0.4),
        prompt_hash="test_hash",
    )


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def governor():
    return RiskGovernor(
        min_confidence=0.5,
        min_strength="STRONG",
        max_daily_alerts=100,
        cooldown_minutes=0,
    )


@pytest.fixture
def strong_long_response():
    return _make_council({"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "WAIT"})


@pytest.fixture
def weak_long_response():
    # Aggregator v2: confidence-weighted voting.
    # LONG=0.25*0.9+0.25*0.5=0.35, SHORT=0.25*0.7=0.175, WAIT=0.25*0.6=0.15
    # norm LONG=0.519 → WEAK, combined_confidence=0.60 (above min 0.5)
    event = MarketEvent(event_type="price_spike", instrument="BZ=F", severity=0.7, data={"price_change_pct": 3.0})
    agg = Aggregator()
    return agg.aggregate(
        event=event,
        grok=_make_signal("LONG", 0.9),
        perplexity=_make_signal("SHORT", 0.7),
        claude=_make_signal("WAIT", 0.6),
        gemini=_make_signal("LONG", 0.5),
        prompt_hash="test_hash",
    )


@pytest.fixture
def wait_response():
    return _make_council({"grok": "WAIT", "perplexity": "WAIT", "claude": "WAIT", "gemini": "WAIT"})


@pytest.fixture
def geo_event():
    return MarketEvent(
        event_type="geopolitical_alert",
        instrument="BZ=F",
        severity=0.9,
        data={"headline": "Strait of Hormuz tensions"},
    )


@pytest.fixture
def spread_event():
    return MarketEvent(
        event_type="spread_change",
        instrument="BZ=F",
        severity=0.6,
        data={"spread_change_pct": 8.0},
    )


# ==============================================================================
# BASIC ALLOW / BLOCK
# ==============================================================================

def test_allow_normal_trade(governor, strong_long_response):
    check = governor.check(council_response=strong_long_response)
    assert check.allowed is True
    assert "passed" in check.reason.lower()


def test_block_low_confidence(governor):
    low = _make_signal("LONG", 0.3)
    agg = Aggregator()
    event = MarketEvent(event_type="price_spike", instrument="BZ=F", severity=0.5, data={})
    resp = agg.aggregate(event=event, grok=low, perplexity=low, claude=low, gemini=low, prompt_hash="t")

    check = governor.check(council_response=resp)
    assert check.allowed is False
    assert "confidence" in check.reason.lower()


def test_block_weak_consensus(governor, weak_long_response):
    check = governor.check(council_response=weak_long_response)
    assert check.allowed is False
    assert "weak" in check.reason.lower() or "consensus" in check.reason.lower()


def test_allow_wait_always(governor, wait_response):
    check = governor.check(council_response=wait_response)
    assert check.allowed is True
    assert "WAIT" in check.reason


# ==============================================================================
# OIL RISK SCORE
# ==============================================================================

def test_risk_check_returns_oil_risk_score(governor, strong_long_response):
    check = governor.check(council_response=strong_long_response)
    assert check.oil_risk_score is not None
    assert isinstance(check.oil_risk_score, OilRiskScore)
    assert 0.0 <= check.oil_risk_score.composite <= 1.0


def test_geopolitical_event_high_score(governor, geo_event):
    score = governor.calculate_risk_score(event=geo_event)
    assert score.geopolitical >= 0.8


def test_spread_change_technical_score(governor, spread_event):
    score = governor.calculate_risk_score(event=spread_event)
    assert score.technical >= 0.4  # 8/15 ~ 0.53


def test_eia_data_demand_score(governor):
    eia = {"inventory_change_mb": 6.0}
    score = governor.calculate_risk_score(eia_data=eia)
    assert score.demand >= 0.7

    eia_draw = {"inventory_change_mb": -6.0}
    score2 = governor.calculate_risk_score(eia_data=eia_draw)
    assert score2.demand >= 0.6


def test_opec_proximity_supply_score(governor):
    events = [{"name": "OPEC+ Meeting", "datetime": "2025-06-01T10:00:00"}]
    score = governor.calculate_risk_score(scheduled_events=events)
    assert score.supply >= 0.7


def test_seasonal_score_varies():
    """Q1 should have higher seasonal risk than Q2."""
    q1_gov = RiskGovernor(now_func=lambda: datetime(2025, 1, 15))
    q2_gov = RiskGovernor(now_func=lambda: datetime(2025, 4, 15))

    s1 = q1_gov.calculate_risk_score()
    s2 = q2_gov.calculate_risk_score()
    assert s1.seasonal > s2.seasonal


def test_no_data_baseline_scores(governor):
    """With no inputs, all factors should return reasonable baselines."""
    score = governor.calculate_risk_score()
    assert 0.0 <= score.geopolitical <= 1.0
    assert 0.0 <= score.supply <= 1.0
    assert 0.0 <= score.demand <= 1.0
    assert 0.0 <= score.financial <= 1.0
    assert 0.0 <= score.seasonal <= 1.0
    assert 0.0 <= score.technical <= 1.0


# ==============================================================================
# DAILY LIMIT + COOLDOWN
# ==============================================================================

def test_daily_alert_limit():
    gov = RiskGovernor(
        min_confidence=0.1,
        min_strength="WEAK",
        max_daily_alerts=3,
        cooldown_minutes=0,
    )
    resp = _make_council({"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "LONG"})

    for _ in range(3):
        c = gov.check(council_response=resp)
        assert c.allowed is True

    c = gov.check(council_response=resp)
    assert c.allowed is False
    assert "limit" in c.reason.lower()


def test_cooldown_blocks():
    now = datetime(2025, 6, 1, 12, 0, 0)

    gov = RiskGovernor(
        min_confidence=0.1,
        min_strength="WEAK",
        max_daily_alerts=100,
        cooldown_minutes=30,
        now_func=lambda: now,
    )
    resp = _make_council({"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "LONG"})

    c1 = gov.check(council_response=resp)
    assert c1.allowed is True

    # 5 minutes later — should be blocked by cooldown
    gov._now_func = lambda: now + timedelta(minutes=5)
    c2 = gov.check(council_response=resp)
    assert c2.allowed is False
    assert "cooldown" in c2.reason.lower()

    # 31 minutes later — should be allowed
    gov._now_func = lambda: now + timedelta(minutes=31)
    c3 = gov.check(council_response=resp)
    assert c3.allowed is True


def test_daily_counter_resets_on_new_day():
    day1 = datetime(2025, 6, 1, 23, 0, 0)
    day2 = datetime(2025, 6, 2, 1, 0, 0)

    gov = RiskGovernor(
        min_confidence=0.1,
        min_strength="WEAK",
        max_daily_alerts=2,
        cooldown_minutes=0,
        now_func=lambda: day1,
    )
    resp = _make_council({"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "LONG"})

    gov.check(council_response=resp)
    gov.check(council_response=resp)
    c = gov.check(council_response=resp)
    assert c.allowed is False  # limit hit

    # Next day — counter should reset
    gov._now_func = lambda: day2
    c = gov.check(council_response=resp)
    assert c.allowed is True


# ==============================================================================
# COMPOSITE RISK CEILING
# ==============================================================================

def test_composite_risk_ceiling_blocks():
    """If composite risk is above ceiling, trade is blocked."""
    gov = RiskGovernor(
        min_confidence=0.1,
        min_strength="WEAK",
        max_composite_risk=0.3,  # very low ceiling
        cooldown_minutes=0,
    )
    geo = MarketEvent(
        event_type="geopolitical_alert",
        instrument="BZ=F",
        severity=1.0,
        data={},
    )
    opec_events = [{"name": "OPEC+ Meeting", "datetime": "2025-06-01"}]
    eia = {"inventory_change_mb": 8.0}

    resp = _make_council({"grok": "LONG", "perplexity": "LONG", "claude": "LONG", "gemini": "LONG"})
    check = gov.check(
        council_response=resp,
        event=geo,
        eia_data=eia,
        scheduled_events=opec_events,
    )
    assert check.allowed is False
    assert "risk" in check.reason.lower()


# ==============================================================================
# FIELD PRESENCE
# ==============================================================================

def test_risk_check_has_all_fields(governor, strong_long_response):
    check = governor.check(council_response=strong_long_response)
    assert hasattr(check, "daily_alerts_count")
    assert hasattr(check, "cooldown_remaining_sec")
    assert hasattr(check, "oil_risk_score")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
