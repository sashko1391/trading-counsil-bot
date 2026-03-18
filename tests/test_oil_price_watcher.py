"""
Tests for OilPriceWatcher — price spike, volume surge, spread change,
and rolling window behaviour.

All tests use a mock data provider so yfinance is not required.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Ensure src/ is on the path so imports work as in the installed package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchers.base_watcher import MarketSnapshot
from watchers.oil_price_watcher import OilPriceWatcher
from watchers.data_providers import DataProviderProtocol


# ======================================================================
# Mock provider
# ======================================================================

class MockProvider:
    """
    A controllable data provider for tests.

    Set `.prices` to a dict mapping symbol -> price-data-dict.
    Each call to fetch_price returns the next item from the list for that
    symbol (cycling back to the last element if exhausted).
    """

    def __init__(self) -> None:
        self._prices: dict[str, list[dict]] = {}
        self._cursors: dict[str, int] = {}

    def set_prices(self, symbol: str, data_list: list[dict]) -> None:
        self._prices[symbol] = data_list
        self._cursors[symbol] = 0

    def fetch_price(self, symbol: str) -> dict:
        data_list = self._prices.get(symbol, [])
        if not data_list:
            return _default_price(symbol)
        idx = self._cursors.get(symbol, 0)
        result = data_list[min(idx, len(data_list) - 1)]
        self._cursors[symbol] = idx + 1
        return result

    def fetch_history(self, symbol: str, periods: int = 50) -> list[dict]:
        return []


# Check the mock satisfies the protocol
assert isinstance(MockProvider(), DataProviderProtocol)


def _default_price(symbol: str, price: float = 80.0, volume: float = 1000.0) -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "open": price - 0.5,
        "high": price + 0.5,
        "low": price - 1.0,
        "close": price,
        "volume": volume,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def _make_price(symbol: str, price: float, volume: float = 1000.0) -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": volume,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def mock_provider():
    return MockProvider()


@pytest.fixture
def watcher(mock_provider):
    """Watcher with small lookback so tests don't need many polls."""
    return OilPriceWatcher(
        provider=mock_provider,
        instruments=["BZ=F"],
        window_size=50,
        price_spike_pct=2.0,
        volume_surge_ratio=2.0,
        spike_lookback=3,
        cooldown_seconds=0,  # disable cooldown for tests
    )


# ======================================================================
# Price spike tests
# ======================================================================

