"""
Data Providers — adapter layer between raw market-data APIs and the watcher.

Every provider implements DataProviderProtocol so the watcher can swap
backends (yfinance, OilPriceAPI, Databento, etc.) without changing its own code.
"""

from typing import Protocol, Dict, List, Any, runtime_checkable

from loguru import logger


@runtime_checkable
class DataProviderProtocol(Protocol):
    """
    Protocol that every data provider must satisfy.

    Methods return plain dicts so the watcher converts them into its own
    MarketSnapshot objects.
    """

    def fetch_price(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch the latest price data for *symbol*.

        Returns a dict with at least:
            symbol, price, open, high, low, close, volume, timestamp
        """
        ...

    def fetch_history(self, symbol: str, periods: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent OHLCV history for *symbol*.

        Returns a list of dicts, each with:
            symbol, open, high, low, close, volume, timestamp
        """
        ...


def get_provider(name: str | None = None) -> DataProviderProtocol:
    """Factory: return a DataProviderProtocol by name.

    Supported names: "yfinance", "oilpriceapi".
    Defaults to settings.DATA_PROVIDER if *name* is None.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    provider_name = (name or settings.DATA_PROVIDER).lower()

    if provider_name == "yfinance":
        from src.watchers.data_providers.yfinance_provider import YFinanceProvider
        return YFinanceProvider(nasdaq_api_key=settings.NASDAQ_DATA_LINK_KEY)

    if provider_name == "oilpriceapi":
        from src.watchers.data_providers.oilpriceapi_provider import OilPriceAPIProvider
        return OilPriceAPIProvider(api_key=settings.OILPRICEAPI_KEY)

    raise ValueError(f"Unknown data provider: {provider_name!r}")
