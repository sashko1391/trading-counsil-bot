"""
Tests for EIAClient — EIA API v2 wrapper.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.watchers.eia_client import EIAClient


# ============================================================
# Sample API response fixture
# ============================================================

SAMPLE_INVENTORY_RESPONSE = {
    "response": {
        "data": [
            {"period": "2024-01-05", "value": "432100", "unit": "thousand barrels"},
            {"period": "2023-12-29", "value": "435000", "unit": "thousand barrels"},
        ]
    }
}

SAMPLE_PRODUCTION_RESPONSE = {
    "response": {
        "data": [
            {"period": "2024-01-05", "value": "13300", "unit": "thousand barrels per day"},
            {"period": "2023-12-29", "value": "13200", "unit": "thousand barrels per day"},
        ]
    }
}

SAMPLE_EMPTY_RESPONSE = {
    "response": {
        "data": []
    }
}


# ============================================================
# Empty API key handling
# ============================================================

class TestEmptyApiKey:
    @pytest.mark.asyncio
    async def test_no_key_returns_none_inventories(self):
        client = EIAClient(api_key="")
        result = await client.get_crude_inventories()
        assert result is None

    @pytest.mark.asyncio
    async def test_no_key_returns_none_production(self):
        client = EIAClient(api_key="")
        result = await client.get_production()
        assert result is None

    @pytest.mark.asyncio
    async def test_no_key_returns_none_utilization(self):
        client = EIAClient(api_key="")
        result = await client.get_refinery_utilization()
        assert result is None


# ============================================================
# Inventory parsing
# ============================================================

class TestInventoryParsing:
    @pytest.mark.asyncio
    async def test_parse_crude_inventories(self):
        client = EIAClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_INVENTORY_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.eia_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.get_crude_inventories()

        assert result is not None
        assert result["value"] == 432100.0
        assert result["date"] == "2024-01-05"
        assert result["unit"] == "thousand barrels"
        assert result["change_from_previous"] == -2900.0

    @pytest.mark.asyncio
    async def test_parse_production(self):
        client = EIAClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_PRODUCTION_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.eia_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.get_production()

        assert result is not None
        assert result["value"] == 13300.0
        assert result["change_from_previous"] == 100.0

    @pytest.mark.asyncio
    async def test_empty_data_returns_none(self):
        client = EIAClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.eia_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.get_crude_inventories()

        assert result is None


# ============================================================
# HTTP error handling
# ============================================================

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        client = EIAClient(api_key="test-key")

        with patch("src.watchers.eia_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.get_crude_inventories()

        assert result is None

    def test_parse_series_with_none(self):
        assert EIAClient._parse_series(None) is None

    def test_parse_series_with_malformed_data(self):
        result = EIAClient._parse_series({"response": {}})
        assert result is None
