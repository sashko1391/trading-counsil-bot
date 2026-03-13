"""
Grok Agent — Real-time Sentiment & News Hunter for Oil Markets
Uses xAI API (OpenAI-compatible SDK) with manual JSON parsing
"""

from openai import OpenAI
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import GROK_SYSTEM_PROMPT, format_user_prompt


class GrokAgent(BaseAgent):
    """
    Grok as real-time sentiment hunter for oil markets.

    - Focus: X/Twitter oil journalists, OPEC rumours, geopolitical flash points
    - API: xAI via OpenAI-compatible SDK
    - Model: configurable (default grok-3)
    """

    def __init__(self, api_key: str, model: str = "grok-3"):
        super().__init__(api_key, "Grok")

        if not api_key:
            raise ValueError("XAI_API_KEY is empty — cannot initialise GrokAgent")

        self.model_name = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
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
    "thesis": "max 500 chars",
    "invalidation_price": number or null,
    "risk_notes": "what could go wrong",
    "sources": ["url1"]
}}
Pure JSON only — no markdown, no preamble."""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": GROK_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
                temperature=0.2,
            )

            response_text = response.choices[0].message.content
            json_data = self.extract_json_from_response(response_text)
            return self.validate_output(json_data, instrument=event.instrument)

        except Exception as e:
            print(f"Grok analysis failed: {e}")
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Grok analysis error",
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
            print(f"Grok connection test failed: {e}")
            return False
