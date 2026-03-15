"""
Gemini Agent — Macro & Fundamentals Analyst for Oil Markets
Uses Google GenAI SDK
"""

from google import genai
from google.genai import types
from loguru import logger
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import GEMINI_SYSTEM_PROMPT, format_user_prompt
import json


class GeminiAgent(BaseAgent):
    """
    Gemini as macro-fundamental analyst for oil markets.

    - Focus: seasonal patterns, China demand, inventory trends,
      contango/backwardation, USD correlation, crack spreads
    - API: Google GenAI SDK
    - Model: configurable via settings.GEMINI_MODEL
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialise Gemini agent.

        Args:
            api_key: Google AI Studio API key
            model: model name (default gemini-2.5-flash)
        """
        super().__init__(api_key, "Gemini")

        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY is empty — cannot initialise GeminiAgent")

        self.model_name = model
        self.client = genai.Client(api_key=api_key)

    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Analyse a market event with focus on macro fundamentals.

        Args:
            event: Oil market event
            context: Additional context (historical data, indicators)

        Returns:
            Signal with recommendation
        """
        user_prompt = format_user_prompt(
            event_type=event.event_type,
            instrument=event.instrument,
            market_data=event.data,
            news=context.get("news", "No recent news"),
            indicators=context.get("indicators", {}),
        )

        # Inject agent's own history if available
        agent_history = context.get("agent_history", "")
        if agent_history:
            user_prompt += f"\n\n{agent_history}\n"

        # Gemini does not natively support system messages in the same way,
        # so we prepend the system prompt to the user content.
        full_prompt = f"""{GEMINI_SYSTEM_PROMPT}

{user_prompt}

IMPORTANT: Return a SINGLE JSON object (not an array) for instrument {event.instrument} only.
Respond ONLY with valid JSON (no markdown, no preamble):
{{
    "action": "LONG" | "SHORT" | "WAIT",
    "confidence": 0.0-1.0,
    "thesis": "макс 500 символів УКРАЇНСЬКОЮ — макро/фундаментальне обґрунтування",
    "invalidation_price": number or null,
    "risk_notes": "що може спростувати тезу — УКРАЇНСЬКОЮ",
    "sources": ["url1", "url2"],
    "drivers": ["driver1", "driver2"]
}}
ОБОВ'ЯЗКОВО: thesis та risk_notes писати УКРАЇНСЬКОЮ (uk-UA). Англійський текст = помилка формату.
ОБОВ'ЯЗКОВО: Include 1-3 drivers from the taxonomy in your JSON."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                ),
            )

            response_text = response.text
            logger.debug(f"Gemini raw response ({len(response_text)} chars): {response_text[:500]}")
            json_data = self.extract_json_from_response(response_text)
            return self.validate_output(json_data, instrument=event.instrument)

        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Gemini analysis error",
                risk_notes="Technical error",
                sources=[],
            )

    def test_connection(self) -> bool:
        """Test connectivity to Gemini API."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Reply with: OK",
                config=types.GenerateContentConfig(
                    temperature=0.0,
                ),
            )
            return "OK" in response.text
        except Exception as e:
            print(f"Gemini connection test failed: {e}")
            return False


# ==============================================================================
# MANUAL TEST
# ==============================================================================

if __name__ == "__main__":
    from config.settings import get_settings

    settings = get_settings()

    api_key = settings.GOOGLE_AI_API_KEY or settings.GOOGLE_API_KEY
    if not api_key:
        print("GOOGLE_AI_API_KEY is empty — skipping live test")
        exit(0)

    gemini = GeminiAgent(
        api_key=api_key,
        model=settings.GEMINI_MODEL,
    )
    print(f"GeminiAgent created: {gemini}")

    print("Testing API connection...")
    if gemini.test_connection():
        print("Connection successful!")
    else:
        print("Connection failed")
        exit(1)
