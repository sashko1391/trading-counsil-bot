"""
Post-Mortem Feedback — compares agent predictions against actual outcomes.

When a forecast resolves (actual price known after timeframe_hours),
builds a short "post-mortem" report per agent that is injected into
future prompts of the same event type, so agents learn from mistakes.

P0.1 improvement: expected +10-15% forecast accuracy.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


class PostMortemEntry:
    """One resolved forecast result for a specific agent."""

    def __init__(
        self,
        timestamp: str,
        agent_name: str,
        instrument: str,
        event_type: str,
        predicted_action: str,
        predicted_confidence: float,
        thesis: str,
        actual_price: float,
        entry_price: float,
        price_change_pct: float,
        was_correct: bool,
        missed_factor: str = "",
    ):
        self.timestamp = timestamp
        self.agent_name = agent_name
        self.instrument = instrument
        self.event_type = event_type
        self.predicted_action = predicted_action
        self.predicted_confidence = predicted_confidence
        self.thesis = thesis
        self.actual_price = actual_price
        self.entry_price = entry_price
        self.price_change_pct = price_change_pct
        self.was_correct = was_correct
        self.missed_factor = missed_factor

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> PostMortemEntry:
        return cls(**{k: v for k, v in d.items() if k != "__dict__"})

    def to_prompt_line(self) -> str:
        result = "ВІРНО" if self.was_correct else "НЕВІРНО"
        conf_str = f"{self.predicted_confidence:.0%}"
        line = (
            f"[{self.timestamp}] {self.event_type} | "
            f"Прогноз: {self.predicted_action} ({conf_str}) | "
            f"Результат: {result} (ціна {self.price_change_pct:+.1f}%)"
        )
        if not self.was_correct and self.missed_factor:
            line += f" | Пропущено: {self.missed_factor}"
        return line


class PostMortemTracker:
    """
    Persistent store for per-agent post-mortem results.

    Structure: { agent_name: { instrument: [ entry_dict, ... ] } }
    """

    def __init__(
        self,
        path: Path = Path("data/post_mortems.json"),
        max_per_agent_instrument: int = 30,
    ):
        self.path = path
        self.max = max_per_agent_instrument
        self._data: Dict[str, Dict[str, List[dict]]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load post-mortems: {exc}")
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, entry: PostMortemEntry) -> None:
        """Save a post-mortem result."""
        agent = entry.agent_name
        inst = entry.instrument
        if agent not in self._data:
            self._data[agent] = {}
        if inst not in self._data[agent]:
            self._data[agent][inst] = []

        self._data[agent][inst].append(entry.to_dict())
        self._data[agent][inst] = self._data[agent][inst][-self.max:]
        self._save()

    def record_outcome(
        self,
        agent_name: str,
        instrument: str,
        event_type: str,
        predicted_action: str,
        predicted_confidence: float,
        thesis: str,
        entry_price: float,
        actual_price: float,
        missed_factor: str = "",
    ) -> PostMortemEntry:
        """Create and save a post-mortem entry from outcome data."""
        price_change_pct = (
            (actual_price - entry_price) / entry_price * 100
            if entry_price > 0 else 0.0
        )
        was_correct = (
            (predicted_action == "LONG" and actual_price > entry_price)
            or (predicted_action == "SHORT" and actual_price < entry_price)
            or (predicted_action == "WAIT" and abs(price_change_pct) < 1.0)
        )

        entry = PostMortemEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            agent_name=agent_name,
            instrument=instrument,
            event_type=event_type,
            predicted_action=predicted_action,
            predicted_confidence=predicted_confidence,
            thesis=thesis[:200],
            actual_price=actual_price,
            entry_price=entry_price,
            price_change_pct=round(price_change_pct, 2),
            was_correct=was_correct,
            missed_factor=missed_factor,
        )
        self.record(entry)
        return entry

    def get_for_agent(
        self,
        agent_name: str,
        instrument: str,
        event_type: str = "",
        n: int = 5,
    ) -> List[PostMortemEntry]:
        """Get last N post-mortems for an agent, optionally filtered by event type."""
        raw = self._data.get(agent_name, {}).get(instrument, [])
        entries = [PostMortemEntry.from_dict(d) for d in raw]
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        return entries[-n:]

    def format_for_prompt(
        self,
        agent_name: str,
        instrument: str,
        event_type: str = "",
        n: int = 5,
    ) -> str:
        """Build a post-mortem context block for injection into agent prompt."""
        entries = self.get_for_agent(agent_name, instrument, event_type, n)
        if not entries:
            return ""

        correct = sum(1 for e in entries if e.was_correct)
        total = len(entries)
        hit_rate = correct / total if total > 0 else 0.0

        lines = [
            f"## Твої минулі результати ({instrument}, останні {total}):",
            f"Точність: {correct}/{total} ({hit_rate:.0%})",
            "",
        ]

        for entry in entries:
            lines.append(entry.to_prompt_line())

        lines.append("")

        if hit_rate < 0.5:
            lines.append(
                "УВАГА: Твоя точність нижче 50%. Переглянь свої помилки вище. "
                "Що саме ти систематично пропускаєш? Скоригуй підхід."
            )
        elif hit_rate < 0.7:
            lines.append(
                "Твоя точність помірна. Зверни увагу на помилки та "
                "калібруй впевненість відповідно до реальних результатів."
            )
        else:
            lines.append(
                "Хороша точність. Продовжуй в тому ж стилі, "
                "але не завищуй впевненість."
            )

        return "\n".join(lines)

    def get_agent_stats(self) -> Dict[str, Dict[str, float]]:
        """Get per-agent accuracy stats across all instruments."""
        stats: Dict[str, Dict[str, float]] = {}
        for agent, instruments in self._data.items():
            all_entries = []
            for entries in instruments.values():
                all_entries.extend(entries)
            if not all_entries:
                continue
            correct = sum(1 for e in all_entries if e.get("was_correct", False))
            total = len(all_entries)
            avg_conf = sum(
                e.get("predicted_confidence", 0.5) for e in all_entries
            ) / total
            stats[agent] = {
                "hit_rate": correct / total,
                "avg_confidence": avg_conf,
                "total": total,
            }
        return stats
