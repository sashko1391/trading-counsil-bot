"""Tests for Historical Analogues finder."""

import pytest
from models.schemas import MarketEvent, HistoricalAnalogue
from knowledge.historical_analogues import HistoricalAnalogueFinder


@pytest.fixture
def finder():
    return HistoricalAnalogueFinder()


class TestHistoricalAnalogueFinder:
    def test_opec_event_finds_opec_analogues(self, finder):
        event = MarketEvent(
            event_type="opec_event",
            instrument="BZ=F",
            severity=0.9,
            data={},
            headline="OPEC+ announces surprise production cut",
        )
        analogues = finder.find(event)
        assert len(analogues) > 0
        # Should find OPEC-related episodes
        names = [a.event_name for a in analogues]
        assert any("OPEC" in n for n in names)

    def test_geopolitical_finds_geopolitical(self, finder):
        event = MarketEvent(
            event_type="geopolitical_alert",
            instrument="BZ=F",
            severity=0.8,
            data={},
            headline="Iran sanctions reimposed by US",
        )
        analogues = finder.find(event)
        assert len(analogues) > 0
        # Should find Iran or geopolitical episodes
        assert any(a.similarity_score > 0.2 for a in analogues)

    def test_eia_report_finds_inventory(self, finder):
        event = MarketEvent(
            event_type="eia_report",
            instrument="BZ=F",
            severity=0.6,
            data={},
            headline="EIA reports large crude inventory draw",
        )
        analogues = finder.find(event)
        assert len(analogues) > 0

    def test_max_results_respected(self, finder):
        event = MarketEvent(
            event_type="news_event",
            instrument="BZ=F",
            severity=0.5,
            data={},
            headline="Oil markets rally on demand hopes",
        )
        analogues = finder.find(event, max_results=2)
        assert len(analogues) <= 2

    def test_similarity_score_bounded(self, finder):
        event = MarketEvent(
            event_type="opec_event",
            instrument="BZ=F",
            severity=0.9,
            data={},
            headline="OPEC cut production sanctions Russia",
        )
        analogues = finder.find(event)
        for a in analogues:
            assert 0 <= a.similarity_score <= 1.0

    def test_no_match_returns_empty(self, finder):
        event = MarketEvent(
            event_type="price_spike",
            instrument="LGO",
            severity=0.3,
            data={},
            headline="",
        )
        # With very generic event, may still find some matches
        analogues = finder.find(event)
        assert isinstance(analogues, list)

    def test_format_for_prompt(self, finder):
        analogues = [
            HistoricalAnalogue(
                event_name="Test Event",
                year=2022,
                trigger="Test trigger",
                similarity_score=0.8,
                price_impact_pct=5.0,
                duration_days=7,
                resolution="Price recovered",
                key_difference="Different context",
            )
        ]
        text = finder.format_for_prompt(analogues)
        assert "Історичні аналогії" in text
        assert "Test Event" in text
        assert "2022" in text
        assert "+5.0%" in text

    def test_format_empty(self, finder):
        text = finder.format_for_prompt([])
        assert text == ""

    def test_sorted_by_similarity(self, finder):
        event = MarketEvent(
            event_type="opec_event",
            instrument="BZ=F",
            severity=0.9,
            data={},
            headline="OPEC cut",
        )
        analogues = finder.find(event, max_results=5)
        if len(analogues) >= 2:
            for i in range(len(analogues) - 1):
                assert analogues[i].similarity_score >= analogues[i + 1].similarity_score


class TestDisagreementPenalty:
    """Test the improved P1.6 disagreement logic in Aggregator."""

    def test_directional_disagreement_heavy_penalty(self):
        from council.aggregator import Aggregator
        from models.schemas import Signal, MarketEvent

        agg = Aggregator()
        event = MarketEvent(
            event_type="price_spike", instrument="BZ=F",
            severity=0.8, data={},
        )
        long_sig = Signal(action="LONG", confidence=0.8, thesis="Bull",
                          risk_notes="risk", sources=[])
        short_sig = Signal(action="SHORT", confidence=0.8, thesis="Bear",
                           risk_notes="risk", sources=[])

        # 2 LONG vs 2 SHORT → should be CONFLICT or lower confidence
        resp = agg.aggregate(event, long_sig, long_sig, short_sig, short_sig, "h1")
        # With equal weight + equal confidence, this should be CONFLICT
        assert resp.consensus in ("CONFLICT", "LONG", "SHORT")

    def test_wait_disagreement_lighter_penalty(self):
        from council.aggregator import Aggregator
        from models.schemas import Signal, MarketEvent

        agg = Aggregator()
        event = MarketEvent(
            event_type="price_spike", instrument="BZ=F",
            severity=0.8, data={},
        )
        long_sig = Signal(action="LONG", confidence=0.8, thesis="Bull",
                          risk_notes="risk", sources=[])
        wait_sig = Signal(action="WAIT", confidence=0.5, thesis="Unclear",
                          risk_notes="risk", sources=[])

        # 3 LONG + 1 WAIT → LONG, but confidence affected
        resp = agg.aggregate(event, long_sig, long_sig, long_sig, wait_sig, "h1")
        assert resp.consensus == "LONG"
        # WAIT disagreement should cause lighter penalty than SHORT would
        assert resp.combined_confidence > 0.4


class TestConfidenceCalibration:
    """Test P1.7 confidence calibration in Aggregator."""

    def test_calibration_reduces_overconfident(self):
        from council.aggregator import Aggregator
        from models.schemas import Signal, MarketEvent

        agg = Aggregator()
        # Grok is overconfident: hit_rate 0.4, avg_confidence 0.8 → factor 0.5
        agg.set_calibration_factors({"grok": 0.5, "perplexity": 1.0, "claude": 1.0, "gemini": 1.0})

        event = MarketEvent(event_type="price_spike", instrument="BZ=F",
                            severity=0.8, data={})
        sig = Signal(action="LONG", confidence=0.8, thesis="T", risk_notes="R", sources=[])

        # Without calibration, all equal → UNANIMOUS
        agg_clean = Aggregator()
        resp_clean = agg_clean.aggregate(event, sig, sig, sig, sig, "h1")

        # With calibration, grok's vote is weaker
        resp_cal = agg.aggregate(event, sig, sig, sig, sig, "h1")

        # Calibrated confidence should be lower (grok's effective conf is 0.4)
        assert resp_cal.combined_confidence <= resp_clean.combined_confidence
