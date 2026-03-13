"""
Aggregator v2 — ABAIC Oil Trading Intelligence Bot
Phase 3A

Changes vs v1:
  ✦ Confidence-weighted voting (not simple majority)
  ✦ Devil's Advocate: 5th virtual agent at 0.15 weight argues against consensus
  ✦ Dynamic weight support (update from BrierScore tracker quarterly)
  ✦ CONFLICT: both sides now logged in recommendation (not just WAIT)
  ✦ Per-agent vote logged in recommendation for transparency
  ✦ Position sizing formula improved

Core principle: This is NOT AI — it is deterministic Python.
Transparent, fast, no hallucinations, no API cost.
"""

import logging
from typing import Dict, List, Literal, Optional, Tuple
from datetime import datetime

from models.schemas import Signal, CouncilResponse, MarketEvent

logger = logging.getLogger(__name__)

# Default equal weights — updated quarterly via BrierScore tracker
DEFAULT_WEIGHTS: Dict[str, float] = {
    "grok": 0.25,
    "perplexity": 0.25,
    "claude": 0.25,
    "gemini": 0.25,
}

# Devil's Advocate weight: high enough to surface doubt, low enough not to override
DEVIL_WEIGHT = 0.15


class Aggregator:
    """
    Deterministic aggregation of AI council signals into a CouncilResponse.

    Steps:
    1. Confidence-weighted vote → consensus + strength
    2. Weighted confidence calculation (with disagreement penalty)
    3. Collect all risk notes
    4. Invalidation price (most conservative)
    5. Structured recommendation with position sizing
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")

    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """Update agent weights. Called by BrierScore tracker quarterly."""
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"New weights must sum to 1.0, got {total:.3f}")
        old = dict(self.weights)
        self.weights = dict(new_weights)
        logger.info(f"📊 Weights updated: {old} → {new_weights}")

    def aggregate(
        self,
        event: MarketEvent,
        grok: Signal,
        perplexity: Signal,
        claude: Signal,
        gemini: Signal,
        prompt_hash: str,
        devil_advocate: Optional[Signal] = None,
    ) -> CouncilResponse:
        """
        Aggregate 4 (or 5) agent signals into a council response.

        Args:
            event:          Triggering market event
            grok:           Grok sentiment signal
            perplexity:     Perplexity fact-check signal
            claude:         Claude Sonnet risk signal
            gemini:         Gemini macro signal
            prompt_hash:    SHA256 of prompts for audit
            devil_advocate: Optional 5th adversarial signal (weight=0.15)

        Returns:
            CouncilResponse
        """
        signals: Dict[str, Signal] = {
            "grok": grok,
            "perplexity": perplexity,
            "claude": claude,
            "gemini": gemini,
        }

        consensus, strength = self._vote(signals, devil_advocate)
        confidence = self._confidence(signals, consensus, devil_advocate)
        risks = self._risks(signals, devil_advocate)
        invalidation = self._invalidation(signals, consensus)
        rec = self._recommendation(consensus, strength, confidence, invalidation, signals)

        return CouncilResponse(
            timestamp=datetime.now(),
            event_type=event.event_type,
            instrument=event.instrument,
            grok=grok,
            perplexity=perplexity,
            claude=claude,
            gemini=gemini,
            devil_advocate=devil_advocate,
            consensus=consensus,
            consensus_strength=strength,
            combined_confidence=confidence,
            key_risks=risks,
            invalidation_price=invalidation,
            recommendation=rec,
            prompt_hash=prompt_hash,
        )

    # ── Voting ────────────────────────────────────────────────────────────────

    def _vote(
        self,
        signals: Dict[str, Signal],
        devil: Optional[Signal],
    ) -> Tuple[
        Literal["LONG", "SHORT", "WAIT", "CONFLICT"],
        Literal["UNANIMOUS", "STRONG", "WEAK", "NONE"],
    ]:
        """
        Confidence-weighted voting.
        Score per action = Σ(weight × confidence) for all agents choosing that action.
        Devil always votes WAIT at DEVIL_WEIGHT.
        """
        scores: Dict[str, float] = {"LONG": 0.0, "SHORT": 0.0, "WAIT": 0.0}

        for name, signal in signals.items():
            w = self.weights.get(name, 0.25)
            scores[signal.action] += w * signal.confidence

        if devil is not None:
            scores["WAIT"] += DEVIL_WEIGHT * devil.confidence

        total = sum(scores.values())
        if total == 0:
            return "WAIT", "NONE"

        norm = {k: v / total for k, v in scores.items()}
        winner = max(norm, key=norm.__getitem__)
        top_score = norm[winner]

        # CONFLICT: two actions within 10% of each other
        sorted_scores = sorted(norm.values(), reverse=True)
        if len(sorted_scores) >= 2 and (sorted_scores[0] - sorted_scores[1]) < 0.10:
            return "CONFLICT", "NONE"

        if top_score >= 0.75:
            strength = "UNANIMOUS"
        elif top_score >= 0.55:
            strength = "STRONG"
        elif top_score >= 0.40:
            strength = "WEAK"
        else:
            strength = "NONE"

        logger.debug(
            f"Vote | norm={norm} | winner={winner} ({top_score:.0%}) | strength={strength}"
        )
        return winner, strength

    # ── Confidence ────────────────────────────────────────────────────────────

    def _confidence(
        self,
        signals: Dict[str, Signal],
        consensus: str,
        devil: Optional[Signal],
    ) -> float:
        """
        Combined confidence = weighted avg of agreeing agents
        minus penalty from disagreeing agents × their weight × 0.30
        minus additional penalty from devil's advocate × 0.20
        """
        if consensus == "CONFLICT":
            vals = [s.confidence for s in signals.values()]
            return round(sum(vals) / len(vals), 2)

        agree_w, agree_c, penalty = 0.0, 0.0, 0.0

        for name, sig in signals.items():
            w = self.weights.get(name, 0.25)
            if sig.action == consensus:
                agree_w += w
                agree_c += w * sig.confidence
            else:
                penalty += w * sig.confidence * 0.30

        if agree_w == 0:
            return 0.0

        base = agree_c / agree_w
        if devil is not None:
            penalty += DEVIL_WEIGHT * devil.confidence * 0.20

        return round(max(0.0, min(1.0, base - penalty)), 2)

    # ── Risks ─────────────────────────────────────────────────────────────────

    def _risks(
        self, signals: Dict[str, Signal], devil: Optional[Signal]
    ) -> List[str]:
        seen: set = set()
        risks: List[str] = []
        for name, sig in signals.items():
            note = sig.risk_notes.strip()
            if note and note not in seen:
                seen.add(note)
                risks.append(f"[{name.upper()}] {note}")
        if devil and devil.risk_notes:
            note = devil.risk_notes.strip()
            if note not in seen:
                risks.append(f"[DEVIL] {note}")
        return risks

    # ── Invalidation ──────────────────────────────────────────────────────────

    def _invalidation(
        self, signals: Dict[str, Signal], consensus: str
    ) -> Optional[float]:
        if consensus in ("WAIT", "CONFLICT"):
            return None
        prices = [s.invalidation_price for s in signals.values() if s.invalidation_price]
        if not prices:
            return None
        return max(prices) if consensus == "LONG" else min(prices)

    # ── Recommendation ────────────────────────────────────────────────────────

    def _recommendation(
        self,
        consensus: str,
        strength: str,
        confidence: float,
        invalidation: Optional[float],
        signals: Dict[str, Signal],
    ) -> dict:
        rec: dict = {
            "action": consensus,
            "strength": strength,
            "confidence": confidence,
            "agent_votes": {
                name: f"{sig.action}:{sig.confidence:.2f}"
                for name, sig in signals.items()
            },
        }

        if consensus in ("WAIT", "CONFLICT"):
            rec["reason"] = (
                "Strong disagreement between agents — no actionable edge"
                if consensus == "CONFLICT"
                else "Insufficient evidence for directional trade"
            )
            return rec

        rec["invalidation_price"] = invalidation

        # Position sizing
        if strength == "UNANIMOUS" and confidence >= 0.80:
            pos = 0.05
        elif strength == "STRONG" and confidence >= 0.70:
            pos = 0.03
        elif strength in ("STRONG", "WEAK") and confidence >= 0.60:
            pos = 0.02
        else:
            pos = 0.01

        rec["max_position_pct"] = pos
        rec["key_insights"] = [
            f"{name.upper()}: {sig.thesis[:120]}"
            for name, sig in signals.items()
            if sig.action == consensus
        ]

        return rec


# ──────────────────────────────────────────────────────────────────────────────
# Smoke test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    s_long = Signal(action="LONG", confidence=0.82, thesis="Supply cut confirmed",
                    invalidation_price=70.0, risk_notes="Demand may drop", sources=[])
    s_wait = Signal(action="WAIT", confidence=0.45, thesis="Unclear picture",
                    invalidation_price=None, risk_notes="Data conflict", sources=[])
    s_devil = Signal(action="WAIT", confidence=0.65, thesis="China PMI below 50",
                     invalidation_price=None, risk_notes="PMI misread risk", sources=[])

    event = MarketEvent(event_type="price_spike", instrument="BZ=F",
                        severity=0.8, data={"price_change_pct": 3.1})

    agg = Aggregator()

    # Test 1: UNANIMOUS
    resp = agg.aggregate(event, s_long, s_long, s_long, s_long, "h1")
    assert resp.consensus == "LONG"
    assert resp.consensus_strength == "UNANIMOUS"
    print(f"✅ UNANIMOUS: {resp.consensus} ({resp.consensus_strength}) @ {resp.combined_confidence:.0%}")

    # Test 2: Devil's advocate reduces confidence
    resp_d = agg.aggregate(event, s_long, s_long, s_long, s_long, "h2", devil_advocate=s_devil)
    assert resp_d.combined_confidence < resp.combined_confidence
    assert resp_d.devil_advocate is not None
    print(f"✅ Devil advocate: confidence {resp.combined_confidence:.0%} → {resp_d.combined_confidence:.0%}")
    devil_risks = [r for r in resp_d.key_risks if "[DEVIL]" in r]
    assert len(devil_risks) > 0
    print(f"✅ Devil risk captured: {devil_risks[0][:60]}")

    # Test 3: STRONG with one WAIT
    resp2 = agg.aggregate(event, s_long, s_long, s_long, s_wait, "h3")
    assert resp2.consensus == "LONG"
    assert resp2.consensus_strength in ("STRONG", "UNANIMOUS")
    print(f"✅ STRONG: {resp2.consensus} ({resp2.consensus_strength})")

    # Test 4: Position sizing
    assert resp.recommendation["max_position_pct"] == 0.05
    assert resp2.recommendation["max_position_pct"] <= 0.03
    print(f"✅ Position sizing: UNANIMOUS={resp.recommendation['max_position_pct']:.0%}")

    # Test 5: Weight update
    agg.update_weights({"grok": 0.30, "perplexity": 0.20, "claude": 0.30, "gemini": 0.20})
    print(f"✅ Weight update: {agg.weights}")

    print("\n🎉 Aggregator v2 all smoke tests passed!")
