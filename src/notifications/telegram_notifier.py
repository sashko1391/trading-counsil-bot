"""
Telegram Notifier -- sends oil trading alerts via Telegram Bot API.

Uses httpx for HTTP calls (no python-telegram-bot dependency needed).
Gracefully degrades when TELEGRAM_BOT_TOKEN is missing.
"""

from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from models.schemas import CouncilResponse, OilForecast, RiskCheck


TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """
    Sends formatted oil alert messages to a Telegram chat.

    If bot_token or chat_id is missing the notifier logs a warning
    and all send methods return False without raising.
    """

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram notifier disabled (missing bot_token or chat_id)")

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_oil_alert(forecast: OilForecast, council: CouncilResponse) -> str:
        """
        Build the oil alert message string.

        Parameters
        ----------
        forecast : OilForecast produced from the council pipeline.
        council  : CouncilResponse with individual agent votes.
        """
        direction_emoji = {
            "BULLISH": "\U0001f4c8",   # chart increasing
            "BEARISH": "\U0001f4c9",   # chart decreasing
            "NEUTRAL": "\u2796",        # heavy minus sign
        }
        d_emoji = direction_emoji.get(forecast.direction, "")

        move_pct = forecast.expected_move_pct

        # Count how many agents agree with the consensus direction
        consensus_action = council.consensus
        agent_signals = [council.grok, council.perplexity, council.claude, council.gemini]
        consensus_count = sum(1 for s in agent_signals if s.action == consensus_action)

        drivers_str = "; ".join(forecast.drivers[:4]) if forecast.drivers else "N/A"
        risks_str = "; ".join(forecast.risks[:3]) if forecast.risks else "N/A"

        lines = [
            f"\U0001f6e2\ufe0f OIL ALERT \u2014 {forecast.instrument}",
            f"{d_emoji} Direction: {forecast.direction}",
            f"\U0001f4aa Confidence: {forecast.confidence * 100:.0f}%",
            f"\u23f0 Timeframe: {forecast.timeframe_hours}h",
            f"\U0001f3af Target: ${forecast.target_price:.2f} ({move_pct:+.1f}%)",
            f"\U0001f4ca Drivers: {drivers_str}",
            f"\u26a0\ufe0f Risks: {risks_str}",
            f"\U0001f916 Council: {consensus_count}/4 {council.consensus} ({council.consensus_strength})",
            f"\U0001f4dd NOT financial advice.",
        ]
        return "\n".join(lines)

    def format_signal(
        self,
        council_response: CouncilResponse,
        risk_check: Optional[RiskCheck] = None,
    ) -> str:
        """
        Legacy format for backward compatibility with old pipeline tests.
        """
        cr = council_response

        action_emoji = {
            "LONG": "\U0001f7e2 LONG",
            "SHORT": "\U0001f534 SHORT",
            "WAIT": "\u23f8\ufe0f WAIT",
            "CONFLICT": "\u26a1 CONFLICT",
        }

        strength_emoji = {
            "UNANIMOUS": "\U0001f4aa UNANIMOUS (4/4)",
            "STRONG": "\u270a STRONG (3/4)",
            "WEAK": "\U0001f90f WEAK (2/4)",
            "NONE": "\u274c NONE",
        }

        lines = [
            f"{'=' * 30}",
            f"\U0001f3db\ufe0f TRADING COUNCIL DECISION",
            f"{'=' * 30}",
            "",
            f"\U0001f4ca Instrument: {cr.instrument}",
            f"\u26a1 Trigger: {cr.event_type}",
            "",
            f"\U0001f3af Consensus: {action_emoji.get(cr.consensus, cr.consensus)}",
            f"\U0001f4aa Strength: {strength_emoji.get(cr.consensus_strength, cr.consensus_strength)}",
            f"\U0001f4c8 Confidence: {cr.combined_confidence:.0%}",
        ]

        if cr.invalidation_price:
            lines.append(f"\U0001f6ab Invalidation: ${cr.invalidation_price:,.0f}")

        rec = cr.recommendation
        if rec.get("max_position_size"):
            lines.append(f"\U0001f4d0 Max Position: {rec['max_position_size']:.1%}")

        lines.extend([
            "",
            f"{'─' * 30}",
            f"\U0001f5f3\ufe0f Individual Votes:",
            f"  \U0001f525 Grok:       {cr.grok.action} ({cr.grok.confidence:.0%})",
            f"  \U0001f50d Perplexity: {cr.perplexity.action} ({cr.perplexity.confidence:.0%})",
            f"  \U0001f6e1\ufe0f Claude:     {cr.claude.action} ({cr.claude.confidence:.0%})",
            f"  \U0001f52c Gemini:     {cr.gemini.action} ({cr.gemini.confidence:.0%})",
        ])

        if cr.key_risks:
            lines.extend(["", f"{'─' * 30}", "\u26a0\ufe0f Key Risks:"])
            for i, risk in enumerate(cr.key_risks[:4], 1):
                risk_short = risk[:80] + "..." if len(risk) > 80 else risk
                lines.append(f"  {i}. {risk_short}")

        if risk_check:
            status = "\u2705 ALLOWED" if risk_check.allowed else "\U0001f6ab BLOCKED"
            lines.extend([
                "",
                f"{'─' * 30}",
                f"\U0001f6e1\ufe0f Risk Governor: {status}",
                f"   Reason: {risk_check.reason}",
            ])

        lines.append(f"\n{'=' * 30}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def _send_message(self, text: str) -> bool:
        """POST a plain-text message via the Telegram Bot API."""
        if not self.enabled:
            logger.info(f"[Telegram disabled] Would send:\n{text}")
            return False

        url = f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info("Telegram message sent successfully")
                return True
        except Exception as exc:
            logger.error(f"Telegram send failed: {exc}")
            return False

    async def send_oil_alert(
        self, forecast: OilForecast, council: CouncilResponse
    ) -> bool:
        """Format and send an oil alert."""
        text = self.format_oil_alert(forecast, council)
        return await self._send_message(text)

    async def send_signal_async(
        self,
        council_response: CouncilResponse,
        risk_check: Optional[RiskCheck] = None,
    ) -> bool:
        """Format and send a legacy council decision."""
        text = self.format_signal(council_response, risk_check)
        return await self._send_message(text)

    def send_signal(
        self,
        council_response: CouncilResponse,
        risk_check: Optional[RiskCheck] = None,
    ) -> bool:
        """Synchronous wrapper around send_signal_async."""
        import asyncio

        text = self.format_signal(council_response, risk_check)

        if not self.enabled:
            logger.info(f"[Telegram disabled] Would send:\n{text}")
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._send_message(text))
                return future.result(timeout=15)
        else:
            return asyncio.run(self._send_message(text))
