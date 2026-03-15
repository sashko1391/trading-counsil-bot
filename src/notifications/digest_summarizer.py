"""
Digest Summarizer — uses a lightweight LLM to produce concise Ukrainian
summaries for Telegram digests instead of hard-truncating text.

Uses Gemini Flash (cheapest/fastest) to compress raw theses and risks
into compact, complete sentences that fit Telegram's 4096-char limit.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger


class DigestSummarizer:
    """Summarise raw agent theses/risks into compact Ukrainian text."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        if not api_key:
            self.client = None
            return

        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    @property
    def available(self) -> bool:
        return self.client is not None

    def summarize(
        self,
        theses: list[str],
        risks: list[str],
        instrument: str = "BZ=F",
        trend: str = "WAIT",
    ) -> tuple[list[str], list[str]]:
        """
        Compress theses and risks into concise Ukrainian bullet points.

        Returns (summarized_theses, summarized_risks).
        Falls back to truncation if LLM is unavailable or fails.
        """
        if not self.available or (not theses and not risks):
            return self._fallback(theses, risks)

        theses_block = "\n".join(f"- {t}" for t in theses) if theses else "(немає)"
        risks_block = "\n".join(f"- {r}" for r in risks) if risks else "(немає)"

        prompt = f"""Ти — редактор Telegram-каналу про нафтовий ринок.
Стисни тези та ризики в короткі, але ПОВНІ речення УКРАЇНСЬКОЮ.

Інструмент: {instrument}
Тренд: {trend}

ТЕЗИ (сирі, від AI-агентів):
{theses_block}

РИЗИКИ (сирі, від AI-агентів):
{risks_block}

ПРАВИЛА:
1. Максимум 4 тези, кожна до 100 символів — але речення має бути ЗАВЕРШЕНИМ
2. Максимум 3 ризики, кожен до 90 символів — речення має бути ЗАВЕРШЕНИМ
3. Об'єднуй схожі тези в одну
4. Видаляй дублікати та загальні фрази
5. Пиши ТІЛЬКИ УКРАЇНСЬКОЮ
6. Відповідай ТІЛЬКИ у форматі JSON:

{{"theses": ["теза1", "теза2"], "risks": ["ризик1", "ризик2"]}}

Чистий JSON, без markdown."""

        try:
            from google.genai import types

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                ),
            )

            import json
            text = response.text.strip()
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(text[start:end])
                sum_theses = data.get("theses", [])[:4]
                sum_risks = data.get("risks", [])[:3]
                if sum_theses or sum_risks:
                    logger.debug(f"Digest summarized: {len(sum_theses)} theses, {len(sum_risks)} risks")
                    return sum_theses, sum_risks

        except Exception as e:
            logger.warning(f"Digest summarizer failed, using fallback: {e}")

        return self._fallback(theses, risks)

    @staticmethod
    def _fallback(theses: list[str], risks: list[str]) -> tuple[list[str], list[str]]:
        """Truncate with ellipsis — used when LLM is unavailable."""
        def trunc(s: str, limit: int) -> str:
            if len(s) <= limit:
                return s
            # Find last space before limit to avoid mid-word cut
            cut = s[:limit].rfind(" ")
            if cut < limit // 2:
                cut = limit
            return s[:cut] + "…"

        return (
            [trunc(t, 120) for t in theses[:4]],
            [trunc(r, 100) for r in risks[:3]],
        )