class TestPriceSpike:
    def test_spike_detected_up(self, mock_provider):
        """A +3% price move should trigger a price_spike event."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            spike_lookback=3,
            cooldown_seconds=0,
        )

        # 3 stable polls at 80.0, then jump to 82.5 (+3.125%)
        prices = [_make_price("BZ=F", 80.0)] * 3 + [_make_price("BZ=F", 82.5)]
        mock_provider.set_prices("BZ=F", prices)

        all_events = []
        for _ in range(4):
            all_events.extend(watcher.poll_once())

        spike_events = [e for e in all_events if e.event_type == "price_spike"]
        assert len(spike_events) >= 1
        assert spike_events[0].data["direction"] == "UP"
        assert spike_events[0].data["price_change_pct"] > 2.0

    def test_spike_detected_down(self, mock_provider):
        """A -3% price move should also trigger a price_spike event."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            spike_lookback=3,
            cooldown_seconds=0,
        )

        prices = [_make_price("BZ=F", 80.0)] * 3 + [_make_price("BZ=F", 77.0)]
        mock_provider.set_prices("BZ=F", prices)

        all_events = []
        for _ in range(4):
            all_events.extend(watcher.poll_once())

        spike_events = [e for e in all_events if e.event_type == "price_spike"]
        assert len(spike_events) >= 1
        assert spike_events[0].data["direction"] == "DOWN"

    def test_no_spike_below_threshold(self, mock_provider):
        """A 1% move should NOT trigger a price_spike."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            spike_lookback=3,
            cooldown_seconds=0,
        )

        prices = [_make_price("BZ=F", 80.0)] * 3 + [_make_price("BZ=F", 80.8)]
        mock_provider.set_prices("BZ=F", prices)

        all_events = []
        for _ in range(4):
            all_events.extend(watcher.poll_once())

        spike_events = [e for e in all_events if e.event_type == "price_spike"]
        assert len(spike_events) == 0


# ======================================================================
# Volume surge tests
# ======================================================================

class TestVolumeSurge:
    def test_volume_surge_detected(self, mock_provider):
        """Volume 3x the average should trigger a volume_surge."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            spike_lookback=100,  # high so price spike won't fire
            cooldown_seconds=0,
        )

        # 5 polls at volume=1000, then spike to 3000
        prices = [_make_price("BZ=F", 80.0, volume=1000)] * 5 + [
            _make_price("BZ=F", 80.0, volume=3000)
        ]
        mock_provider.set_prices("BZ=F", prices)

        all_events = []
        for _ in range(6):
            all_events.extend(watcher.poll_once())

        vol_events = [e for e in all_events if e.event_type == "volume_surge"]
        assert len(vol_events) >= 1
        assert vol_events[0].data["volume_ratio"] >= 2.0

    def test_no_volume_surge_below_threshold(self, mock_provider):
        """Volume 1.5x should NOT trigger a volume_surge (threshold=2x)."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            spike_lookback=100,
            cooldown_seconds=0,
        )

        prices = [_make_price("BZ=F", 80.0, volume=1000)] * 5 + [
            _make_price("BZ=F", 80.0, volume=1500)
        ]
        mock_provider.set_prices("BZ=F", prices)

        all_events = []
        for _ in range(6):
            all_events.extend(watcher.poll_once())

        vol_events = [e for e in all_events if e.event_type == "volume_surge"]
        assert len(vol_events) == 0


# ======================================================================
# Rolling window tests
# ======================================================================

class TestRollingWindow:
    def test_window_size_respected(self, mock_provider):
        """History should not exceed window_size."""
        small_window = 5
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            window_size=small_window,
            cooldown_seconds=0,
        )

        mock_provider.set_prices(
            "BZ=F", [_make_price("BZ=F", 80.0 + i * 0.01) for i in range(20)]
        )

        for _ in range(20):
            watcher.poll_once()

        history = watcher.get_history("BZ=F")
        assert len(history) == small_window

    def test_get_latest_snapshot(self, mock_provider):
        """get_latest_snapshot returns the most recent poll data."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            cooldown_seconds=0,
        )

        mock_provider.set_prices("BZ=F", [_make_price("BZ=F", 85.5)])
        watcher.poll_once()

        snap = watcher.get_latest_snapshot("BZ=F")
        assert snap is not None
        assert snap.price == 85.5
        assert snap.symbol == "BZ=F"

    def test_get_history_with_periods(self, mock_provider):
        """get_history(periods=N) returns only the last N snapshots."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
            window_size=50,
            cooldown_seconds=0,
        )

        mock_provider.set_prices(
            "BZ=F", [_make_price("BZ=F", 80.0 + i) for i in range(10)]
        )

        for _ in range(10):
            watcher.poll_once()

        last3 = watcher.get_history("BZ=F", periods=3)
        assert len(last3) == 3
        # The last snapshot should have the highest price
        assert last3[-1].price == 89.0

    def test_empty_history_returns_none(self, mock_provider):
        """get_latest_snapshot returns None when no data has been polled."""
        watcher = OilPriceWatcher(
            provider=mock_provider,
            instruments=["BZ=F"],
        )
        assert watcher.get_latest_snapshot("BZ=F") is None
        assert watcher.get_history("BZ=F") == []


# ======================================================================
# Protocol conformance
# ======================================================================

class TestProtocol:
    def test_mock_provider_satisfies_protocol(self):
        assert isinstance(MockProvider(), DataProviderProtocol)

    def test_watcher_is_base_watcher(self, mock_provider):
        watcher = OilPriceWatcher(provider=mock_provider, instruments=["BZ=F"])
        assert isinstance(watcher, OilPriceWatcher)


# ======================================================================
# OilPriceAPIProvider tests
# ======================================================================

from watchers.data_providers.oilpriceapi_provider import OilPriceAPIProvider


class TestOilPriceAPIProvider:
    def test_satisfies_protocol(self):
        assert isinstance(OilPriceAPIProvider(api_key="test"), DataProviderProtocol)

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="OILPRICEAPI_KEY"):
            OilPriceAPIProvider(api_key="")

    def test_fetch_price_brent(self, monkeypatch):
        """Mock HTTP response for Brent price."""
        provider = OilPriceAPIProvider(api_key="test-key")

        mock_json = {
            "data": {
                "price": "82.45",
                "created_at": "2026-03-10T12:00:00Z",
            }
        }

        class MockResponse:
            def raise_for_status(self): pass
            def json(self): return mock_json

        class MockClient:
            def __init__(self, **kw): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def get(self, *a, **kw): return MockResponse()

        monkeypatch.setattr("watchers.data_providers.oilpriceapi_provider.httpx.Client", MockClient)

        result = provider.fetch_price("BZ=F")
        assert result["symbol"] == "BZ=F"
        assert result["price"] == 82.45
        assert result["close"] == 82.45

    def test_fetch_price_lgo_returns_empty(self):
        """LGO is not supported — should return zero price."""
        provider = OilPriceAPIProvider(api_key="test-key")
        result = provider.fetch_price("LGO")
        assert result["symbol"] == "LGO"
        assert result["price"] == 0.0

    def test_fetch_history_brent(self, monkeypatch):
        provider = OilPriceAPIProvider(api_key="test-key")

        mock_json = {
            "data": {
                "prices": [
                    {"price": "80.0", "created_at": "2026-03-08T00:00:00Z"},
                    {"price": "81.0", "created_at": "2026-03-09T00:00:00Z"},
                    {"price": "82.0", "created_at": "2026-03-10T00:00:00Z"},
                ]
            }
        }

        class MockResponse:
            def raise_for_status(self): pass
            def json(self): return mock_json

        class MockClient:
            def __init__(self, **kw): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def get(self, *a, **kw): return MockResponse()

        monkeypatch.setattr("watchers.data_providers.oilpriceapi_provider.httpx.Client", MockClient)

        result = provider.fetch_history("BZ=F", periods=3)
        assert len(result) == 3
        assert result[-1]["close"] == 82.0

    def test_fetch_history_lgo_empty(self):
        provider = OilPriceAPIProvider(api_key="test-key")
        result = provider.fetch_history("LGO")
        assert result == []


# ======================================================================
# get_provider factory tests
# ======================================================================

class TestGetProvider:
    def test_yfinance_provider(self, monkeypatch):
        monkeypatch.setenv("DATA_PROVIDER", "yfinance")
        import src.config.settings as settings_mod
        settings_mod._settings = None

        from src.watchers.data_providers import get_provider
        provider = get_provider("yfinance")
        assert isinstance(provider, DataProviderProtocol)
        assert type(provider).__name__ == "YFinanceProvider"
        settings_mod._settings = None

    def test_oilpriceapi_provider(self, monkeypatch):
        monkeypatch.setenv("OILPRICEAPI_KEY", "test-key-123")
        import src.config.settings as settings_mod
        settings_mod._settings = None

        from src.watchers.data_providers import get_provider
        provider = get_provider("oilpriceapi")
        assert isinstance(provider, DataProviderProtocol)
        assert type(provider).__name__ == "OilPriceAPIProvider"
        settings_mod._settings = None

    def test_unknown_provider_raises(self):
        from src.watchers.data_providers import get_provider
        with pytest.raises(ValueError, match="Unknown data provider"):
            get_provider("nonexistent")
