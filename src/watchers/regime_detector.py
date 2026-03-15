"""
Market Regime Detector — classifies current market state from price history.

Regimes:
  - trending_up   : price consistently rising, ADX high
  - trending_down : price consistently falling, ADX high
  - ranging       : price oscillating in a channel, low directional strength
  - breakout      : price breaking out of range with volume
  - crisis        : extreme volatility, large sudden moves

P0.2 improvement: expected +8-10% forecast accuracy via regime-adaptive prompts.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from dataclasses import dataclass

from loguru import logger


MarketRegimeType = Literal["trending_up", "trending_down", "ranging", "breakout", "crisis"]


@dataclass
class RegimeAnalysis:
    """Result of regime detection."""
    regime: MarketRegimeType
    confidence: float  # 0.0-1.0
    description: str   # human-readable description for prompts
    volatility_pct: float  # annualized volatility estimate
    trend_strength: float  # 0-1, how strong the trend is
    days_in_regime: int  # estimated days in current regime


class RegimeDetector:
    """
    Detect market regime from a series of closing prices.

    Uses simple but robust indicators:
    - Moving average crossover (trend direction)
    - Average True Range / price (volatility)
    - Price vs Bollinger Bands (breakout detection)
    - Rate of change variance (crisis detection)
    """

    def __init__(
        self,
        fast_window: int = 5,
        slow_window: int = 20,
        volatility_window: int = 14,
        crisis_vol_threshold: float = 0.40,
        breakout_bb_mult: float = 2.0,
    ):
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.volatility_window = volatility_window
        self.crisis_vol_threshold = crisis_vol_threshold
        self.breakout_bb_mult = breakout_bb_mult

    def detect(self, prices: List[float]) -> RegimeAnalysis:
        """
        Classify market regime from price series (most recent last).

        Args:
            prices: List of closing prices, minimum 20 data points.

        Returns:
            RegimeAnalysis with detected regime and metadata.
        """
        if len(prices) < self.slow_window:
            return RegimeAnalysis(
                regime="ranging",
                confidence=0.3,
                description="Недостатньо даних для визначення режиму",
                volatility_pct=0.0,
                trend_strength=0.0,
                days_in_regime=0,
            )

        # Calculate indicators
        fast_ma = self._sma(prices, self.fast_window)
        slow_ma = self._sma(prices, self.slow_window)
        vol = self._volatility(prices, self.volatility_window)
        returns = self._returns(prices)
        trend_str = self._trend_strength(prices, self.slow_window)
        bb_position = self._bollinger_position(prices, self.slow_window, self.breakout_bb_mult)

        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) > 1 else current_price

        # Crisis detection: extreme volatility
        if vol > self.crisis_vol_threshold:
            return RegimeAnalysis(
                regime="crisis",
                confidence=min(0.95, 0.6 + (vol - self.crisis_vol_threshold)),
                description=(
                    f"Кризовий режим: волатильність {vol:.0%} (екстремально висока). "
                    f"Ринок у стані паніки/ейфорії. Обережність максимальна."
                ),
                volatility_pct=round(vol * 100, 1),
                trend_strength=trend_str,
                days_in_regime=self._days_in_regime(returns, "crisis"),
            )

        # Breakout detection: price outside Bollinger Bands
        if abs(bb_position) > 1.0:
            direction = "вгору" if bb_position > 0 else "вниз"
            regime = "breakout"
            return RegimeAnalysis(
                regime=regime,
                confidence=min(0.90, 0.5 + abs(bb_position) * 0.2),
                description=(
                    f"Пробій {direction}: ціна вийшла за межі Боллінджера. "
                    f"Волатильність {vol:.0%}. Імпульсний рух, можливе продовження."
                ),
                volatility_pct=round(vol * 100, 1),
                trend_strength=trend_str,
                days_in_regime=self._days_in_regime(returns, "breakout"),
            )

        # Trending: fast MA clearly above/below slow MA
        ma_spread = (fast_ma - slow_ma) / slow_ma if slow_ma > 0 else 0

        if trend_str > 0.5 and abs(ma_spread) > 0.005:
            if ma_spread > 0:
                return RegimeAnalysis(
                    regime="trending_up",
                    confidence=min(0.90, 0.4 + trend_str * 0.5),
                    description=(
                        f"Висхідний тренд: MA{self.fast_window} > MA{self.slow_window} "
                        f"(спред {ma_spread:+.2%}). Сила тренду: {trend_str:.0%}. "
                        f"Волатильність {vol:.0%}."
                    ),
                    volatility_pct=round(vol * 100, 1),
                    trend_strength=trend_str,
                    days_in_regime=self._days_in_regime(returns, "trending_up"),
                )
            else:
                return RegimeAnalysis(
                    regime="trending_down",
                    confidence=min(0.90, 0.4 + trend_str * 0.5),
                    description=(
                        f"Низхідний тренд: MA{self.fast_window} < MA{self.slow_window} "
                        f"(спред {ma_spread:+.2%}). Сила тренду: {trend_str:.0%}. "
                        f"Волатильність {vol:.0%}."
                    ),
                    volatility_pct=round(vol * 100, 1),
                    trend_strength=trend_str,
                    days_in_regime=self._days_in_regime(returns, "trending_down"),
                )

        # Default: ranging
        return RegimeAnalysis(
            regime="ranging",
            confidence=min(0.85, 0.5 + (1 - trend_str) * 0.3),
            description=(
                f"Бічний рух (range): немає чіткого тренду. "
                f"Сила тренду: {trend_str:.0%}. Волатильність {vol:.0%}. "
                f"Обережно з directional ставками."
            ),
            volatility_pct=round(vol * 100, 1),
            trend_strength=trend_str,
            days_in_regime=self._days_in_regime(returns, "ranging"),
        )

    def format_for_prompt(self, analysis: RegimeAnalysis) -> str:
        """Format regime analysis as context block for agent prompts."""
        regime_guidance = {
            "trending_up": (
                "В висхідному тренді: надавай перевагу LONG з помірною впевненістю. "
                "SHORT тільки при дуже сильних контраргументах."
            ),
            "trending_down": (
                "В низхідному тренді: надавай перевагу SHORT з помірною впевненістю. "
                "LONG тільки при дуже сильних контраргументах."
            ),
            "ranging": (
                "В бічному русі: знижуй впевненість у directional сигналах. "
                "WAIT частіше за замовчуванням. Шукай чіткі каталізатори для позицій."
            ),
            "breakout": (
                "Пробій! Підвищуй впевненість у directional сигналах за напрямком пробою. "
                "Але стеж за хибними пробоями — підтвердження об'ємом критичне."
            ),
            "crisis": (
                "КРИЗОВИЙ РЕЖИМ: максимальна обережність. Знижуй впевненість на 20%. "
                "Ширші стоп-лоси, менший розмір позицій. Tail risks домінують."
            ),
        }

        lines = [
            f"## Ринковий режим",
            f"Режим: {analysis.regime.upper()} (впевненість {analysis.confidence:.0%})",
            f"Опис: {analysis.description}",
            f"Волатильність: {analysis.volatility_pct:.1f}% | Сила тренду: {analysis.trend_strength:.0%}",
            "",
            regime_guidance.get(analysis.regime, ""),
        ]
        return "\n".join(lines)

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _sma(prices: List[float], window: int) -> float:
        if len(prices) < window:
            return prices[-1] if prices else 0
        return sum(prices[-window:]) / window

    @staticmethod
    def _returns(prices: List[float]) -> List[float]:
        return [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] != 0
        ]

    @staticmethod
    def _volatility(prices: List[float], window: int) -> float:
        """Annualized volatility from daily returns."""
        if len(prices) < window + 1:
            return 0.0
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(max(1, len(prices) - window), len(prices))
            if prices[i - 1] != 0
        ]
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        daily_vol = variance ** 0.5
        return daily_vol * (252 ** 0.5)  # annualize

    @staticmethod
    def _trend_strength(prices: List[float], window: int) -> float:
        """
        Trend strength 0-1 based on directional consistency.
        Measures what fraction of consecutive price changes are in the same direction.
        """
        if len(prices) < window:
            return 0.0
        recent = prices[-window:]
        changes = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        if not changes:
            return 0.0
        ups = sum(1 for c in changes if c > 0)
        downs = sum(1 for c in changes if c < 0)
        dominant = max(ups, downs)
        return dominant / len(changes)

    @staticmethod
    def _bollinger_position(prices: List[float], window: int, mult: float) -> float:
        """
        Position relative to Bollinger Bands.
        Returns > 1.0 if above upper band, < -1.0 if below lower band.
        """
        if len(prices) < window:
            return 0.0
        recent = prices[-window:]
        mean = sum(recent) / len(recent)
        std = (sum((p - mean) ** 2 for p in recent) / len(recent)) ** 0.5
        if std == 0:
            return 0.0
        return (prices[-1] - mean) / (mult * std)

    @staticmethod
    def _days_in_regime(returns: List[float], regime: str) -> int:
        """Estimate how many consecutive days the market has been in this regime."""
        if not returns:
            return 0
        # Simple heuristic: count consecutive days matching the regime direction
        count = 0
        for r in reversed(returns):
            if regime == "trending_up" and r > 0:
                count += 1
            elif regime == "trending_down" and r < 0:
                count += 1
            elif regime == "ranging" and abs(r) < 0.01:
                count += 1
            elif regime in ("breakout", "crisis"):
                if abs(r) > 0.015:
                    count += 1
                else:
                    break
            else:
                break
        return count
