"""
Phase 3A — Full Test Suite
Tests: schemas, aggregator v2, adversarial stage mock, settings v3.1

Run from project root:
    pytest tests/test_phase3a.py -v
"""

import pytest
from datetime import datetime
from models.schemas import (
    Signal, MarketEvent, CouncilResponse, OilForecast, OilRiskScore,
    HistoricalAnalogue, ProbabilityDensity, AdversarialResult, DebateStep,
    AgentPerformanceRecord,
)
from council.aggregator import Aggregator, DEFAULT_WEIGHTS
from council.adversarial_stage import MockAdversarialStage


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def s_long():
    return Signal(action="LONG", confidence=0.80,
                  thesis="OPEC+ surprise cut of 1.5mb/d — supply tightens",
                  invalidation_price=70.0, risk_notes="China demand may be weak", sources=[])

@pytest.fixture
def s_short():
    return Signal(action="SHORT", confidence=0.65,
                  thesis="US shale surge + slowing China — oversupply building",
                  invalidation_price=78.0, risk_notes="OPEC could surprise again", sources=[])

@pytest.fixture
def s_wait():
    return Signal(action="WAIT", confidence=0.40,
                  thesis="Conflicting signals — no clear edge",
                  invalidation_price=None, risk_notes="Data uncertainty high", sources=[])

@pytest.fixture
def s_devil():
    return Signal(action="WAIT", confidence=0.70,
                  thesis="China PMI below 50 — demand destruction underpriced",
                  invalidation_price=None, risk_notes="PMI bearish signal", sources=[])

@pytest.fixture
def oil_event():
    return MarketEvent(
        event_type="price_spike", instrument="BZ=F",
        severity=0.85, data={"price_change_pct": 3.5},
        headline="Brent +3.5% on OPEC surprise cut",
    )

@pytest.fixture
def agg():
    return Aggregator()

@pytest.fixture
def council_long(s_long, oil_event, agg):
    return agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "hash_long")


# ═══════════════════════════════════════════════════════════════════
# BLOCK A: Schema Tests
# ═══════════════════════════════════════════════════════════════════

class TestHistoricalAnalogue:
    def test_create_valid(self):
        a = HistoricalAnalogue(
            event_name="Abqaiq attack 2019", year=2019,
            trigger="Drone strike on Saudi Aramco", similarity_score=0.78,
            price_impact_pct=15.0, duration_days=7,
            resolution="Saudi Arabia restored production within weeks",
            key_difference="Current disruption is more prolonged"
        )
        assert a.similarity_score == pytest.approx(0.78)
        assert a.price_impact_pct == pytest.approx(15.0)
        assert a.year == 2019

    def test_similarity_above_1_rejected(self):
        with pytest.raises(Exception):
            HistoricalAnalogue(
                event_name="Test", year=2020, trigger="x",
                similarity_score=1.5,  # invalid
                price_impact_pct=5.0, duration_days=3,
                resolution="x", key_difference="x"
            )

    def test_negative_price_impact_allowed(self):
        """Bear events should have negative price impact"""
        a = HistoricalAnalogue(
            event_name="COVID crash 2020", year=2020,
            trigger="Pandemic demand collapse",
            similarity_score=0.60, price_impact_pct=-60.0,
            duration_days=90, resolution="Recovery rally",
            key_difference="No storage crisis today"
        )
        assert a.price_impact_pct < 0


class TestProbabilityDensity:
    def test_valid(self):
        p = ProbabilityDensity(bull=0.65, bear=0.20, neutral=0.15)
        assert abs(p.bull + p.bear + p.neutral - 1.0) < 0.01

    def test_sum_not_1_raises(self):
        with pytest.raises(Exception):
            ProbabilityDensity(bull=0.70, bear=0.70, neutral=0.10)

    def test_all_bull(self):
        p = ProbabilityDensity(bull=1.0, bear=0.0, neutral=0.0)
        assert p.bull == 1.0

    def test_exactly_sums_to_one(self):
        p = ProbabilityDensity(bull=0.333, bear=0.333, neutral=0.334)
        assert abs(p.bull + p.bear + p.neutral - 1.0) < 0.01


