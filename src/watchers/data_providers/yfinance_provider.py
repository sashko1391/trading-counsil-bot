"""
YFinanceProvider — fetches oil prices via the yfinance library.

Supported instruments:
  - BZ=F  : Brent Crude futures (ICE)
  - LGO   : Gasoil (ICE London) — fetched via nasdaqdatalink if available,
             otherwise a fallback warning is logged.

Note: Yahoo Finance's generic BZ=F ticker can roll to the next contract month
before the actual front-month expires.  This provider detects the roll and
falls back to the specific near-month contract (e.g. BZK26.NYM) so the price
matches what TradingView / Investing.com show.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

# Month code mapping for futures contracts
_MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _resolve_active_brent_ticker() -> str:
    """
    Determine which specific Brent contract to use.

    Yahoo's generic BZ=F sometimes rolls early.  We check the underlying
    symbol and, if it has already moved to the next month, try the
    previous (still-active) specific contract instead.
    """
    if yf is None:
        return "BZ=F"

    try:
        generic = yf.Ticker("BZ=F")
        underlying = generic.info.get("underlyingSymbol", "")

        if not underlying or underlying == "BZ=F":
            return "BZ=F"

        # underlying looks like "BZM26.NYM" — extract month code + year
        # Build the *previous* month contract to compare
        code_part = underlying.replace(".NYM", "")  # "BZM26"
        month_code = code_part[2]   # "M"
        year_suffix = code_part[3:]  # "26"

        # Find month number from code
        code_to_month = {v: k for k, v in _MONTH_CODES.items()}
        underlying_month = code_to_month.get(month_code)
        if not underlying_month:
            return "BZ=F"

        # Build previous month ticker
        prev_month = underlying_month - 1
        prev_year = int(year_suffix)
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1

        prev_code = _MONTH_CODES[prev_month]
        prev_ticker = f"BZ{prev_code}{prev_year:02d}.NYM"

        # Check if previous month contract still has data (not expired)
        try:
            prev = yf.Ticker(prev_ticker)
            hist = prev.history(period="5d")
            if not hist.empty and len(hist) > 0:
                last_date = hist.index[-1]
                # If the previous contract traded within the last 5 business days, use it
                days_ago = (datetime.now(tz=last_date.tzinfo or timezone.utc) - last_date).days
                if days_ago <= 5:
                    prev_price = float(hist.iloc[-1]["Close"])
                    generic_price = generic.fast_info.last_price
                    # Only use prev contract if there's a meaningful price difference
                    if abs(prev_price - generic_price) / generic_price > 0.005:
                        logger.info(
                            f"Brent roll detected: BZ=F=${generic_price:.2f} (→{underlying}), "
                            f"using {prev_ticker}=${prev_price:.2f} (active front month)"
                        )
                        return prev_ticker
        except Exception:
            pass

        return "BZ=F"
    except Exception as exc:
        logger.debug(f"Active Brent ticker resolution failed: {exc}")
        return "BZ=F"


class YFinanceProvider:
    """
    Implements DataProviderProtocol using yfinance (+ optional nasdaqdatalink).
    """

    # Instruments that yfinance can handle directly
    _YF_SYMBOLS = {"BZ=F", "CL=F", "HO=F", "RB=F"}

    def __init__(self, nasdaq_api_key: str = "") -> None:
        if nasdaq_api_key and _HAS_NASDAQ:
            nasdaqdatalink.ApiConfig.api_key = nasdaq_api_key

        # Resolve actual active Brent ticker (handles Yahoo early roll)
        self._brent_ticker: str = _resolve_active_brent_ticker()
        self._brent_resolved_at: Optional[datetime] = _now_utc()

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

    def _get_yf_ticker(self, symbol: str) -> str:
        """Map logical symbol to actual yfinance ticker (handles Brent roll)."""
        if symbol == "BZ=F":
            # Re-resolve every 6 hours to catch contract expiry
            if self._brent_resolved_at:
                elapsed = (_now_utc() - self._brent_resolved_at).total_seconds()
                if elapsed > 6 * 3600:
                    self._brent_ticker = _resolve_active_brent_ticker()
                    self._brent_resolved_at = _now_utc()
            return self._brent_ticker
        return symbol

    def _fetch_yf_price(self, symbol: str) -> Dict[str, Any]:
        if yf is None:
            raise RuntimeError("yfinance is not installed")

        actual_ticker = self._get_yf_ticker(symbol)
        ticker = yf.Ticker(actual_ticker)
        hist = ticker.history(period="2d", interval="1d")

        if hist.empty:
            raise ValueError(f"No data returned by yfinance for {actual_ticker}")

        last = hist.iloc[-1]
        return {
            "symbol": symbol,  # keep original symbol for consistency
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

        actual_ticker = self._get_yf_ticker(symbol)
        ticker = yf.Ticker(actual_ticker)
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
