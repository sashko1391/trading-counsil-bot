"""
Tests for oil-specific prompts and agent prompt configuration.
Verifies that all prompts are oil-focused, contain required keywords,
and include JSON output format instructions.
"""

import pytest
from config.prompts import (
    SYSTEM_PROMPT,
    GROK_SYSTEM_PROMPT,
    PERPLEXITY_SYSTEM_PROMPT,
    CLAUDE_SYSTEM_PROMPT,
    GEMINI_SYSTEM_PROMPT,
    get_agent_prompt,
    format_user_prompt,
)


# ── helpers ──────────────────────────────────────────────────────────

ALL_AGENT_PROMPTS = {
    "grok": GROK_SYSTEM_PROMPT,
    "perplexity": PERPLEXITY_SYSTEM_PROMPT,
    "claude": CLAUDE_SYSTEM_PROMPT,
    "gemini": GEMINI_SYSTEM_PROMPT,
}

# Oil-specific keywords that must appear across the prompt set
OIL_KEYWORDS_ANY = [
    "OPEC",
    "Brent",
    "Gasoil",
    "EIA",
    "crack spread",
    "contango",
    "backwardation",
    "BZ=F",
    "LGO",
    "crude",
    "oil",
]

# Keywords that must appear in each specific agent prompt
AGENT_KEYWORDS = {
    "grok": ["@JavierBlas", "@Amena_Bakr", "@OilShepard", "sentiment", "geopolitical"],
    "perplexity": ["EIA", "IEA", "OPEC", "inventory", "production"],
    "claude": ["contango", "crack spread", "OPEC compliance", "geopolitical premium", "demand destruction", "invalidation"],
    "gemini": ["seasonal", "China demand", "contango", "backwardation", "USD", "crack spread"],
}


# ── test: all prompts exist and are non-empty ────────────────────────

class TestPromptsExist:
    """Verify all four agent prompts exist and have meaningful length."""

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_prompt_exists_and_nonempty(self, agent_name):
        prompt = get_agent_prompt(agent_name)
        assert prompt, f"{agent_name} prompt is empty"
        assert len(prompt) > 200, f"{agent_name} prompt is suspiciously short ({len(prompt)} chars)"

    def test_unknown_agent_raises(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent_prompt("unknown_agent")

    def test_system_prompt_nonempty(self):
        assert len(SYSTEM_PROMPT) > 100


# ── test: oil-specific keywords ──────────────────────────────────────

class TestOilKeywords:
    """Verify prompts contain oil-market-specific terminology."""

    def test_oil_keywords_present_across_prompts(self):
        """At least 8 of the core oil keywords appear across all prompts combined."""
        combined = " ".join(ALL_AGENT_PROMPTS.values())
        found = [kw for kw in OIL_KEYWORDS_ANY if kw.lower() in combined.lower()]
        assert len(found) >= 8, (
            f"Only {len(found)}/{len(OIL_KEYWORDS_ANY)} oil keywords found: {found}"
        )

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_agent_specific_keywords(self, agent_name):
        """Each agent prompt contains its role-specific keywords."""
        prompt = ALL_AGENT_PROMPTS[agent_name]
        missing = [kw for kw in AGENT_KEYWORDS[agent_name] if kw.lower() not in prompt.lower()]
        assert not missing, (
            f"{agent_name} prompt missing keywords: {missing}"
        )

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_no_crypto_references(self, agent_name):
        """Prompts should not contain crypto-specific terms."""
        prompt = ALL_AGENT_PROMPTS[agent_name]
        crypto_terms = ["BTC", "Bitcoin", "Ethereum", "crypto", "altcoin"]
        import re
        found = [t for t in crypto_terms if re.search(r'\b' + re.escape(t) + r'\b', prompt, re.IGNORECASE)]
        assert not found, (
            f"{agent_name} prompt still contains crypto terms: {found}"
        )


# ── test: JSON output instructions ──────────────────────────────────

class TestJSONOutputFormat:
    """Verify prompts instruct agents to return structured JSON."""

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_json_format_mentioned(self, agent_name):
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "json" in prompt.lower(), f"{agent_name} prompt does not mention JSON"

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_action_field_mentioned(self, agent_name):
        prompt = ALL_AGENT_PROMPTS[agent_name]
        for action in ["LONG", "SHORT", "WAIT"]:
            assert action in prompt, f"{agent_name} prompt missing action '{action}'"

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_confidence_field_mentioned(self, agent_name):
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "confidence" in prompt.lower(), f"{agent_name} prompt missing 'confidence'"

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_sources_field_mentioned(self, agent_name):
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "sources" in prompt.lower(), f"{agent_name} prompt missing 'sources'"


# ── test: negative constraint and chain-of-thought ───────────────────

class TestPromptConstraints:
    """Verify negative constraint and chain-of-thought instructions."""

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_negative_constraint(self, agent_name):
        """Each prompt must tell agents not to speculate beyond data."""
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "do not speculate beyond available data" in prompt.lower(), (
            f"{agent_name} prompt missing negative constraint"
        )

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_chain_of_thought(self, agent_name):
        """Each prompt must include chain-of-thought instruction."""
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "facts" in prompt.lower() and "impact" in prompt.lower(), (
            f"{agent_name} prompt missing chain-of-thought (facts -> impact)"
        )

    @pytest.mark.parametrize("agent_name", ["grok", "perplexity", "claude", "gemini"])
    def test_separate_brent_gasoil(self, agent_name):
        """Each prompt must require separate Brent and Gasoil analysis."""
        prompt = ALL_AGENT_PROMPTS[agent_name]
        assert "brent" in prompt.lower() and "gasoil" in prompt.lower(), (
            f"{agent_name} prompt must mention both Brent and Gasoil"
        )


# ── test: format_user_prompt ─────────────────────────────────────────

class TestFormatUserPrompt:
    """Verify the user prompt template works correctly."""

    def test_basic_formatting(self):
        result = format_user_prompt(
            event_type="price_spike",
            instrument="BZ=F",
            market_data={"price_change": 2.5, "current_price": 81.0},
        )
        assert "price_spike" in result
        assert "BZ=F" in result
        assert "81.0" in result

    def test_with_news_and_indicators(self):
        result = format_user_prompt(
            event_type="eia_report",
            instrument="LGO",
            market_data={"draw": -3.2},
            news="EIA reported larger-than-expected draw",
            indicators={"rsi": 55, "contango": 0.3},
        )
        assert "eia_report" in result
        assert "LGO" in result
        assert "EIA reported" in result
        assert "contango" in result

    def test_default_news(self):
        result = format_user_prompt(
            event_type="opec_event",
            instrument="BZ=F",
            market_data={},
        )
        assert "No recent news available" in result
