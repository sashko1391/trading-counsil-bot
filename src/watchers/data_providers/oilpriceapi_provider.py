"""
OilPriceAPIProvider — fetches Brent crude prices via OilPriceAPI.com.

Covers Brent only. Gasoil (LGO) is not available through this API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from loguru import logger


class OilPriceAPIProvider:
    """
    Implements DataProviderProtocol using OilPriceAPI.com REST API.

    Requires an API key from https://www.oilpriceapi.com/
    """

    BASE_URL = "https://api.oilpriceapi.com/v1"

    def __init__(self, api_key: str = "") -> None:
        if not api_key:
            raise ValueError(
                "OilPriceAPIProvider requires OILPRICEAPI_KEY. "
                "Get one at https://www.oilpriceapi.com/"
            )
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # DataProviderProtocol
    # ------------------------------------------------------------------

    def fetch_price(self, symbol: str) -> Dict[str, Any]:
        if symbol == "LGO":
            logger.warning("OilPriceAPI does not cover Gasoil (LGO)")
            return self._empty_price(symbol)

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{self.BASE_URL}/prices/latest",
                    headers=self._headers,
                    params={"by_code": "BRENT_CRUDE_USD"},
                )
                resp.raise_for_status()
                data = resp.json()

            price_data = data.get("data", {})
            price = float(price_data.get("price", 0))
            ts = price_data.get("created_at", datetime.now(tz=timezone.utc).isoformat())

            return {
                "symbol": symbol,
                "price": price,
                "open": None,
                "high": None,
                "low": None,
                "close": price,
                "volume": None,
                "timestamp": ts,
            }
        except Exception as exc:
            logger.error(f"OilPriceAPI fetch_price failed: {exc}")
            raise

    def fetch_history(self, symbol: str, periods: int = 50) -> List[Dict[str, Any]]:
        if symbol == "LGO":
            logger.warning("OilPriceAPI does not cover Gasoil (LGO) history")
            return []

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{self.BASE_URL}/prices",
                    headers=self._headers,
                    params={
                        "by_code": "BRENT_CRUDE_USD",
                        "by_type": "daily_average_price",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            prices = data.get("data", {}).get("prices", [])
            result: List[Dict[str, Any]] = []
            for entry in prices[-periods:]:
                price = float(entry.get("price", 0))
                result.append({
                    "symbol": symbol,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": price,
                    "volume": None,
                    "timestamp": entry.get("created_at", ""),
                })
            return result
        except Exception as exc:
            logger.error(f"OilPriceAPI fetch_history failed: {exc}")
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_price(symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "price": 0.0,
            "open": None,
            "high": None,
            "low": None,
            "close": 0.0,
            "volume": None,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
