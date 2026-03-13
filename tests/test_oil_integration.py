"""
End-to-end oil integration test.

Mocks all 3 event sources (price watcher, news scanner, EIA client),
all 4 agents, and verifies the full pipeline:
  sources -> agents -> aggregator -> forecast -> telegram format

Also verifies --dry-run does not call Telegram.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from council.aggregator import Aggregator
from journal.trade_journal import TradeJournal
from main import MockAgent, TradingCouncil
from models.schemas import MarketEvent, OilForecast, OilRiskScore, Signal
from notifications.telegram_notifier import TelegramNotifier
from risk.risk_governor import RiskGovernor
from watchers.eia_client import EIAClient
from watchers.oil_news_scanner import OilNewsScanner
from watchers.oil_price_watcher import OilPriceWatcher
from watchers.scheduled_events import ScheduledEventsManager


# ==============================================================================
# Helpers
# ==============================================================================

def _make_signal(action: str = "LONG", confidence: float = 0.8) -> Signal:
    return Signal(
        action=action,
        confidence=confidence,
        thesis=f"Test thesis for {action}",
        risk_notes="Test risk note",
        sources=[],
    )


def _make_price_event() -> MarketEvent:
    return MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.85,
        headline="Brent crude spike UP 3.5%",
        data={
            "price_change_pct": 3.5,
            "current_price": 83.00,
            "direction": "UP",
        },
    )


def _make_news_event() -> MarketEvent:
    return MarketEvent(
        event_type="opec_event",
        instrument="BZ=F",
        severity=0.9,
        headline="OPEC+ agrees deeper production cuts",
        data={"source": "oilprice", "link": "", "relevance_level": "high"},
    )


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def deterministic_agents() -> dict:
    """Four agents that always return predefined signals."""
    agents: dict = {}

    class FixedAgent(MockAgent):
        def __init__(self, name, action, confidence):
            super().__init__(name)
            self._action = action
            self._confidence = confidence

        def analyze(self, event, context):
            return _make_signal(self._action, self._confidence)

    agents["grok"] = FixedAgent("Grok", "LONG", 0.85)
    agents["perplexity"] = FixedAgent("Perplexity", "LONG", 0.70)
    agents["claude"] = FixedAgent("Claude", "WAIT", 0.40)
    agents["gemini"] = FixedAgent("Gemini", "LONG", 0.80)
    return agents


@pytest.fixture
def mock_price_watcher():
    watcher = MagicMock(spec=OilPriceWatcher)
    watcher.instruments = ["BZ=F", "LGO"]
    watcher.poll_once_async = AsyncMock(return_value=[_make_price_event()])
    watcher.get_latest_snapshot.return_value = MagicMock(
        price=83.0, high=84.0, low=82.0, volume=120000,
    )
    return watcher


@pytest.fixture
def mock_news_scanner():
    scanner = MagicMock(spec=OilNewsScanner)
    scanner.scan = AsyncMock(return_value=[_make_news_event()])
    return scanner


@pytest.fixture
def mock_eia_client():
    eia = MagicMock(spec=EIAClient)
    eia.get_crude_inventories = AsyncMock(return_value={
        "value": 430000, "date": "2026-03-06", "unit": "thousand barrels",
        "change_from_previous": -2100,
    })
    eia.get_production = AsyncMock(return_value={
        "value": 13200, "date": "2026-03-06", "unit": "thousand barrels/day",
        "change_from_previous": 50,
    })
    eia.get_refinery_utilization = AsyncMock(return_value={
        "value": 87.5, "date": "2026-03-06", "unit": "percent",
        "change_from_previous": 0.3,
    })
    return eia


@pytest.fixture
def mock_events_manager():
    mgr = MagicMock(spec=ScheduledEventsManager)
    mgr.is_event_window.return_value = False
    mgr.get_upcoming_events.return_value = [
        {"name": "EIA Weekly Petroleum Status", "datetime": "2026-03-11T10:30:00-05:00",
         "impact_level": "high", "description": "US crude inventories"},
    ]
    return mgr


@pytest.fixture
def pipeline_e2e(
    deterministic_agents,
    mock_price_watcher,
    mock_news_scanner,
    mock_eia_client,
    mock_events_manager,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        notifier = TelegramNotifier()  # disabled
        council = TradingCouncil(
            agents=deterministic_agents,
            aggregator=Aggregator(),
            risk_governor=RiskGovernor(min_confidence=0.5, min_strength="STRONG"),
            journal=TradeJournal(journal_path=Path(tmpdir) / "e2e.json"),
            notifier=notifier,
            price_watcher=mock_price_watcher,
            news_scanner=mock_news_scanner,
            events_manager=mock_events_manager,
            eia_client=mock_eia_client,
            dry_run=True,
            min_confidence=0.5,
        )
        yield council


# ==============================================================================
# Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_full_e2e_pipeline(pipeline_e2e):
    """Sources -> agents -> aggregator -> forecast -> telegram format."""
    results = await pipeline_e2e.run_once()

    # We expect events from price watcher + news scanner
    assert len(results) >= 1

    for r in results:
        cr = r["council_response"]
        assert cr.instrument == "BZ=F"
        assert cr.consensus in ("LONG", "SHORT", "WAIT")
        # 3 agents said LONG, 1 WAIT -> consensus should be LONG, STRONG
        assert cr.consensus == "LONG"
        # Aggregator v2: confidence-weighted → 3 LONG at high conf = UNANIMOUS
        assert cr.consensus_strength == "UNANIMOUS"


@pytest.mark.asyncio
async def test_forecast_created(pipeline_e2e):
    """A forecast is produced when consensus is actionable."""
    results = await pipeline_e2e.run_once()

    forecasts = [r.get("forecast") for r in results if r.get("forecast") is not None]
    assert len(forecasts) >= 1

    fc = forecasts[0]
    assert isinstance(fc, OilForecast)
    assert fc.direction == "BULLISH"
    assert fc.instrument == "BZ=F"
    assert fc.current_price > 0
    assert fc.target_price > fc.current_price


@pytest.mark.asyncio
async def test_telegram_format():
    """The formatted oil alert contains all required fields."""
    forecast = OilForecast(
        instrument="BZ=F",
        direction="BULLISH",
        confidence=0.75,
        timeframe_hours=24,
        current_price=83.00,
        target_price=85.00,
        stop_loss_price=81.00,
        drivers=["OPEC cuts", "EIA draw"],
        risks=["Demand weakness"],
        risk_score=OilRiskScore(
            geopolitical=0.6, supply=0.7, demand=0.4,
            financial=0.3, seasonal=0.2, technical=0.3,
        ),
    )

    signal_long = _make_signal("LONG", 0.8)
    signal_wait = _make_signal("WAIT", 0.3)
    event = MarketEvent(
        event_type="price_spike", instrument="BZ=F", severity=0.8, data={},
    )
    agg = Aggregator()
    council = agg.aggregate(
        event=event,
        grok=signal_long, perplexity=signal_long,
        claude=signal_long, gemini=signal_wait,
        prompt_hash="test",
    )

    msg = TelegramNotifier.format_oil_alert(forecast, council)

    assert "OIL ALERT" in msg
    assert "BZ=F" in msg
    assert "BULLISH" in msg
    assert "75%" in msg
    assert "24h" in msg
    assert "$85.00" in msg
    assert "OPEC cuts" in msg
    assert "Demand weakness" in msg
    assert "NOT financial advice" in msg


@pytest.mark.asyncio
async def test_dry_run_does_not_call_telegram(
    deterministic_agents,
    mock_price_watcher,
    mock_news_scanner,
    mock_eia_client,
    mock_events_manager,
):
    """In dry-run mode, the notifier's send method is never invoked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notifier = TelegramNotifier(bot_token="fake_token", chat_id="fake_chat")
        notifier._send_message = AsyncMock(return_value=True)

        council = TradingCouncil(
            agents=deterministic_agents,
            aggregator=Aggregator(),
            risk_governor=RiskGovernor(min_confidence=0.3, min_strength="WEAK"),
            journal=TradeJournal(journal_path=Path(tmpdir) / "dry.json"),
            notifier=notifier,
            price_watcher=mock_price_watcher,
            news_scanner=mock_news_scanner,
            events_manager=mock_events_manager,
            eia_client=mock_eia_client,
            dry_run=True,
            min_confidence=0.3,
        )

        await council.run_once()

        # _send_message should NOT have been called because dry_run=True
        notifier._send_message.assert_not_called()


@pytest.mark.asyncio
async def test_non_dry_run_calls_telegram(
    deterministic_agents,
    mock_price_watcher,
    mock_news_scanner,
    mock_eia_client,
    mock_events_manager,
):
    """When dry_run=False and confidence is above threshold, Telegram is called."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notifier = TelegramNotifier(bot_token="fake_token", chat_id="fake_chat")
        notifier._send_message = AsyncMock(return_value=True)

        council = TradingCouncil(
            agents=deterministic_agents,
            aggregator=Aggregator(),
            risk_governor=RiskGovernor(min_confidence=0.3, min_strength="WEAK"),
            journal=TradeJournal(journal_path=Path(tmpdir) / "live.json"),
            notifier=notifier,
            price_watcher=mock_price_watcher,
            news_scanner=mock_news_scanner,
            events_manager=mock_events_manager,
            eia_client=mock_eia_client,
            dry_run=False,
            min_confidence=0.3,
        )

        await council.run_once()

        # With 3 LONG agents, consensus is LONG -> forecast should be built
        # and _send_message should be called
        assert notifier._send_message.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
