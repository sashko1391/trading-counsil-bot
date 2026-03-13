"""
Налаштування проєкту — Oil Trading Intelligence Bot
Читає значення з .env файлу
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Налаштування додатку з environment variables"""

    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # ===== AI APIs =====
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str  # used for embeddings (Pinecone)
    GOOGLE_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    XAI_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    PINECONE_API_KEY: str = ""

    # ===== AI MODELS =====
    GROK_MODEL: str = "grok-3"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    PERPLEXITY_MODEL: str = "sonar"

    # ===== DATA PROVIDERS =====
    DATA_PROVIDER: str = "yfinance"  # yfinance | ibkr
    EIA_API_KEY: str = ""
    NASDAQ_DATA_LINK_API_KEY: str = ""

    # ===== TELEGRAM =====
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # ===== ІНСТРУМЕНТИ ДЛЯ МОНІТОРИНГУ =====
    WATCH_INSTRUMENTS: list[str] = ["BZ=F", "LGO"]

    # ===== ПОРОГИ ДЛЯ ДЕТЕКТОРІВ =====
    PRICE_SPIKE_THRESHOLD: float = 0.02
    VOLUME_SURGE_THRESHOLD: float = 2.0  # multiplier vs average
    SPREAD_CHANGE_THRESHOLD: float = 0.05  # 5% crack spread change

    # ===== РИЗИК-МЕНЕДЖМЕНТ =====
    MAX_DAILY_ALERTS: int = 10
    MIN_CONFIDENCE: float = 0.6
    COOLDOWN_MINUTES: int = 30

    # ===== ВАГИ ДЛЯ АГЕНТІВ =====
    COUNCIL_WEIGHTS: dict = {
        "grok": 0.25,
        "perplexity": 0.25,
        "claude": 0.25,
        "gemini": 0.25
    }

    # ===== ШЛЯХИ ДО ФАЙЛІВ =====
    JOURNAL_PATH: Path = Path("data/trades.json")
    KNOWLEDGE_PATH: Path = Path("data/knowledge")
    LOG_LEVEL: str = "INFO"


def get_settings() -> Settings:
    """Lazy factory — не крашить імпорт якщо .env неповний"""
    return Settings()
