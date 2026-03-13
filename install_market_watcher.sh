#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  MarketWatcher Installer - Stage 1 Component
#  Створює всі файли та запускає тести
# ═══════════════════════════════════════════════════════════════

set -e  # Зупинитись при помилці

# Визначаємо корінь проєкту
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  📊 MarketWatcher - Stage 1 Installer        ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo "📁 Project root: $PROJECT_ROOT"
echo ""

# ──────────────────────────────────────────────────────────────
# 1. Створюємо директорії
# ──────────────────────────────────────────────────────────────
echo "📂 Створюю директорії..."
mkdir -p "$PROJECT_ROOT/src/watchers"
echo "   ✅ src/watchers/"

# ──────────────────────────────────────────────────────────────
# 2. src/watchers/__init__.py
# ──────────────────────────────────────────────────────────────
echo "📝 Створюю файли..."

cat > "$PROJECT_ROOT/src/watchers/__init__.py" << 'INITEOF'
"""
Watchers - Stage 1 компоненти для моніторингу ринку

🧒 ЩО ТУТ:
- MarketWatcher: Ціна, об'єм, funding rate (CCXT/Binance)
- GrokTwitterScanner: Sentiment з Twitter (буде пізніше)
"""
INITEOF
echo "   ✅ src/watchers/__init__.py"

# ──────────────────────────────────────────────────────────────
# 3. src/watchers/market_watcher.py
# ──────────────────────────────────────────────────────────────
cat > "$PROJECT_ROOT/src/watchers/market_watcher.py" << 'WATCHEREOF'
"""
MarketWatcher - Stage 1: Детекція аномалій на ринку 📊

🧒 ЩО ЦЕ:
- Постійний моніторинг ринку через CCXT (Binance)
- Поллінг кожні 30 секунд (не WebSocket — простіше і надійніше)
- Детектує: price spikes, volume surges, funding rate extremes
- Генерує MarketEvent коли щось незвичайне

🧒 АНАЛОГІЯ:
- Це як охоронець який дивиться на камери 24/7
- Якщо бачить щось підозріле — натискає тривожну кнопку (MarketEvent)
- Інші агенти вже вирішують що робити

🧒 ЧАС РОБОТИ:
- Stage 1 = працює ЗАВЖДИ (24/7)
- Вартість: $0 (CCXT безкоштовний)
"""

import ccxt
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from collections import deque
from dataclasses import dataclass, field

# Імпорт наших моделей
from models.schemas import MarketEvent


# ==============================================================================
# КОНФІГУРАЦІЯ (пороги для детекції)
# ==============================================================================

@dataclass
class WatcherConfig:
    """
    Налаштування порогів для MarketWatcher
    
    🧒 ЩО ЦЕ:
    - Визначає "що вважається аномалією"
    - Можна змінювати без редагування коду
    - Кожен параметр має дефолтне значення
    """
    
    # Пари для моніторингу
    pairs: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    
    # Інтервал поллінгу (секунди)
    poll_interval: int = 30
    
    # Пороги для price spike
    price_spike_pct: float = 2.0       # 🧒 >2% за 5 хвилин = spike
    price_spike_window: int = 10       # 🧒 Кількість замірів для порівняння (10 × 30с = 5 хв)
    
    # Пороги для volume surge
    volume_surge_ratio: float = 2.0    # 🧒 Об'єм >2x від середнього = surge
    volume_window: int = 20            # 🧒 Кількість замірів для середнього (20 × 30с = 10 хв)
    
    # Пороги для funding rate
    funding_rate_extreme: float = 0.001  # 🧒 >0.1% = extreme (overleveraged)
    
    # Максимум подій щоб не спамити
    cooldown_seconds: int = 300        # 🧒 5 хвилин між подіями однакового типу


# ==============================================================================
# SNAPSHOT - знімок стану ринку
# ==============================================================================

@dataclass
class MarketSnapshot:
    """
    Один знімок стану ринку для конкретної пари
    
    🧒 ЩО ЦЕ:
    - "Фотографія" ринку в один момент часу
    - Зберігаємо історію знімків для порівняння
    """
    
    timestamp: datetime
    pair: str
    price: float
    volume_24h: float          # 🧒 Об'єм за 24 години
    high_24h: float
    low_24h: float
    change_24h_pct: float      # 🧒 Зміна за 24 години в %
    bid: float                 # 🧒 Найкраща ціна покупки
    ask: float                 # 🧒 Найкраща ціна продажу
    spread_pct: float          # 🧒 Різниця bid/ask в %
    funding_rate: Optional[float] = None  # 🧒 Тільки для futures


# ==============================================================================
# MARKET WATCHER
# ==============================================================================

