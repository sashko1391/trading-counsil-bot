"""
Telegram Notifier -- sends oil trading alerts via Telegram Bot API.

Uses httpx for HTTP calls (no python-telegram-bot dependency needed).
Gracefully degrades when TELEGRAM_BOT_TOKEN is missing.
"""

from __future__ import annotations

from typing import Optional, List, Dict
from datetime import datetime

import httpx
from loguru import logger

from models.schemas import CouncilResponse, OilForecast, RiskCheck, Signal


TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """
    Sends formatted oil alert messages to a Telegram chat.

    If bot_token or chat_id is missing the notifier logs a warning
    and all send methods return False without raising.
    """

    def __init__(self, bot_token: str = None, chat_id: str = None, chat_ids: str = None):
        self.bot_token = bot_token or ""
        # Support multiple chat IDs (comma-separated) via chat_ids, fallback to single chat_id
        if chat_ids:
            self.chat_ids = [cid.strip() for cid in chat_ids.split(",") if cid.strip()]
        elif chat_id:
            self.chat_ids = [chat_id.strip()]
        else:
            self.chat_ids = []
        # Keep for backward compat
        self.chat_id = self.chat_ids[0] if self.chat_ids else ""
        self.enabled = bool(self.bot_token and self.chat_ids)

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

        direction_ua = {
            "BULLISH": "ЗРОСТАННЯ",
            "BEARISH": "ПАДІННЯ",
            "NEUTRAL": "НЕЙТРАЛЬНО",
        }

        lines = [
            f"\U0001f6e2\ufe0f BREKHUNI \u2014 {forecast.instrument}",
            f"{d_emoji} Напрямок: {direction_ua.get(forecast.direction, forecast.direction)}",
            f"\U0001f4aa Впевненість: {forecast.confidence * 100:.0f}%",
            f"\u23f0 Горизонт: {forecast.timeframe_hours} год",
            f"\U0001f3af Ціль: ${forecast.target_price:.2f} ({move_pct:+.1f}%)",
            f"\U0001f4ca Драйвери: {drivers_str}",
            f"\u26a0\ufe0f Ризики: {risks_str}",
            f"\U0001f916 Рада: {consensus_count}/4 {council.consensus} ({council.consensus_strength})",
            f"\U0001f4dd Це НЕ фінансова порада.",
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
            f"\U0001f3db\ufe0f BREKHUNI — РІШЕННЯ РАДИ",
            f"{'=' * 30}",
            "",
            f"\U0001f4ca Інструмент: {cr.instrument}",
            f"\u26a1 Тригер: {cr.event_type}",
            "",
            f"\U0001f3af Консенсус: {action_emoji.get(cr.consensus, cr.consensus)}",
            f"\U0001f4aa Сила: {strength_emoji.get(cr.consensus_strength, cr.consensus_strength)}",
            f"\U0001f4c8 Впевненість: {cr.combined_confidence:.0%}",
        ]

        if cr.invalidation_price:
            lines.append(f"\U0001f6ab Інвалідація: ${cr.invalidation_price:,.0f}")

        rec = cr.recommendation
        if rec.get("max_position_size"):
            lines.append(f"\U0001f4d0 Макс. позиція: {rec['max_position_size']:.1%}")

        lines.extend([
            "",
            f"{'─' * 30}",
            f"\U0001f5f3\ufe0f Голоси агентів:",
            f"  \U0001f525 Grok:       {cr.grok.action} ({cr.grok.confidence:.0%})",
            f"  \U0001f50d Perplexity: {cr.perplexity.action} ({cr.perplexity.confidence:.0%})",
            f"  \U0001f6e1\ufe0f Claude:     {cr.claude.action} ({cr.claude.confidence:.0%})",
            f"  \U0001f52c Gemini:     {cr.gemini.action} ({cr.gemini.confidence:.0%})",
        ])

        if cr.key_risks:
            lines.extend(["", f"{'─' * 30}", "\u26a0\ufe0f Ключові ризики:"])
            for i, risk in enumerate(cr.key_risks[:4], 1):
                risk_short = risk[:80] + "..." if len(risk) > 80 else risk
                lines.append(f"  {i}. {risk_short}")

        if risk_check:
            status = "\u2705 ДОЗВОЛЕНО" if risk_check.allowed else "\U0001f6ab ЗАБЛОКОВАНО"
            lines.extend([
                "",
                f"{'─' * 30}",
                f"\U0001f6e1\ufe0f Ризик-контроль: {status}",
                f"   Причина: {risk_check.reason}",
            ])

        lines.append(f"\n{'=' * 30}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Digest (consolidated N-hour summary)
    # ------------------------------------------------------------------

    @staticmethod
    def format_digest(
        instrument: str,
        analyses: List[Dict],
        hours: int,
        current_price: float = 0.0,
    ) -> str:
        """
        Build a consolidated digest message from accumulated analyses.

        analyses: list of dicts with keys:
            - timestamp: datetime
            - event_type: str
            - signals: dict[agent_name, Signal]
            - consensus: str
            - combined_confidence: float
        """
        if not analyses:
            return ""

        # Count actions across all analyses
        action_counts: Dict[str, int] = {"LONG": 0, "SHORT": 0, "WAIT": 0, "CONFLICT": 0}
        agent_actions: Dict[str, Dict[str, int]] = {
            "Grok": {"LONG": 0, "SHORT": 0, "WAIT": 0},
            "Perplexity": {"LONG": 0, "SHORT": 0, "WAIT": 0},
            "Claude": {"LONG": 0, "SHORT": 0, "WAIT": 0},
            "Gemini": {"LONG": 0, "SHORT": 0, "WAIT": 0},
        }
        all_theses: List[str] = []
        all_risks: List[str] = []
        confidences: List[float] = []
        event_types: Dict[str, int] = {}

        for a in analyses:
            consensus = a.get("consensus", "WAIT")
            action_counts[consensus] = action_counts.get(consensus, 0) + 1
            confidences.append(a.get("combined_confidence", 0.0))

            et = a.get("event_type", "unknown")
            event_types[et] = event_types.get(et, 0) + 1

            signals = a.get("signals", {})
            for agent_name, sig in signals.items():
                display_name = agent_name.capitalize()
                if display_name in agent_actions:
                    agent_actions[display_name][sig.action] = (
                        agent_actions[display_name].get(sig.action, 0) + 1
                    )
                if sig.thesis and sig.action != "WAIT" and len(all_theses) < 6:
                    short = sig.thesis[:120]
                    if short not in all_theses:
                        all_theses.append(short)
                if sig.risk_notes and len(all_risks) < 4:
                    short = sig.risk_notes[:100]
                    if short not in all_risks:
                        all_risks.append(short)

        # Determine dominant trend
        directional = action_counts["LONG"] + action_counts["SHORT"]
        total = sum(action_counts.values())
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        if action_counts["LONG"] > action_counts["SHORT"] and action_counts["LONG"] > action_counts["WAIT"]:
            trend = "ЗРОСТАННЯ"
            trend_emoji = "\U0001f4c8"
            trend_action = "LONG"
        elif action_counts["SHORT"] > action_counts["LONG"] and action_counts["SHORT"] > action_counts["WAIT"]:
            trend = "ПАДІННЯ"
            trend_emoji = "\U0001f4c9"
            trend_action = "SHORT"
        else:
            trend = "НЕЙТРАЛЬНО"
            trend_emoji = "\u2696\ufe0f"
            trend_action = "WAIT"

        # Event types summary
        events_str = ", ".join(f"{v}x {k}" for k, v in sorted(event_types.items(), key=lambda x: -x[1]))

        now = datetime.now()
        lines = [
            f"\U0001f6e2\ufe0f BREKHUNI — ДАЙДЖЕСТ {hours}ГОД",
            f"\U0001f4ca {instrument} | {now.strftime('%d.%m.%Y %H:%M')}",
            f"{'=' * 32}",
            "",
            f"{trend_emoji} ТРЕНД: {trend}",
            f"\U0001f4aa Середня впевненість: {avg_conf:.0%}",
        ]

        if current_price > 0:
            lines.append(f"\U0001f4b0 Поточна ціна: ${current_price:.2f}")

        lines.extend([
            "",
            f"\U0001f4cb Проаналізовано {total} подій:",
            f"   \U0001f7e2 LONG: {action_counts['LONG']}  |  \U0001f534 SHORT: {action_counts['SHORT']}  |  \u23f8 WAIT: {action_counts['WAIT']}",
            f"   Типи: {events_str}",
        ])

        # Per-agent breakdown
        lines.extend(["", f"{'─' * 32}", "\U0001f5f3\ufe0f Агенти за {hours} год:"])
        for agent_name, counts in agent_actions.items():
            emoji_map = {"Grok": "\U0001f525", "Perplexity": "\U0001f50d", "Claude": "\U0001f6e1\ufe0f", "Gemini": "\U0001f52c"}
            emoji = emoji_map.get(agent_name, "\U0001f916")
            dominant = max(counts, key=counts.get)
            lines.append(
                f"   {emoji} {agent_name}: {counts['LONG']}L / {counts['SHORT']}S / {counts['WAIT']}W → {dominant}"
            )

        # Key theses
        if all_theses:
            lines.extend(["", f"{'─' * 32}", "\U0001f4a1 Ключові тези:"])
            for i, t in enumerate(all_theses[:4], 1):
                lines.append(f"   {i}. {t}")

        # Risks
        if all_risks:
            lines.extend(["", f"{'─' * 32}", "\u26a0\ufe0f Ризики:"])
            for i, r in enumerate(all_risks[:3], 1):
                lines.append(f"   {i}. {r}")

        lines.extend([
            "",
            f"{'=' * 32}",
            "\U0001f4dd Це НЕ фінансова порада.",
        ])

        return "\n".join(lines)

    async def send_digest(
        self,
        instrument: str,
        analyses: List[Dict],
        hours: int,
        current_price: float = 0.0,
    ) -> bool:
        """Format and send a digest message."""
        text = self.format_digest(instrument, analyses, hours, current_price)
        if not text:
            return False
        return await self._send_message(text)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def _send_message(self, text: str) -> bool:
        """POST a plain-text message to all configured chat IDs."""
        if not self.enabled:
            logger.info(f"[Telegram disabled] Would send:\n{text}")
            return False

        url = f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage"
        any_sent = False

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for chat_id in self.chat_ids:
                    try:
                        resp = await client.post(url, json={"chat_id": chat_id, "text": text})
                        resp.raise_for_status()
                        any_sent = True
                    except Exception as exc:
                        logger.error(f"Telegram send to {chat_id} failed: {exc}")
            if any_sent:
                logger.info(f"Telegram message sent to {len(self.chat_ids)} chat(s)")
            return any_sent
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
