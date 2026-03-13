"""
Digest History — stores past digest summaries for cross-digest learning.

Each digest records:
- instrument, timestamp, trend, avg confidence
- per-agent dominant actions
- event count, key theses, key risks

Agents receive the last N digest summaries as context so they can
track trend evolution and avoid repeating stale analysis.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger


class DigestRecord:
    """One digest summary."""

    def __init__(
        self,
        instrument: str,
        timestamp: str,
        trend: str,
        avg_confidence: float,
        event_count: int,
        action_counts: Dict[str, int],
        agent_dominants: Dict[str, str],
        key_theses: List[str],
        key_risks: List[str],
    ):
        self.instrument = instrument
        self.timestamp = timestamp
        self.trend = trend
        self.avg_confidence = avg_confidence
        self.event_count = event_count
        self.action_counts = action_counts
        self.agent_dominants = agent_dominants
        self.key_theses = key_theses
        self.key_risks = key_risks

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "timestamp": self.timestamp,
            "trend": self.trend,
            "avg_confidence": self.avg_confidence,
            "event_count": self.event_count,
            "action_counts": self.action_counts,
            "agent_dominants": self.agent_dominants,
            "key_theses": self.key_theses,
            "key_risks": self.key_risks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DigestRecord:
        return cls(
            instrument=d["instrument"],
            timestamp=d["timestamp"],
            trend=d["trend"],
            avg_confidence=d["avg_confidence"],
            event_count=d["event_count"],
            action_counts=d.get("action_counts", {}),
            agent_dominants=d.get("agent_dominants", {}),
            key_theses=d.get("key_theses", []),
            key_risks=d.get("key_risks", []),
        )

    def to_context_string(self) -> str:
        """Format as text for agent context injection."""
        lines = [
            f"[{self.timestamp}] {self.instrument}: {self.trend} "
            f"(conf {self.avg_confidence:.0%}, {self.event_count} events)",
        ]
        if self.agent_dominants:
            agents_str = ", ".join(f"{k}={v}" for k, v in self.agent_dominants.items())
            lines.append(f"  Agents: {agents_str}")
        if self.key_theses:
            lines.append(f"  Theses: {'; '.join(self.key_theses[:2])}")
        if self.key_risks:
            lines.append(f"  Risks: {'; '.join(self.key_risks[:2])}")
        return "\n".join(lines)


class DigestHistory:
    """
    Persistent store for past digest summaries.

    Keeps the last `max_records` digests per instrument on disk (JSON).
    """

    def __init__(self, path: Path = Path("data/digest_history.json"), max_records: int = 24):
        self.path = path
        self.max_records = max_records
        self._data: Dict[str, List[dict]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load digest history: {exc}")
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, record: DigestRecord) -> None:
        """Append a digest record and trim to max_records."""
        instrument = record.instrument
        if instrument not in self._data:
            self._data[instrument] = []
        self._data[instrument].append(record.to_dict())
        # Keep only last N
        self._data[instrument] = self._data[instrument][-self.max_records:]
        self._save()
        logger.debug(
            f"Digest history: added {instrument} @ {record.timestamp}, "
            f"total={len(self._data[instrument])}"
        )

    def get_recent(self, instrument: str, n: int = 8) -> List[DigestRecord]:
        """Get last N digest records for an instrument."""
        raw = self._data.get(instrument, [])
        return [DigestRecord.from_dict(d) for d in raw[-n:]]

    def get_context_for_agents(self, instrument: str, n: int = 4) -> str:
        """
        Build a text block summarizing recent digest history
        for injection into agent prompts.
        """
        records = self.get_recent(instrument, n)
        if not records:
            return ""

        lines = [
            "## Previous Digest History (most recent last)",
            f"The council has produced {len(records)} recent digests for {instrument}:",
            "",
        ]
        for rec in records:
            lines.append(rec.to_context_string())
            lines.append("")

        lines.append(
            "Consider how the current situation compares to previous digests. "
            "Has the trend changed? Are the same risks still relevant? "
            "Is the market confirming or contradicting previous analysis?"
        )
        return "\n".join(lines)

    def get_previous_trend(self, instrument: str) -> Optional[str]:
        """Get the trend from the most recent digest."""
        records = self.get_recent(instrument, 1)
        if records:
            return records[0].trend
        return None
