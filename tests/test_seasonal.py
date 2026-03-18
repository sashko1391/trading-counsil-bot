"""Tests for Seasonal Context (P2.9)."""

import pytest
from datetime import date

from watchers.seasonal import (
    get_seasonal_context,
    format_seasonal_for_prompt,
    MONTHLY_PATTERNS,
    SeasonalContext,
)


class TestSeasonalContext:
    def test_all_months_defined(self):
        for month in range(1, 13):
            assert month in MONTHLY_PATTERNS

    def test_get_seasonal_context_january(self):
        ctx = get_seasonal_context(date(2026, 1, 15))
        assert ctx.season == "Q1 — пік опалювального сезону"
        assert ctx.brent_bias == "neutral"
        assert len(ctx.key_factors) >= 2

    def test_get_seasonal_context_july(self):
        ctx = get_seasonal_context(date(2026, 7, 1))
        assert "driving season" in ctx.season.lower() or "Q3" in ctx.season
        assert ctx.brent_bias == "bullish"

    def test_get_seasonal_context_december(self):
        ctx = get_seasonal_context(date(2026, 12, 25))
        assert ctx.brent_bias == "bearish"
        assert ctx.historical_avg_move < 0

    def test_get_seasonal_context_defaults_to_today(self):
        ctx = get_seasonal_context()
        today = date.today()
        expected = MONTHLY_PATTERNS[today.month]
        assert ctx.season == expected["season"]

    def test_format_seasonal_for_prompt(self):
        ctx = SeasonalContext(
            season="Q3 — пік driving season",
            month_pattern="Липень: максимальний бензиновий попит.",
            brent_bias="bullish",
            key_factors=["Пік driving season", "Ризик ураганів"],
            historical_avg_move=1.8,
        )
        text = format_seasonal_for_prompt(ctx)
        assert "Сезонний контекст" in text
        assert "БИЧАЧИЙ" in text
        assert "+1.8%" in text
        assert "Пік driving season" in text
        assert "Ризик ураганів" in text

    def test_format_seasonal_bearish(self):
        ctx = get_seasonal_context(date(2026, 4, 10))
        text = format_seasonal_for_prompt(ctx)
        assert "ВЕДМЕЖИЙ" in text

    def test_format_seasonal_has_disclaimer(self):
        ctx = get_seasonal_context(date(2026, 6, 1))
        text = format_seasonal_for_prompt(ctx)
        assert "не переоцінюй" in text

    def test_historical_avg_move_types(self):
        for month, pattern in MONTHLY_PATTERNS.items():
            assert isinstance(pattern["historical_avg_move"], (int, float))
            assert isinstance(pattern["brent_bias"], str)
            assert pattern["brent_bias"] in ("bullish", "bearish", "neutral")
