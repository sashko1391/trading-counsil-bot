"""
Settings — Oil Trading Intelligence Bot v3.1
Phase 3A: New API keys, RSS feeds, influencer list, events calendar,
          adversarial stage config, RAG decay lambdas
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional, Dict

from dotenv import load_dotenv

# Load .env from project root (handles both src/ WORKDIR and project root)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)


class Settings:
    # ── AI APIs ───────────────────────────────────────────────────────────────
    XAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Telegram ─────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_CHAT_IDS: str = ""  # comma-separated, overrides TELEGRAM_CHAT_ID

    # ── Data APIs (Phase 3A) ──────────────────────────────────────────────────
    EIA_API_KEY: str = ""
    OILPRICEAPI_KEY: str = ""          # OilPriceAPI.com — Brent ~$30/mo
    DATABENTO_API_KEY: str = ""        # Databento — ICE Brent + Gasoil ~$1000/mo
    NASDAQ_DATA_LINK_KEY: str = ""     # Quandl/Nasdaq — LGO historical

    # ── Models ────────────────────────────────────────────────────────────────
    GROK_MODEL: str = "grok-3-latest"
    CLAUDE_SONNET_MODEL: str = "claude-sonnet-4-6"      # council agent
    CLAUDE_OPUS_MODEL: str = "claude-opus-4-6"          # adversarial stage
    GEMINI_MODEL: str = "gemini-2.5-pro"                # council + adversarial
    GEMINI_ADVERSARIAL_MODEL: str = "gemini-2.5-pro"
    OPENAI_SUMMARY_MODEL: str = "gpt-4o"                # user-facing summary

    # ── Instruments ───────────────────────────────────────────────────────────
    WATCH_INSTRUMENTS: List[str] = ["BZ=F", "LGO"]
    DATA_PROVIDER: str = "yfinance"   # yfinance | oilpriceapi | databento

    # ── Thresholds ────────────────────────────────────────────────────────────
    VOLUME_SURGE_THRESHOLD: float = 2.0
    SPREAD_CHANGE_THRESHOLD: float = 5.0
    PRICE_SPIKE_THRESHOLD_PCT: float = 1.5
    MIN_CONFIDENCE: float = 0.60
    COOLDOWN_MINUTES: int = 10
    MAX_DAILY_ALERTS: int = 30
    MAX_PIPELINE_RUNS_PER_HOUR: int = 5

    # ── Adversarial stage ─────────────────────────────────────────────────────
    ADVERSARIAL_ENABLED: bool = True
    ADVERSARIAL_MIN_CONFIDENCE_DELTA: float = 0.05

    # ── RAG / Knowledge Base ──────────────────────────────────────────────────
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "oil-intelligence"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_TOP_K: int = 6
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 160
    # Confidence decay formula: score *= e^(-lambda * hours_since_indexed)
    RAG_NEWS_DECAY_LAMBDA: float = 0.05    # half-life ≈ 14h for news
    RAG_FACT_DECAY_LAMBDA: float = 0.005   # half-life ≈ 140h for fundamentals

    # ── RSS feeds ─────────────────────────────────────────────────────────────
    RSS_FEEDS: Dict[str, Dict] = {
        "oilprice_main":       {"url": "https://oilprice.com/rss/main",                                            "weight": 0.40, "category": "news"},
        "eia_today":           {"url": "https://www.eia.gov/rss/todayinenergy.xml",                                "weight": 0.85, "category": "official"},
        "energy_intel":        {"url": "https://www.energyintel.com/rss/energy-intelligence",                      "weight": 0.80, "category": "pro"},
        "argus_media":         {"url": "https://www.argusmedia.com/en/rss-feeds",                                  "weight": 0.80, "category": "pro"},
        "rigzone":             {"url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",                     "weight": 0.60, "category": "news"},
        "opec_press":          {"url": "https://www.opec.org/opec_web/en/press_room/rss.htm",                      "weight": 0.95, "category": "official"},
        "spglobal_energy":     {"url": "https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/oil/rss", "weight": 0.75, "category": "pro"},
        "iea_reports":         {"url": "https://www.iea.org/api/v1/rss",                                           "weight": 0.85, "category": "official"},
        "ogj_upstream":        {"url": "https://www.ogj.com/rss/upstream.xml",                                    "weight": 0.60, "category": "trade"},
        "reuters_commodities": {"url": "https://feeds.reuters.com/reuters/businessNews",                           "weight": 0.80, "category": "wire"},
    }

    # ── News keywords (signal scoring) ────────────────────────────────────────
    OIL_KEYWORDS_HIGH: List[str] = [
        "OPEC cut", "OPEC+ cut", "production cut", "output cut",
        "sanctions imposed", "sanctions expanded",
        "Strait of Hormuz", "Hormuz closure", "tanker attack",
        "refinery outage", "force majeure",
        "war escalation", "military strike",
        "Iran nuclear", "Iran sanctions",
        "emergency meeting OPEC", "inventory draw", "crude draw",
    ]
    OIL_KEYWORDS_MED: List[str] = [
        "OPEC decision", "quota compliance", "OPEC+ meeting",
        "EIA report", "API report", "inventory build",
        "China demand", "Chinese PMI", "Fujairah storage",
        "Russia cap", "Russian exports",
        "demand surge", "demand destruction",
        "refinery maintenance", "crack spread",
        "Baker Hughes", "rig count", "export ban",
        "shale output", "US production",
    ]
    OIL_KEYWORDS_LOW: List[str] = [
        "oil price", "crude oil", "Brent", "WTI", "gasoil", "diesel",
        "energy market", "petroleum",
    ]

    # ── Twitter/X influencers ─────────────────────────────────────────────────
    OIL_INFLUENCERS: Dict[str, Dict] = {
        "@JavierBlas":      {"weight": 0.90, "type": "journalist", "signals": "leading",  "org": "Bloomberg"},
        "@Amena_Bakr":      {"weight": 0.92, "type": "journalist", "signals": "leading",  "org": "EnergyIntel"},
        "@DavidSheppard_":  {"weight": 0.85, "type": "journalist", "signals": "leading",  "org": "FT"},
        "@AlexLongley1":    {"weight": 0.82, "type": "journalist", "signals": "leading",  "org": "Bloomberg"},
        "@summer_said":     {"weight": 0.88, "type": "journalist", "signals": "leading",  "org": "WSJ"},
        "@EnergyAspects":   {"weight": 0.75, "type": "analyst",    "signals": "lagging",  "org": "EnergyAspects"},
        "@AnasAlhajji":     {"weight": 0.72, "type": "analyst",    "signals": "mixed",    "org": "Independent"},
        "@TankerTrackers":  {"weight": 0.80, "type": "data",       "signals": "leading",  "org": "TankerTrackers"},
        "@Kpler":           {"weight": 0.82, "type": "data",       "signals": "leading",  "org": "Kpler"},
        "@Vortexa":         {"weight": 0.80, "type": "data",       "signals": "leading",  "org": "Vortexa"},
        "@staunovo":        {"weight": 0.70, "type": "analyst",    "signals": "mixed",    "org": "UBS"},
        "@ArjunNMurti":     {"weight": 0.65, "type": "analyst",    "signals": "lagging",  "org": "Independent"},
        "@HFI_Research":    {"weight": 0.62, "type": "analyst",    "signals": "mixed",    "org": "HFI Research"},
        "@IEA":             {"weight": 0.88, "type": "official",   "signals": "lagging",  "org": "IEA"},
        "@EIAgov":          {"weight": 0.90, "type": "official",   "signals": "lagging",  "org": "EIA"},
        "@OPECnews":        {"weight": 0.95, "type": "official",   "signals": "lagging",  "org": "OPEC"},
        "@OilShepard":      {"weight": 0.65, "type": "analyst",    "signals": "mixed",    "org": "Independent"},
    }

    # ── Scheduled events calendar ─────────────────────────────────────────────
    SCHEDULED_EVENTS: List[Dict] = [
        # ─── ORIGINAL 6 ──────────────────────────────────────────────────────
        {"name": "EIA Weekly Petroleum Status",    "schedule": "weekly",  "day": 3,
         "utc_hour": 15, "utc_min": 30, "pre_alert_min": 30, "impact": "high",
         "instruments": ["BZ=F", "LGO"],
         "note": "Crude inventories, Cushing hub, refinery runs, gasoil stocks"},

        {"name": "API Private Inventory Report",   "schedule": "weekly",  "day": 2,
         "utc_hour": 20, "utc_min": 30, "pre_alert_min": 30, "impact": "high",
         "instruments": ["BZ=F"],
         "note": "Private — market pre-positions 24h before EIA"},

        {"name": "Baker Hughes Rig Count",         "schedule": "weekly",  "day": 5,
         "utc_hour": 17, "utc_min": 0,  "pre_alert_min": 30, "impact": "medium",
         "instruments": ["BZ=F"],
         "note": "US drilling activity — leading indicator for future production"},

        {"name": "US Non-Farm Payrolls",           "schedule": "monthly_first_friday",
         "utc_hour": 12, "utc_min": 30, "pre_alert_min": 60, "impact": "high",
         "instruments": ["BZ=F", "LGO"],
         "note": "US economy proxy → fuel demand. Broad market mover"},

        {"name": "OPEC Monthly Oil Market Report", "schedule": "monthly", "day_of_month": 15,
         "utc_hour": 10, "utc_min": 0,  "pre_alert_min": 60, "impact": "high",
         "instruments": ["BZ=F", "LGO"],
         "note": "Quota vs actual production, demand forecast, supply balance"},

        {"name": "IEA Oil Market Report",          "schedule": "monthly", "day_of_month": 14,
         "utc_hour": 9,  "utc_min": 0,  "pre_alert_min": 60, "impact": "high",
         "instruments": ["BZ=F", "LGO"],
         "note": "Independent demand/supply balance. Often diverges from OPEC"},

        # ─── NEW Phase 3A ─────────────────────────────────────────────────────
        {"name": "Chinese Manufacturing PMI",      "schedule": "monthly", "day_of_month": 1,
         "utc_hour": 1,  "utc_min": 30, "pre_alert_min": 60, "impact": "high",
         "instruments": ["BZ=F"],
         "note": "China = largest crude importer. PMI below 50 = bearish demand"},

        {"name": "Fujairah Petroleum Storage",     "schedule": "weekly",  "day": 1,
         "utc_hour": 8,  "utc_min": 0,  "pre_alert_min": 30, "impact": "medium",
         "instruments": ["LGO"],
         "note": "Key Middle East gasoil stocks. Direct LGO proxy for ARA equivalent"},

        {"name": "EU Gas Storage Report (GIE)",    "schedule": "weekly",  "day": 4,
         "utc_hour": 9,  "utc_min": 0,  "pre_alert_min": 30, "impact": "medium",
         "instruments": ["LGO"],
         "note": "European gas storage → heating oil demand correlation"},

        {"name": "Russian Oil Production Update",  "schedule": "monthly", "day_of_month": 20,
         "utc_hour": 8,  "utc_min": 0,  "pre_alert_min": 30, "impact": "medium",
         "instruments": ["BZ=F"],
         "note": "Rosstat data. Under-tracked. Shows real sanctions impact"},

        {"name": "Indian Oil Import Data (PPAC)",  "schedule": "monthly", "day_of_month": 25,
         "utc_hour": 7,  "utc_min": 0,  "pre_alert_min": 30, "impact": "low",
         "instruments": ["BZ=F"],
         "note": "India = 3rd largest importer, fastest growing demand"},
    ]

    # ── Paths ─────────────────────────────────────────────────────────────────
    JOURNAL_PATH: Path = Path("data/trades.json")
    PERFORMANCE_PATH: Path = Path("data/agent_performance.json")
    KNOWLEDGE_PATH: Path = Path("data/knowledge")

    def __init__(self):
        str_keys = [
            "XAI_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY",
            "GOOGLE_AI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_IDS",
            "EIA_API_KEY", "OILPRICEAPI_KEY", "DATABENTO_API_KEY",
            "NASDAQ_DATA_LINK_KEY", "PINECONE_API_KEY",
            "GROK_MODEL", "CLAUDE_SONNET_MODEL", "CLAUDE_OPUS_MODEL",
            "GEMINI_MODEL", "GEMINI_ADVERSARIAL_MODEL", "OPENAI_SUMMARY_MODEL",
            "DATA_PROVIDER", "PINECONE_INDEX", "OPENAI_EMBEDDING_MODEL",
        ]
        for key in str_keys:
            setattr(self, key, os.environ.get(key, getattr(self, key, "")))

        for key in ["MIN_CONFIDENCE", "PRICE_SPIKE_THRESHOLD_PCT",
                    "SPREAD_CHANGE_THRESHOLD", "VOLUME_SURGE_THRESHOLD",
                    "RAG_NEWS_DECAY_LAMBDA", "RAG_FACT_DECAY_LAMBDA",
                    "ADVERSARIAL_MIN_CONFIDENCE_DELTA"]:
            v = os.environ.get(key)
            if v is not None:
                setattr(self, key, float(v))

        for key in ["MAX_DAILY_ALERTS", "COOLDOWN_MINUTES", "RAG_TOP_K",
                    "RAG_CHUNK_SIZE", "RAG_CHUNK_OVERLAP", "MAX_PIPELINE_RUNS_PER_HOUR"]:
            v = os.environ.get(key)
            if v is not None:
                setattr(self, key, int(v))

        v = os.environ.get("ADVERSARIAL_ENABLED")
        if v is not None:
            self.ADVERSARIAL_ENABLED = v.lower() in ("1", "true", "yes")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
