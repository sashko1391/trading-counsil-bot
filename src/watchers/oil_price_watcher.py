"""
OilPriceWatcher — monitors Brent Crude and Gasoil prices for anomalies.

Detectors:
  - price_spike   : single instrument moves >2 % since N polls ago
  - volume_surge  : current volume >2x rolling average
  - spread_change : Brent-Gasoil crack spread shifts >5 %

Uses DataProviderProtocol (default: YFinanceProvider) so the data source
can be swapped without changing detection logic.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from loguru import logger

from models.schemas import MarketEvent
from watchers.base_watcher import BaseWatcher, MarketSnapshot
from watchers.data_providers import DataProviderProtocol
from watchers.data_providers.yfinance_provider import YFinanceProvider


class OilPriceWatcher(BaseWatcher):
    """
    Watches oil instruments, detects anomalies, returns MarketEvent objects.

    Args:
        provider: Any object satisfying DataProviderProtocol.
        instruments: List of symbols to monitor (default: ["BZ=F", "LGO"]).
        window_size: Rolling history window size per instrument.
        price_spike_pct: Minimum % move to trigger price_spike (default 2.0).
        volume_surge_ratio: Volume / avg_volume threshold (default 2.0).
        spread_change_pct: Crack-spread % change threshold (default 5.0).
        spike_lookback: How many snapshots back to compare for price spike.
        cooldown_seconds: Min seconds between events of the same type+instrument.
    """

    def __init__(
        self,
        provider: Optional[DataProviderProtocol] = None,
        instruments: Optional[List[str]] = None,
        window_size: int = 50,
        price_spike_pct: float = 2.0,
        volume_surge_ratio: float = 2.0,
        spread_change_pct: float = 5.0,
        spike_lookback: int = 10,
        cooldown_seconds: int = 300,
    ) -> None:
        self.provider: DataProviderProtocol = provider or YFinanceProvider()
        self.instruments = instruments or ["BZ=F", "LGO"]
        self.window_size = window_size
        self.price_spike_pct = price_spike_pct
        self.volume_surge_ratio = volume_surge_ratio
        self.spread_change_pct = spread_change_pct
        self.spike_lookback = spike_lookback
        self.cooldown_seconds = cooldown_seconds

        # Rolling history per instrument
        self._history: Dict[str, Deque[MarketSnapshot]] = {
            sym: deque(maxlen=window_size) for sym in self.instruments
        }

        # Cooldown tracker: "BZ=F:price_spike" -> last_event_time
        self._last_event: Dict[str, datetime] = {}

        # Track previous crack spread for spread_change detection
        self._prev_crack_spread: Optional[float] = None

        # Stats
        self.total_polls = 0
        self.total_events = 0
        self.errors = 0

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    def poll_once(self) -> List[MarketEvent]:
        """
        Single polling cycle: fetch data for each instrument, detect anomalies.
        """
        events: List[MarketEvent] = []

        for symbol in self.instruments:
            try:
                raw = self.provider.fetch_price(symbol)
                snapshot = self._raw_to_snapshot(raw)
                self._history[symbol].append(snapshot)

                if len(self._history[symbol]) >= 2:
                    events.extend(self._detect_price_spike(symbol, snapshot))
                    events.extend(self._detect_volume_surge(symbol, snapshot))

            except Exception as exc:
                self.errors += 1
                logger.error(f"OilPriceWatcher error for {symbol}: {exc}")

        # Crack spread detection (needs both Brent and Gasoil)
        if "BZ=F" in self.instruments and "LGO" in self.instruments:
            try:
                events.extend(self._detect_spread_change())
            except Exception as exc:
                logger.error(f"Spread change detection error: {exc}")

        self.total_polls += 1
        self.total_events += len(events)
        return events

    async def poll_once_async(self) -> List[MarketEvent]:
        """Async wrapper around poll_once for event-loop integration."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.poll_once)

    def get_latest_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        history = self._history.get(symbol)
        if history and len(history) > 0:
            return history[-1]
        return None

    def get_history(self, symbol: str, periods: int = 0) -> List[MarketSnapshot]:
        history = self._history.get(symbol, deque())
        items = list(history)
        if periods > 0:
            return items[-periods:]
        return items

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_price_spike(
        self, symbol: str, current: MarketSnapshot
    ) -> List[MarketEvent]:
        history = self._history[symbol]
        lookback = self.spike_lookback

        if len(history) < lookback:
            return []

        old = history[-lookback]
        if old.price == 0:
            return []

        change_pct = ((current.price - old.price) / old.price) * 100

        if abs(change_pct) < self.price_spike_pct:
            return []

        if self._is_on_cooldown(symbol, "price_spike"):
            return []

        self._set_cooldown(symbol, "price_spike")

        severity = min(abs(change_pct) / 10.0, 1.0)
        severity = max(severity, 0.3)
        direction = "UP" if change_pct > 0 else "DOWN"

        return [
            MarketEvent(
                event_type="price_spike",
                instrument=symbol,
                severity=round(severity, 2),
                headline=f"{symbol} price spike {direction} {abs(change_pct):.1f}%",
                data={
                    "price_change_pct": round(change_pct, 2),
                    "direction": direction,
                    "current_price": current.price,
                    "previous_price": old.price,
                },
            )
        ]

    def _detect_volume_surge(
        self, symbol: str, current: MarketSnapshot
    ) -> List[MarketEvent]:
        history = self._history[symbol]
        window = min(len(history) - 1, 20)

        if window < 2:
            return []

        recent_volumes = [s.volume for s in list(history)[-window - 1 : -1]]
        if not recent_volumes:
            return []

        avg_vol = sum(recent_volumes) / len(recent_volumes)
        if avg_vol == 0:
            return []

        ratio = current.volume / avg_vol
        if ratio < self.volume_surge_ratio:
            return []

        if self._is_on_cooldown(symbol, "volume_surge"):
            return []

        self._set_cooldown(symbol, "volume_surge")

        severity = min(ratio / 5.0, 1.0)
        severity = max(severity, 0.3)

        return [
            MarketEvent(
                event_type="volume_surge",
                instrument=symbol,
                severity=round(severity, 2),
                headline=f"{symbol} volume surge {ratio:.1f}x average",
                data={
                    "volume_ratio": round(ratio, 2),
                    "current_volume": current.volume,
                    "average_volume": round(avg_vol, 2),
                    "current_price": current.price,
                },
            )
        ]

    def _detect_spread_change(self) -> List[MarketEvent]:
        """
        Crack spread = Brent price - Gasoil price (simplified).
        Fires when spread changes by more than spread_change_pct relative
        to the previous poll.
        """
        brent_snap = self.get_latest_snapshot("BZ=F")
        gasoil_snap = self.get_latest_snapshot("LGO")

        if brent_snap is None or gasoil_snap is None:
            return []

        if brent_snap.price == 0 or gasoil_snap.price == 0:
            return []

        current_spread = brent_snap.price - gasoil_snap.price

        if self._prev_crack_spread is None:
            self._prev_crack_spread = current_spread
            return []

        if self._prev_crack_spread == 0:
            self._prev_crack_spread = current_spread
            return []

        prev_spread = self._prev_crack_spread
        spread_change = (
            (current_spread - prev_spread) / abs(prev_spread) * 100
        )

        # Update for next poll
        self._prev_crack_spread = current_spread

        if abs(spread_change) < self.spread_change_pct:
            return []

        if self._is_on_cooldown("CRACK_SPREAD", "spread_change"):
            return []

        self._set_cooldown("CRACK_SPREAD", "spread_change")

        severity = min(abs(spread_change) / 15.0, 1.0)
        severity = max(severity, 0.3)
        direction = "WIDENING" if spread_change > 0 else "NARROWING"

        return [
            MarketEvent(
                event_type="spread_change",
                instrument="BZ=F",
                severity=round(severity, 2),
                headline=f"Crack spread {direction} {abs(spread_change):.1f}%",
                data={
                    "spread_change_pct": round(spread_change, 2),
                    "direction": direction,
                    "current_spread": round(current_spread, 2),
                    "previous_spread": round(prev_spread, 2),
                    "brent_price": brent_snap.price,
                    "gasoil_price": gasoil_snap.price,
                },
            )
        ]

    # ------------------------------------------------------------------
    # Cooldown
    # ------------------------------------------------------------------

    def _is_on_cooldown(self, symbol: str, event_type: str) -> bool:
        key = f"{symbol}:{event_type}"
        if key not in self._last_event:
            return False
        elapsed = (datetime.now(tz=timezone.utc) - self._last_event[key]).total_seconds()
        return elapsed < self.cooldown_seconds

    def _set_cooldown(self, symbol: str, event_type: str) -> None:
        self._last_event[f"{symbol}:{event_type}"] = datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_to_snapshot(raw: Dict[str, Any]) -> MarketSnapshot:
        return MarketSnapshot(
            timestamp=datetime.now(tz=timezone.utc),
            symbol=raw.get("symbol", ""),
            price=float(raw.get("price", 0)),
            open=float(raw.get("open", 0)),
            high=float(raw.get("high", 0)),
            low=float(raw.get("low", 0)),
            close=float(raw.get("close", 0)),
            volume=float(raw.get("volume", 0)),
        )

    def __repr__(self) -> str:
        return (
            f"OilPriceWatcher(instruments={self.instruments}, "
            f"polls={self.total_polls}, events={self.total_events})"
        )
