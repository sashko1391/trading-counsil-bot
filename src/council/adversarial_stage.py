"""
Adversarial Reasoning Stage — ABAIC v3.1
Phase 3A

3-step debate to surface hidden risks and prevent sycophantic consensus:
  Step 1: Claude Opus 4.6      → primary thesis  (bold position)
  Step 2: Gemini 2.5 Pro       → steel-man counter  (blind to Opus confidence)
  Step 3: Claude Opus 4.6      → reads counter → accept/reject → final verdict

Only runs when council has STRONG or UNANIMOUS consensus ≥ 0.65 confidence.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional, List

from config.prompts import (
    ADVERSARIAL_PRIMARY_PROMPT,
    ADVERSARIAL_COUNTER_PROMPT,
    ADVERSARIAL_VERDICT_PROMPT,
)
from src.config.settings import get_settings
from models.schemas import (
    AdversarialResult, DebateStep,
    HistoricalAnalogue, CouncilResponse,
)

logger = logging.getLogger(__name__)


class AdversarialStage:
    """
    3-step adversarial debate for final forecast refinement.

    Cost estimate per run: ~$0.50–1.20 (Opus is expensive — only run on strong signals)
    """

    def __init__(self):
        self.settings = get_settings()
        self._anthropic = None
        self._genai = None

    # ── Public API ────────────────────────────────────────────────────────────

    def should_run(self, council: CouncilResponse) -> bool:
        """Gate: skip if disabled, CONFLICT/WAIT, WEAK strength, or low confidence."""
        if not self.settings.ADVERSARIAL_ENABLED:
            return False
        if council.consensus in ("CONFLICT", "WAIT"):
            return False
        if council.consensus_strength not in ("UNANIMOUS", "STRONG"):
            return False
        if council.combined_confidence < 0.65:
            return False
        return True

    def run(
        self,
        instrument: str,
        event_headline: str,
        current_price: float,
        council: CouncilResponse,
        historical_analogues: Optional[List[HistoricalAnalogue]] = None,
    ) -> AdversarialResult:
        """
        Run the full 3-step adversarial debate.

        Returns AdversarialResult with full transcript and final verdict.
        """
        logger.info(
            f"⚔️  Adversarial stage | {instrument} | {council.consensus} "
            f"({council.combined_confidence:.0%}) | {event_headline[:60]}"
        )
        t0 = time.time()

        council_summary = self._summarize_council(council)
        analogues_text = self._format_analogues(historical_analogues or [])

        # ── Step 1: Opus primary thesis ───────────────────────────────────────
        p1 = ADVERSARIAL_PRIMARY_PROMPT.format(
            instrument=instrument,
            event_headline=event_headline,
            current_price=current_price,
            preliminary_consensus=council.consensus,
            preliminary_confidence=council.combined_confidence,
            council_summary=council_summary,
            historical_analogues=analogues_text,
        )
        raw1, cost1, tok1 = self._call_opus(p1)
        d1 = self._parse(raw1, "primary")

        step1 = DebateStep(
            model=self.settings.CLAUDE_OPUS_MODEL,
            role="primary_thesis",
            content=raw1,
            confidence_before=council.combined_confidence,
            confidence_after=d1.get("confidence", council.combined_confidence),
            tokens_used=tok1,
            cost_usd=cost1,
        )
        logger.info(f"   Step 1 → {d1.get('action')} @ {d1.get('confidence', 0):.0%} | ${cost1:.3f}")

        # ── Step 2: Gemini counterargument (blind to Opus confidence) ─────────
        # Remove confidence before sending to Gemini — prevent anchoring
        d1_blind = {k: v for k, v in d1.items() if k != "confidence"}
        p2 = ADVERSARIAL_COUNTER_PROMPT.format(
            instrument=instrument,
            event_headline=event_headline,
            current_price=current_price,
            primary_thesis_json=json.dumps(d1_blind, indent=2),
            additional_context=council_summary,
        )
        raw2, cost2, tok2 = self._call_gemini(p2)
        d2 = self._parse(raw2, "counter")

        step2 = DebateStep(
            model=self.settings.GEMINI_ADVERSARIAL_MODEL,
            role="counterargument",
            content=raw2,
            confidence_before=d1.get("confidence", 0.5),
            confidence_after=d2.get("confidence", 0.5),
            tokens_used=tok2,
            cost_usd=cost2,
        )
        objections_count = len(d2.get("objections", []))
        logger.info(f"   Step 2 → {d2.get('action')} | {objections_count} objections | ${cost2:.3f}")

        # ── Step 3: Opus final verdict ────────────────────────────────────────
        p3 = ADVERSARIAL_VERDICT_PROMPT.format(
            primary_thesis_json=json.dumps(d1, indent=2),
            counterargument_json=json.dumps(d2, indent=2),
        )
        raw3, cost3, tok3 = self._call_opus(p3)
        d3 = self._parse(raw3, "verdict")

        # Classify each objection as accepted/rejected
        accepted, rejected = [], []
        for v in d3.get("verdict_on_objections", []):
            oid = v.get("objection_id", "?")
            orig = next((o for o in d2.get("objections", []) if o.get("id") == oid), {})
            text = f"[{oid}] {orig.get('title', '')}: {v.get('reasoning', '')}"
            (accepted if v.get("decision") == "ACCEPTED" else rejected).append(text)

        step3 = DebateStep(
            model=self.settings.CLAUDE_OPUS_MODEL,
            role="final_verdict",
            content=raw3,
            confidence_before=d1.get("confidence", 0.5),
            confidence_after=d3.get("final_confidence", d1.get("confidence", 0.5)),
            accepted_counterarguments=accepted,
            rejected_counterarguments=rejected,
            tokens_used=tok3,
            cost_usd=cost3,
        )

        total_cost = cost1 + cost2 + cost3
        delta = d3.get("confidence_delta", 0.0)
        logger.info(
            f"   Step 3 → {d3.get('final_action')} @ {d3.get('final_confidence', 0):.0%} "
            f"| δ={delta:+.2f} | accepted={len(accepted)} | total ${total_cost:.3f}"
        )

        result = AdversarialResult(
            instrument=instrument,
            completed_at=datetime.now(),
            primary_thesis=step1,
            counterargument=step2,
            final_verdict=step3,
            final_action=d3.get("final_action", council.consensus),
            final_confidence=d3.get("final_confidence", council.combined_confidence),
            confidence_delta=delta,
            narrative_divergence=d3.get("narrative_divergence", ""),
            total_cost_usd=total_cost,
            debate_quality=d3.get("debate_quality", "strong"),
        )

        elapsed = time.time() - t0
        logger.info(
            f"⚔️  Done | {elapsed:.1f}s | meaningful={result.was_meaningful} "
            f"| quality={result.debate_quality}"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _call_opus(self, prompt: str) -> tuple:
        """Call Claude Opus 4.6. Returns (text, cost_usd, tokens)."""
        client = self._get_anthropic()
        if client is None:
            return _FALLBACK_PRIMARY, 0.0, 0
        try:
            resp = client.messages.create(
                model=self.settings.CLAUDE_OPUS_MODEL,
                max_tokens=2000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            inp, out = resp.usage.input_tokens, resp.usage.output_tokens
            # Opus 4.6: $15/M input, $75/M output
            cost = (inp * 15 + out * 75) / 1_000_000
            return text, cost, inp + out
        except Exception as e:
            logger.error(f"Opus API error: {e}")
            return _FALLBACK_PRIMARY, 0.0, 0

    def _call_gemini(self, prompt: str) -> tuple:
        """Call Gemini 2.5 Pro. Returns (text, cost_usd, tokens)."""
        genai = self._get_genai()
        if genai is None:
            return _FALLBACK_COUNTER, 0.0, 0
        try:
            model = genai.GenerativeModel(self.settings.GEMINI_ADVERSARIAL_MODEL)
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(temperature=0.4, max_output_tokens=2000),
            )
            text = resp.text.strip()
            tokens = len(prompt.split()) + len(text.split())
            cost = tokens * 1.25 / 1_000_000  # Gemini 2.5 Pro ~$1.25/M
            return text, cost, tokens
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return _FALLBACK_COUNTER, 0.0, 0

    def _get_anthropic(self):
        if self._anthropic is None:
            try:
                import anthropic
                self._anthropic = anthropic.Anthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._anthropic

    def _get_genai(self):
        if self._genai is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.settings.GOOGLE_AI_API_KEY)
                self._genai = genai
            except ImportError:
                logger.warning("google.generativeai not installed")
        return self._genai

    def _parse(self, raw: str, ctx: str = "") -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error [{ctx}]: {e}")
            return {}

    def _summarize_council(self, council: CouncilResponse) -> str:
        lines = [
            f"Consensus: {council.consensus} ({council.consensus_strength})",
            f"Confidence: {council.combined_confidence:.0%}",
            "",
        ]
        for name in ("grok", "perplexity", "claude", "gemini"):
            s = getattr(council, name, None)
            if s:
                lines.append(f"  {name.upper()}: {s.action} ({s.confidence:.0%}) — {s.thesis[:100]}")
        return "\n".join(lines)

    def _format_analogues(self, analogues: List[HistoricalAnalogue]) -> str:
        if not analogues:
            return "No historical analogues available."
        return "\n".join(
            f"• {a.event_name} ({a.year}): similarity={a.similarity_score:.0%}, "
            f"impact={a.price_impact_pct:+.1f}% over {a.duration_days}d. "
            f"Key diff: {a.key_difference}"
            for a in analogues[:3]
        )


# ── Fallback JSON strings when APIs unavailable ───────────────────────────────

_FALLBACK_PRIMARY = '{"action":"WAIT","confidence":0.30,"thesis":"API unavailable","price_target":null,"invalidation_price":null,"risk_notes":"Anthropic API unavailable","key_arguments":[],"historical_support":"N/A"}'
_FALLBACK_COUNTER = '{"action":"WAIT","confidence":0.40,"opposing_thesis":"API unavailable","objections":[{"id":1,"title":"API error","detail":"Gemini API unavailable"}],"alternative_scenario":"N/A","confidence_in_primary_being_wrong":0.3}'


# ── Mock for testing (no API calls) ──────────────────────────────────────────

class MockAdversarialStage(AdversarialStage):
    """Drop-in mock for unit tests — returns deterministic results."""

    def run(self, instrument, event_headline, current_price, council,
            historical_analogues=None):

        step1 = DebateStep(
            model="mock-opus-4-6", role="primary_thesis",
            content='{"action":"LONG","confidence":0.78}',
            confidence_before=council.combined_confidence, confidence_after=0.78,
            tokens_used=500, cost_usd=0.015,
        )
        step2 = DebateStep(
            model="mock-gemini-2.5-pro", role="counterargument",
            content='{"action":"WAIT","objections":[{"id":1,"title":"China demand","detail":"PMI below 50 not priced in"}]}',
            confidence_before=0.78, confidence_after=0.55,
            tokens_used=400, cost_usd=0.005,
        )
        step3 = DebateStep(
            model="mock-opus-4-6", role="final_verdict",
            content='{"final_action":"LONG","final_confidence":0.72,"confidence_delta":-0.06}',
            confidence_before=0.78, confidence_after=0.72,
            accepted_counterarguments=["[1] China demand: Valid — reduced confidence by 0.06"],
            rejected_counterarguments=[],
            tokens_used=600, cost_usd=0.020,
        )
        return AdversarialResult(
            instrument=instrument,
            completed_at=datetime.now(),
            primary_thesis=step1,
            counterargument=step2,
            final_verdict=step3,
            final_action="LONG",
            final_confidence=0.72,
            confidence_delta=-0.06,
            narrative_divergence="Opus bullish on OPEC cut. Gemini flagged China PMI risk.",
            total_cost_usd=0.040,
            debate_quality="strong",
        )