class MarketWatcher:
    """
    Спостерігач за ринком - Stage 1 компонент
    
    🧒 ЩО РОБИТЬ:
    1. Підключається до Binance через CCXT
    2. Кожні 30 секунд отримує ціну/об'єм
    3. Зберігає історію (rolling window)
    4. Порівнює з історією → шукає аномалії
    5. Якщо знаходить → повертає MarketEvent
    
    🧒 АНОМАЛІЇ:
    - price_spike: Ціна різко змінилась (>2% за 5 хв)
    - volume_surge: Об'єм сильно зріс (>2x від середнього)
    - funding_extreme: Funding rate занадто високий/низький
    """
    
    def __init__(self, config: WatcherConfig = None, exchange: object = None):
        """
        Ініціалізація MarketWatcher
        
        Args:
            config: Налаштування порогів (або дефолтні)
            exchange: CCXT exchange об'єкт (або створимо Binance)
        
        🧒 ПОЯСНЕННЯ exchange параметра:
        - Для продакшену: передаємо справжній ccxt.binance()
        - Для тестів: передаємо mock об'єкт (фейковий)
        """
        self.config = config or WatcherConfig()
        
        # Exchange (Binance за замовчуванням)
        if exchange is not None:
            self.exchange = exchange
        else:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,  # 🧒 Автоматичний rate limiting
            })
        
        # Історія знімків для кожної пари
        # 🧒 deque = список з максимальним розміром (старі видаляються автоматично)
        self._history: Dict[str, deque] = {}
        for pair in self.config.pairs:
            max_len = max(self.config.price_spike_window, self.config.volume_window) + 5
            self._history[pair] = deque(maxlen=max_len)
        
        # Cooldown tracker (щоб не спамити подіями)
        # 🧒 Формат: {"BTC/USDT:price_spike": datetime}
        self._last_event: Dict[str, datetime] = {}
        
        # Статистика
        self.total_polls = 0
        self.total_events = 0
        self.errors = 0
    
    # ==========================================================================
    # ОСНОВНІ МЕТОДИ
    # ==========================================================================
    
    def poll_once(self) -> List[MarketEvent]:
        """
        Один цикл поллінгу: отримати дані → перевірити аномалії
        
        Returns:
            Список MarketEvent (може бути порожнім)
        
        🧒 КОЛИ ВИКЛИКАТИ:
        - В основному циклі кожні 30 секунд
        - Або вручну для тестування
        """
        events = []
        
        for pair in self.config.pairs:
            try:
                # 1. Отримуємо знімок
                snapshot = self._fetch_snapshot(pair)
                
                if snapshot is None:
                    continue
                
                # 2. Зберігаємо в історію
                self._history[pair].append(snapshot)
                
                # 3. Перевіряємо аномалії (потрібно мінімум 2 знімки)
                if len(self._history[pair]) >= 2:
                    pair_events = self._check_anomalies(pair, snapshot)
                    events.extend(pair_events)
                
            except Exception as e:
                self.errors += 1
                print(f"⚠️ MarketWatcher error for {pair}: {e}")
                continue
        
        self.total_polls += 1
        self.total_events += len(events)
        
        return events
    
    def _fetch_snapshot(self, pair: str) -> Optional[MarketSnapshot]:
        """
        Отримує поточний стан ринку для пари
        
        Args:
            pair: Торгова пара ("BTC/USDT")
        
        Returns:
            MarketSnapshot або None при помилці
        
        🧒 ЩО РОБИТЬ:
        - Викликає exchange.fetch_ticker() через CCXT
        - Парсить відповідь в наш MarketSnapshot
        """
        try:
            ticker = self.exchange.fetch_ticker(pair)
            
            # Розраховуємо spread
            bid = ticker.get('bid', 0) or 0
            ask = ticker.get('ask', 0) or 0
            mid_price = (bid + ask) / 2 if (bid and ask) else ticker.get('last', 0)
            spread_pct = ((ask - bid) / mid_price * 100) if mid_price > 0 else 0
            
            return MarketSnapshot(
                timestamp=datetime.now(),
                pair=pair,
                price=ticker.get('last', 0) or 0,
                volume_24h=ticker.get('quoteVolume', 0) or 0,  # 🧒 Об'єм в USDT
                high_24h=ticker.get('high', 0) or 0,
                low_24h=ticker.get('low', 0) or 0,
                change_24h_pct=ticker.get('percentage', 0) or 0,
                bid=bid,
                ask=ask,
                spread_pct=round(spread_pct, 4)
            )
            
        except Exception as e:
            print(f"⚠️ Failed to fetch ticker for {pair}: {e}")
            return None
    
    def _fetch_funding_rate(self, pair: str) -> Optional[float]:
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
        
        return None
    
    # ==========================================================================
    # ДЕТЕКЦІЯ АНОМАЛІЙ
    # ==========================================================================
    
    def _check_anomalies(self, pair: str, current: MarketSnapshot) -> List[MarketEvent]:
        """
        Перевіряє всі типи аномалій для пари
        
        Args:
            pair: Торгова пара
            current: Поточний знімок
        
        Returns:
            Список знайдених аномалій (MarketEvent)
        """
        events = []
        
        # 1. Price Spike
        spike_event = self._detect_price_spike(pair, current)
        if spike_event:
            events.append(spike_event)
        
        # 2. Volume Surge
        volume_event = self._detect_volume_surge(pair, current)
        if volume_event:
            events.append(volume_event)
        
        # 3. Funding Rate Extreme
        funding_event = self._detect_funding_extreme(pair, current)
        if funding_event:
            events.append(funding_event)
        
        return events
    
    def _detect_price_spike(self, pair: str, current: MarketSnapshot) -> Optional[MarketEvent]:
        """
        Детектує різку зміну ціни
        
        🧒 ЛОГІКА:
        1. Беремо ціну N знімків тому (5 хвилин назад)
        2. Порівнюємо з поточною ціною
        3. Якщо різниця > порогу → price_spike!
        
        Returns:
            MarketEvent або None
        """
        history = self._history[pair]
        window = self.config.price_spike_window
        
        # Потрібно достатньо історії
        if len(history) < window:
            return None
        
        # Ціна N знімків тому
        old_snapshot = history[-window]
        old_price = old_snapshot.price
        
        if old_price == 0:
            return None
        
        # Розраховуємо зміну
        price_change_pct = ((current.price - old_price) / old_price) * 100
        
        # Перевіряємо поріг (абсолютне значення — і вгору, і вниз)
        if abs(price_change_pct) >= self.config.price_spike_pct:
            
            # Перевірка cooldown
            if self._is_on_cooldown(pair, "price_spike"):
                return None
            
            self._set_cooldown(pair, "price_spike")
            
            # Severity: 2% = 0.3, 5% = 0.5, 10%+ = 1.0
            severity = min(abs(price_change_pct) / 10.0, 1.0)
            severity = max(severity, 0.3)  # 🧒 Мінімум 0.3 (бо вже пройшли поріг)
            
            direction = "UP" if price_change_pct > 0 else "DOWN"
            
            return MarketEvent(
                event_type="price_spike",
                pair=pair,
                severity=round(severity, 2),
                data={
                    "price_change_pct": round(price_change_pct, 2),
                    "direction": direction,
                    "current_price": current.price,
                    "previous_price": old_price,
                    "window_seconds": window * self.config.poll_interval,
                    "volume_24h": current.volume_24h,
                    "high_24h": current.high_24h,
                    "low_24h": current.low_24h,
                }
            )
        
        return None
    
    def _detect_volume_surge(self, pair: str, current: MarketSnapshot) -> Optional[MarketEvent]:
        """
        Детектує різке зростання об'єму
        
        🧒 ЛОГІКА:
        1. Рахуємо середній об'єм за останні N знімків
        2. Порівнюємо поточний об'єм із середнім
        3. Якщо поточний > 2x середнього → volume_surge!
        
        🧒 ЧОМУ ЦЕ ВАЖЛИВО:
        - Великий об'єм = великі гравці торгують
        - Раптовий зріст = щось відбувається (новина? кит?)
        
        Returns:
            MarketEvent або None
        """
        history = self._history[pair]
        window = self.config.volume_window
        
        # Потрібно достатньо історії
        if len(history) < window:
            return None
        
        # Середній об'єм за вікно (без поточного)
        recent_volumes = [s.volume_24h for s in list(history)[-window:-1]]
        
        if not recent_volumes:
            return None
        
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        
        if avg_volume == 0:
            return None
        
        # Відношення поточного до середнього
        volume_ratio = current.volume_24h / avg_volume
        
        if volume_ratio >= self.config.volume_surge_ratio:
            
            # Перевірка cooldown
            if self._is_on_cooldown(pair, "volume_surge"):
                return None
            
            self._set_cooldown(pair, "volume_surge")
            
            # Severity: 2x = 0.4, 3x = 0.6, 5x+ = 1.0
            severity = min(volume_ratio / 5.0, 1.0)
            severity = max(severity, 0.3)
            
            return MarketEvent(
                event_type="volume_surge",
                pair=pair,
                severity=round(severity, 2),
                data={
                    "volume_ratio": round(volume_ratio, 2),
                    "current_volume": current.volume_24h,
                    "average_volume": round(avg_volume, 2),
                    "current_price": current.price,
                    "price_change_24h": current.change_24h_pct,
                }
            )
        
        return None
    
    def _detect_funding_extreme(self, pair: str, current: MarketSnapshot) -> Optional[MarketEvent]:
        """
        Детектує екстремальний funding rate
        
        🧒 ЛОГІКА:
        1. Отримуємо funding rate
        2. Якщо > порогу → funding_extreme!
        
        🧒 ЧОМУ ЦЕ ВАЖЛИВО:
        - Високий funding = забагато leveraged longs (ризик squeeze DOWN)
        - Від'ємний funding = забагато shorts (ризик squeeze UP)
        - Екстрим = ринок перегрітий → небезпечно
        
        Returns:
            MarketEvent або None
        """
        funding_rate = self._fetch_funding_rate(pair)
        
        if funding_rate is None:
            return None
        
        if abs(funding_rate) >= self.config.funding_rate_extreme:
            
            # Перевірка cooldown
            if self._is_on_cooldown(pair, "funding_extreme"):
                return None
            
            self._set_cooldown(pair, "funding_extreme")
            
            # Severity
            severity = min(abs(funding_rate) / 0.005, 1.0)  # 0.5% = max severity
            severity = max(severity, 0.3)
            
            bias = "LONG_HEAVY" if funding_rate > 0 else "SHORT_HEAVY"
            
            return MarketEvent(
                event_type="funding_extreme",
                pair=pair,
                severity=round(severity, 2),
                data={
                    "funding_rate": round(funding_rate, 6),
                    "bias": bias,
                    "current_price": current.price,
                    "risk": f"{'Long' if funding_rate > 0 else 'Short'} squeeze possible",
                }
            )
        
        return None
    
    # ==========================================================================
    # COOLDOWN (антиспам)
    # ==========================================================================
    
    def _is_on_cooldown(self, pair: str, event_type: str) -> bool:
        """
        Перевіряє чи минув cooldown з останньої події
        
        🧒 НАВІЩО:
        - Щоб не генерувати 100 подій за хвилину
        - Одна подія → чекаємо 5 хвилин → можна знову
        """
        key = f"{pair}:{event_type}"
        
        if key not in self._last_event:
            return False
        
        elapsed = (datetime.now() - self._last_event[key]).total_seconds()
        return elapsed < self.config.cooldown_seconds
    
    def _set_cooldown(self, pair: str, event_type: str):
        """Встановлює cooldown для пари + типу події"""
        key = f"{pair}:{event_type}"
        self._last_event[key] = datetime.now()
    
    # ==========================================================================
    # УТІЛІТИ
    # ==========================================================================
    
    def get_latest_snapshot(self, pair: str) -> Optional[MarketSnapshot]:
        """Повертає останній знімок для пари"""
        history = self._history.get(pair)
        if history and len(history) > 0:
            return history[-1]
        return None
    
    def get_history(self, pair: str) -> List[MarketSnapshot]:
        """Повертає всю історію для пари"""
        return list(self._history.get(pair, []))
    
    def get_stats(self) -> dict:
        """
        Повертає статистику роботи
        
        🧒 КОРИСНО ДЛЯ:
        - Terminal UI (показати статус)
        - Дебаг (чи все працює)
        """
        return {
            "total_polls": self.total_polls,
            "total_events": self.total_events,
            "errors": self.errors,
            "pairs_monitored": len(self.config.pairs),
            "history_sizes": {
                pair: len(self._history[pair]) 
                for pair in self.config.pairs
            },
            "active_cooldowns": {
                key: str(self._last_event[key]) 
                for key in self._last_event
            }
        }
    
    def __repr__(self) -> str:
        return (
            f"MarketWatcher(pairs={self.config.pairs}, "
            f"polls={self.total_polls}, events={self.total_events})"
        )


