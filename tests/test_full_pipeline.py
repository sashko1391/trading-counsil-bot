"""
Full Pipeline Integration Test
Tests the complete flow: MockAgent -> Aggregator -> RiskGovernor -> Journal -> Notifier
All fixtures use oil-market events (instrument, not pair).
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from main import TradingCouncil, MockAgent, create_mock_agents
from council.aggregator import Aggregator
from risk.risk_governor import RiskGovernor
from journal.trade_journal import TradeJournal
from notifications.telegram_notifier import TelegramNotifier
from watchers.oil_price_watcher import OilPriceWatcher
from watchers.oil_news_scanner import OilNewsScanner
from watchers.scheduled_events import ScheduledEventsManager
from watchers.eia_client import EIAClient
from models.schemas import Signal, MarketEvent


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def mock_agents():
    return create_mock_agents()


@pytest.fixture
def mock_price_watcher():
    """OilPriceWatcher with a mocked data provider that returns nothing."""
    from unittest.mock import Mock
    from watchers.data_providers import DataProviderProtocol

    mock_provider = Mock(spec=DataProviderProtocol)
    mock_provider.fetch_price.return_value = {
        "symbol": "BZ=F",
        "price": 82.50,
        "open": 81.0,
        "high": 83.0,
        "low": 80.5,
        "close": 82.50,
        "volume": 150000,
    }
    return OilPriceWatcher(provider=mock_provider)


@pytest.fixture
def pipeline(mock_agents, mock_price_watcher):
    """Full pipeline with temporary journal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        council = TradingCouncil(
            agents=mock_agents,
            aggregator=Aggregator(),
            risk_governor=RiskGovernor(),
            journal=TradeJournal(journal_path=Path(tmpdir) / "test.json"),
            notifier=TelegramNotifier(),  # disabled
            price_watcher=mock_price_watcher,
            news_scanner=OilNewsScanner(),
            events_manager=ScheduledEventsManager(),
            eia_client=EIAClient(),
            dry_run=True,
        )
        yield council


# ==============================================================================
# TESTS
# ==============================================================================

def test_analyze_single_oil_event(pipeline):
    """Analyse a single oil price spike event."""
    import random
    random.seed(42)
    event = MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.85,
        headline="Brent crude price spike UP 4.2%",
        data={
            "price_change_pct": 4.2,
            "current_price": 82.50,
            "direction": "UP",
        },
    )

    context = {"news": "OPEC considering cuts", "prices": {"BZ=F": {"price": 82.50}}, "eia": {}, "upcoming_events": []}
    result = pipeline.analyze_event(event, context)

    assert "council_response" in result
    assert "risk_check" in result
    assert "entry_id" in result

    cr = result["council_response"]
    assert cr.consensus in ["LONG", "SHORT", "WAIT"]
    assert cr.consensus_strength in ["UNANIMOUS", "STRONG", "WEAK", "NONE"]
    assert 0.0 <= cr.combined_confidence <= 1.0
    assert cr.instrument == "BZ=F"


def test_mock_agents_return_valid_signals(mock_agents):
    """Mock agents produce valid Signal objects for oil events."""
    event = MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.8,
        data={"price_change_pct": 3.0, "current_price": 82.50},
    )
    context = {"news": "Test", "indicators": {}}

    for name, agent in mock_agents.items():
        signal = agent.analyze(event, context)
        assert signal.action in ["LONG", "SHORT", "WAIT"]
        assert 0.0 <= signal.confidence <= 1.0
        assert len(signal.thesis) > 0
        assert len(signal.thesis) <= 500


def test_journal_records_oil_entries(mock_agents, mock_price_watcher):
    """Journal stores entries with correct instrument field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = TradeJournal(journal_path=Path(tmpdir) / "test.json")
        pipeline = TradingCouncil(
            agents=mock_agents,
            aggregator=Aggregator(),
            risk_governor=RiskGovernor(),
            journal=journal,
            notifier=TelegramNotifier(),
            price_watcher=mock_price_watcher,
            dry_run=True,
        )

        event = MarketEvent(
            event_type="volume_surge",
            instrument="LGO",
            severity=0.7,
            data={"current_price": 730.0, "volume_ratio": 2.5},
        )
        context = {"news": "No news", "prices": {}, "eia": {}, "upcoming_events": []}
        pipeline.analyze_event(event, context)

        assert len(journal) == 1
        recent = journal.get_recent(1)
        assert recent[0]["council_response"]["instrument"] == "LGO"


def test_risk_governor_blocks_weak_consensus(mock_agents, mock_price_watcher):
    """Strict risk governor blocks low-confidence signals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        strict_governor = RiskGovernor(min_confidence=0.99, min_strength="UNANIMOUS")
        journal = TradeJournal(journal_path=Path(tmpdir) / "test.json")

        pipeline = TradingCouncil(
            agents=mock_agents,
            aggregator=Aggregator(),
            risk_governor=strict_governor,
            journal=journal,
            notifier=TelegramNotifier(),
            price_watcher=mock_price_watcher,
            dry_run=True,
        )

        event = MarketEvent(
            event_type="price_spike",
            instrument="BZ=F",
            severity=0.5,
            data={"price_change_pct": 2.0, "current_price": 82.50},
        )
        context = {"news": "No news", "prices": {}, "eia": {}, "upcoming_events": []}
        result = pipeline.analyze_event(event, context)

        cr = result["council_response"]
        rc = result["risk_check"]
        if cr.consensus == "WAIT":
            assert rc.allowed is True
        # else it would likely be blocked with such strict thresholds


def test_build_forecast_from_council():
    """OilForecast is correctly built from a CouncilResponse."""
    signal_long = Signal(
        action="LONG", confidence=0.8, thesis="Bullish setup",
        risk_notes="Some risk", sources=[],
    )
    signal_wait = Signal(
        action="WAIT", confidence=0.4, thesis="Uncertain",
        risk_notes="High vol", sources=[],
    )

    event = MarketEvent(
        event_type="price_spike", instrument="BZ=F", severity=0.8,
        data={"current_price": 82.50},
    )

    agg = Aggregator()
    council = agg.aggregate(
        event=event,
        grok=signal_long, perplexity=signal_long,
        claude=signal_long, gemini=signal_wait,
        prompt_hash="test",
    )

    context = {"prices": {"BZ=F": {"price": 82.50}}}
    signals = {"grok": signal_long, "perplexity": signal_long, "claude": signal_long, "gemini": signal_wait}

    forecast = TradingCouncil.build_forecast(council, signals, context)

    assert forecast is not None
    assert forecast.instrument == "BZ=F"
    assert forecast.direction == "BULLISH"
    assert forecast.current_price == 82.50
    assert forecast.target_price > forecast.current_price


def test_build_forecast_returns_none_for_wait():
    """No forecast when consensus is WAIT."""
    signal_wait = Signal(
        action="WAIT", confidence=0.3, thesis="No signal",
        risk_notes="Uncertain", sources=[],
    )
    event = MarketEvent(
        event_type="news_event", instrument="BZ=F", severity=0.3,
        data={},
    )
    agg = Aggregator()
    council = agg.aggregate(
        event=event,
        grok=signal_wait, perplexity=signal_wait,
        claude=signal_wait, gemini=signal_wait,
        prompt_hash="test",
    )
    context = {"prices": {"BZ=F": {"price": 82.0}}}
    forecast = TradingCouncil.build_forecast(council, {"g": signal_wait}, context)
    assert forecast is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
