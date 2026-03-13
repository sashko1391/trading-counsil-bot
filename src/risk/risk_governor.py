"""
Risk Governor — oil-specific risk management filter.

Evaluates 6-category OilRiskScore and enforces:
  - daily alert limit
  - cooldown between alerts
  - minimum confidence threshold
  - OPEC meeting proximity caution
  - composite risk ceiling

Input : MarketEvent + optional EIA data + optional scheduled events
Output: RiskCheck (allowed / blocked with reason)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from models.schemas import (
    CouncilResponse,
    MarketEvent,
    OilRiskScore,
    RiskCheck,
)


# ── Seasonal risk lookup (quarter → base risk) ──────────────────────
_SEASONAL_RISK: dict[int, float] = {
    1: 0.6,   # Q1 — heating-oil demand, winter storms
    2: 0.3,   # Q2 — refinery maintenance shoulder
    3: 0.5,   # Q3 — driving season, hurricane season
    4: 0.4,   # Q4 — year-end rebalancing
}


class RiskGovernor:
    """
    Oil-market risk governor.

    Calculates an OilRiskScore from available market data and decides
    whether an alert / trade recommendation should be allowed.

    Rules
    -----
    1. daily_alerts_count >= max_daily_alerts  → block
    2. cooldown not expired                    → block
    3. combined_confidence < min_confidence     → block
    4. consensus_strength < min_strength        → block
    5. OPEC meeting within 24 h                → raise caution (score bump)
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        min_strength: str = "STRONG",
        max_daily_alerts: int = 10,
        cooldown_minutes: int = 30,
        max_composite_risk: float = 0.85,
        now_func=None,
    ):
        self.min_confidence = min_confidence
        self.min_strength = min_strength
        self.max_daily_alerts = max_daily_alerts
        self.cooldown_minutes = cooldown_minutes
        self.max_composite_risk = max_composite_risk
        self._now_func = now_func or datetime.now

        # Strength hierarchy
        self._strength_order = {
            "NONE": 0,
            "WEAK": 1,
            "STRONG": 2,
            "UNANIMOUS": 3,
        }

        # State
        self._daily_alerts_count: int = 0
        self._last_alert_time: Optional[datetime] = None
        self._current_day: Optional[int] = None  # ordinal day for reset

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def check(
        self,
        council_response: CouncilResponse,
        event: Optional[MarketEvent] = None,
        eia_data: Optional[dict] = None,
        scheduled_events: Optional[list[dict]] = None,
        daily_pnl: float = 0.0,
    ) -> RiskCheck:
        """
        Main entry point — evaluate whether the council recommendation
        should be forwarded to the user.
        """
        now = self._now_func()
        self._maybe_reset_daily_counter(now)

        # Build oil risk score from available data
        risk_score = self.calculate_risk_score(
            event=event,
            eia_data=eia_data,
            scheduled_events=scheduled_events,
        )

        # Cooldown remaining
        cooldown_sec = self._cooldown_remaining_sec(now)

        # --- WAIT is always allowed (no action taken) ---
        if council_response.consensus == "WAIT":
            return RiskCheck(
                allowed=True,
                reason="Consensus is WAIT — no action needed",
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- Check 1: daily alert limit ---
        if self._daily_alerts_count >= self.max_daily_alerts:
            return RiskCheck(
                allowed=False,
                reason=f"Daily alert limit reached: {self._daily_alerts_count}/{self.max_daily_alerts}",
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- Check 2: cooldown ---
        if cooldown_sec > 0:
            return RiskCheck(
                allowed=False,
                reason=f"Cooldown active: {cooldown_sec}s remaining",
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- Check 3: confidence ---
        if council_response.combined_confidence < self.min_confidence:
            return RiskCheck(
                allowed=False,
                reason=(
                    f"Confidence too low: "
                    f"{council_response.combined_confidence:.0%} < {self.min_confidence:.0%}"
                ),
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- Check 4: consensus strength ---
        current_str = self._strength_order.get(council_response.consensus_strength, 0)
        required_str = self._strength_order.get(self.min_strength, 2)
        if current_str < required_str:
            return RiskCheck(
                allowed=False,
                reason=(
                    f"Consensus too weak: "
                    f"{council_response.consensus_strength} < {self.min_strength}"
                ),
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- Check 5: composite risk ceiling ---
        if risk_score.composite > self.max_composite_risk:
            return RiskCheck(
                allowed=False,
                reason=(
                    f"Composite risk too high: "
                    f"{risk_score.composite:.2f} > {self.max_composite_risk:.2f}"
                ),
                oil_risk_score=risk_score,
                daily_alerts_count=self._daily_alerts_count,
                cooldown_remaining_sec=cooldown_sec,
            )

        # --- All checks passed ---
        self._daily_alerts_count += 1
        self._last_alert_time = now

        return RiskCheck(
            allowed=True,
            reason=f"All checks passed — {council_response.consensus} approved",
            oil_risk_score=risk_score,
            daily_alerts_count=self._daily_alerts_count,
            cooldown_remaining_sec=0,
        )

    # ------------------------------------------------------------------ #
    # Risk score calculation                                               #
    # ------------------------------------------------------------------ #

    def calculate_risk_score(
        self,
        event: Optional[MarketEvent] = None,
        eia_data: Optional[dict] = None,
        scheduled_events: Optional[list[dict]] = None,
    ) -> OilRiskScore:
        """
        Build an OilRiskScore from available market context.

        Each factor is 0..1 where higher = more risk.
        """
        geopolitical = self._calc_geopolitical(event)
        supply = self._calc_supply(event, scheduled_events)
        demand = self._calc_demand(eia_data)
        financial = self._calc_financial(event)
        seasonal = self._calc_seasonal()
        technical = self._calc_technical(event)

        return OilRiskScore(
            geopolitical=round(geopolitical, 2),
            supply=round(supply, 2),
            demand=round(demand, 2),
            financial=round(financial, 2),
            seasonal=round(seasonal, 2),
            technical=round(technical, 2),
        )

    # ── Factor helpers ──────────────────────────────────────────────

    @staticmethod
    def _calc_geopolitical(event: Optional[MarketEvent]) -> float:
        """Geopolitical risk from news severity and event type."""
        if event is None:
            return 0.3  # baseline

        if event.event_type in ("geopolitical_alert", "news_event"):
            return min(event.severity * 1.2, 1.0)

        if event.event_type == "opec_event":
            return min(event.severity * 1.0, 1.0)

        # Any other event — mild geo contribution from severity
        return min(event.severity * 0.3, 1.0)

    @staticmethod
    def _calc_supply(
        event: Optional[MarketEvent],
        scheduled_events: Optional[list[dict]],
    ) -> float:
        """Supply risk — OPEC proximity, production disruptions."""
        base = 0.3

        # OPEC meeting proximity
        if scheduled_events:
            for se in scheduled_events:
                name = se.get("name", "")
                if "OPEC" in name.upper():
                    base = max(base, 0.7)
                    break

        if event is not None and event.event_type == "opec_event":
            base = max(base, event.severity)

        return min(base, 1.0)

    @staticmethod
    def _calc_demand(eia_data: Optional[dict]) -> float:
        """Demand risk from EIA data (inventory changes)."""
        if eia_data is None:
            return 0.3  # baseline

        # Inventory build = bearish demand signal
        inventory_change = eia_data.get("inventory_change_mb", 0.0)
        if inventory_change > 5.0:
            return 0.8
        if inventory_change > 2.0:
            return 0.6
        if inventory_change < -5.0:
            return 0.7  # large draw also risky (potential reversal)
        if inventory_change < -2.0:
            return 0.4

        return 0.3

    @staticmethod
    def _calc_financial(event: Optional[MarketEvent]) -> float:
        """Financial risk — USD/DXY moves implied by event data."""
        if event is None:
            return 0.2

        dxy_change = event.data.get("dxy_change_pct", 0.0)
        if abs(dxy_change) > 1.0:
            return 0.7
        if abs(dxy_change) > 0.5:
            return 0.5

        return 0.2

    def _calc_seasonal(self) -> float:
        """Seasonal risk based on current quarter."""
        now = self._now_func()
        quarter = (now.month - 1) // 3 + 1
        return _SEASONAL_RISK.get(quarter, 0.3)

    @staticmethod
    def _calc_technical(event: Optional[MarketEvent]) -> float:
        """Technical risk from spread changes and price spikes."""
        if event is None:
            return 0.2

        if event.event_type == "spread_change":
            change = abs(event.data.get("spread_change_pct", 0.0))
            return min(change / 15.0, 1.0)

        if event.event_type == "price_spike":
            change = abs(event.data.get("price_change_pct", 0.0))
            return min(change / 10.0, 1.0)

        return 0.2

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _cooldown_remaining_sec(self, now: datetime) -> int:
        if self._last_alert_time is None:
            return 0
        elapsed = (now - self._last_alert_time).total_seconds()
        remaining = self.cooldown_minutes * 60 - elapsed
        return max(int(remaining), 0)

    def _maybe_reset_daily_counter(self, now: datetime) -> None:
        today = now.toordinal()
        if self._current_day is None or self._current_day != today:
            self._current_day = today
            self._daily_alerts_count = 0

    def reset_daily(self) -> None:
        """Manual reset (e.g. from scheduler at midnight)."""
        self._daily_alerts_count = 0
        self._current_day = self._now_func().toordinal()