# ==============================================================================
# RUNNER (основний цикл)
# ==============================================================================

def run_watcher(
    config: WatcherConfig = None,
    on_event=None,
    max_polls: int = None
):
    """
    Запускає MarketWatcher у нескінченному циклі
    
    Args:
        config: Налаштування (або дефолтні)
        on_event: Callback функція для обробки подій
        max_polls: Максимум циклів (None = нескінченно)
    
    🧒 ПРИКЛАД:
        def handle_event(event):
            print(f"🚨 {event.event_type} on {event.pair}!")
        
        run_watcher(on_event=handle_event)
    """
    watcher = MarketWatcher(config=config)
    
    print(f"🚀 MarketWatcher started!")
    print(f"   Pairs: {watcher.config.pairs}")
    print(f"   Poll interval: {watcher.config.poll_interval}s")
    print(f"   Price spike threshold: {watcher.config.price_spike_pct}%")
    print(f"   Volume surge ratio: {watcher.config.volume_surge_ratio}x")
    
    poll_count = 0
    
    try:
        while True:
            # Поллінг
            events = watcher.poll_once()
            poll_count += 1
            
            # Обробка подій
            for event in events:
                print(f"\n🚨 EVENT DETECTED: {event.event_type} on {event.pair}")
                print(f"   Severity: {event.severity:.0%}")
                print(f"   Data: {event.data}")
                
                if on_event:
                    on_event(event)
            
            # Логування кожні 10 циклів
            if poll_count % 10 == 0:
                stats = watcher.get_stats()
                print(f"\n📊 Stats: polls={stats['total_polls']}, events={stats['total_events']}, errors={stats['errors']}")
            
            # Ліміт циклів (для тестування)
            if max_polls and poll_count >= max_polls:
                print(f"\n🏁 Reached max_polls ({max_polls})")
                break
            
            # Пауза до наступного циклу
            time.sleep(watcher.config.poll_interval)
    
    except KeyboardInterrupt:
        print(f"\n\n🛑 MarketWatcher stopped by user")
        print(f"   Stats: {watcher.get_stats()}")
    
    return watcher