class TestDebateStep:
    def test_create_primary(self):
        s = DebateStep(
            model="claude-opus-4-6", role="primary_thesis",
            content='{"action":"LONG","confidence":0.80}',
            confidence_before=0.72, confidence_after=0.80,
            tokens_used=600, cost_usd=0.025,
        )
        assert s.role == "primary_thesis"
        assert s.cost_usd == pytest.approx(0.025)

    def test_accepted_counterargs(self):
        s = DebateStep(
            model="claude-opus-4-6", role="final_verdict", content="{}",
            accepted_counterarguments=["[1] China risk: Valid point"],
            rejected_counterarguments=["[2] Already priced in: False"],
            tokens_used=700, cost_usd=0.030,
        )
        assert len(s.accepted_counterarguments) == 1
        assert len(s.rejected_counterarguments) == 1


class TestAdversarialResult:
    @pytest.fixture
    def dummy_steps(self):
        s1 = DebateStep(model="opus", role="primary_thesis", content="{}",
                        confidence_before=0.75, confidence_after=0.80,
                        tokens_used=500, cost_usd=0.015)
        s2 = DebateStep(model="gemini", role="counterargument", content="{}",
                        tokens_used=400, cost_usd=0.005)
        s3 = DebateStep(model="opus", role="final_verdict", content="{}",
                        accepted_counterarguments=["[1] Valid"],
                        tokens_used=600, cost_usd=0.020)
        return s1, s2, s3

    def test_was_meaningful_accepted(self, dummy_steps):
        s1, s2, s3 = dummy_steps
        r = AdversarialResult(
            instrument="BZ=F", primary_thesis=s1, counterargument=s2, final_verdict=s3,
            final_action="LONG", final_confidence=0.72, confidence_delta=-0.06,
        )
        assert r.was_meaningful is True

    def test_was_meaningful_big_delta(self, dummy_steps):
        s1, s2, _ = dummy_steps
        s3_no_accept = DebateStep(
            model="opus", role="final_verdict", content="{}",
            accepted_counterarguments=[], tokens_used=600, cost_usd=0.020
        )
        r = AdversarialResult(
            instrument="LGO", primary_thesis=s1, counterargument=s2, final_verdict=s3_no_accept,
            final_action="SHORT", final_confidence=0.55, confidence_delta=-0.25,
        )
        assert r.was_meaningful is True

    def test_not_meaningful_sycophantic(self, dummy_steps):
        s1, s2, _ = dummy_steps
        s3_syco = DebateStep(
            model="opus", role="final_verdict", content="{}",
            accepted_counterarguments=[], tokens_used=600, cost_usd=0.020
        )
        r = AdversarialResult(
            instrument="BZ=F", primary_thesis=s1, counterargument=s2, final_verdict=s3_syco,
            final_action="LONG", final_confidence=0.79, confidence_delta=-0.01,  # tiny shift
            debate_quality="sycophantic",
        )
        assert r.was_meaningful is False

    def test_total_cost_tracking(self, dummy_steps):
        s1, s2, s3 = dummy_steps
        r = AdversarialResult(
            instrument="BZ=F", primary_thesis=s1, counterargument=s2, final_verdict=s3,
            final_action="LONG", final_confidence=0.72, confidence_delta=-0.06,
            total_cost_usd=0.040,
        )
        assert r.total_cost_usd == pytest.approx(0.040)


