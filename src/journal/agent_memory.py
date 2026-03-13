"""
Agent Memory — per-agent history of previous analyses.

Each agent stores its last N signals per instrument.
Before each query, the agent receives its own history as context,
enabling it to track its own reasoning evolution and avoid
repeating stale analysis.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger


class AgentMemoryEntry:
    """One agent response snapshot."""

    def __init__(
        self,
        timestamp: str,
        instrument: str,
        event_type: str,
        action: str,
        confidence: float,
        thesis: str,
        risk_notes: str,
    ):
        self.timestamp = timestamp
        self.instrument = instrument
        self.event_type = event_type
        self.action = action
        self.confidence = confidence
        self.thesis = thesis
        self.risk_notes = risk_notes

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "instrument": self.instrument,
            "event_type": self.event_type,
            "action": self.action,
            "confidence": self.confidence,
            "thesis": self.thesis,
            "risk_notes": self.risk_notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentMemoryEntry:
        return cls(
            timestamp=d["timestamp"],
            instrument=d["instrument"],
            event_type=d["event_type"],
            action=d["action"],
            confidence=d["confidence"],
            thesis=d.get("thesis", ""),
            risk_notes=d.get("risk_notes", ""),
        )

    def to_context_line(self) -> str:
        """One-line summary for prompt injection."""
        return (
            f"[{self.timestamp}] {self.event_type} → {self.action} "
            f"({self.confidence:.0%}): {self.thesis[:150]}"
        )


class AgentMemory:
    """
    Persistent per-agent memory.

    Structure: { agent_name: { instrument: [ entry_dict, ... ] } }
    Keeps last `max_per_instrument` entries per agent per instrument.
    """

    def __init__(
        self,
        path: Path = Path("data/agent_memory.json"),
        max_per_instrument: int = 20,
    ):
        self.path = path
        self.max_per_instrument = max_per_instrument
        self._data: Dict[str, Dict[str, List[dict]]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load agent memory: {exc}")
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_signal(
        self,
        agent_name: str,
        instrument: str,
        event_type: str,
        action: str,
        confidence: float,
        thesis: str,
        risk_notes: str,
    ) -> None:
        """Record an agent's response."""
        if agent_name not in self._data:
            self._data[agent_name] = {}
        if instrument not in self._data[agent_name]:
            self._data[agent_name][instrument] = []

        entry = AgentMemoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            instrument=instrument,
            event_type=event_type,
            action=action,
            confidence=confidence,
            thesis=thesis,
            risk_notes=risk_notes,
        )
        self._data[agent_name][instrument].append(entry.to_dict())
        # Trim
        self._data[agent_name][instrument] = (
            self._data[agent_name][instrument][-self.max_per_instrument:]
        )
        self._save()

    def get_history(
        self, agent_name: str, instrument: str, n: int = 8
    ) -> List[AgentMemoryEntry]:
        """Get last N entries for an agent + instrument."""
        raw = self._data.get(agent_name, {}).get(instrument, [])
        return [AgentMemoryEntry.from_dict(d) for d in raw[-n:]]

    def format_for_prompt(
        self, agent_name: str, instrument: str, n: int = 8
    ) -> str:
        """
        Build a text block with the agent's own history
        for injection into its prompt.
        """
        entries = self.get_history(agent_name, instrument, n)
        if not entries:
            return ""

        lines = [
            f"## Твої попередні аналізи ({instrument}, останні {len(entries)}):",
            "Переглянь свої минулі сигнали. Враховуй еволюцію своєї позиції.",
            "Якщо твоя попередня теза підтвердилась — підсиль впевненість.",
            "Якщо спростувалась — визнай це та скоригуй.",
            "",
        ]
        for entry in entries:
            lines.append(entry.to_context_line())

        lines.append("")
        lines.append(
            "Використовуй ці дані для калібрування впевненості та уникнення повторів."
        )
        return "\n".join(lines)
