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
from datetime import datetime, timedelta
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
from notifications.digest_summarizer import DigestSummarizer
from risk.risk_governor import RiskGovernor
from journal.trade_journal import TradeJournal
from journal.digest_history import DigestHistory, DigestRecord
from journal.agent_memory import AgentMemory
from journal.daily_summary import DailySummaryHistory
from watchers.oil_price_watcher import OilPriceWatcher
from watchers.oil_news_scanner import OilNewsScanner
from watchers.scheduled_events import ScheduledEventsManager
from watchers.eia_client import EIAClient
from watchers.regime_detector import RegimeDetector
from watchers.microstructure import MicrostructureProvider
from metrics.post_mortem import PostMortemTracker
from metrics.weight_calibrator import WeightCalibrator
from knowledge.historical_analogues import HistoricalAnalogueFinder
from watchers.seasonal import get_seasonal_context, format_seasonal_for_prompt
from watchers.volatility_watcher import VolatilityWatcher
from watchers.macro_watcher import MacroWatcher
from watchers.cot_client import COTClient
from watchers.weather_watcher import WeatherWatcher
from watchers.refinery_margins import RefineryMarginsWatcher


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
        digest_interval_hours: int = 3,
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
        self.digest_interval_hours = digest_interval_hours
        self.digest_history = DigestHistory()
        self.agent_memory = AgentMemory()
        self.daily_summary = DailySummaryHistory()
        self.regime_detector = RegimeDetector()
        self.post_mortem = PostMortemTracker()
        self.weight_calibrator = WeightCalibrator(
            default_weights=dict(self.aggregator.weights)
        )
        self.microstructure = MicrostructureProvider()
        self.analogue_finder = HistoricalAnalogueFinder()
        self.volatility_watcher = VolatilityWatcher()
        self.macro_watcher = MacroWatcher()
        self.cot_client = COTClient()
        self.weather_watcher = WeatherWatcher()
        self.refinery_margins = RefineryMarginsWatcher()
        self._current_day: str = datetime.now().strftime("%Y-%m-%d")
        self.running = False

        # Accumulator: stores analyses between digest cycles
        # Key: instrument, Value: list of analysis dicts
        self._accumulator: dict[str, list[dict]] = {}
        self._last_digest_time: datetime = datetime.now()

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

        # 5. Market regime detection per instrument
        regimes: dict[str, str] = {}
        for symbol in self.price_watcher.instruments:
            try:
                history = getattr(self.price_watcher, "_history", {}).get(symbol, [])
                if len(history) >= 10:
                    prices = [snap.price for snap in history]
                    analysis = self.regime_detector.detect(prices)
                    regimes[symbol] = self.regime_detector.format_for_prompt(analysis)
                    logger.info(
                        f"Regime {symbol}: {analysis.regime} "
                        f"(conf={analysis.confidence:.0%}, vol={analysis.volatility_pct:.1f}%)"
                    )
                else:
                    regimes[symbol] = "Недостатньо даних для визначення режиму"
            except Exception as exc:
                logger.warning(f"Regime detection error for {symbol}: {exc}")
                regimes[symbol] = "Помилка визначення режиму"
        context["regimes"] = regimes

        # 6. Market microstructure data (futures curve, crack spread)
        try:
            brent_price = prices.get("BZ=F", {}).get("price", 0.0)
            ms_data = self.microstructure.fetch(brent_price)
            ms_text = self.microstructure.format_for_prompt(ms_data)
            context["microstructure"] = ms_text
        except Exception as exc:
            logger.warning(f"Microstructure fetch error: {exc}")
            context["microstructure"] = ""

        # 7. Previous digest history (for cross-digest learning)
        digest_contexts: dict[str, str] = {}
        for instrument in self.price_watcher.instruments:
            hist = self.digest_history.get_context_for_agents(instrument, n=4)
            if hist:
                digest_contexts[instrument] = hist
        context["digest_history"] = digest_contexts

        # 6. Daily summaries (multi-day trend context)
        daily_contexts: dict[str, str] = {}
        for instrument in self.price_watcher.instruments:
            daily = self.daily_summary.get_context_for_agents(instrument, n=7)
            if daily:
                daily_contexts[instrument] = daily
        context["daily_history"] = daily_contexts

        # 8. Seasonal context
        try:
            seasonal_ctx = get_seasonal_context()
            context["seasonal"] = format_seasonal_for_prompt(seasonal_ctx)
        except Exception as exc:
            logger.warning(f"Seasonal context error: {exc}")
            context["seasonal"] = ""

        # 9. OVX volatility context
        try:
            vol_snap = self.volatility_watcher.fetch()
            context["volatility"] = vol_snap.to_prompt_text()
        except Exception as exc:
            logger.warning(f"Volatility watcher error: {exc}")
            context["volatility"] = ""

        # 10. Macro correlations (DXY, FX)
        try:
            macro_snap = self.macro_watcher.fetch()
            context["macro"] = macro_snap.to_prompt_text()
        except Exception as exc:
            logger.warning(f"Macro watcher error: {exc}")
            context["macro"] = ""

        # 11. CFTC COT positioning
        try:
            cot_data = self.cot_client.fetch()
            context["cot"] = cot_data.to_prompt_text()
        except Exception as exc:
            logger.warning(f"COT client error: {exc}")
            context["cot"] = ""

        # 12. Weather / hurricane context
        try:
            weather_snap = self.weather_watcher.fetch()
            context["weather"] = weather_snap.to_prompt_text()
        except Exception as exc:
            logger.warning(f"Weather watcher error: {exc}")
            context["weather"] = ""

        # 13. Refinery margins (3-2-1 crack spread)
        try:
            brent_price = prices.get("BZ=F", {}).get("price", 0.0)
            ref_margins = self.refinery_margins.fetch(brent_price)
            context["refinery_margins"] = ref_margins.to_prompt_text()
        except Exception as exc:
            logger.warning(f"Refinery margins error: {exc}")
            context["refinery_margins"] = ""

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

        # Format user prompt with rich context + regime
        regime_text = context.get("regimes", {}).get(
            event.instrument, "No regime data available"
        )
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
            market_regime=regime_text,
        )

        # Inject previous digest history for cross-digest learning
        digest_hist = context.get("digest_history", {}).get(event.instrument, "")
        if digest_hist:
            user_prompt += f"\n\n{digest_hist}\n"

        # Inject daily summaries for multi-day trend context
        daily_hist = context.get("daily_history", {}).get(event.instrument, "")
        if daily_hist:
            user_prompt += f"\n\n{daily_hist}\n"

        # Inject microstructure data
        ms_text = context.get("microstructure", "")
        if ms_text:
            user_prompt += f"\n\n{ms_text}\n"

        # Inject seasonal context
        seasonal_text = context.get("seasonal", "")
        if seasonal_text:
            user_prompt += f"\n\n{seasonal_text}\n"

        # Inject volatility context (OVX)
        vol_text = context.get("volatility", "")
        if vol_text:
            user_prompt += f"\n\n{vol_text}\n"

        # Inject macro correlations (DXY, FX)
        macro_text = context.get("macro", "")
        if macro_text:
            user_prompt += f"\n\n{macro_text}\n"

        # Inject CFTC COT positioning
        cot_text = context.get("cot", "")
        if cot_text:
            user_prompt += f"\n\n{cot_text}\n"

        # Inject weather / hurricane context
        weather_text = context.get("weather", "")
        if weather_text:
            user_prompt += f"\n\n{weather_text}\n"

        # Inject refinery margins
        margins_text = context.get("refinery_margins", "")
        if margins_text:
            user_prompt += f"\n\n{margins_text}\n"

        # Inject historical analogues
        try:
            analogues = self.analogue_finder.find(event, max_results=3)
            if analogues:
                analogues_text = self.analogue_finder.format_for_prompt(analogues)
                user_prompt += f"\n\n{analogues_text}\n"
                logger.info(
                    f"Historical analogues: "
                    f"{', '.join(a.event_name for a in analogues)}"
                )
        except Exception as exc:
            logger.warning(f"Historical analogues error: {exc}")

        # 1. Collect signals from all agents
        logger.info("Querying all 4 agents...")
        signals: dict[str, Signal] = {}
        for name, agent in self.agents.items():
            try:
                logger.info(f"  -> {name.upper()}...")
                # Inject per-agent history + post-mortem into context
                agent_ctx = {"prompt": user_prompt, **context}
                agent_hist = self.agent_memory.format_for_prompt(
                    name, event.instrument, n=8
                )
                # Post-mortem feedback from past predictions
                post_mortem_ctx = self.post_mortem.format_for_prompt(
                    name, event.instrument, event.event_type, n=5
                )
                combined_history = ""
                if agent_hist:
                    combined_history += agent_hist + "\n\n"
                if post_mortem_ctx:
                    combined_history += post_mortem_ctx
                if combined_history:
                    agent_ctx["agent_history"] = combined_history

                sig = agent.analyze(event, agent_ctx)
                signals[name] = sig
                logger.info(f"    {name}: {sig.action} ({sig.confidence:.0%})")

                # Save to agent memory
                self.agent_memory.save_signal(
                    agent_name=name,
                    instrument=event.instrument,
                    event_type=event.event_type,
                    action=sig.action,
                    confidence=sig.confidence,
                    thesis=sig.thesis,
                    risk_notes=sig.risk_notes,
                )
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

        # 5. Accumulate for digest
        instrument = event.instrument
        if instrument not in self._accumulator:
            self._accumulator[instrument] = []
        self._accumulator[instrument].append({
            "timestamp": datetime.now(),
            "event_type": event.event_type,
            "signals": signals,
            "consensus": council_response.consensus,
            "consensus_strength": council_response.consensus_strength,
            "combined_confidence": council_response.combined_confidence,
            "key_risks": council_response.key_risks,
        })

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

        # Polish raw agent theses/risks into clean Ukrainian text
        summarizer = self.notifier.summarizer
        if summarizer and summarizer.available:
            try:
                polished_drivers, polished_risks = summarizer.polish_alert(
                    drivers=forecast.drivers,
                    risks=forecast.risks,
                    instrument=forecast.instrument,
                    direction=forecast.direction,
                )
                forecast = forecast.model_copy(update={
                    "drivers": polished_drivers or forecast.drivers,
                    "risks": polished_risks or forecast.risks,
                })
            except Exception as exc:
                logger.warning(f"Alert polishing failed, using raw text: {exc}")

        if self.dry_run:
            msg = TelegramNotifier.format_oil_alert(forecast, council)
            logger.info(f"[DRY-RUN] Oil alert:\n{msg}")
            return

        try:
            await self.notifier.send_oil_alert(forecast, council)
        except Exception as exc:
            logger.error(f"Notification error: {exc}")

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def _is_digest_due(self) -> bool:
        """Check if enough time has passed for a digest."""
        elapsed = datetime.now() - self._last_digest_time
        return elapsed >= timedelta(hours=self.digest_interval_hours)

    async def _send_digest(self, context: dict) -> None:
        """Build and send a consolidated digest for each instrument."""
        if not self._accumulator:
            logger.info("No accumulated analyses — skipping digest")
            return

        for instrument, analyses in self._accumulator.items():
            if not analyses:
                continue

            # Get current price from context
            prices = context.get("prices", {})
            current_price = prices.get(instrument, {}).get("price", 0.0)

            # Get previous trend for evolution display
            previous_trend = self.digest_history.get_previous_trend(instrument)

            logger.info(
                f"Sending digest for {instrument}: "
                f"{len(analyses)} analyses over {self.digest_interval_hours}h"
            )

            if self.dry_run:
                msg = TelegramNotifier.format_digest(
                    instrument, analyses, self.digest_interval_hours,
                    current_price, previous_trend=previous_trend,
                )
                logger.info(f"[DRY-RUN] Digest:\n{msg}")
            else:
                try:
                    await self.notifier.send_digest(
                        instrument, analyses, self.digest_interval_hours,
                        current_price, previous_trend=previous_trend,
                    )
                except Exception as exc:
                    logger.error(f"Digest notification error: {exc}")

            # Save to digest history for cross-digest learning
            self._save_digest_record(instrument, analyses)

        # Check if day changed — build daily summary
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_day:
            self._build_daily_summaries(context)
            self._current_day = today

        # Clear accumulator
        self._accumulator.clear()
        self._last_digest_time = datetime.now()

    def _save_digest_record(self, instrument: str, analyses: list[dict]) -> None:
        """Compute stats from analyses and persist a DigestRecord."""
        action_counts: dict[str, int] = {"LONG": 0, "SHORT": 0, "WAIT": 0}
        agent_dominants: dict[str, dict[str, int]] = {}
        confidences: list[float] = []
        theses: list[str] = []
        risks: list[str] = []

        for a in analyses:
            consensus = a.get("consensus", "WAIT")
            action_counts[consensus] = action_counts.get(consensus, 0) + 1
            confidences.append(a.get("combined_confidence", 0.0))

            for agent_name, sig in a.get("signals", {}).items():
                if agent_name not in agent_dominants:
                    agent_dominants[agent_name] = {"LONG": 0, "SHORT": 0, "WAIT": 0}
                agent_dominants[agent_name][sig.action] = (
                    agent_dominants[agent_name].get(sig.action, 0) + 1
                )
                if sig.thesis and sig.action != "WAIT" and len(theses) < 6:
                    if sig.thesis not in theses:
                        theses.append(sig.thesis)
                if sig.risk_notes and len(risks) < 4:
                    if sig.risk_notes not in risks:
                        risks.append(sig.risk_notes)

        # Determine trend
        if action_counts["LONG"] > action_counts["SHORT"] and action_counts["LONG"] > action_counts["WAIT"]:
            trend = "LONG"
        elif action_counts["SHORT"] > action_counts["LONG"] and action_counts["SHORT"] > action_counts["WAIT"]:
            trend = "SHORT"
        else:
            trend = "WAIT"

        # Per-agent dominant action
        agent_dom_str = {}
        for name, counts in agent_dominants.items():
            agent_dom_str[name] = max(counts, key=counts.get)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        record = DigestRecord(
            instrument=instrument,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            trend=trend,
            avg_confidence=round(avg_conf, 2),
            event_count=len(analyses),
            action_counts=action_counts,
            agent_dominants=agent_dom_str,
            key_theses=theses,
            key_risks=risks,
        )
        self.digest_history.add(record)

    def _calibrate_weights(self) -> None:
        """Auto-calibrate agent weights and confidence factors from accuracy data."""
        agent_stats = self.post_mortem.get_agent_stats()
        if not agent_stats:
            return

        # P0.3: Update agent weights
        old_weights = dict(self.aggregator.weights)
        new_weights = self.weight_calibrator.calibrate(agent_stats)
        if new_weights != old_weights:
            report = self.weight_calibrator.format_report(
                agent_stats, old_weights, new_weights
            )
            logger.info(f"Weight calibration:\n{report}")
            self.aggregator.update_weights(new_weights)

        # P1.7: Update confidence calibration factors
        # factor = hit_rate / avg_confidence (1.0 = well-calibrated)
        cal_factors: dict[str, float] = {}
        for name, stats in agent_stats.items():
            hit = stats.get("hit_rate", 0.5)
            conf = stats.get("avg_confidence", 0.5)
            if conf > 0 and stats.get("total", 0) >= 5:
                cal_factors[name] = round(hit / conf, 2)
        if cal_factors:
            self.aggregator.set_calibration_factors(cal_factors)
            logger.info(f"Confidence calibration factors: {cal_factors}")

    def _build_daily_summaries(self, context: dict) -> None:
        """Build daily summaries from today's digests for each instrument."""
        # Auto-calibrate agent weights at end of day
        self._calibrate_weights()

        yesterday = self._current_day  # day that just ended
        prices = context.get("prices", {})

        for instrument in self.price_watcher.instruments:
            # Get all digests from today (filter by date prefix)
            all_digests = self.digest_history.get_recent(instrument, n=24)
            todays_digests = [
                d for d in all_digests if d.timestamp.startswith(yesterday)
            ]

            if not todays_digests:
                continue

            # Get price for daily summary
            price_info = prices.get(instrument, {})
            current_price = price_info.get("price", 0.0)

            record = self.daily_summary.build_from_digests(
                instrument=instrument,
                digests=todays_digests,
                closing_price=current_price,
            )
            self.daily_summary.add(record)
            logger.info(
                f"Daily summary saved: {instrument} @ {record.date} — "
                f"{record.dominant_trend}, {record.total_events} events, "
                f"{record.digest_count} digests"
            )

    def save_daily_summary_now(self, context: dict) -> None:
        """Force-save daily summary (for --once mode or manual trigger)."""
        today = datetime.now().strftime("%Y-%m-%d")
        prices = context.get("prices", {})

        for instrument in self.price_watcher.instruments:
            all_digests = self.digest_history.get_recent(instrument, n=24)
            todays_digests = [
                d for d in all_digests if d.timestamp.startswith(today)
            ]

            if not todays_digests:
                continue

            price_info = prices.get(instrument, {})
            current_price = price_info.get("price", 0.0)

            record = self.daily_summary.build_from_digests(
                instrument=instrument,
                digests=todays_digests,
                closing_price=current_price,
            )
            self.daily_summary.add(record)
            logger.info(
                f"Daily summary (forced): {instrument} @ {record.date} — "
                f"{record.dominant_trend}, {record.total_events} events"
            )

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
                # Build forecast for journal/tracking (no Telegram per event)
                council_resp = result["council_response"]
                forecast = self.build_forecast(council_resp, result["signals"], context)
                result["forecast"] = forecast
                results.append(result)
            except Exception as exc:
                logger.error(f"Error analysing event: {exc}")

        # Check if digest is due
        if self._is_digest_due():
            await self._send_digest(context)
            # Also update daily summary after each digest
            self.save_daily_summary_now(context)

        return results

    async def run(self, poll_interval: int = 300) -> None:
        """Main async loop -- runs until stopped via stop()."""
        self.running = True
        cycle = 0

        logger.info("=" * 60)
        logger.info("BREKHUNI — OIL TRADING INTELLIGENCE BOT")
        logger.info(f"   Agents: {list(self.agents.keys())}")
        logger.info(f"   Poll interval: {poll_interval}s")
        logger.info(f"   Digest every: {self.digest_interval_hours}h")
        logger.info(f"   Journal: {self.journal.journal_path}")
        logger.info(f"   Telegram: {'enabled' if self.notifier.enabled else 'disabled'}")
        logger.info(f"   Dry-run: {self.dry_run}")
        logger.info("=" * 60)

        while self.running:
            cycle += 1
            acc_count = sum(len(v) for v in self._accumulator.values())
            time_to_digest = self.digest_interval_hours * 3600 - (datetime.now() - self._last_digest_time).total_seconds()
            logger.info(f"\n{'─' * 40}")
            logger.info(
                f"Cycle #{cycle} -- {datetime.now().strftime('%H:%M:%S')} "
                f"| accumulated: {acc_count} | digest in: {max(0, time_to_digest)/60:.0f}m"
            )
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
    parser.add_argument("--interval", type=int, default=900, help="Poll interval in seconds (default 900 = 15min)")
    parser.add_argument("--digest-hours", type=int, default=None, help="Digest interval in hours (default from settings, usually 3)")

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
        digest_interval_hours = 3
        poll_interval_sec = 900
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
            digest_interval_hours = settings.DIGEST_INTERVAL_HOURS
            poll_interval_sec = settings.POLL_INTERVAL_SECONDS
        except Exception as exc:
            logger.error(f"Failed to load settings: {exc}")
            logger.info("Try running with --dry-run flag")
            sys.exit(1)

    aggregator = Aggregator()
    risk_governor = RiskGovernor()
    journal = TradeJournal(journal_path=journal_path)
    # Create digest summarizer (uses Gemini Flash for cheap/fast summarization)
    summarizer_key = None
    if not args.dry_run:
        summarizer_key = settings.GOOGLE_AI_API_KEY or settings.GOOGLE_API_KEY
    summarizer = DigestSummarizer(api_key=summarizer_key or "") if summarizer_key else None
    notifier = TelegramNotifier(bot_token=telegram_token, chat_id=telegram_chat, chat_ids=telegram_chat_ids,
                                summarizer=summarizer)

    # CLI --digest-hours overrides settings
    if args.digest_hours is not None:
        digest_interval_hours = args.digest_hours
    # CLI --interval overrides settings
    if args.interval != 900:
        poll_interval_sec = args.interval

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
        digest_interval_hours=digest_interval_hours,
    )

    # Graceful shutdown
    loop = asyncio.new_event_loop()

    def signal_handler(sig, frame):
        council.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run
    if args.once:
        logger.info("Running ONE cycle (with immediate digest)...")
        # Set last digest to past so digest fires immediately
        council._last_digest_time = datetime.now() - timedelta(hours=999)
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
        loop.run_until_complete(council.run(poll_interval=poll_interval_sec))


if __name__ == "__main__":
    main()
