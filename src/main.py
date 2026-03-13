"""
Oil Trading Intelligence Bot -- Main Pipeline

Orchestrates all components in one async loop:
1. Three event sources: OilPriceWatcher, OilNewsScanner, ScheduledEventsManager
2. Build rich context (prices, news, EIA data, event proximity)
3. All 4 AI agents analyse each event
4. Aggregator produces council consensus
5. Build OilForecast from council response
6. Telegram notifier sends alert if confidence > MIN_CONFIDENCE
7. Repeat on configurable interval (default 5 min)

USAGE:
    python -m main                 # full run
    python -m main --dry-run       # mock agents, no Telegram
    python -m main --once          # single poll, then exit
    python -m main --dry-run --once
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# Local modules
from config.settings import get_settings
from config.prompts import format_user_prompt
from council.aggregator import Aggregator
from council.base_agent import BaseAgent
from council.claude_agent import ClaudeAgent
from council.gemini_agent import GeminiAgent
from council.grok_agent import GrokAgent
from council.perplexity_agent import PerplexityAgent
from models.schemas import (
    CouncilResponse,
    MarketEvent,
    OilForecast,
    OilRiskScore,
    Signal,
)
from notifications.telegram_notifier import TelegramNotifier
from risk.risk_governor import RiskGovernor
from journal.trade_journal import TradeJournal
from watchers.oil_price_watcher import OilPriceWatcher
from watchers.oil_news_scanner import OilNewsScanner
from watchers.scheduled_events import ScheduledEventsManager
from watchers.eia_client import EIAClient


# ==============================================================================
# MOCK AGENT (for dry-run)
# ==============================================================================

class MockAgent(BaseAgent):
    """Fake agent for testing the pipeline without real API calls."""

    def __init__(self, name: str, default_action: str = "WAIT"):
        super().__init__(api_key="mock", name=name)
        self.default_action = default_action

    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        import random

        actions = ["LONG", "SHORT", "WAIT"]
        weights = {
            "LONG": [0.4, 0.2, 0.4],
            "SHORT": [0.2, 0.4, 0.4],
            "WAIT": [0.2, 0.2, 0.6],
        }

        action = random.choices(
            actions,
            weights=weights.get(self.default_action, [0.33, 0.33, 0.34]),
        )[0]

        current_price = event.data.get("current_price", 0)
        return Signal(
            action=action,
            confidence=round(random.uniform(0.3, 0.9), 2),
            thesis=f"[MOCK {self.name}] Simulated analysis for {event.instrument} {event.event_type}",
            invalidation_price=round(current_price * 0.97, 2) if current_price else None,
            risk_notes=f"[MOCK] Simulated risk from {self.name}",
            sources=[],
        )


# ==============================================================================
# TRADING COUNCIL (orchestrator)
# ==============================================================================

class TradingCouncil:
    """
    Main orchestrator -- wires all components together.

    Attributes
    ----------
    agents : dict mapping name -> BaseAgent
    aggregator : Aggregator
    risk_governor : RiskGovernor
    journal : TradeJournal
    notifier : TelegramNotifier
    price_watcher : OilPriceWatcher
    news_scanner : OilNewsScanner
    events_manager : ScheduledEventsManager
    eia_client : EIAClient
    dry_run : bool  -- if True, print to console instead of Telegram
    min_confidence : float -- threshold for sending alerts
    """

    def __init__(
        self,
        agents: dict,
        aggregator: Aggregator,
        risk_governor: RiskGovernor,
        journal: TradeJournal,
        notifier: TelegramNotifier,
        price_watcher: OilPriceWatcher,
        news_scanner: Optional[OilNewsScanner] = None,
        events_manager: Optional[ScheduledEventsManager] = None,
        eia_client: Optional[EIAClient] = None,
        dry_run: bool = False,
        min_confidence: float = 0.6,
    ):
        self.agents = agents
        self.aggregator = aggregator
        self.risk_governor = risk_governor
        self.journal = journal
        self.notifier = notifier
        self.price_watcher = price_watcher
        self.news_scanner = news_scanner or OilNewsScanner()
        self.events_manager = events_manager or ScheduledEventsManager()
        self.eia_client = eia_client or EIAClient()
        self.dry_run = dry_run
        self.min_confidence = min_confidence
        self.running = False

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    async def _build_context(self) -> dict:
        """
        Gather rich context from all data sources:
        prices, recent news, EIA data, upcoming scheduled events.
        """
        context: dict = {}

        # 1. Current prices from the price watcher history
        prices = {}
        for symbol in self.price_watcher.instruments:
            snap = self.price_watcher.get_latest_snapshot(symbol)
            if snap:
                prices[symbol] = {
                    "price": snap.price,
                    "high": snap.high,
                    "low": snap.low,
                    "volume": snap.volume,
                }
        context["prices"] = prices

        # 2. Recent news (best-effort)
        try:
            news_events = await self.news_scanner.scan()
            headlines = [e.headline for e in news_events[:10]]
            context["news"] = "\n".join(headlines) if headlines else "No recent news"
        except Exception as exc:
            logger.warning(f"News scanner error: {exc}")
            context["news"] = "News unavailable"

        # 3. EIA data (best-effort)
        eia_data: dict = {}
        try:
            inv = await self.eia_client.get_crude_inventories()
            if inv:
                eia_data["crude_inventories"] = inv
            prod = await self.eia_client.get_production()
            if prod:
                eia_data["production"] = prod
            util = await self.eia_client.get_refinery_utilization()
            if util:
                eia_data["refinery_utilization"] = util
        except Exception as exc:
            logger.warning(f"EIA client error: {exc}")
        context["eia"] = eia_data

        # 4. Upcoming scheduled events
        try:
            upcoming = self.events_manager.get_upcoming_events(hours_ahead=48)
            context["upcoming_events"] = upcoming[:5]
        except Exception as exc:
            logger.warning(f"Scheduled events error: {exc}")
            context["upcoming_events"] = []

        return context

    # ------------------------------------------------------------------
    # Event analysis
    # ------------------------------------------------------------------

    def analyze_event(self, event: MarketEvent, context: dict) -> dict:
        """
        Pass a single event through all 4 agents, aggregate, risk-check,
        journal, and optionally notify.
        """
        logger.info(
            f"Event: {event.event_type} on {event.instrument} "
            f"(severity: {event.severity:.0%})"
        )

        # Format user prompt with rich context
        user_prompt = format_user_prompt(
            event_type=event.event_type,
            instrument=event.instrument,
            market_data=event.data,
            news=context.get("news", "No recent news"),
            indicators={
                "eia": context.get("eia", {}),
                "upcoming_events": context.get("upcoming_events", []),
                "prices": context.get("prices", {}),
            },
        )

        # 1. Collect signals from all agents
        logger.info("Querying all 4 agents...")
        signals: dict[str, Signal] = {}
        for name, agent in self.agents.items():
            try:
                logger.info(f"  -> {name.upper()}...")
                sig = agent.analyze(event, {"prompt": user_prompt, **context})
                signals[name] = sig
                logger.info(f"    {name}: {sig.action} ({sig.confidence:.0%})")
            except Exception as exc:
                logger.error(f"    {name} failed: {exc}")
                signals[name] = Signal(
                    action="WAIT",
                    confidence=0.0,
                    thesis=f"{name} agent error",
                    risk_notes="Technical error",
                    sources=[],
                )

        # 2. Aggregate
        logger.info("Aggregating signals...")
        first_agent = next(iter(self.agents.values()))
        prompt_hash = first_agent.hash_prompt(
            f"{event.event_type}_{event.instrument}_{datetime.now().isoformat()}"
        )

        council_response = self.aggregator.aggregate(
            event=event,
            grok=signals.get("grok", signals[next(iter(signals))]),
            perplexity=signals.get("perplexity", signals[next(iter(signals))]),
            claude=signals.get("claude", signals[next(iter(signals))]),
            gemini=signals.get("gemini", signals[next(iter(signals))]),
            prompt_hash=prompt_hash,
        )

        logger.info(
            f"Consensus: {council_response.consensus} "
            f"({council_response.consensus_strength}, "
            f"{council_response.combined_confidence:.0%})"
        )

        # 3. Risk Governor
        daily_pnl = self.journal.get_daily_pnl()
        risk_check = self.risk_governor.check(
            council_response=council_response,
            daily_pnl=daily_pnl,
        )
        logger.info(
            f"Risk Governor: {'ALLOWED' if risk_check.allowed else 'BLOCKED'} "
            f"-- {risk_check.reason}"
        )

        # 4. Journal
        entry_id = self.journal.add_entry(event, council_response, risk_check)
        logger.info(f"Journal entry: {entry_id}")

        return {
            "council_response": council_response,
            "risk_check": risk_check,
            "entry_id": entry_id,
            "signals": signals,
            "context": context,
        }

    # ------------------------------------------------------------------
    # Forecast builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_forecast(
        council: CouncilResponse,
        signals: dict[str, Signal],
        context: dict,
    ) -> Optional[OilForecast]:
        """
        Convert a CouncilResponse into an OilForecast.
        Returns None when consensus is WAIT or data is insufficient.
        """
        if council.consensus == "WAIT":
            return None

        direction_map = {"LONG": "BULLISH", "SHORT": "BEARISH"}
        direction = direction_map.get(council.consensus, "NEUTRAL")

        # Current price from context or latest signal data
        prices = context.get("prices", {})
        instrument = council.instrument
        price_info = prices.get(instrument, {})
        current_price = price_info.get("price", 0.0)

        # Fallback: try invalidation_price from signals as price proxy
        if current_price == 0:
            for sig in signals.values():
                if sig.invalidation_price and sig.invalidation_price > 0:
                    current_price = sig.invalidation_price
                    break

        if current_price == 0:
            return None

        # Target: simple heuristic -- move proportional to confidence
        move_pct = council.combined_confidence * 3.0  # max ~3 %
        if direction == "BEARISH":
            move_pct = -move_pct
        target_price = round(current_price * (1 + move_pct / 100), 2)

        stop_loss = council.invalidation_price

        # Drivers from agent theses
        drivers = [
            sig.thesis[:120]
            for sig in signals.values()
            if sig.action == council.consensus and sig.thesis
        ][:4]
        if not drivers:
            drivers = ["Council consensus"]

        # Risks from aggregator
        risks = council.key_risks[:4] if council.key_risks else ["See full report"]

        risk_score = OilRiskScore(
            geopolitical=0.5,
            supply=0.5,
            demand=0.5,
            financial=0.3,
            seasonal=0.3,
            technical=0.3,
        )

        return OilForecast(
            instrument=instrument,
            direction=direction,
            confidence=council.combined_confidence,
            timeframe_hours=24,
            current_price=current_price,
            target_price=target_price,
            stop_loss_price=stop_loss,
            drivers=drivers,
            risks=risks,
            risk_score=risk_score,
        )

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------

    async def _notify(
        self,
        forecast: Optional[OilForecast],
        council: CouncilResponse,
        risk_check,
    ) -> None:
        """Send notification if appropriate."""
        if forecast is None:
            return

        if forecast.confidence < self.min_confidence:
            logger.info(
                f"Skipping alert: confidence {forecast.confidence:.0%} "
                f"< {self.min_confidence:.0%}"
            )
            return

        if self.dry_run:
            msg = TelegramNotifier.format_oil_alert(forecast, council)
            logger.info(f"[DRY-RUN] Oil alert:\n{msg}")
            return

        try:
            await self.notifier.send_oil_alert(forecast, council)
        except Exception as exc:
            logger.error(f"Notification error: {exc}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run_once(self) -> list[dict]:
        """Single polling cycle: gather events from all sources, analyse each."""
        logger.info("Polling market sources...")

        all_events: list[MarketEvent] = []

        # Source 1: Price watcher
        try:
            price_events = await self.price_watcher.poll_once_async()
            all_events.extend(price_events)
        except Exception as exc:
            logger.error(f"Price watcher error: {exc}")

        # Source 2: News scanner
        try:
            news_events = await self.news_scanner.scan()
            all_events.extend(news_events)
        except Exception as exc:
            logger.error(f"News scanner error: {exc}")

        # Source 3: Scheduled events (generate event if inside an event window)
        try:
            if self.events_manager.is_event_window("EIA Weekly Petroleum Status"):
                all_events.append(
                    MarketEvent(
                        event_type="eia_report",
                        instrument="BZ=F",
                        severity=0.8,
                        headline="EIA Weekly Petroleum Status window active",
                        data={"source": "scheduled_events"},
                    )
                )
        except Exception as exc:
            logger.error(f"Scheduled events error: {exc}")

        if not all_events:
            logger.info("No events detected. Market is calm.")
            return []

        logger.info(f"Found {len(all_events)} events")

        # Build rich context once per cycle
        context = await self._build_context()

        results: list[dict] = []
        for event in all_events:
            try:
                result = self.analyze_event(event, context)
                council = result["council_response"]
                signals = result["signals"]

                forecast = self.build_forecast(council, signals, context)
                await self._notify(forecast, council, result["risk_check"])

                result["forecast"] = forecast
                results.append(result)
            except Exception as exc:
                logger.error(f"Error analysing event: {exc}")

        return results

    async def run(self, poll_interval: int = 300) -> None:
        """Main async loop -- runs until stopped via stop()."""
        self.running = True
        cycle = 0

        logger.info("=" * 60)
        logger.info("OIL TRADING INTELLIGENCE BOT STARTED")
        logger.info(f"   Agents: {list(self.agents.keys())}")
        logger.info(f"   Poll interval: {poll_interval}s")
        logger.info(f"   Journal: {self.journal.journal_path}")
        logger.info(f"   Telegram: {'enabled' if self.notifier.enabled else 'disabled'}")
        logger.info(f"   Dry-run: {self.dry_run}")
        logger.info("=" * 60)

        while self.running:
            cycle += 1
            logger.info(f"\n{'─' * 40}")
            logger.info(f"Cycle #{cycle} -- {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"{'─' * 40}")

            await self.run_once()

            if not self.running:
                break

            logger.info(f"Sleeping {poll_interval}s until next cycle...")

            # Sleep in 1-second increments so stop() takes effect promptly
            for _ in range(poll_interval):
                if not self.running:
                    break
                await asyncio.sleep(1)

        logger.info("\nOil Trading Intelligence Bot stopped.")
        stats = self.journal.get_stats()
        logger.info(f"Session stats: {stats}")

    def stop(self) -> None:
        """Signal the main loop to stop."""
        logger.info("Stop signal received...")
        self.running = False


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_real_agents(settings) -> dict:
    """Create agents with real API keys from settings."""
    agents: dict = {}

    try:
        agents["grok"] = GrokAgent(
            api_key=settings.XAI_API_KEY,
            model=settings.GROK_MODEL,
        )
        logger.info("Grok agent created")
    except Exception as exc:
        logger.warning(f"Grok agent failed: {exc}")

    try:
        if settings.PERPLEXITY_API_KEY:
            agents["perplexity"] = PerplexityAgent(api_key=settings.PERPLEXITY_API_KEY)
            logger.info("Perplexity agent created")
        else:
            agents["perplexity"] = MockAgent("Perplexity", default_action="WAIT")
            logger.info("Perplexity: using mock (no API key)")
    except Exception as exc:
        agents["perplexity"] = MockAgent("Perplexity", default_action="WAIT")
        logger.warning(f"Perplexity agent failed, using mock: {exc}")

    try:
        agents["claude"] = ClaudeAgent(api_key=settings.ANTHROPIC_API_KEY)
        logger.info("Claude agent created")
    except Exception as exc:
        logger.warning(f"Claude agent failed: {exc}")

    try:
        agents["gemini"] = GeminiAgent(api_key=settings.GOOGLE_AI_API_KEY or settings.GOOGLE_API_KEY)
        logger.info("Gemini agent created")
    except Exception as exc:
        logger.warning(f"Gemini agent failed: {exc}")

    return agents


def create_mock_agents() -> dict:
    """Create mock agents for dry-run mode."""
    return {
        "grok": MockAgent("Grok", default_action="LONG"),
        "perplexity": MockAgent("Perplexity", default_action="WAIT"),
        "claude": MockAgent("Claude", default_action="WAIT"),
        "gemini": MockAgent("Gemini", default_action="LONG"),
    }


# ==============================================================================
# MAIN
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Oil Trading Intelligence Bot -- AI-powered oil market analysis",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mock agents, no Telegram")
    parser.add_argument("--once", action="store_true", help="Single poll cycle, then exit")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds (default 300)")

    args = parser.parse_args()

    # Logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        level="INFO",
    )
    logger.add(
        "data/logs/bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
    )

    # Build components
    if args.dry_run:
        logger.info("DRY-RUN MODE -- using mock agents")
        agents = create_mock_agents()
        price_watcher = OilPriceWatcher()
        news_scanner = OilNewsScanner()
        events_manager = ScheduledEventsManager()
        eia_client = EIAClient()
        telegram_token = None
        telegram_chat = None
        telegram_chat_ids = None
        journal_path = Path("data/trades_dryrun.json")
        min_confidence = 0.6
    else:
        logger.info("Loading settings...")
        try:
            settings = get_settings()
            agents = create_real_agents(settings)
            price_watcher = OilPriceWatcher()
            news_scanner = OilNewsScanner()
            events_manager = ScheduledEventsManager()
            eia_client = EIAClient(api_key=settings.EIA_API_KEY)
            telegram_token = settings.TELEGRAM_BOT_TOKEN
            telegram_chat = settings.TELEGRAM_CHAT_ID
            telegram_chat_ids = settings.TELEGRAM_CHAT_IDS
            journal_path = settings.JOURNAL_PATH
            min_confidence = settings.MIN_CONFIDENCE
        except Exception as exc:
            logger.error(f"Failed to load settings: {exc}")
            logger.info("Try running with --dry-run flag")
            sys.exit(1)

    aggregator = Aggregator()
    risk_governor = RiskGovernor()
    journal = TradeJournal(journal_path=journal_path)
    notifier = TelegramNotifier(bot_token=telegram_token, chat_id=telegram_chat, chat_ids=telegram_chat_ids)

    council = TradingCouncil(
        agents=agents,
        aggregator=aggregator,
        risk_governor=risk_governor,
        journal=journal,
        notifier=notifier,
        price_watcher=price_watcher,
        news_scanner=news_scanner,
        events_manager=events_manager,
        eia_client=eia_client,
        dry_run=args.dry_run,
        min_confidence=min_confidence,
    )

    # Graceful shutdown
    loop = asyncio.new_event_loop()

    def signal_handler(sig, frame):
        council.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run
    if args.once:
        logger.info("Running ONE cycle...")
        results = loop.run_until_complete(council.run_once())
        logger.info(f"\nResults: {len(results)} events analysed")
        for r in results:
            cr = r["council_response"]
            rc = r["risk_check"]
            logger.info(
                f"   {cr.instrument}: {cr.consensus} ({cr.consensus_strength}) "
                f"-- {'ALLOWED' if rc.allowed else 'BLOCKED'} {rc.reason}"
            )
    else:
        loop.run_until_complete(council.run(poll_interval=args.interval))


if __name__ == "__main__":
    main()
