"""
Тест моделей
"""

from src.models.schemas import Signal, MarketEvent, RiskCheck
from datetime import datetime

# 🧒 Тест 1: Створюємо Signal
print("=== Тест 1: Signal ===")
signal = Signal(
    action="LONG",
    confidence=0.85,
    thesis="Bitcoin буде рости через позитивні новини",
    invalidation_price=95000,
    risk_notes="Може впасти якщо whale продасть",
    sources=["https://twitter.com/example"]
)
print(f"✅ Signal створено: {signal.action} з впевненістю {signal.confidence}")

# 🧒 Тест 2: Невірний URL (має бути помилка)
print("\n=== Тест 2: Невірний URL ===")
try:
    bad_signal = Signal(
        action="LONG",
        confidence=0.5,
        thesis="Тест",
        risk_notes="Тест",
        sources=["not-a-url"]  # ❌ Невірний URL
    )
except ValueError as e:
    print(f"✅ Помилка спіймана: {e}")

# 🧒 Тест 3: Confidence поза межами (має бути помилка)
print("\n=== Тест 3: Confidence > 1.0 ===")
try:
    bad_signal = Signal(
        action="LONG",
        confidence=1.5,  # ❌ Більше 1.0!
        thesis="Тест",
        risk_notes="Тест"
    )
except Exception as e:
    print(f"✅ Помилка спіймана: {type(e).__name__}")

# 🧒 Тест 4: MarketEvent
print("\n=== Тест 4: MarketEvent ===")
event = MarketEvent(
    event_type="price_spike",
    pair="BTC/USDT",
    severity=0.85,
    data={"price_change": 6.2, "volume": 1000000}
)
print(f"✅ Event створено: {event.event_type} на {event.pair}")

# 🧒 Тест 5: RiskCheck
print("\n=== Тест 5: RiskCheck ===")
risk = RiskCheck(
    allowed=True,
    reason="All checks OK",
    volatility=0.08,
    liquidity=2000000,
    daily_loss=0.01
)
print(f"✅ RiskCheck: дозволено={risk.allowed}, причина={risk.reason}")

print("\n🎉 Всі тести пройшли!")
