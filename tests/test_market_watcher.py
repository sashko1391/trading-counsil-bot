"""
Tests for MarketWatcher (legacy watcher) WITHOUT real API

Tests:
1. Creation
2. Price spike detection (UP + DOWN)
3. Volume surge detection
4. Spread change detection (was funding_extreme)
5. Cooldown (anti-spam)
6. poll_once with mock exchange
7. Edge cases (zeros, empty data)

Works WITHOUT Binance API - uses mock objects.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from watchers.market_watcher import (
    MarketWatcher,
    MarketSnapshot,
    WatcherConfig,
)
from models.schemas import MarketEvent


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def config():
    """Test configuration"""
    return WatcherConfig(
        pairs=["BZ=F"],
        poll_interval=30,
        price_spike_pct=2.0,
        price_spike_window=10,
        volume_surge_ratio=2.0,
        volume_window=20,
        funding_rate_extreme=0.001,
        cooldown_seconds=300,
    )


@pytest.fixture
def mock_exchange():
    """
    Fake exchange (mock)
    - No need for real exchange
    - Can control responses
    - Tests work offline
    """
    exchange = Mock()
    exchange.fetch_ticker = Mock(return_value={
        'last': 82.50,
        'bid': 82.49,
        'ask': 82.51,
        'high': 84.00,
        'low': 81.00,
        'quoteVolume': 300_000,
        'percentage': 1.5,
    })
    exchange.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    return exchange


@pytest.fixture
def watcher(config, mock_exchange):
    """Creates MarketWatcher with mock exchange"""
    return MarketWatcher(config=config, exchange=mock_exchange)


def make_snapshot(pair="BZ=F", price=82.50, volume=300_000, **kwargs):
    """Helper for creating snapshots"""
    defaults = {
        "timestamp": datetime.now(),
        "pair": pair,
        "price": price,
        "volume_24h": volume,
        "high_24h": price * 1.01,
        "low_24h": price * 0.99,
        "change_24h_pct": 1.0,
        "bid": price - 0.01,
        "ask": price + 0.01,
        "spread_pct": 0.002,
    }
    defaults.update(kwargs)
    return MarketSnapshot(**defaults)


# ==============================================================================
# TEST 1: Creation
# ==============================================================================

def test_watcher_creation(watcher):
    """Test MarketWatcher creation"""
    assert watcher is not None
    assert len(watcher.config.pairs) == 1
    assert watcher.config.pairs[0] == "BZ=F"
    assert watcher.total_polls == 0
    assert watcher.total_events == 0
    assert watcher.errors == 0


def test_watcher_default_config():
    """Test default configuration"""
    config = WatcherConfig()
    assert len(config.pairs) > 0
    assert config.poll_interval == 30
    assert config.price_spike_pct == 2.0
    assert config.volume_surge_ratio == 2.0


# ==============================================================================
# TEST 2: Price Spike Detection
# ==============================================================================

def test_price_spike_up(watcher):
    """
    Scenario:
    - 10 snapshots at $82.50
    - Price jumps to $84.98 (+3%)
    - Expected: price_spike event with direction=UP
    """
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=84.98)
    events = watcher._check_anomalies("BZ=F", current)

    assert len(events) >= 1
    spike = events[0]
    assert spike.event_type == "price_spike"
    assert spike.data["direction"] == "UP"
    assert spike.data["price_change_pct"] == pytest.approx(3.0, abs=0.1)
    assert spike.severity > 0


def test_price_spike_down(watcher):
    """
    Scenario:
    - 10 snapshots at $82.50
    - Price drops to $80.03 (-3%)
    - Expected: price_spike with direction=DOWN
    """
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=80.03)
    events = watcher._check_anomalies("BZ=F", current)

    assert len(events) >= 1
    spike = events[0]
    assert spike.event_type == "price_spike"
    assert spike.data["direction"] == "DOWN"
    assert spike.data["price_change_pct"] == pytest.approx(-3.0, abs=0.1)


def test_no_spike_below_threshold(watcher):
    """1% change - below 2% threshold -> no event"""
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=83.33)  # ~+1%
    events = watcher._check_anomalies("BZ=F", current)

    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) == 0


# ==============================================================================
# TEST 3: Volume Surge Detection
# ==============================================================================

def test_volume_surge(watcher):
    """
    Scenario:
    - 20 snapshots with volume 100k
    - Volume jumps to 300k (3x)
    - Expected: volume_surge event
    """
    for _ in range(20):
        watcher._history["BZ=F"].append(make_snapshot(volume=100_000))

    current = make_snapshot(volume=300_000)
    events = watcher._check_anomalies("BZ=F", current)

    volume_events = [e for e in events if e.event_type == "volume_surge"]
    assert len(volume_events) >= 1

    surge = volume_events[0]
    assert surge.data["volume_ratio"] == pytest.approx(3.0, abs=0.1)


def test_no_volume_surge_below_threshold(watcher):
    """Volume 1.5x - below 2x threshold -> no event"""
    for _ in range(20):
        watcher._history["BZ=F"].append(make_snapshot(volume=100_000))

    current = make_snapshot(volume=150_000)  # 1.5x
    events = watcher._check_anomalies("BZ=F", current)

    volume_events = [e for e in events if e.event_type == "volume_surge"]
    assert len(volume_events) == 0


# ==============================================================================
# TEST 4: Spread Change Detection (was funding_extreme)
# ==============================================================================

def test_spread_change_detection(watcher):
    """Funding rate 0.2% -> spread_change event"""
    watcher._fetch_funding_rate = Mock(return_value=0.002)
    watcher._history["BZ=F"].append(make_snapshot())

    current = make_snapshot()
    events = watcher._check_anomalies("BZ=F", current)

    spread_events = [e for e in events if e.event_type == "spread_change"]
    assert len(spread_events) >= 1

    se = spread_events[0]
    assert se.data["bias"] == "LONG_HEAVY"
    assert se.data["funding_rate"] == 0.002


def test_negative_spread_change(watcher):
    """Negative funding rate -> SHORT_HEAVY"""
    watcher._fetch_funding_rate = Mock(return_value=-0.0015)
    watcher._history["BZ=F"].append(make_snapshot())

    current = make_snapshot()
    events = watcher._check_anomalies("BZ=F", current)

    spread_events = [e for e in events if e.event_type == "spread_change"]
    assert len(spread_events) >= 1
    assert spread_events[0].data["bias"] == "SHORT_HEAVY"


def test_normal_funding_rate(watcher):
    """Normal funding rate 0.05% -> no event"""
    watcher._fetch_funding_rate = Mock(return_value=0.0005)
    watcher._history["BZ=F"].append(make_snapshot())

    current = make_snapshot()
    events = watcher._check_anomalies("BZ=F", current)

    spread_events = [e for e in events if e.event_type == "spread_change"]
    assert len(spread_events) == 0


# ==============================================================================
# TEST 5: Cooldown (anti-spam)
# ==============================================================================

def test_cooldown_prevents_duplicate_events(watcher):
    """First spike -> event. Second spike immediately -> blocked by cooldown"""
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=84.98)
    events1 = watcher._check_anomalies("BZ=F", current)
    assert len(events1) >= 1

    # Second time - cooldown blocks
    events2 = watcher._check_anomalies("BZ=F", current)
    price_spikes = [e for e in events2 if e.event_type == "price_spike"]
    assert len(price_spikes) == 0


def test_cooldown_expires():
    """Cooldown 1 second -> after pause allows new event"""
    config = WatcherConfig(
        pairs=["BZ=F"],
        cooldown_seconds=1,
    )
    mock_ex = Mock()
    mock_ex.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    watcher = MarketWatcher(config=config, exchange=mock_ex)

    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=84.98)
    events1 = watcher._check_anomalies("BZ=F", current)
    assert len(events1) >= 1

    import time
    time.sleep(1.5)

    events2 = watcher._check_anomalies("BZ=F", current)
    price_spikes = [e for e in events2 if e.event_type == "price_spike"]
    assert len(price_spikes) >= 1


# ==============================================================================
# TEST 6: poll_once with mock exchange
# ==============================================================================

def test_poll_once_normal(watcher, mock_exchange):
    """poll_once fetches data and stores in history"""
    events = watcher.poll_once()

    assert watcher.total_polls == 1
    assert mock_exchange.fetch_ticker.called
    assert len(watcher._history["BZ=F"]) == 1


def test_poll_once_with_spike(mock_exchange):
    """poll_once detects price spike after several polls"""
    config = WatcherConfig(pairs=["BZ=F"], price_spike_window=3)
    mock_exchange.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    watcher = MarketWatcher(config=config, exchange=mock_exchange)

    # 3 polls with stable price
    mock_exchange.fetch_ticker.return_value = {
        'last': 82.50, 'bid': 82.49, 'ask': 82.51,
        'high': 84.0, 'low': 81.0,
        'quoteVolume': 300_000, 'percentage': 1.0,
    }
    for _ in range(3):
        watcher.poll_once()

    # 4th poll: price +5%
    mock_exchange.fetch_ticker.return_value = {
        'last': 86.63, 'bid': 86.62, 'ask': 86.64,
        'high': 87.0, 'low': 81.0,
        'quoteVolume': 300_000, 'percentage': 5.0,
    }
    events = watcher.poll_once()

    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) >= 1
    assert price_spikes[0].data["direction"] == "UP"


def test_poll_once_handles_api_error():
    """API error -> doesn't crash watcher, errors counted"""
    mock_ex = Mock()
    mock_ex.fetch_ticker.side_effect = Exception("API timeout")
    mock_ex.fetch_funding_rate = Mock(return_value={'fundingRate': None})

    config = WatcherConfig(pairs=["BZ=F"])
    watcher = MarketWatcher(config=config, exchange=mock_ex)

    events = watcher.poll_once()

    assert events == []
    assert watcher.errors >= 1
    assert watcher.total_polls == 1