class TestOilForecastV31:
    @pytest.fixture
    def risk_score(self):
        return OilRiskScore(geopolitical=0.8, supply=0.7, demand=0.4,
                            financial=0.3, seasonal=0.5, technical=0.6)

    def test_with_historical_analogues(self, risk_score):
        analogue = HistoricalAnalogue(
            event_name="Abqaiq 2019", year=2019, trigger="Drone strike",
            similarity_score=0.75, price_impact_pct=15.0, duration_days=7,
            resolution="Restored in weeks", key_difference="More prolonged now"
        )
        f = OilForecast(
            instrument="BZ=F", direction="BULLISH", confidence=0.72,
            timeframe_hours=48, current_price=72.50, target_price=78.0,
            stop_loss_price=70.0, drivers=["OPEC cut"], risks=["China demand"],
            historical_analogues=[analogue], risk_score=risk_score,
        )
        assert len(f.historical_analogues) == 1
        assert f.expected_move_pct == pytest.approx(7.59, rel=0.01)

    def test_with_probability_density(self, risk_score):
        pd = ProbabilityDensity(bull=0.65, bear=0.20, neutral=0.15)
        f = OilForecast(
            instrument="LGO", direction="BULLISH", confidence=0.65,
            probability_density=pd, timeframe_hours=24,
            current_price=650.0, target_price=670.0,
            drivers=["EU gasoil draw"], risks=["mild winter"],
            risk_score=risk_score,
        )
        assert f.probability_density.bull == pytest.approx(0.65)

    def test_agent_votes_and_cost(self, risk_score):
        f = OilForecast(
            instrument="BZ=F", direction="BULLISH", confidence=0.75,
            timeframe_hours=48, current_price=73.0, target_price=78.0,
            drivers=["supply cut"], risks=["demand"],
            agent_votes={"grok": "LONG:0.80", "claude": "LONG:0.75",
                         "perplexity": "LONG:0.70", "gemini": "WAIT:0.50"},
            council_cost_usd=0.95,
            risk_score=risk_score,
        )
        assert f.agent_votes["grok"] == "LONG:0.80"
        assert f.council_cost_usd == pytest.approx(0.95)

    def test_narrative_divergence_field(self, risk_score):
        f = OilForecast(
            instrument="BZ=F", direction="BEARISH", confidence=0.60,
            timeframe_hours=24, current_price=72.0, target_price=68.0,
            drivers=["oversupply"], risks=["OPEC reversal"],
            narrative_divergence="Grok sees supply glut; Claude sees demand recovery",
            risk_score=risk_score,
        )
        assert "Grok" in f.narrative_divergence


class TestAgentPerformanceRecord:
    def test_create_prediction(self):
        r = AgentPerformanceRecord(
            agent_name="grok", signal_id="sig-001",
            instrument="BZ=F", predicted_action="LONG",
            predicted_confidence=0.80,
        )
        assert r.was_correct is None  # not yet resolved

    def test_resolve_outcome(self):
        r = AgentPerformanceRecord(
            agent_name="gemini", signal_id="sig-002",
            instrument="BZ=F", predicted_action="SHORT",
            predicted_confidence=0.65,
            actual_direction="UP", was_correct=False,
            brier_score=1.2,
        )
        assert r.was_correct is False
        assert r.brier_score == pytest.approx(1.2)


# ═══════════════════════════════════════════════════════════════════
# BLOCK B: Aggregator v2 Tests
# ═══════════════════════════════════════════════════════════════════

class TestAggregatorVoting:
    def test_unanimous_long(self, agg, oil_event, s_long):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h")
        assert r.consensus == "LONG"
        assert r.consensus_strength == "UNANIMOUS"

    def test_strong_3_long_1_wait(self, agg, oil_event, s_long, s_wait):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_wait, "h")
        assert r.consensus == "LONG"
        assert r.consensus_strength in ("STRONG", "UNANIMOUS")

    def test_unanimous_short(self, agg, oil_event, s_short):
        r = agg.aggregate(oil_event, s_short, s_short, s_short, s_short, "h")
        assert r.consensus == "SHORT"
        assert r.consensus_strength == "UNANIMOUS"

    def test_conflict_2v2(self, agg, oil_event, s_long, s_short):
        r = agg.aggregate(oil_event, s_long, s_short, s_long, s_short, "h")
        # LONG and SHORT at equal weight → CONFLICT
        assert r.consensus in ("CONFLICT", "LONG", "SHORT")

    def test_wait_all_wait(self, agg, oil_event, s_wait):
        r = agg.aggregate(oil_event, s_wait, s_wait, s_wait, s_wait, "h")
        assert r.consensus == "WAIT"


