"""
YFinanceProvider — fetches oil prices via the yfinance library.

Supported instruments:
  - BZ=F  : Brent Crude futures (ICE)
  - LGO   : Gasoil (ICE London) — fetched via nasdaqdatalink if available,
             otherwise a fallback warning is logged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger

try:
    import yfinance as yf  # type: ignore
except ImportError:  # pragma: no cover
    yf = None
    logger.warning("yfinance is not installed — YFinanceProvider will not work")

# Optional: nasdaqdatalink for Gasoil (LGO)
try:
    import nasdaqdatalink  # type: ignore

    _HAS_NASDAQ = True
except ImportError:
    _HAS_NASDAQ = False


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class YFinanceProvider:
    """
    Implements DataProviderProtocol using yfinance (+ optional nasdaqdatalink).
    """

    # Instruments that yfinance can handle directly
    _YF_SYMBOLS = {"BZ=F", "CL=F", "HO=F", "RB=F"}

    def __init__(self, nasdaq_api_key: str = "") -> None:
        if nasdaq_api_key and _HAS_NASDAQ:
            nasdaqdatalink.ApiConfig.api_key = nasdaq_api_key

    # ------------------------------------------------------------------
    # DataProviderProtocol
    # ------------------------------------------------------------------

    def fetch_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch latest price data for *symbol*."""
        if symbol == "LGO" and not self._can_use_yf(symbol):
            return self._fetch_lgo_price()

        return self._fetch_yf_price(symbol)

    def fetch_history(self, symbol: str, periods: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent OHLCV bars for *symbol*."""
        if symbol == "LGO" and not self._can_use_yf(symbol):
            return self._fetch_lgo_history(periods)

        return self._fetch_yf_history(symbol, periods)

    # ------------------------------------------------------------------
    # yfinance helpers
    # ------------------------------------------------------------------

    def _can_use_yf(self, symbol: str) -> bool:
        return symbol in self._YF_SYMBOLS

    def _fetch_yf_price(self, symbol: str) -> Dict[str, Any]:
        if yf is None:
            raise RuntimeError("yfinance is not installed")

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")

        if hist.empty:
            raise ValueError(f"No data returned by yfinance for {symbol}")

        last = hist.iloc[-1]
        return {
            "symbol": symbol,
            "price": float(last["Close"]),
            "open": float(last["Open"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "close": float(last["Close"]),
            "volume": float(last["Volume"]),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _fetch_yf_history(self, symbol: str, periods: int) -> List[Dict[str, Any]]:
        if yf is None:
            raise RuntimeError("yfinance is not installed")

        ticker = yf.Ticker(symbol)
        # Fetch a bit more than needed to account for non-trading days
        days = max(periods * 2, 30)
        hist = ticker.history(period=f"{days}d", interval="1d")

        if hist.empty:
            return []

        rows = hist.tail(periods)
        result: List[Dict[str, Any]] = []
        for idx, row in rows.iterrows():
            result.append(
                {
                    "symbol": symbol,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "timestamp": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                }
            )
        return result

    # ------------------------------------------------------------------
    # Gasoil (LGO) via nasdaqdatalink or fallback
    # ------------------------------------------------------------------

    def _fetch_lgo_price(self) -> Dict[str, Any]:
        if _HAS_NASDAQ:
            try:
                import pandas as pd  # type: ignore

                data = nasdaqdatalink.get("CHRIS/ICE_G1", rows=1)
                if data is not None and not data.empty:
                    last = data.iloc[-1]
                    return {
                        "symbol": "LGO",
                        "price": float(last.get("Settle", last.iloc[-1])),
                        "open": float(last.get("Open", 0)),
                        "high": float(last.get("High", 0)),
                        "low": float(last.get("Low", 0)),
                        "close": float(last.get("Settle", last.iloc[-1])),
                        "volume": float(last.get("Volume", 0)),
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    }
            except Exception as exc:
                logger.warning(f"nasdaqdatalink fetch for LGO failed: {exc}")

        logger.warning(
            "LGO (Gasoil) data unavailable — nasdaqdatalink not installed or fetch failed. "
            "Install nasdaqdatalink and set NASDAQ_DATA_LINK_API_KEY for Gasoil support."
        )
        return {
            "symbol": "LGO",
            "price": 0.0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0.0,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _fetch_lgo_history(self, periods: int) -> List[Dict[str, Any]]:
        if _HAS_NASDAQ:
            try:
                data = nasdaqdatalink.get("CHRIS/ICE_G1", rows=periods)
                if data is not None and not data.empty:
                    result: List[Dict[str, Any]] = []
                    for idx, row in data.iterrows():
                        result.append(
                            {
                                "symbol": "LGO",
                                "open": float(row.get("Open", 0)),
                                "high": float(row.get("High", 0)),
                                "low": float(row.get("Low", 0)),
                                "close": float(row.get("Settle", row.iloc[-1])),
                                "volume": float(row.get("Volume", 0)),
                                "timestamp": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                            }
                        )
                    return result
            except Exception as exc:
                logger.warning(f"nasdaqdatalink history for LGO failed: {exc}")

        logger.warning("LGO history unavailable — returning empty list.")
        return []
