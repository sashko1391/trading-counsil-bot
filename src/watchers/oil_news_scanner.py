"""
Oil News Scanner — RSS-based oil market news monitor.

Monitors multiple RSS feeds for oil-relevant news, scores relevance by keywords,
deduplicates headlines, and returns MarketEvent objects.

Phase 3B: Keywords and feeds loaded from settings. Source credibility weights.
New event types: influencer_signal, tanker_alert.
"""

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx
from loguru import logger

from models.schemas import MarketEvent


# ============================================================
# Fallback keyword lists (used when settings unavailable)
# ============================================================

_FALLBACK_HIGH: list[str] = [
    "opec", "sanctions", "hormuz", "embargo", "production cut",
    "eia", "inventory", "inventories", "draw", "build",
    "crude oil stocks", "petroleum status",
]

_FALLBACK_MED: list[str] = [
    "refinery", "pipeline", "tanker", "demand", "china", "pmi",
    "gdp", "recession", "brent", "gasoil", "crude",
    "oil price", "barrel", "supply disruption",
]

_FALLBACK_LOW: list[str] = [
    "renewable", "ev", "electric vehicle", "climate",
    "solar", "wind energy", "green energy",
]

# Tanker/shipping keywords for tanker_alert classification
TANKER_KEYWORDS: list[str] = [
    "tanker", "vlcc", "freight", "shipping", "suez", "hormuz",
    "chokepoint", "vessel", "aframax", "suezmax", "tanker attack",
    "floating storage", "ship-to-ship", "dark fleet",
]


def _get_keywords() -> tuple[list[str], list[str], list[str]]:
    """Load keyword lists from settings, fallback to hardcoded."""
    try:
        from src.config.settings import get_settings
        s = get_settings()
        high = [kw.lower() for kw in s.OIL_KEYWORDS_HIGH] if s.OIL_KEYWORDS_HIGH else _FALLBACK_HIGH
        med = [kw.lower() for kw in s.OIL_KEYWORDS_MED] if s.OIL_KEYWORDS_MED else _FALLBACK_MED
        low = [kw.lower() for kw in s.OIL_KEYWORDS_LOW] if s.OIL_KEYWORDS_LOW else _FALLBACK_LOW
        return high, med, low
    except Exception:
        return _FALLBACK_HIGH, _FALLBACK_MED, _FALLBACK_LOW


def _get_influencer_names() -> list[str]:
    """Load influencer names from settings."""
    try:
        from src.config.settings import get_settings
        s = get_settings()
        return [name.lower().lstrip("@") for name in s.OIL_INFLUENCERS.keys()]
    except Exception:
        return []