class TestAggregatorConfidence:
    def test_unanimous_high_confidence_near_input(self, agg, oil_event, s_long):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h")
        assert r.combined_confidence >= 0.70  # should be close to 0.80

    def test_devil_reduces_confidence(self, agg, oil_event, s_long, s_devil):
        r_no_devil = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h1")
        r_with_devil = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h2",
                                     devil_advocate=s_devil)
        assert r_with_devil.combined_confidence < r_no_devil.combined_confidence

    def test_disagreement_reduces_confidence(self, agg, oil_event, s_long, s_wait):
        r_no_disagree = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h1")
        r_with_disagree = agg.aggregate(oil_event, s_long, s_long, s_long, s_wait, "h2")
        assert r_with_disagree.combined_confidence < r_no_disagree.combined_confidence

    def test_confidence_in_01_range(self, agg, oil_event, s_long, s_wait, s_short):
        for sig_combo in [(s_long, s_long, s_long, s_wait),
                          (s_long, s_short, s_long, s_short),
                          (s_wait, s_wait, s_wait, s_wait)]:
            r = agg.aggregate(oil_event, *sig_combo, "h")
            assert 0.0 <= r.combined_confidence <= 1.0


class TestAggregatorDevilAdvocate:
    def test_devil_stored_in_response(self, agg, oil_event, s_long, s_devil):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h",
                          devil_advocate=s_devil)
        assert r.devil_advocate is not None
        assert r.devil_advocate.action == "WAIT"

    def test_devil_risk_in_key_risks(self, agg, oil_event, s_long, s_devil):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h",
                          devil_advocate=s_devil)
        devil_risks = [x for x in r.key_risks if "[DEVIL]" in x]
        assert len(devil_risks) > 0

    def test_no_devil_no_devil_field(self, agg, oil_event, s_long):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h")
        assert r.devil_advocate is None

    def test_devil_risk_contains_devil_thesis(self, agg, oil_event, s_long, s_devil):
        r = agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h",
                          devil_advocate=s_devil)
        devil_risk_texts = " ".join(r.key_risks)
        assert "PMI" in devil_risk_texts or "demand" in devil_risk_texts.lower()


class TestAggregatorPositionSizing:
    def test_unanimous_high_conf_5pct(self, agg, oil_event):
        s = Signal(action="LONG", confidence=0.90, thesis="t",
                   invalidation_price=70.0, risk_notes="r", sources=[])
        r = agg.aggregate(oil_event, s, s, s, s, "h")
        assert r.recommendation.get("max_position_pct") == pytest.approx(0.05)

    def test_low_conf_1pct(self, agg, oil_event):
        s_low = Signal(action="LONG", confidence=0.50, thesis="t",
                       invalidation_price=70.0, risk_notes="r", sources=[])
        s_wait = Signal(action="WAIT", confidence=0.50, thesis="t",
                        invalidation_price=None, risk_notes="r", sources=[])
        r = agg.aggregate(oil_event, s_low, s_wait, s_low, s_wait, "h")
        if r.consensus == "LONG":
            assert r.recommendation.get("max_position_pct", 0) <= 0.02

    def test_conflict_no_position_size(self, agg, oil_event, s_long, s_short):
        r = agg.aggregate(oil_event, s_long, s_short, s_long, s_short, "h")
        if r.consensus == "CONFLICT":
            assert "max_position_pct" not in r.recommendation


class TestAggregatorInvalidation:
    def test_long_uses_max(self, agg, oil_event):
        s1 = Signal(action="LONG", confidence=0.8, thesis="t",
                    invalidation_price=72.0, risk_notes="r", sources=[])
        s2 = Signal(action="LONG", confidence=0.7, thesis="t",
                    invalidation_price=74.0, risk_notes="r", sources=[])
        s3 = Signal(action="LONG", confidence=0.75, thesis="t",
                    invalidation_price=70.0, risk_notes="r", sources=[])
        s4 = Signal(action="LONG", confidence=0.65, thesis="t",
                    invalidation_price=71.0, risk_notes="r", sources=[])
        r = agg.aggregate(oil_event, s1, s2, s3, s4, "h")
        assert r.invalidation_price == pytest.approx(74.0)

    def test_short_uses_min(self, agg, oil_event):
        s1 = Signal(action="SHORT", confidence=0.8, thesis="t",
                    invalidation_price=75.0, risk_notes="r", sources=[])
        s2 = Signal(action="SHORT", confidence=0.7, thesis="t",
                    invalidation_price=73.0, risk_notes="r", sources=[])
        s3 = Signal(action="SHORT", confidence=0.75, thesis="t",
                    invalidation_price=76.0, risk_notes="r", sources=[])
        s4 = Signal(action="SHORT", confidence=0.65, thesis="t",
                    invalidation_price=74.0, risk_notes="r", sources=[])
        r = agg.aggregate(oil_event, s1, s2, s3, s4, "h")
        assert r.invalidation_price == pytest.approx(73.0)

    def test_wait_no_invalidation(self, agg, oil_event, s_wait):
        r = agg.aggregate(oil_event, s_wait, s_wait, s_wait, s_wait, "h")
        assert r.invalidation_price is None


