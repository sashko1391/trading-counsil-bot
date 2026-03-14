"""
Daily Summary — end-of-day aggregation of all digests.

Stores the last 30 daily summaries per instrument.
Agents receive recent daily summaries as multi-day context,
giving them a broader picture of trend evolution over weeks.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger

from journal.digest_history import DigestRecord


class DailySummaryRecord:
    """One day's aggregated summary."""

    def __init__(
        self,
        instrument: str,
        date: str,
        digest_count: int,
        total_events: int,
        dominant_trend: str,
        trend_changes: int,
        avg_confidence: float,
        action_counts: Dict[str, int],
        agent_dominants: Dict[str, str],
        key_theses: List[str],
        key_risks: List[str],
        opening_price: float = 0.0,
        closing_price: float = 0.0,
        price_change_pct: float = 0.0,
    ):
        self.instrument = instrument
        self.date = date
        self.digest_count = digest_count
        self.total_events = total_events
        self.dominant_trend = dominant_trend
        self.trend_changes = trend_changes
        self.avg_confidence = avg_confidence
        self.action_counts = action_counts
        self.agent_dominants = agent_dominants
        self.key_theses = key_theses
        self.key_risks = key_risks
        self.opening_price = opening_price
        self.closing_price = closing_price
        self.price_change_pct = price_change_pct

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "date": self.date,
            "digest_count": self.digest_count,
            "total_events": self.total_events,
            "dominant_trend": self.dominant_trend,
            "trend_changes": self.trend_changes,
            "avg_confidence": self.avg_confidence,
            "action_counts": self.action_counts,
            "agent_dominants": self.agent_dominants,
            "key_theses": self.key_theses,
            "key_risks": self.key_risks,
            "opening_price": self.opening_price,
            "closing_price": self.closing_price,
            "price_change_pct": self.price_change_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DailySummaryRecord:
        return cls(
            instrument=d["instrument"],
            date=d["date"],
            digest_count=d.get("digest_count", 0),
            total_events=d.get("total_events", 0),
            dominant_trend=d.get("dominant_trend", "WAIT"),
            trend_changes=d.get("trend_changes", 0),
            avg_confidence=d.get("avg_confidence", 0.0),
            action_counts=d.get("action_counts", {}),
            agent_dominants=d.get("agent_dominants", {}),
            key_theses=d.get("key_theses", []),
            key_risks=d.get("key_risks", []),
            opening_price=d.get("opening_price", 0.0),
            closing_price=d.get("closing_price", 0.0),
            price_change_pct=d.get("price_change_pct", 0.0),
        )

    def to_context_line(self) -> str:
        """Compact summary for prompt injection."""
        trend_ua = {"LONG": "ЗРОСТ", "SHORT": "ПАД", "WAIT": "НЕЙТР"}
        t = trend_ua.get(self.dominant_trend, self.dominant_trend)

        price_str = ""
        if self.closing_price > 0:
            price_str = f" ${self.closing_price:.2f} ({self.price_change_pct:+.1f}%)"

        agents_str = ""
        if self.agent_dominants:
            agents_str = " | " + ", ".join(
                f"{k}={v}" for k, v in self.agent_dominants.items()
            )

        return (
            f"[{self.date}] {t} (впевн {self.avg_confidence:.0%}, "
            f"{self.total_events} подій, {self.digest_count} дайдж, "
            f"змін тренду: {self.trend_changes}){price_str}{agents_str}"
        )


