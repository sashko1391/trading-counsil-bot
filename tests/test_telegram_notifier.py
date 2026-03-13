"""
Tests for Telegram Notifier
Verifies formatting without actual sending
"""

import pytest

from notifications.telegram_notifier import TelegramNotifier
from models.schemas import Signal, MarketEvent, RiskCheck
from council.aggregator import Aggregator


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def notifier():
    """Creates disabled notifier (no token)"""
    return TelegramNotifier()  # No token = disabled


@pytest.fixture
def sample_response():
    """Creates test council response"""
    grok = Signal(action="LONG", confidence=0.9, thesis="Bullish oil!", risk_notes="Fake hype", sources=[])
    perp = Signal(action="WAIT", confidence=0.45, thesis="Old news", risk_notes="Unverified", sources=[])
    claude = Signal(action="LONG", confidence=0.65, thesis="Risk ok", risk_notes="High spread", sources=[])
    gemini = Signal(action="LONG", confidence=0.8, thesis="Pattern match", risk_notes="Volume drop", sources=[])

    event = MarketEvent(
        event_type="price_spike", instrument="BZ=F",
        severity=0.85, data={"price_change": 6.5}
    )

    aggregator = Aggregator()
    return aggregator.aggregate(
        event=event,
        grok=grok, perplexity=perp,
        claude=claude, gemini=gemini,
        prompt_hash="test_hash"
    )


@pytest.fixture
def sample_risk_allowed():
    """Risk check -- allowed"""
    return RiskCheck(
        allowed=True,
        reason="All checks passed — LONG approved",
        daily_alerts_count=3,
        cooldown_remaining_sec=0,
    )


@pytest.fixture
def sample_risk_blocked():
    """Risk check -- blocked"""
    return RiskCheck(
        allowed=False,
        reason="Daily loss limit reached: 2.5% >= 2.0%",
        daily_alerts_count=10,
        cooldown_remaining_sec=120,
    )


# ==============================================================================
# TESTS
# ==============================================================================

def test_format_signal_basic(notifier, sample_response):
    """Formatting without risk check"""
    message = notifier.format_signal(sample_response)

    assert "TRADING COUNCIL DECISION" in message
    assert "BZ=F" in message
    assert "LONG" in message
    assert "Grok" in message
    assert "Claude" in message
    assert "Gemini" in message
    assert "Perplexity" in message

    print(f"Basic format: {len(message)} chars")


def test_format_signal_with_risk_allowed(notifier, sample_response, sample_risk_allowed):
    """Formatting with allowed risk check"""
    message = notifier.format_signal(sample_response, sample_risk_allowed)

    assert "ALLOWED" in message
    assert "Risk Governor" in message

    print(f"Allowed risk format OK")


def test_format_signal_with_risk_blocked(notifier, sample_response, sample_risk_blocked):
    """Formatting with blocked risk check"""
    message = notifier.format_signal(sample_response, sample_risk_blocked)

    assert "BLOCKED" in message
    assert "Daily loss" in message or "daily loss" in message

    print(f"Blocked risk format OK")


def test_format_contains_votes(notifier, sample_response):
    """Message contains votes from each agent"""
    message = notifier.format_signal(sample_response)

    assert "90%" in message  # Grok confidence
    assert "45%" in message  # Perplexity confidence
    assert "65%" in message  # Claude confidence
    assert "80%" in message  # Gemini confidence

    print("All votes present in message")


def test_disabled_notifier(notifier, sample_response):
    """Disabled notifier doesn't send"""
    assert notifier.enabled is False

    result = notifier.send_signal(sample_response)
    assert result is False

    print("Disabled notifier handled gracefully")


def test_format_risks(notifier, sample_response):
    """Risks are included in message"""
    message = notifier.format_signal(sample_response)

    assert "Key Risks" in message

    print("Risks included in message")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
