"""
EIA API v2 Client — US Energy Information Administration data.

Provides methods for fetching crude oil inventories, production,
and refinery utilization from the EIA open data API.
"""

from typing import Optional

import httpx
from loguru import logger


EIA_BASE_URL = "https://api.eia.gov/v2/"


class EIAClient:
    """
    Async client for the EIA API v2.

    Parameters
    ----------
    api_key : EIA API key. If empty/None, methods log a warning and return None.
    base_url : Override for the API base URL (useful in testing).
    """

    def __init__(self, api_key: str = "", base_url: str = EIA_BASE_URL):
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")

    def _has_key(self) -> bool:
        if not self.api_key:
            logger.warning("EIA_API_KEY is not set — skipping EIA request")
            return False
        return True

    async def _get(self, route: str, params: dict) -> Optional[dict]:
        """Issue a GET request to the EIA API."""
        if not self._has_key():
            return None

        params["api_key"] = self.api_key
        url = f"{self.base_url}/{route.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(f"EIA API HTTP error {exc.response.status_code}: {exc}")
            return None
        except Exception as exc:
            logger.error(f"EIA API request failed: {exc}")
            return None

    @staticmethod
    def _parse_series(raw: Optional[dict]) -> Optional[dict]:
        """
        Extract the most recent data point from an EIA v2 response.

        Returns a dict with keys: value, date, unit, change_from_previous
        or None if data is unavailable.
        """
        if raw is None:
            return None

        try:
            response_data = raw.get("response", {})
            data_rows = response_data.get("data", [])
            if not data_rows:
                logger.warning("EIA response contained no data rows")
                return None

            # rows come sorted newest-first by default
            latest = data_rows[0]
            value = latest.get("value")
            if value is not None:
                value = float(value)

            result = {
                "value": value,
                "date": latest.get("period", ""),
                "unit": latest.get("unit", latest.get("units", "")),
                "change_from_previous": None,
            }

            if len(data_rows) >= 2:
                prev_value = data_rows[1].get("value")
                if prev_value is not None and value is not None:
                    result["change_from_previous"] = round(value - float(prev_value), 3)

            return result
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.error(f"Failed to parse EIA response: {exc}")
            return None

    # ----------------------------------------------------------
    # Public data methods
    # ----------------------------------------------------------

    async def get_crude_inventories(self) -> Optional[dict]:
        """
        Fetch weekly US crude oil ending stocks (thousand barrels).

        EIA series: PET → STEO → weekly crude oil stocks.
        """
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "WCESTUS1",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "2",
        }
        raw = await self._get("petroleum/stoc/wstk/data/", params)
        return self._parse_series(raw)

    async def get_production(self) -> Optional[dict]:
        """
        Fetch weekly US field production of crude oil (thousand barrels/day).
        """
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "WCRFPUS2",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "2",
        }
        raw = await self._get("petroleum/sum/sndw/data/", params)
        return self._parse_series(raw)

    async def get_refinery_utilization(self) -> Optional[dict]:
        """
        Fetch weekly US refinery utilization rate (percent).
        """
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "WPULEUS3",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "2",
        }
        raw = await self._get("petroleum/sum/sndw/data/", params)
        return self._parse_series(raw)
