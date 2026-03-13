"""
Claude Agent — Risk Assessment CFO for Oil Markets
Uses Anthropic SDK with manual JSON parsing
"""

import json
from anthropic import Anthropic
from loguru import logger
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import CLAUDE_SYSTEM_PROMPT, format_user_prompt


class ClaudeAgent(BaseAgent):
    """
    Claude as Chief Risk Officer of the oil trading council.

    - Focus: contango risk, crack spreads, OPEC compliance, geopolitical premium,
      demand destruction, invalidation scenarios
    - API: Anthropic SDK
    - Model: configurable via settings.CLAUDE_MODEL
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        super().__init__(api_key, "Claude")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is empty — cannot initialise ClaudeAgent")

        self.model_name = model
        self.client = Anthropic(api_key=api_key)

    def analyze(self, event: MarketEvent, context: dict) -> Signal:
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
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1000,
                system=CLAUDE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )

            response_text = response.content[0].text
            logger.debug(f"Claude raw response ({len(response_text)} chars): {response_text[:500]}")
            json_data = self.extract_json_from_response(response_text)
            return self.validate_output(json_data, instrument=event.instrument)

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Analysis error",
                risk_notes="Technical error",
                sources=[],
            )

    def test_connection(self) -> bool:
        try:
            self.client.messages.create(
                model=self.model_name,
                max_tokens=50,
                messages=[{"role": "user", "content": "Reply with: OK"}],
                temperature=0.0,
            )
            return True
        except Exception as e:
            print(f"Claude connection test failed: {e}")
            return False
