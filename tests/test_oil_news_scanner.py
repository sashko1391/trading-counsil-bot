"""
Tests for OilNewsScanner — RSS feed monitoring, keyword scoring,
deduplication, and cooldown logic.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from watchers.oil_news_scanner import (
    OilNewsScanner,
    score_relevance,
    classify_event_type,
    _headline_hash,
    _similar_headlines,
)


# ============================================================
# Keyword relevance scoring
# ============================================================

class TestScoreRelevance:
    def test_high_keyword_opec(self):
        severity, level = score_relevance("OPEC+ announces major production cut")
        assert level == "high"
        assert severity >= 0.7

    def test_high_keyword_eia(self):
        severity, level = score_relevance("EIA reports massive crude inventory draw")
        assert level == "high"
        assert severity >= 0.7

    def test_high_keyword_sanctions(self):
        severity, level = score_relevance("New sanctions imposed on Iran oil exports")
        assert level == "high"

    def test_medium_keyword_refinery(self):
        severity, level = score_relevance("Refinery maintenance season begins in Texas")
        assert level == "medium"
        assert 0.4 <= severity < 0.7

    def test_medium_keyword_china_demand(self):
        severity, level = score_relevance("China demand for crude surges")
        assert level == "medium"

    def test_low_keyword_oil_price(self):
        severity, level = score_relevance("oil price moves slightly today")
        assert level == "low"
        assert severity <= 0.2

    def test_noise(self):
        severity, level = score_relevance("Local bakery opens new branch")
        assert level == "noise"
        assert severity == 0.0

    def test_multiple_high_keywords_boost(self):
        severity, level = score_relevance("OPEC cut plus sanctions imposed near Strait of Hormuz")
        assert level == "high"
        assert severity > 0.8


# ============================================================
# Event type classification
# ============================================================

class TestClassifyEventType:
    def test_eia_report(self):
        assert classify_event_type("EIA weekly petroleum status report") == "eia_report"

    def test_opec_event(self):
        assert classify_event_type("OPEC+ agrees on production cut") == "opec_event"

    def test_geopolitical(self):
        assert classify_event_type("US sanctions on Russian oil") == "geopolitical_alert"

    def test_weather(self):
        assert classify_event_type("Hurricane threatens Gulf refineries") == "weather_event"

    def test_generic_news(self):
        assert classify_event_type("Oil prices rise on demand optimism") == "news_event"


# ============================================================
# Deduplication
# ============================================================

class TestDeduplication:
    def test_exact_duplicate(self):
        scanner = OilNewsScanner(cooldown_seconds=0, relevance_threshold="medium")
        headline = "OPEC+ announces production cut"
        scanner._record_headline(headline)
        assert scanner._is_duplicate(headline) is True

    def test_similar_headline(self):
        scanner = OilNewsScanner(cooldown_seconds=0, relevance_threshold="medium")
        scanner._record_headline("OPEC announces major production cut for Q3")
        assert scanner._is_duplicate("OPEC announces major production cut for Q4") is True

    def test_different_headline(self):
        scanner = OilNewsScanner(cooldown_seconds=0, relevance_threshold="medium")
        scanner._record_headline("OPEC announces production cut")
        assert scanner._is_duplicate("Hurricane threatens Gulf refineries") is False

    def test_similarity_function_high(self):
        assert _similar_headlines(
            "OPEC agrees to cut oil production",
            "OPEC agrees to cut oil production by 1 mbpd",
        ) is True

    def test_similarity_function_low(self):
        assert _similar_headlines(
            "OPEC agrees to cut oil production",
            "Hurricane makes landfall in Texas coast",
        ) is False


# ============================================================
# Cooldown logic
# ============================================================

class TestCooldown:
    def test_not_on_cooldown_initially(self):
        scanner = OilNewsScanner(cooldown_seconds=300)
        assert scanner._is_on_cooldown("oilprice") is False

    def test_on_cooldown_after_fetch(self):
        scanner = OilNewsScanner(cooldown_seconds=300)
        scanner._mark_fetched("oilprice")
        assert scanner._is_on_cooldown("oilprice") is True

    def test_cooldown_expires(self):
        scanner = OilNewsScanner(cooldown_seconds=1)
        scanner._last_fetch["oilprice"] = time.time() - 2
        assert scanner._is_on_cooldown("oilprice") is False

    def test_different_sources_independent(self):
        scanner = OilNewsScanner(cooldown_seconds=300)
        scanner._mark_fetched("oilprice")
        assert scanner._is_on_cooldown("oilprice") is True
        assert scanner._is_on_cooldown("eia") is False


# ============================================================
# RSS feed scanning (mocked)
# ============================================================

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Oil News</title>
    <item>
      <title>OPEC+ agrees to extend production cuts through Q3</title>
      <link>https://example.com/opec-cuts</link>
      <description>OPEC+ ministers agreed to extend cuts.</description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>EIA reports surprise inventory draw of 5 million barrels</title>
      <link>https://example.com/eia-draw</link>
      <description>Crude inventories fell sharply.</description>
      <pubDate>Mon, 01 Jan 2024 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Local bakery opens new branch in Houston</title>
      <link>https://example.com/bakery</link>
      <description>Nothing to do with oil.</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


# ============================================================
# Source weight affects scoring
# ============================================================

class TestSourceWeight:
    def test_high_weight_increases_severity(self):
        sev_high, level = score_relevance("OPEC production cut", source_weight=0.95)
        sev_low, _ = score_relevance("OPEC production cut", source_weight=0.40)
        assert sev_high > sev_low

    def test_default_weight_is_one(self):
        sev_default, _ = score_relevance("OPEC sanctions")
        sev_explicit, _ = score_relevance("OPEC sanctions", source_weight=1.0)
        assert sev_default == sev_explicit


# ============================================================
# New event types: influencer_signal, tanker_alert
# ============================================================

class TestNewEventTypes:
    def test_tanker_alert(self):
        assert classify_event_type("VLCC tanker rates surge on Hormuz tensions") == "tanker_alert"

    def test_tanker_alert_shipping(self):
        assert classify_event_type("Shipping disruption in Suez Canal") == "tanker_alert"

    def test_tanker_alert_vessel(self):
        assert classify_event_type("Dark fleet vessel spotted near Singapore") == "tanker_alert"

    def test_influencer_signal_by_category(self):
        assert classify_event_type("Oil prices may rise", source_category="social") == "influencer_signal"

    def test_influencer_signal_by_name(self):
        # @JavierBlas is in default settings
        assert classify_event_type("JavierBlas reports OPEC insider intel") == "influencer_signal"

    def test_eia_still_works(self):
        assert classify_event_type("EIA inventory report shows draw") == "eia_report"

    def test_opec_still_works(self):
        assert classify_event_type("OPEC production cut agreed") == "opec_event"


# ============================================================
# RSS feed scanning (mocked)
# ============================================================

class TestScanMocked:
    @pytest.mark.asyncio
    async def test_scan_returns_relevant_events(self):
        scanner = OilNewsScanner(
            feeds={"test_feed": "https://example.com/rss"},
            cooldown_seconds=0,
            relevance_threshold="medium",
        )

        mock_response = MagicMock()
        mock_response.text = MOCK_RSS_XML
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.oil_news_scanner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            events = await scanner.scan()

        # Should pick up OPEC and EIA headlines, skip bakery noise
        assert len(events) == 2
        headlines = [e.headline for e in events]
        assert any("OPEC" in h for h in headlines)
        assert any("EIA" in h for h in headlines)

    @pytest.mark.asyncio
    async def test_scan_deduplicates(self):
        scanner = OilNewsScanner(
            feeds={"test_feed": "https://example.com/rss"},
            cooldown_seconds=0,
            relevance_threshold="medium",
        )

        mock_response = MagicMock()
        mock_response.text = MOCK_RSS_XML
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.oil_news_scanner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            events1 = await scanner.scan()
            events2 = await scanner.scan()

        # Second scan should produce 0 new events (all duplicates)
        assert len(events1) == 2
        assert len(events2) == 0

    @pytest.mark.asyncio
    async def test_scan_respects_cooldown(self):
        scanner = OilNewsScanner(
            feeds={"test_feed": "https://example.com/rss"},
            cooldown_seconds=9999,
            relevance_threshold="medium",
        )
        scanner._mark_fetched("test_feed")

        mock_response = MagicMock()
        mock_response.text = MOCK_RSS_XML
        mock_response.raise_for_status = MagicMock()

        with patch("src.watchers.oil_news_scanner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            events = await scanner.scan()

        # Cooldown should prevent any fetch
        assert len(events) == 0
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_handles_fetch_error(self):
        scanner = OilNewsScanner(
            feeds={"bad_feed": "https://example.com/broken"},
            cooldown_seconds=0,
            relevance_threshold="medium",
        )

        with patch("src.watchers.oil_news_scanner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            events = await scanner.scan()

        assert len(events) == 0