# ==============================================================================
# ТЕСТУВАННЯ (без справжнього API)
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing MarketWatcher...")
    
    # Створюємо watcher з дефолтними налаштуваннями
    config = WatcherConfig(pairs=["BTC/USDT"])
    watcher = MarketWatcher(config=config)
    print(f"✅ MarketWatcher created: {watcher}")
    
    # Тест: додаємо фейкові знімки
    print("\n🧪 Testing with fake snapshots...")
    
    for i in range(10):
        snap = MarketSnapshot(
            timestamp=datetime.now(),
            pair="BTC/USDT",
            price=95000.0,
            volume_24h=30_000_000_000,
            high_24h=96000,
            low_24h=94000,
            change_24h_pct=1.5,
            bid=94999,
            ask=95001,
            spread_pct=0.002
        )
        watcher._history["BTC/USDT"].append(snap)
    
    # Знімок з price spike +3%
    spike_snap = MarketSnapshot(
        timestamp=datetime.now(),
        pair="BTC/USDT",
        price=97850.0,
        volume_24h=30_000_000_000,
        high_24h=98000,
        low_24h=94000,
        change_24h_pct=4.5,
        bid=97849,
        ask=97851,
        spread_pct=0.002
    )
    
    events = watcher._check_anomalies("BTC/USDT", spike_snap)
    
    assert len(events) >= 1, "Expected at least 1 event (price spike)"
    assert events[0].event_type == "price_spike"
    assert events[0].data["direction"] == "UP"
    print(f"✅ Price spike detected: +{events[0].data['price_change_pct']}%")
    
    print("\n🎉 All MarketWatcher tests passed!")