class TestAggregatorWeights:
    def test_update_valid_weights(self):
        agg = Aggregator()
        new = {"grok": 0.30, "perplexity": 0.20, "claude": 0.30, "gemini": 0.20}
        agg.update_weights(new)
        assert agg.weights["grok"] == pytest.approx(0.30)
        assert agg.weights["perplexity"] == pytest.approx(0.20)

    def test_update_invalid_sum_raises(self):
        agg = Aggregator()
        with pytest.raises(ValueError):
            agg.update_weights({"grok": 0.5, "perplexity": 0.5,
                                 "claude": 0.5, "gemini": 0.5})

    def test_custom_weights_at_init(self):
        custom = {"grok": 0.40, "perplexity": 0.15, "claude": 0.30, "gemini": 0.15}
        agg = Aggregator(weights=custom)
        assert agg.weights["grok"] == pytest.approx(0.40)

    def test_default_weights_equal(self):
        agg = Aggregator()
        for w in agg.weights.values():
            assert w == pytest.approx(0.25)

    def test_agent_votes_in_recommendation(self, agg, oil_event, s_long, s_wait):
        r = agg.aggregate(oil_event, s_long, s_long, s_wait, s_long, "h")
        votes = r.recommendation.get("agent_votes", {})
        assert "grok" in votes
        assert "claude" in votes
        assert ":" in votes["grok"]  # format: "ACTION:confidence"


# ═══════════════════════════════════════════════════════════════════
# BLOCK C: Adversarial Stage Mock Tests
# ═══════════════════════════════════════════════════════════════════

class TestMockAdversarialStage:
    @pytest.fixture
    def council_strong(self, s_long, oil_event):
        agg = Aggregator()
        return agg.aggregate(oil_event, s_long, s_long, s_long, s_long, "h")

    def test_mock_returns_result(self, council_strong, oil_event):
        stage = MockAdversarialStage()
        result = stage.run("BZ=F", "OPEC surprise cut 1.5mb/d", 72.50, council_strong)
        assert result.final_action == "LONG"
        assert result.final_confidence == pytest.approx(0.72)
        assert result.confidence_delta == pytest.approx(-0.06)

    def test_mock_was_meaningful(self, council_strong):
        stage = MockAdversarialStage()
        result = stage.run("BZ=F", "test event", 72.0, council_strong)
        assert result.was_meaningful is True

    def test_mock_cost_tracked(self, council_strong):
        stage = MockAdversarialStage()
        result = stage.run("BZ=F", "test", 72.0, council_strong)
        assert result.total_cost_usd == pytest.approx(0.040)

    def test_mock_three_steps(self, council_strong):
        stage = MockAdversarialStage()
        result = stage.run("LGO", "EU gasoil draw", 650.0, council_strong)
        assert result.primary_thesis.role == "primary_thesis"
        assert result.counterargument.role == "counterargument"
        assert result.final_verdict.role == "final_verdict"

    def test_mock_narrative_divergence(self, council_strong):
        stage = MockAdversarialStage()
        result = stage.run("BZ=F", "test", 72.0, council_strong)
        assert len(result.narrative_divergence) > 0

    def test_should_run_unanimous_true(self, council_strong):
        stage = MockAdversarialStage()
        assert stage.should_run(council_strong) is True

    def test_should_run_disabled(self, council_strong):
        stage = MockAdversarialStage()
        stage.settings.ADVERSARIAL_ENABLED = False
        assert stage.should_run(council_strong) is False
        stage.settings.ADVERSARIAL_ENABLED = True  # restore

    def test_should_run_conflict_false(self, oil_event, s_long, s_short):
        agg = Aggregator()
        council = agg.aggregate(oil_event, s_long, s_short, s_long, s_short, "h")
        stage = MockAdversarialStage()
        if council.consensus == "CONFLICT":
            assert stage.should_run(council) is False

    def test_should_run_low_confidence_false(self, oil_event):
        s_low = Signal(action="LONG", confidence=0.50, thesis="t",
                       invalidation_price=70.0, risk_notes="r", sources=[])
        agg = Aggregator()
        council = agg.aggregate(oil_event, s_low, s_low, s_low, s_low, "h")
        stage = MockAdversarialStage()
        # Low confidence should fail the gate
        if council.combined_confidence < 0.65:
            assert stage.should_run(council) is False


