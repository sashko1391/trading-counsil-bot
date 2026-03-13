"""
Perplexity Agent — Data Verifier & Fact Checker for Oil Markets
Uses Perplexity API (OpenAI-compatible SDK) with manual JSON parsing
"""

from openai import OpenAI
from loguru import logger
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import PERPLEXITY_SYSTEM_PROMPT, format_user_prompt


class PerplexityAgent(BaseAgent):
    """
    Perplexity as data verification specialist for oil markets.

    - Focus: EIA/IEA/OPEC official data, inventory verification,
      production numbers, fact-checking news claims
    - API: Perplexity via OpenAI-compatible SDK
    - Model: configurable (default sonar)
    """

    def __init__(self, api_key: str, model: str = "sonar"):
        super().__init__(api_key, "Perplexity")

        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY is empty — cannot initialise PerplexityAgent")

        self.model_name = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai",
        )

    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        user_prompt = format_user_prompt(
            event_type=event.event_type,
            instrument=event.instrument,
            market_data=event.data,
            news=context.get("news", "No recent news"),
            indicators=context.get("indicators", {}),
        )

        # Ask for single instrument signal only
        user_prompt += f"""

IMPORTANT: Return a SINGLE JSON object (not an array) for instrument {event.instrument} only.
Use this exact schema:
{{
    "action": "LONG" | "SHORT" | "WAIT",
    "confidence": 0.0-1.0,
    "thesis": "макс 500 символів УКРАЇНСЬКОЮ — чому саме ця дія",
    "invalidation_price": number or null,
    "risk_notes": "що може піти не так — УКРАЇНСЬКОЮ",
    "sources": ["url1"]
}}
ОБОВ'ЯЗКОВО: thesis та risk_notes писати УКРАЇНСЬКОЮ (uk-UA). Англійський текст = помилка формату.
Pure JSON only — no markdown, no preamble."""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": PERPLEXITY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
                temperature=0.2,
            )

            response_text = response.choices[0].message.content
            logger.debug(f"Perplexity raw response ({len(response_text)} chars): {response_text[:500]}")
            json_data = self.extract_json_from_response(response_text)
            return self.validate_output(json_data, instrument=event.instrument)

        except Exception as e:
            logger.error(f"Perplexity analysis failed: {e}")
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Perplexity analysis error",
                risk_notes="Technical error",
                sources=[],
            )

    def test_connection(self) -> bool:
        try:
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Reply with: OK"}],
                max_tokens=10,
                temperature=0.0,
            )
            return True
        except Exception as e:
            print(f"Perplexity connection test failed: {e}")
            return False