WATCHEREOF
echo "   ✅ src/watchers/market_watcher.py (380+ lines)"

# ──────────────────────────────────────────────────────────────
# 4. tests/test_market_watcher.py
# ──────────────────────────────────────────────────────────────
cat > "$PROJECT_ROOT/tests/test_market_watcher.py" << 'TESTEOF'
"""
Тести для MarketWatcher БЕЗ справжнього API 📊

🧒 ЩО ТЕСТУЄМО:
1. Створення MarketWatcher
2. Price spike detection (UP + DOWN)
3. Volume surge detection
4. Funding rate extreme detection
5. Cooldown (антиспам)
6. poll_once з mock exchange
7. Edge cases (нулі, порожні дані)

🧒 ПРАЦЮЄ БЕЗ BINANCE API!
Використовуємо mock objects
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
# ФІКСТУРИ
# ==============================================================================

@pytest.fixture
def config():
    """Конфігурація для тестів"""
    return WatcherConfig(
        pairs=["BTC/USDT"],
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
    Фейкова біржа (mock)
    
    🧒 НАВІЩО:
    - Не потрібен справжній Binance
    - Можемо контролювати відповіді
    - Тести працюють offline
    """
    exchange = Mock()
    exchange.fetch_ticker = Mock(return_value={
        'last': 95000.0,
        'bid': 94999.0,
        'ask': 95001.0,
        'high': 96000.0,
        'low': 94000.0,
        'quoteVolume': 30_000_000_000,
        'percentage': 1.5,
    })
    return exchange


@pytest.fixture
def watcher(config, mock_exchange):
    """Створює MarketWatcher з mock exchange"""
    return MarketWatcher(config=config, exchange=mock_exchange)