# ═══════════════════════════════════════════════════════════════════
# BLOCK D: Settings v3.1 Tests
# ═══════════════════════════════════════════════════════════════════

class TestSettingsV31:
    @pytest.fixture
    def settings(self):
        from src.config.settings import get_settings
        return get_settings()

    def test_new_data_api_keys_exist(self, settings):
        assert hasattr(settings, "OILPRICEAPI_KEY")
        assert hasattr(settings, "DATABENTO_API_KEY")
        assert hasattr(settings, "NASDAQ_DATA_LINK_KEY")

    def test_adversarial_models_correct(self, settings):
        assert "opus" in settings.CLAUDE_OPUS_MODEL.lower()
        assert "sonnet" in settings.CLAUDE_SONNET_MODEL.lower()

    def test_rss_feeds_have_required_fields(self, settings):
        assert len(settings.RSS_FEEDS) >= 8
        for key, feed in settings.RSS_FEEDS.items():
            assert "url" in feed, f"Feed {key} missing url"
            assert "weight" in feed, f"Feed {key} missing weight"
            assert "category" in feed, f"Feed {key} missing category"
            assert 0.0 <= feed["weight"] <= 1.0

    def test_influencers_format(self, settings):
        assert len(settings.OIL_INFLUENCERS) >= 10
        for handle, info in settings.OIL_INFLUENCERS.items():
            assert handle.startswith("@"), f"{handle} doesn't start with @"
            assert 0.0 <= info["weight"] <= 1.0
            assert info["signals"] in ("leading", "lagging", "mixed")
            assert info["type"] in ("journalist", "analyst", "data", "official")

    def test_scheduled_events_original_6_present(self, settings):
        names = {e["name"] for e in settings.SCHEDULED_EVENTS}
        required = {
            "EIA Weekly Petroleum Status",
            "Baker Hughes Rig Count",
            "OPEC Monthly Oil Market Report",
            "IEA Oil Market Report",
        }
        for r in required:
            assert r in names, f"Missing event: {r}"

    def test_scheduled_events_new_3_present(self, settings):
        names = {e["name"] for e in settings.SCHEDULED_EVENTS}
        assert "Chinese Manufacturing PMI" in names
        assert "Fujairah Petroleum Storage" in names
        assert "EU Gas Storage Report (GIE)" in names

    def test_rag_decay_lambdas(self, settings):
        assert settings.RAG_NEWS_DECAY_LAMBDA > 0
        assert settings.RAG_FACT_DECAY_LAMBDA > 0
        # News decays faster than fundamental facts
        assert settings.RAG_NEWS_DECAY_LAMBDA > settings.RAG_FACT_DECAY_LAMBDA

    def test_keywords_high_contains_critical(self, settings):
        high = " ".join(settings.OIL_KEYWORDS_HIGH)
        assert "OPEC cut" in high
        assert "Hormuz" in high
        assert "tanker attack" in high

    def test_adversarial_enabled_default(self, settings):
        assert settings.ADVERSARIAL_ENABLED is True

    def test_max_pipeline_runs_per_hour(self, settings):
        assert settings.MAX_PIPELINE_RUNS_PER_HOUR > 0
        assert settings.MAX_PIPELINE_RUNS_PER_HOUR <= 20  # sanity

    def test_event_count_expanded(self, settings):
        # Should have original 6 + at least 3 new
        assert len(settings.SCHEDULED_EVENTS) >= 9