# ==============================================================================
# TEST 7: Edge Cases
# ==============================================================================

def test_not_enough_history(watcher):
    """Not enough history -> no events generated"""
    watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    current = make_snapshot(price=90.0)  # +9%!
    events = watcher._check_anomalies("BZ=F", current)

    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) == 0


def test_zero_price_no_crash(watcher):
    """Price = 0 -> no crash (divide by zero)"""
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=0.0))

    current = make_snapshot(price=82.50)
    events = watcher._check_anomalies("BZ=F", current)
    # Just verify no exception


def test_multiple_instruments():
    """Monitoring 3 instruments simultaneously"""
    config = WatcherConfig(pairs=["BZ=F", "LGO", "CL=F"])
    mock_ex = Mock()
    mock_ex.fetch_ticker.return_value = {
        'last': 82.50, 'bid': 82.49, 'ask': 82.51,
        'high': 84.0, 'low': 81.0,
        'quoteVolume': 300_000, 'percentage': 1.0,
    }

    watcher = MarketWatcher(config=config, exchange=mock_ex)
    events = watcher.poll_once()

    assert mock_ex.fetch_ticker.call_count == 3
    assert len(watcher._history["BZ=F"]) == 1
    assert len(watcher._history["LGO"]) == 1
    assert len(watcher._history["CL=F"]) == 1


def test_get_stats(watcher, mock_exchange):
    """Stats work correctly"""
    watcher.poll_once()
    watcher.poll_once()

    stats = watcher.get_stats()
    assert stats["total_polls"] == 2
    assert stats["pairs_monitored"] == 1
    assert "BZ=F" in stats["history_sizes"]


def test_severity_scaling(watcher):
    """Severity scales: small spike -> lower severity"""
    for _ in range(10):
        watcher._history["BZ=F"].append(make_snapshot(price=82.50))

    # 2.5% spike
    current_small = make_snapshot(price=84.56)
    events_small = watcher._check_anomalies("BZ=F", current_small)

    if events_small:
        severity_small = events_small[0].severity
        watcher._last_event.clear()  # Reset cooldown

        # 8% spike
        current_big = make_snapshot(price=89.10)
        events_big = watcher._check_anomalies("BZ=F", current_big)

        if events_big:
            severity_big = events_big[0].severity
            assert severity_big > severity_small


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