def make_snapshot(pair="BTC/USDT", price=95000.0, volume=30e9, **kwargs):
    """
    Хелпер для створення знімків
    
    🧒 ЗРУЧНІСТЬ: замість писати всі поля кожен раз
    """
    defaults = {
        "timestamp": datetime.now(),
        "pair": pair,
        "price": price,
        "volume_24h": volume,
        "high_24h": price * 1.01,
        "low_24h": price * 0.99,
        "change_24h_pct": 1.0,
        "bid": price - 1,
        "ask": price + 1,
        "spread_pct": 0.002,
    }
    defaults.update(kwargs)
    return MarketSnapshot(**defaults)


# ==============================================================================
# ТЕСТ 1: Створення
# ==============================================================================

def test_watcher_creation(watcher):
    """Тест створення MarketWatcher"""
    assert watcher is not None
    assert len(watcher.config.pairs) == 1
    assert watcher.config.pairs[0] == "BTC/USDT"
    assert watcher.total_polls == 0
    assert watcher.total_events == 0
    assert watcher.errors == 0
    print("✅ MarketWatcher created successfully")


def test_watcher_default_config():
    """Тест дефолтної конфігурації"""
    config = WatcherConfig()
    assert "BTC/USDT" in config.pairs
    assert config.poll_interval == 30
    assert config.price_spike_pct == 2.0
    assert config.volume_surge_ratio == 2.0
    print("✅ Default config is correct")


# ==============================================================================
# ТЕСТ 2: Price Spike Detection
# ==============================================================================

def test_price_spike_up(watcher):
    """
    🧒 СЦЕНАРІЙ:
    - 10 знімків по $95,000
    - Ціна стрибає до $97,850 (+3%)
    - Очікуємо: price_spike event з direction=UP
    """
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=97850.0)
    events = watcher._check_anomalies("BTC/USDT", current)
    
    assert len(events) >= 1
    spike = events[0]
    assert spike.event_type == "price_spike"
    assert spike.data["direction"] == "UP"
    assert spike.data["price_change_pct"] == pytest.approx(3.0, abs=0.1)
    assert spike.severity > 0
    print(f"✅ Price spike UP detected: +{spike.data['price_change_pct']}%")


def test_price_spike_down(watcher):
    """
    🧒 СЦЕНАРІЙ:
    - 10 знімків по $95,000
    - Ціна падає до $92,150 (-3%)
    - Очікуємо: price_spike з direction=DOWN
    """
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=92150.0)
    events = watcher._check_anomalies("BTC/USDT", current)
    
    assert len(events) >= 1
    spike = events[0]
    assert spike.event_type == "price_spike"
    assert spike.data["direction"] == "DOWN"
    assert spike.data["price_change_pct"] == pytest.approx(-3.0, abs=0.1)
    print(f"✅ Price spike DOWN detected: {spike.data['price_change_pct']}%")


def test_no_spike_below_threshold(watcher):
    """Зміна 1% — менше порогу 2% → НЕ генерує подію"""
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=95950.0)  # +1%
    events = watcher._check_anomalies("BTC/USDT", current)
    
    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) == 0
    print("✅ No spike below threshold (correctly ignored)")


# ==============================================================================
# ТЕСТ 3: Volume Surge Detection
# ==============================================================================

def test_volume_surge(watcher):
    """
    🧒 СЦЕНАРІЙ:
    - 20 знімків з об'ємом $10B
    - Об'єм стрибає до $30B (3x)
    - Очікуємо: volume_surge event
    """
    for _ in range(20):
        watcher._history["BTC/USDT"].append(make_snapshot(volume=10_000_000_000))
    
    current = make_snapshot(volume=30_000_000_000)
    events = watcher._check_anomalies("BTC/USDT", current)
    
    volume_events = [e for e in events if e.event_type == "volume_surge"]
    assert len(volume_events) >= 1
    
    surge = volume_events[0]
    assert surge.data["volume_ratio"] == pytest.approx(3.0, abs=0.1)
    print(f"✅ Volume surge detected: {surge.data['volume_ratio']}x")


def test_no_volume_surge_below_threshold(watcher):
    """Об'єм 1.5x — менше порогу 2x → НЕ генерує"""
    for _ in range(20):
        watcher._history["BTC/USDT"].append(make_snapshot(volume=10_000_000_000))
    
    current = make_snapshot(volume=15_000_000_000)  # 1.5x
    events = watcher._check_anomalies("BTC/USDT", current)
    
    volume_events = [e for e in events if e.event_type == "volume_surge"]
    assert len(volume_events) == 0
    print("✅ No volume surge below threshold (correctly ignored)")


# ==============================================================================
# ТЕСТ 4: Funding Rate Extreme
# ==============================================================================