class DailySummaryHistory:
    """
    Persistent store for daily summaries.

    Keeps last `max_records` days per instrument on disk (JSON).
    """

    def __init__(
        self,
        path: Path = Path("data/daily_summary.json"),
        max_records: int = 30,
    ):
        self.path = path
        self.max_records = max_records
        self._data: Dict[str, List[dict]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load daily summary: {exc}")
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def build_from_digests(
        self,
        instrument: str,
        digests: List[DigestRecord],
        opening_price: float = 0.0,
        closing_price: float = 0.0,
    ) -> DailySummaryRecord:
        """Aggregate today's digests into a daily summary."""
        if not digests:
            return DailySummaryRecord(
                instrument=instrument,
                date=date.today().isoformat(),
                digest_count=0,
                total_events=0,
                dominant_trend="WAIT",
                trend_changes=0,
                avg_confidence=0.0,
                action_counts={"LONG": 0, "SHORT": 0, "WAIT": 0},
                agent_dominants={},
                key_theses=[],
                key_risks=[],
            )

        # Aggregate across all digests of the day
        total_events = sum(d.event_count for d in digests)
        confidences = [d.avg_confidence for d in digests]
        avg_conf = sum(confidences) / len(confidences)

        # Merge action counts
        merged_actions: Dict[str, int] = {"LONG": 0, "SHORT": 0, "WAIT": 0}
        for d in digests:
            for action, count in d.action_counts.items():
                merged_actions[action] = merged_actions.get(action, 0) + count

        # Count trend changes between consecutive digests
        trend_changes = 0
        for i in range(1, len(digests)):
            if digests[i].trend != digests[i - 1].trend:
                trend_changes += 1

        # Dominant trend = most common across digests
        trend_counts: Dict[str, int] = {}
        for d in digests:
            trend_counts[d.trend] = trend_counts.get(d.trend, 0) + 1
        dominant_trend = max(trend_counts, key=trend_counts.get)

        # Merge agent dominants (most common per agent across digests)
        agent_votes: Dict[str, Dict[str, int]] = {}
        for d in digests:
            for agent, action in d.agent_dominants.items():
                if agent not in agent_votes:
                    agent_votes[agent] = {}
                agent_votes[agent][action] = agent_votes[agent].get(action, 0) + 1
        agent_dominants = {
            agent: max(votes, key=votes.get)
            for agent, votes in agent_votes.items()
        }

        # Collect unique theses and risks
        all_theses: List[str] = []
        all_risks: List[str] = []
        for d in digests:
            for t in d.key_theses:
                if t not in all_theses and len(all_theses) < 5:
                    all_theses.append(t)
            for r in d.key_risks:
                if r not in all_risks and len(all_risks) < 4:
                    all_risks.append(r)

        # Price change
        price_change_pct = 0.0
        if opening_price > 0 and closing_price > 0:
            price_change_pct = round(
                (closing_price - opening_price) / opening_price * 100, 2
            )

        return DailySummaryRecord(
            instrument=instrument,
            date=date.today().isoformat(),
            digest_count=len(digests),
            total_events=total_events,
            dominant_trend=dominant_trend,
            trend_changes=trend_changes,
            avg_confidence=round(avg_conf, 2),
            action_counts=merged_actions,
            agent_dominants=agent_dominants,
            key_theses=all_theses,
            key_risks=all_risks,
            opening_price=opening_price,
            closing_price=closing_price,
            price_change_pct=price_change_pct,
        )

    def add(self, record: DailySummaryRecord) -> None:
        """Save a daily summary, replacing if same date exists."""
        instrument = record.instrument
        if instrument not in self._data:
            self._data[instrument] = []

        # Replace existing entry for the same date
        self._data[instrument] = [
            d for d in self._data[instrument] if d.get("date") != record.date
        ]
        self._data[instrument].append(record.to_dict())
        self._data[instrument] = self._data[instrument][-self.max_records:]
        self._save()
        logger.debug(
            f"Daily summary: saved {instrument} @ {record.date}, "
            f"total={len(self._data[instrument])}"
        )

    def get_recent(self, instrument: str, n: int = 7) -> List[DailySummaryRecord]:
        """Get last N daily summaries for an instrument."""
        raw = self._data.get(instrument, [])
        return [DailySummaryRecord.from_dict(d) for d in raw[-n:]]

    def get_context_for_agents(self, instrument: str, n: int = 7) -> str:
        """
        Build a text block with recent daily summaries
        for injection into agent prompts.
        """
        records = self.get_recent(instrument, n)
        if not records:
            return ""

        lines = [
            f"## Історія за останні дні ({instrument}, {len(records)} днів):",
            "Переглянь щоденні підсумки для розуміння тижневих трендів.",
            "",
        ]
        for rec in records:
            lines.append(rec.to_context_line())
            # Add top thesis if available
            if rec.key_theses:
                lines.append(f"  Теза: {rec.key_theses[0][:100]}")
            lines.append("")

        lines.append(
            "Враховуй багатоденну динаміку: чи тренд стабільний? "
            "Чи є розворот? Як змінювалась впевненість агентів?"
        )
        return "\n".join(lines)
