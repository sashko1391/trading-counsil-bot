"""
ForecastTracker — records OilForecast objects, matches them against
actual outcomes, and computes calibration / accuracy metrics.

Storage: JSON file at data/forecast_history.json
Persists across restarts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from models.schemas import OilForecast


_DEFAULT_PATH = Path("data/forecast_history.json")


class ForecastTracker:
    """
    Tracks OilForecast predictions and their outcomes.

    Each record is a dict:
        {
            "id": str,
            "forecast": { ... serialised OilForecast ... },
            "actual_price": float | None,
            "outcome_recorded_at": str | None,
            "direction_correct": bool | None,
        }
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _DEFAULT_PATH
        self._records: list[dict] = []
        self._load()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def record_forecast(self, forecast: OilForecast) -> str:
        """
        Save a new forecast. Returns assigned forecast id.
        """
        forecast_id = uuid.uuid4().hex[:12]

        record = {
            "id": forecast_id,
            "forecast": forecast.model_dump(mode="json"),
            "actual_price": None,
            "outcome_recorded_at": None,
            "direction_correct": None,
        }
        self._records.append(record)
        self._save()
        logger.info(f"Recorded forecast {forecast_id} for {forecast.instrument}")
        return forecast_id

    def record_outcome(self, forecast_id: str, actual_price: float) -> bool:
        """
        Record what actually happened for a given forecast.
        Returns True if the forecast was found and updated.
        """
        for rec in self._records:
            if rec["id"] == forecast_id:
                rec["actual_price"] = actual_price
                rec["outcome_recorded_at"] = datetime.now().isoformat()

                fc = rec["forecast"]
                direction = fc["direction"]
                current_price = fc["current_price"]

                if direction == "BULLISH":
                    rec["direction_correct"] = actual_price > current_price
                elif direction == "BEARISH":
                    rec["direction_correct"] = actual_price < current_price
                else:  # NEUTRAL
                    # correct if price moved less than 1%
                    move_pct = abs(actual_price - current_price) / current_price * 100
                    rec["direction_correct"] = move_pct < 1.0

                self._save()
                logger.info(
                    f"Outcome for {forecast_id}: actual={actual_price}, "
                    f"correct={rec['direction_correct']}"
                )
                return True

        logger.warning(f"Forecast {forecast_id} not found")
        return False

    def get_hit_rate(self) -> float:
        """
        Percentage of resolved forecasts where direction was correct.
        Returns 0.0 if no outcomes recorded yet.
        """
        resolved = [r for r in self._records if r["direction_correct"] is not None]
        if not resolved:
            return 0.0
        correct = sum(1 for r in resolved if r["direction_correct"])
        return correct / len(resolved)

    def get_brier_score(self) -> float:
        """
        Brier score: mean of (confidence - outcome)^2  (lower = better).

        outcome = 1.0 if direction correct, 0.0 otherwise.
        Returns 0.0 if no outcomes recorded.
        """
        resolved = [r for r in self._records if r["direction_correct"] is not None]
        if not resolved:
            return 0.0

        total = 0.0
        for rec in resolved:
            confidence = rec["forecast"]["confidence"]
            outcome = 1.0 if rec["direction_correct"] else 0.0
            total += (confidence - outcome) ** 2

        return total / len(resolved)

    def get_summary(self) -> dict:
        """
        Overall stats dict.
        """
        resolved = [r for r in self._records if r["direction_correct"] is not None]
        confidences = [r["forecast"]["confidence"] for r in self._records]

        return {
            "total_forecasts": len(self._records),
            "resolved": len(resolved),
            "hit_rate": self.get_hit_rate(),
            "avg_confidence": (
                sum(confidences) / len(confidences) if confidences else 0.0
            ),
            "brier_score": self.get_brier_score(),
        }

    def generate_weekly_report(self) -> str:
        """
        Formatted text report suitable for Telegram.
        Covers forecasts from the last 7 days.
        """
        cutoff = datetime.now() - timedelta(days=7)

        week_records = []
        for rec in self._records:
            ts_str = rec["forecast"].get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts >= cutoff:
                        week_records.append(rec)
                except (ValueError, TypeError):
                    pass

        resolved = [r for r in week_records if r["direction_correct"] is not None]
        correct = sum(1 for r in resolved if r["direction_correct"])
        hit_rate = correct / len(resolved) if resolved else 0.0

        # Brier for the week
        brier = 0.0
        if resolved:
            for rec in resolved:
                c = rec["forecast"]["confidence"]
                o = 1.0 if rec["direction_correct"] else 0.0
                brier += (c - o) ** 2
            brier /= len(resolved)

        lines = [
            "=== Weekly Forecast Report ===",
            f"Period: last 7 days",
            f"Total forecasts: {len(week_records)}",
            f"Resolved: {len(resolved)}",
            f"Hit rate: {hit_rate:.0%}",
            f"Brier score: {brier:.3f}",
            "",
        ]

        # Per-instrument breakdown
        instruments: dict[str, list] = {}
        for rec in week_records:
            inst = rec["forecast"].get("instrument", "?")
            instruments.setdefault(inst, []).append(rec)

        for inst, recs in instruments.items():
            res = [r for r in recs if r["direction_correct"] is not None]
            c = sum(1 for r in res if r["direction_correct"])
            hr = c / len(res) if res else 0.0
            lines.append(f"  {inst}: {len(recs)} forecasts, {hr:.0%} hit rate")

        # All-time summary
        summary = self.get_summary()
        lines.append("")
        lines.append("--- All-time ---")
        lines.append(f"Total: {summary['total_forecasts']}")
        lines.append(f"Hit rate: {summary['hit_rate']:.0%}")
        lines.append(f"Avg confidence: {summary['avg_confidence']:.0%}")
        lines.append(f"Brier: {summary['brier_score']:.3f}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._records = json.load(f)
                logger.info(f"Loaded {len(self._records)} forecasts from {self.path}")
            except (json.JSONDecodeError, IOError) as exc:
                logger.error(f"Failed to load forecast history: {exc}")
                self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.path, "w") as f:
                json.dump(self._records, f, indent=2, default=str)
        except IOError as exc:
            logger.error(f"Failed to save forecast history: {exc}")