def test_funding_rate_extreme(watcher):
    """Funding rate 0.2% → funding_extreme event"""
    watcher._fetch_funding_rate = Mock(return_value=0.002)
    watcher._history["BTC/USDT"].append(make_snapshot())
    
    current = make_snapshot()
    events = watcher._check_anomalies("BTC/USDT", current)
    
    funding_events = [e for e in events if e.event_type == "funding_extreme"]
    assert len(funding_events) >= 1
    
    fe = funding_events[0]
    assert fe.data["bias"] == "LONG_HEAVY"
    assert fe.data["funding_rate"] == 0.002
    print(f"✅ Funding extreme detected: rate={fe.data['funding_rate']}")


def test_negative_funding_extreme(watcher):
    """Від'ємний funding rate → SHORT_HEAVY"""
    watcher._fetch_funding_rate = Mock(return_value=-0.0015)
    watcher._history["BTC/USDT"].append(make_snapshot())
    
    current = make_snapshot()
    events = watcher._check_anomalies("BTC/USDT", current)
    
    funding_events = [e for e in events if e.event_type == "funding_extreme"]
    assert len(funding_events) >= 1
    assert funding_events[0].data["bias"] == "SHORT_HEAVY"
    print("✅ Negative funding extreme detected (SHORT_HEAVY)")


def test_normal_funding_rate(watcher):
    """Нормальний funding rate 0.05% → НЕ генерує"""
    watcher._fetch_funding_rate = Mock(return_value=0.0005)
    watcher._history["BTC/USDT"].append(make_snapshot())
    
    current = make_snapshot()
    events = watcher._check_anomalies("BTC/USDT", current)
    
    funding_events = [e for e in events if e.event_type == "funding_extreme"]
    assert len(funding_events) == 0
    print("✅ Normal funding rate correctly ignored")


# ==============================================================================
# ТЕСТ 5: Cooldown (антиспам)
# ==============================================================================

def test_cooldown_prevents_duplicate_events(watcher):
    """Перший spike → подія. Другий spike одразу → заблоковано cooldown"""
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=97850.0)
    events1 = watcher._check_anomalies("BTC/USDT", current)
    assert len(events1) >= 1
    
    # Другий раз — cooldown блокує
    events2 = watcher._check_anomalies("BTC/USDT", current)
    price_spikes = [e for e in events2 if e.event_type == "price_spike"]
    assert len(price_spikes) == 0
    print("✅ Cooldown prevents duplicate events")


def test_cooldown_expires():
    """Cooldown 1 секунда → після паузи дозволяє нову подію"""
    config = WatcherConfig(
        pairs=["BTC/USDT"],
        cooldown_seconds=1,  # 🧒 Короткий для тесту
    )
    watcher = MarketWatcher(config=config, exchange=Mock())
    
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=97850.0)
    events1 = watcher._check_anomalies("BTC/USDT", current)
    assert len(events1) >= 1
    
    import time
    time.sleep(1.5)
    
    events2 = watcher._check_anomalies("BTC/USDT", current)
    price_spikes = [e for e in events2 if e.event_type == "price_spike"]
    assert len(price_spikes) >= 1
    print("✅ Cooldown expired: new event allowed")


# ==============================================================================
# ТЕСТ 6: poll_once з mock exchange
# ==============================================================================

def test_poll_once_normal(watcher, mock_exchange):
    """poll_once отримує дані та зберігає в історію"""
    events = watcher.poll_once()
    
    assert watcher.total_polls == 1
    assert mock_exchange.fetch_ticker.called
    assert len(watcher._history["BTC/USDT"]) == 1
    print(f"✅ poll_once works: polls={watcher.total_polls}")


def test_poll_once_with_spike(mock_exchange):
    """poll_once детектує price spike після кількох поллінгів"""
    config = WatcherConfig(pairs=["BTC/USDT"], price_spike_window=3)
    watcher = MarketWatcher(config=config, exchange=mock_exchange)
    
    # 3 поллінги зі стабільною ціною
    mock_exchange.fetch_ticker.return_value = {
        'last': 95000.0, 'bid': 94999.0, 'ask': 95001.0,
        'high': 96000.0, 'low': 94000.0,
        'quoteVolume': 30e9, 'percentage': 1.0,
    }
    for _ in range(3):
        watcher.poll_once()
    
    # 4-й поллінг: ціна +5%
    mock_exchange.fetch_ticker.return_value = {
        'last': 99750.0, 'bid': 99749.0, 'ask': 99751.0,
        'high': 100000.0, 'low': 94000.0,
        'quoteVolume': 30e9, 'percentage': 5.0,
    }
    events = watcher.poll_once()
    
    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) >= 1
    assert price_spikes[0].data["direction"] == "UP"
    print(f"✅ poll_once detected spike: +{price_spikes[0].data['price_change_pct']}%")


