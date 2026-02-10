"""
Налаштування проєкту
Читає значення з .env файлу
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Налаштування додатку з environment variables"""
    
    # ===== БІРЖА =====
    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str
    BINANCE_TESTNET: bool = True
    
    # ===== AI APIs =====
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    
    # ===== TELEGRAM =====
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    
    # ===== РИЗИК-МЕНЕДЖМЕНТ =====
    MAX_POSITION_SIZE: float = 0.05
    MAX_DAILY_LOSS: float = 0.02
    MIN_LIQUIDITY: float = 1_000_000
    MAX_VOLATILITY: float = 0.10
    
    # ===== ШЛЯХИ ДО ФАЙЛІВ =====
    JOURNAL_PATH: Path = Path("data/trades.json")
    LOG_LEVEL: str = "INFO"
    
    # ===== ПАРИ ДЛЯ МОНІТОРИНГУ =====
    WATCH_PAIRS: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    # ===== ПОРОГИ ДЛЯ ДЕТЕКТОРІВ =====
    PRICE_SPIKE_THRESHOLD: float = 0.02
    WHALE_THRESHOLD: float = 1_000_000
    FUNDING_RATE_EXTREME: float = 0.001
    
    # ===== ВАГИ ДЛЯ АГЕНТІВ =====
    COUNCIL_WEIGHTS: dict = {
        "grok": 0.25,
        "perplexity": 0.25,
        "claude": 0.25,
        "gemini": 0.25
    }
    
    class Config:
        """Конфігурація Pydantic"""
        env_file = ".env"
        case_sensitive = True


# Створюємо глобальний об'єкт settings
settings = Settings()

# Створюємо папки
settings.JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

# Виводимо підтвердження
print("✅ Settings loaded successfully!")
print(f"📊 Watching pairs: {settings.WATCH_PAIRS}")
print(f"🛡️ Max position size: {settings.MAX_POSITION_SIZE * 100}%")
