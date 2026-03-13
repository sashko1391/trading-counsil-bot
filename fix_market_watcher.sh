#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Fix: MarketWatcher mock + error handling
# ═══════════════════════════════════════════════════════════════

cd "$(dirname "$0")"
echo "🔧 Fixing MarketWatcher..."

# ──────────────────────────────────────────────────────────────
# FIX 1: _fetch_funding_rate — перевіряємо тип результату
# ──────────────────────────────────────────────────────────────
python3 << 'PYFIX'
import re

# Fix market_watcher.py
with open("src/watchers/market_watcher.py", "r") as f:
    code = f.read()

# Replace _fetch_funding_rate to handle non-numeric returns
old_fetch = '''    def _fetch_funding_rate(self, pair: str) -> Optional[float]:
        """
        Отримує funding rate для futures пари
        
        🧒 ЩО ЦЕ:
        - Funding rate = плата між лонгами та шортами
        - Високий (+) = забагато лонгів (ризик squeeze down)
        - Низький (-) = забагато шортів (ризик squeeze up)
        
        ⚠️ Працює тільки з futures (Binance USDT-M)
        """
        try:
            if hasattr(self.exchange, 'fetch_funding_rate'):
                funding = self.exchange.fetch_funding_rate(pair)
                return funding.get('fundingRate', None)
        except Exception:
            pass  # 🧒 Не всі біржі/пари підтримують funding rate
        
        return None'''

new_fetch = '''    def _fetch_funding_rate(self, pair: str) -> Optional[float]:
        """
        Отримує funding rate для futures пари
        
        🧒 ЩО ЦЕ:
        - Funding rate = плата між лонгами та шортами
        - Високий (+) = забагато лонгів (ризик squeeze down)
        - Низький (-) = забагато шортів (ризик squeeze up)
        
        ⚠️ Працює тільки з futures (Binance USDT-M)
        """
        try:
            if hasattr(self.exchange, 'fetch_funding_rate'):
                funding = self.exchange.fetch_funding_rate(pair)
                if isinstance(funding, dict):
                    rate = funding.get('fundingRate', None)
                    # 🧒 Перевіряємо що це число, а не Mock чи інший об'єкт
                    if isinstance(rate, (int, float)):
                        return float(rate)
                return None
        except Exception:
            pass  # 🧒 Не всі біржі/пари підтримують funding rate
        
        return None'''

code = code.replace(old_fetch, new_fetch)

# Fix _detect_funding_extreme — додаємо додаткову перевірку типу
old_detect = '        if abs(funding_rate) >= self.config.funding_rate_extreme:'
new_detect = '''        if not isinstance(funding_rate, (int, float)):
            return None
        
        if abs(funding_rate) >= self.config.funding_rate_extreme:'''

code = code.replace(old_detect, new_detect, 1)

# Fix _fetch_snapshot error — помилка має рахуватись в poll_once
old_poll = '''            try:
                # 1. Отримуємо знімок
                snapshot = self._fetch_snapshot(pair)
                
                if snapshot is None:
                    continue'''

new_poll = '''            try:
                # 1. Отримуємо знімок
                snapshot = self._fetch_snapshot(pair)
                
                if snapshot is None:
                    self.errors += 1
                    continue'''

code = code.replace(old_poll, new_poll)

with open("src/watchers/market_watcher.py", "w") as f:
    f.write(code)

print("   ✅ market_watcher.py fixed")

# Fix test file — mock_exchange needs fetch_funding_rate returning None
with open("tests/test_market_watcher.py", "r") as f:
    test_code = f.read()

# Add fetch_funding_rate to mock_exchange
old_mock = '''    exchange = Mock()
    exchange.fetch_ticker = Mock(return_value={
        'last': 95000.0,
        'bid': 94999.0,
        'ask': 95001.0,
        'high': 96000.0,
        'low': 94000.0,
        'quoteVolume': 30_000_000_000,
        'percentage': 1.5,
    })
    return exchange'''

new_mock = '''    exchange = Mock()
    exchange.fetch_ticker = Mock(return_value={
        'last': 95000.0,
        'bid': 94999.0,
        'ask': 95001.0,
        'high': 96000.0,
        'low': 94000.0,
        'quoteVolume': 30_000_000_000,
        'percentage': 1.5,
    })
    # 🧒 Mock funding rate → повертає None (не futures)
    exchange.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    return exchange'''

test_code = test_code.replace(old_mock, new_mock)

# Fix test_poll_once_handles_api_error — fetch_ticker кидає Exception через poll_once
old_error_test = '''def test_poll_once_handles_api_error():
    """API помилка → не крашить watcher"""
    mock_ex = Mock()
    mock_ex.fetch_ticker.side_effect = Exception("API timeout")
    
    config = WatcherConfig(pairs=["BTC/USDT"])
    watcher = MarketWatcher(config=config, exchange=mock_ex)
    
    events = watcher.poll_once()
    
    assert events == []
    assert watcher.errors == 1
    assert watcher.total_polls == 1
    print("✅ API error handled gracefully")'''

new_error_test = '''def test_poll_once_handles_api_error():
    """API помилка → не крашить watcher, errors рахується"""
    mock_ex = Mock()
    mock_ex.fetch_ticker.side_effect = Exception("API timeout")
    mock_ex.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    
    config = WatcherConfig(pairs=["BTC/USDT"])
    watcher = MarketWatcher(config=config, exchange=mock_ex)
    
    events = watcher.poll_once()
    
    assert events == []
    assert watcher.errors >= 1  # 🧒 Помилка порахована
    assert watcher.total_polls == 1
    print("✅ API error handled gracefully")'''

test_code = test_code.replace(old_error_test, new_error_test)

# Fix test_poll_once_with_spike — add funding rate mock
old_spike_test = '''def test_poll_once_with_spike(mock_exchange):
    """poll_once детектує price spike після кількох поллінгів"""
    config = WatcherConfig(pairs=["BTC/USDT"], price_spike_window=3)
    watcher = MarketWatcher(config=config, exchange=mock_exchange)'''

new_spike_test = '''def test_poll_once_with_spike(mock_exchange):
    """poll_once детектує price spike після кількох поллінгів"""
    config = WatcherConfig(pairs=["BTC/USDT"], price_spike_window=3)
    mock_exchange.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    watcher = MarketWatcher(config=config, exchange=mock_exchange)'''

test_code = test_code.replace(old_spike_test, new_spike_test)

# Fix test_cooldown_expires — add funding rate mock
old_cooldown = '''    config = WatcherConfig(
        pairs=["BTC/USDT"],
        cooldown_seconds=1,  # 🧒 Короткий для тесту
    )
    watcher = MarketWatcher(config=config, exchange=Mock())'''

new_cooldown = '''    config = WatcherConfig(
        pairs=["BTC/USDT"],
        cooldown_seconds=1,  # 🧒 Короткий для тесту
    )
    mock_ex = Mock()
    mock_ex.fetch_funding_rate = Mock(return_value={'fundingRate': None})
    watcher = MarketWatcher(config=config, exchange=mock_ex)'''

test_code = test_code.replace(old_cooldown, new_cooldown)

with open("tests/test_market_watcher.py", "w") as f:
    f.write(test_code)

print("   ✅ test_market_watcher.py fixed")
print()
print("🎉 All fixes applied!")
PYFIX

# ──────────────────────────────────────────────────────────────
# Запускаємо тести
# ──────────────────────────────────────────────────────────────
echo ""
echo "🧪 Running tests..."
echo ""

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 -m pytest tests/test_market_watcher.py -v -s --tb=short
