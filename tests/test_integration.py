"""
Integration Test - Full council pipeline

Tests:
1. All 4 agents (Claude, Grok, Gemini, Perplexity)
2. Aggregator
3. Full flow: Event -> Signals -> Consensus -> Recommendation

Works WITHOUT real API keys - uses mock objects.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Imports
from council.claude_agent import ClaudeAgent
from council.grok_agent import GrokAgent
from council.gemini_agent import GeminiAgent
from council.perplexity_agent import PerplexityAgent
from council.aggregator import Aggregator
from models.schemas import Signal, MarketEvent, CouncilResponse


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def test_event():
    """Creates a test oil market event"""
    return MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.85,
        data={
            "price_change": 6.5,
            "current_price": 82.50,
            "volume": 420_000,
            "timeframe": "15min",
            "trigger": "Broke resistance at $82"
        }
    )


@pytest.fixture
def test_context():
    """Creates a test context"""
    return {
        "news": "Brent crude breaks $82 resistance, OPEC+ cuts extended",
        "indicators": {
            "rsi": 76,
            "macd": "bullish_crossover",
            "volume_profile": "high",
            "crack_spread": 18.5,
            "geopolitical_risk": "elevated"
        }
    }


@pytest.fixture
def mock_grok_signal():
    """Mock signal from Grok (bullish, high confidence)"""
    return Signal(
        action="LONG",
        confidence=0.90,
        thesis="Massive bullish sentiment on oil. OPEC+ cuts driving supply squeeze.",
        invalidation_price=80.0,
        risk_notes="Sentiment can shift fast on geopolitical de-escalation.",
        sources=["https://x.com/oil_analyst1", "https://x.com/energy_tracker"]
    )


@pytest.fixture
def mock_perplexity_signal():
    """Mock signal from Perplexity (skeptical, low confidence)"""
    return Signal(
        action="WAIT",
        confidence=0.45,
        thesis="News is real but already 2 hours old. EIA report tomorrow may change picture.",
        invalidation_price=None,
        risk_notes="Old news, likely priced in. Wait for EIA confirmation.",
        sources=["https://bloomberg.com/energy", "https://reuters.com/commodities"]
    )


@pytest.fixture
def mock_claude_signal():
    """Mock signal from Claude (cautious, medium confidence)"""
    return Signal(
        action="LONG",
        confidence=0.65,
        thesis="Risk/reward acceptable IF small position. Crack spread supports upside.",
        invalidation_price=80.0,
        risk_notes="Geopolitical risk elevated. Max 2% position. Set tight stop-loss.",
        sources=[]
    )


@pytest.fixture
def mock_gemini_signal():
    """Mock signal from Gemini (analytical, high confidence)"""
    return Signal(
        action="LONG",
        confidence=0.80,
        thesis="Pattern matches OPEC+ cut breakout from 2024. Volume confirms. Success rate: 7/10.",
        invalidation_price=79.50,
        risk_notes="Pattern fails if volume drops or breaks below $79.50 support.",
        sources=["https://tradingview.com/chart", "https://oilprice.com"]
    )


# ==============================================================================
# TESTS
# ==============================================================================

def test_council_integration_mock(
    test_event,
    test_context,
    mock_grok_signal,
    mock_perplexity_signal,
    mock_claude_signal,
    mock_gemini_signal
):
    """
    Main integration test - full flow:
    1. Create all agents
    2. Mock their responses
    3. Aggregator combines signals
    4. Verify consensus

    Expected:
    - Grok: LONG (0.90)
    - Perplexity: WAIT (0.45)
    - Claude: LONG (0.65)
    - Gemini: LONG (0.80)

    Consensus: 3/4 LONG -> STRONG consensus
    """

    # 1. Create agents with fake keys
    grok = GrokAgent(api_key="fake-grok-key")
    perplexity = PerplexityAgent(api_key="fake-perp-key")
    claude = ClaudeAgent(api_key="fake-claude-key")
    gemini = GeminiAgent(api_key="fake-gemini-key")

    # 2. Mock their analyze methods
    with patch.object(grok, 'analyze', return_value=mock_grok_signal), \
         patch.object(perplexity, 'analyze', return_value=mock_perplexity_signal), \
         patch.object(claude, 'analyze', return_value=mock_claude_signal), \
         patch.object(gemini, 'analyze', return_value=mock_gemini_signal):

        # 3. Call analysis from each agent
        grok_result = grok.analyze(test_event, test_context)
        perp_result = perplexity.analyze(test_event, test_context)
        claude_result = claude.analyze(test_event, test_context)
        gemini_result = gemini.analyze(test_event, test_context)

        # 4. Aggregator combines
        aggregator = Aggregator()
        council_response = aggregator.aggregate(
            event=test_event,
            grok=grok_result,
            perplexity=perp_result,
            claude=claude_result,
            gemini=gemini_result,
            prompt_hash="test_integration_hash_123"
        )

        # 5. Assertions
        # Consensus should be LONG (3/4 votes)
        assert council_response.consensus == "LONG", "Expected LONG consensus"

        # Aggregator v2: confidence-weighted voting.
        # LONG = 0.25*0.90 + 0.25*0.65 + 0.25*0.80 = 0.5875
        # WAIT = 0.25*0.45 = 0.1125 → normalized LONG = 83.9% → UNANIMOUS
        assert council_response.consensus_strength == "UNANIMOUS", "Expected UNANIMOUS"

        # Combined confidence = weighted avg of agreeing agents minus penalty
        assert 0.5 <= council_response.combined_confidence <= 0.95

        # Invalidation should be max for LONG
        assert council_response.invalidation_price == 80.0  # max(80.0, 79.5)

        # Position size should be reasonable (v2 uses max_position_pct)
        rec = council_response.recommendation
        assert 0.01 <= rec['max_position_pct'] <= 0.05

        # Should have risks
        assert len(council_response.key_risks) == 4  # One from each agent

        assert council_response is not None


def test_unanimous_consensus():
    """Test UNANIMOUS consensus (all 4 agree)"""

    all_long = Signal(
        action="LONG",
        confidence=0.85,
        thesis="Strong bullish setup",
        invalidation_price=78.0,
        risk_notes="Minimal risk",
        sources=[]
    )

    event = MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.9,
        data={"price_change": 8.0}
    )

    aggregator = Aggregator()
    response = aggregator.aggregate(
        event=event,
        grok=all_long,
        perplexity=all_long,
        claude=all_long,
        gemini=all_long,
        prompt_hash="unanimous_test"
    )

    assert response.consensus == "LONG"
    assert response.consensus_strength == "UNANIMOUS"


def test_conflict_consensus():
    """Test CONFLICT consensus (split evenly)"""

    long_signal = Signal(
        action="LONG",
        confidence=0.7,
        thesis="Bullish",
        risk_notes="Some risk",
        sources=[]
    )

    short_signal = Signal(
        action="SHORT",
        confidence=0.7,
        thesis="Bearish",
        risk_notes="Some risk",
        sources=[]
    )

    event = MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.5,
        data={"price_change": 2.0}
    )

    aggregator = Aggregator()
    response = aggregator.aggregate(
        event=event,
        grok=long_signal,
        perplexity=short_signal,
        claude=long_signal,
        gemini=short_signal,
        prompt_hash="conflict_test"
    )

    # 2 LONG vs 2 SHORT = CONFLICT (Aggregator v2 returns "CONFLICT", not "WAIT")
    assert response.consensus == "CONFLICT"
    assert response.consensus_strength == "NONE"


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
