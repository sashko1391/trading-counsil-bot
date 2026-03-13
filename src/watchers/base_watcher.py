"""
BaseWatcher - Abstract base class for all market watchers.

Defines the interface that every watcher must implement:
- poll_once(): single polling cycle, returns list of MarketEvent
- get_latest_snapshot(): most recent market data
- get_history(): rolling window of past snapshots
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from models.schemas import MarketEvent


@dataclass
class MarketSnapshot:
    """
    A single snapshot of market data for one instrument.

    Fields are generic enough for oil (Brent, Gasoil) or any commodity.
    """

    timestamp: datetime
    symbol: str
    price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseWatcher(ABC):
    """Abstract base class for all watchers."""

    @abstractmethod
    def poll_once(self) -> List[MarketEvent]:
        """
        Execute one polling cycle.

        Returns:
            List of MarketEvent objects detected during this cycle.
            May be empty if nothing unusual happened.
        """
        ...

    @abstractmethod
    def get_latest_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        Return the most recent snapshot for the given symbol.

        Args:
            symbol: Instrument identifier (e.g. "BZ=F" for Brent).

        Returns:
            Latest MarketSnapshot or None if no data yet.
        """
        ...

    @abstractmethod
    def get_history(self, symbol: str, periods: int = 0) -> List[MarketSnapshot]:
        """
        Return historical snapshots for a symbol.

        Args:
            symbol: Instrument identifier.
            periods: Number of recent snapshots to return.
                     0 means return all available history.

        Returns:
            List of MarketSnapshot ordered oldest-first.
        """
        ...