def _normalize(text: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    return text.lower().strip()


def _headline_hash(headline: str) -> str:
    """Produce a short hash of a normalised headline for dedup."""
    return hashlib.md5(_normalize(headline).encode()).hexdigest()


def _similar_headlines(a: str, b: str, threshold: float = 0.7) -> bool:
    """Simple word-overlap similarity check between two headlines."""
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    return overlap / min(len(words_a), len(words_b)) >= threshold


def score_relevance(text: str, source_weight: float = 1.0) -> tuple[float, str]:
    """
    Score a piece of text for oil-market relevance.

    source_weight: credibility weight of the RSS source (0.0-1.0).
    Final severity is multiplied by source_weight.

    Returns (severity, level) where:
        level is 'high', 'medium', 'low', or 'noise'
        severity is a float 0-1 for MarketEvent.severity
    """
    lower = _normalize(text)
    high_kw, med_kw, low_kw = _get_keywords()

    high_hits = sum(1 for kw in high_kw if kw in lower)
    medium_hits = sum(1 for kw in med_kw if kw in lower)
    low_hits = sum(1 for kw in low_kw if kw in lower)

    if high_hits:
        raw = min(0.7 + high_hits * 0.1, 1.0)
        return min(raw * source_weight, 1.0), "high"
    if medium_hits:
        raw = min(0.4 + medium_hits * 0.1, 0.69)
        return min(raw * source_weight, 1.0), "medium"
    if low_hits:
        return 0.1 * source_weight, "low"
    return 0.0, "noise"


def classify_event_type(text: str, source_category: str = "") -> str:
    """Map headline text to an OilEventType string.

    source_category: the feed category (e.g. 'official', 'pro', 'social').
    """
    lower = _normalize(text)

    # Tanker/shipping → tanker_alert
    if any(kw in lower for kw in TANKER_KEYWORDS):
        return "tanker_alert"

    # Influencer signal — check if headline mentions known influencer or social source
    influencer_names = _get_influencer_names()
    if source_category in ("social", "influencer"):
        return "influencer_signal"
    if influencer_names and any(name in lower for name in influencer_names):
        return "influencer_signal"

    if any(kw in lower for kw in ("eia", "inventory", "inventories", "crude oil stocks", "petroleum status", "draw", "build")):
        return "eia_report"
    if any(kw in lower for kw in ("opec", "production cut", "quota")):
        return "opec_event"
    if any(kw in lower for kw in ("sanctions", "embargo", "war", "conflict", "geopolit")):
        return "geopolitical_alert"
    if any(kw in lower for kw in ("hurricane", "storm", "cold snap", "freeze", "weather")):
        return "weather_event"
    return "news_event"


def _load_feeds_from_settings() -> dict[str, dict]:
    """Load RSS feeds from settings, returning {name: {url, weight, category}}."""
    try:
        from src.config.settings import get_settings
        s = get_settings()
        feeds = {}
        for name, cfg in s.RSS_FEEDS.items():
            if isinstance(cfg, str):
                feeds[name] = {"url": cfg, "weight": 1.0, "category": "news"}
            else:
                feeds[name] = {
                    "url": cfg.get("url", ""),
                    "weight": cfg.get("weight", 1.0),
                    "category": cfg.get("category", "news"),
                }
        return feeds
    except Exception:
        return {
            "oilprice": {"url": "https://oilprice.com/rss", "weight": 0.40, "category": "news"},
            "eia": {"url": "https://www.eia.gov/rss/todayinenergy.xml", "weight": 0.85, "category": "official"},
        }


class OilNewsScanner:
    """
    Async RSS feed scanner for oil market news.

    Parameters
    ----------
    feeds : dict mapping source_name -> url or {url, weight, category}
    cooldown_seconds : minimum seconds between fetches per source
    relevance_threshold : minimum level to keep ('high', 'medium', 'low').
    """

    def __init__(
        self,
        feeds: Optional[dict] = None,
        cooldown_seconds: int = 300,
        relevance_threshold: str = "medium",
    ):
        if feeds is not None:
            # Normalize: accept both {name: url} and {name: {url, weight, category}}
            self.feeds: dict[str, dict] = {}
            for name, val in feeds.items():
                if isinstance(val, str):
                    self.feeds[name] = {"url": val, "weight": 1.0, "category": "news"}
                else:
                    self.feeds[name] = val
        else:
            self.feeds = _load_feeds_from_settings()

        self.cooldown_seconds = cooldown_seconds
        self.relevance_threshold = relevance_threshold

        self._last_fetch: dict[str, float] = {}
        self._seen_hashes: set[str] = set()
        self._seen_headlines: list[str] = []

    # ----------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------

    def _is_on_cooldown(self, source: str) -> bool:
        last = self._last_fetch.get(source, 0.0)
        return (time.time() - last) < self.cooldown_seconds

    def _mark_fetched(self, source: str) -> None:
        self._last_fetch[source] = time.time()

    def _is_duplicate(self, headline: str) -> bool:
        h = _headline_hash(headline)
        if h in self._seen_hashes:
            return True
        for prev in self._seen_headlines[-200:]:
            if _similar_headlines(headline, prev):
                self._seen_hashes.add(h)
                return True
        return False

    def _record_headline(self, headline: str) -> None:
        h = _headline_hash(headline)
        self._seen_hashes.add(h)
        self._seen_headlines.append(headline)
        if len(self._seen_headlines) > 1000:
            self._seen_headlines = self._seen_headlines[-500:]

    def _passes_threshold(self, level: str) -> bool:
        order = {"high": 3, "medium": 2, "low": 1, "noise": 0}
        threshold_val = order.get(self.relevance_threshold, 2)
        return order.get(level, 0) >= threshold_val

    # ----------------------------------------------------------
    # Feed fetching
    # ----------------------------------------------------------

    async def _fetch_feed(self, source: str, feed_cfg: dict) -> list[dict]:
        """Fetch and parse a single RSS feed, returning raw entries."""
        if self._is_on_cooldown(source):
            logger.debug(f"Source '{source}' is on cooldown, skipping")
            return []

        url = feed_cfg["url"]
        weight = feed_cfg.get("weight", 1.0)
        category = feed_cfg.get("category", "news")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                raw = resp.text
        except Exception as exc:
            logger.warning(f"Failed to fetch RSS from {source}: {exc}")
            return []

        self._mark_fetched(source)

        feed = feedparser.parse(raw)
        entries = []
        for entry in feed.entries:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")
            published = getattr(entry, "published", "")
            entries.append({
                "source": source,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "source_weight": weight,
                "source_category": category,
            })
        logger.info(f"Fetched {len(entries)} entries from {source}")
        return entries

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    async def scan(self) -> list[MarketEvent]:
        """
        Scan all configured RSS feeds and return relevant MarketEvents.

        Deduplicates, scores, filters by relevance threshold.
        """
        tasks = [
            self._fetch_feed(source, cfg)
            for source, cfg in self.feeds.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events: list[MarketEvent] = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch error: {result}")
                continue

            for entry in result:
                headline = entry["title"]
                if not headline:
                    continue

                if self._is_duplicate(headline):
                    logger.debug(f"Duplicate headline skipped: {headline[:60]}")
                    continue

                combined_text = f"{headline} {entry.get('summary', '')}"
                source_weight = entry.get("source_weight", 1.0)
                source_category = entry.get("source_category", "")

                severity, level = score_relevance(combined_text, source_weight=source_weight)

                if not self._passes_threshold(level):
                    logger.debug(f"Below threshold ({level}): {headline[:60]}")
                    continue

                self._record_headline(headline)

                event_type = classify_event_type(combined_text, source_category=source_category)

                event = MarketEvent(
                    event_type=event_type,
                    instrument="BZ=F",
                    severity=severity,
                    headline=headline,
                    data={
                        "source": entry["source"],
                        "link": entry["link"],
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "relevance_level": level,
                        "source_weight": source_weight,
                        "source_category": source_category,
                    },
                )
                events.append(event)

        logger.info(f"Oil news scan complete: {len(events)} relevant events")
        return events

    def reset(self) -> None:
        """Clear dedup caches and cooldown timers."""
        self._last_fetch.clear()
        self._seen_hashes.clear()
        self._seen_headlines.clear()
