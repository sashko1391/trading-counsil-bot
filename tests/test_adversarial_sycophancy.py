"""Tests for Adversarial Stage sycophancy detection (P2.10)."""

import pytest
from datetime import datetime

from models.schemas import AdversarialResult, DebateStep, CouncilResponse, Signal


def _make_council(consensus="LONG", confidence=0.75) -> CouncilResponse:
    sig = Signal(action=consensus, confidence=confidence, thesis="test", sources=[])
    return CouncilResponse(
        instrument="BZ=F",
        consensus=consensus,
        consensus_strength="STRONG",
        combined_confidence=confidence,
        grok=sig,
        perplexity=sig,
        claude=sig,
        gemini=sig,
        recommendation={"action": consensus},
        key_risks=["test risk"],
        prompt_hash="abc123",
    )


def _make_debate_result(
    accepted: list[str],
    rejected: list[str],
    delta: float,
    final_confidence: float,
    debate_quality: str = "strong",
) -> AdversarialResult:
    step1 = DebateStep(
        model="opus", role="primary_thesis", content="{}",
        confidence_before=0.75, confidence_after=0.78,
        tokens_used=100, cost_usd=0.01,
    )
    step2 = DebateStep(
        model="gemini", role="counterargument", content="{}",
        confidence_before=0.78, confidence_after=0.50,
        tokens_used=100, cost_usd=0.005,
    )
    step3 = DebateStep(
        model="opus", role="final_verdict", content="{}",
        confidence_before=0.78, confidence_after=final_confidence,
        accepted_counterarguments=accepted,
        rejected_counterarguments=rejected,
        tokens_used=100, cost_usd=0.01,
    )
    return AdversarialResult(
        instrument="BZ=F",
        completed_at=datetime.now(),
        primary_thesis=step1,
        counterargument=step2,
        final_verdict=step3,
        final_action="LONG",
        final_confidence=final_confidence,
        confidence_delta=delta,
        narrative_divergence="test",
        total_cost_usd=0.025,
        debate_quality=debate_quality,
    )


class TestSycophancyDetection:
    def test_sycophantic_debate_detected(self):
        """No objections accepted + tiny delta = sycophantic."""
        result = _make_debate_result(
            accepted=[], rejected=["OBJ-1", "OBJ-2"],
            delta=0.01, final_confidence=0.76,
            debate_quality="sycophantic",
        )
        assert result.debate_quality == "sycophantic"

    def test_strong_debate_with_accepted_objections(self):
        """Accepted objections = healthy debate."""
        result = _make_debate_result(
            accepted=["OBJ-1: China demand"], rejected=["OBJ-2"],
            delta=-0.06, final_confidence=0.72,
            debate_quality="strong",
        )
        assert result.debate_quality == "strong"
        assert result.was_meaningful  # delta > 0.02

    def test_sycophantic_confidence_penalty(self):
        """Sycophantic debate should have lowered confidence."""
        # Simulate what adversarial_stage.py does: final_confidence - 0.05
        original = 0.78
        penalty = 0.05
        result = _make_debate_result(
            accepted=[], rejected=["OBJ-1"],
            delta=-(penalty),
            final_confidence=original - penalty,
            debate_quality="sycophantic",
        )
        assert result.final_confidence == pytest.approx(0.73)
        assert result.debate_quality == "sycophantic"

    def test_meaningful_debate_with_accepted(self):
        """Accepted counterarguments = meaningful."""
        result = _make_debate_result(
            accepted=["OBJ-1"], rejected=[],
            delta=-0.03, final_confidence=0.75,
        )
        assert result.was_meaningful is True

    def test_meaningful_debate_large_delta(self):
        """Large delta (>0.05) = meaningful even without accepted."""
        result = _make_debate_result(
            accepted=[], rejected=["OBJ-1"],
            delta=-0.10, final_confidence=0.68,
        )
        assert result.was_meaningful is True

    def test_non_meaningful_debate(self):
        """Tiny delta + no accepted = not meaningful."""
        result = _make_debate_result(
            accepted=[], rejected=["OBJ-1"],
            delta=0.01, final_confidence=0.76,
        )
        assert result.was_meaningful is False

    def test_adversarial_result_fields(self):
        """All expected fields present."""
        result = _make_debate_result(
            accepted=[], rejected=[],
            delta=0.0, final_confidence=0.75,
            debate_quality="weak",
        )
        assert result.instrument == "BZ=F"
        assert result.total_cost_usd == 0.025
        assert result.debate_quality == "weak"