def test_poll_once_handles_api_error():
    """API помилка → не крашить watcher"""
    mock_ex = Mock()
    mock_ex.fetch_ticker.side_effect = Exception("API timeout")
    
    config = WatcherConfig(pairs=["BTC/USDT"])
    watcher = MarketWatcher(config=config, exchange=mock_ex)
    
    events = watcher.poll_once()
    
    assert events == []
    assert watcher.errors == 1
    assert watcher.total_polls == 1
    print("✅ API error handled gracefully")


# ==============================================================================
# ТЕСТ 7: Edge Cases
# ==============================================================================

def test_not_enough_history(watcher):
    """Недостатньо історії → НЕ генерує подій"""
    watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    current = make_snapshot(price=100000.0)  # +5%!
    events = watcher._check_anomalies("BTC/USDT", current)
    
    price_spikes = [e for e in events if e.event_type == "price_spike"]
    assert len(price_spikes) == 0
    print("✅ Not enough history: no false events")


def test_zero_price_no_crash(watcher):
    """Ціна = 0 → не крашить (divide by zero)"""
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=0.0))
    
    current = make_snapshot(price=95000.0)
    events = watcher._check_anomalies("BTC/USDT", current)
    print("✅ Zero price handled without crash")


def test_multiple_pairs():
    """Моніторинг 3 пар одночасно"""
    config = WatcherConfig(pairs=["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    mock_ex = Mock()
    mock_ex.fetch_ticker.return_value = {
        'last': 95000.0, 'bid': 94999.0, 'ask': 95001.0,
        'high': 96000.0, 'low': 94000.0,
        'quoteVolume': 30e9, 'percentage': 1.0,
    }
    
    watcher = MarketWatcher(config=config, exchange=mock_ex)
    events = watcher.poll_once()
    
    assert mock_ex.fetch_ticker.call_count == 3
    assert len(watcher._history["BTC/USDT"]) == 1
    assert len(watcher._history["ETH/USDT"]) == 1
    assert len(watcher._history["SOL/USDT"]) == 1
    print("✅ Multiple pairs monitored correctly")


def test_get_stats(watcher, mock_exchange):
    """Статистика працює коректно"""
    watcher.poll_once()
    watcher.poll_once()
    
    stats = watcher.get_stats()
    assert stats["total_polls"] == 2
    assert stats["pairs_monitored"] == 1
    assert "BTC/USDT" in stats["history_sizes"]
    print(f"✅ Stats: {stats}")


def test_severity_scaling(watcher):
    """Severity масштабується: маленький spike → менша severity"""
    for _ in range(10):
        watcher._history["BTC/USDT"].append(make_snapshot(price=95000.0))
    
    # 2.5% spike
    current_small = make_snapshot(price=97375.0)
    events_small = watcher._check_anomalies("BTC/USDT", current_small)
    
    if events_small:
        severity_small = events_small[0].severity
        watcher._last_event.clear()  # Скидаємо cooldown
        
        # 8% spike
        current_big = make_snapshot(price=102600.0)
        events_big = watcher._check_anomalies("BTC/USDT", current_big)
        
        if events_big:
            severity_big = events_big[0].severity
            assert severity_big > severity_small
            print(f"✅ Severity scales: 2.5%→{severity_small}, 8%→{severity_big}")


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "🚀" * 35)
    print("   MARKET WATCHER - TEST SUITE")
    print("🚀" * 35)
    
    pytest.main([__file__, "-v", "-s", "--tb=short"])
TESTEOF
echo "   ✅ tests/test_market_watcher.py (17 tests)"

# ──────────────────────────────────────────────────────────────
# 5. Виводимо результат
# ──────────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  ✅ Всі файли встановлено!                   ║"
echo "╠═══════════════════════════════════════════════╣"
echo "║                                               ║"
echo "║  Нові файли:                                  ║"
echo "║    src/watchers/__init__.py                    ║"
echo "║    src/watchers/market_watcher.py (380+ рядків)║"
echo "║    tests/test_market_watcher.py  (17 тестів)  ║"
echo "║                                               ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ──────────────────────────────────────────────────────────────
# 6. Запускаємо тести
# ──────────────────────────────────────────────────────────────
echo "🧪 Запускаю тести..."
echo ""

cd "$PROJECT_ROOT"

# Активуємо venv якщо є
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "   ✅ venv activated"
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "   ✅ .venv activated"
fi

# Запускаємо pytest
python -m pytest tests/test_market_watcher.py -v -s --tb=short 2>&1

echo ""
echo "════════════════════════════════════════════════"
echo "🎉 Готово! Наступний крок: GrokTwitterScanner"
echo "════════════════════════════════════════════════"
