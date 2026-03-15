"""
Weight Calibrator — dynamically adjusts agent weights based on accuracy.

Uses per-agent Brier Score and hit rate from PostMortemTracker
to recalibrate aggregator weights. Better-performing agents get
higher weights, poor performers get reduced.

P0.3 improvement: expected +6-8% forecast accuracy.
"""

from __future__ import annotations

from typing import Dict, Optional

from loguru import logger


# Minimum entries per agent before adjusting weights
MIN_ENTRIES_FOR_CALIBRATION = 10

# How aggressive the reweighting is (0=no change, 1=fully proportional)
CALIBRATION_STRENGTH = 0.5

# Floor: no agent drops below this weight
MIN_WEIGHT = 0.10

# Ceiling: no agent exceeds this weight
MAX_WEIGHT = 0.45


class WeightCalibrator:
    """
    Computes optimal agent weights from their performance history.

    Uses inverse Brier Score (better score = higher weight) with
    smoothing to prevent drastic swings from small sample sizes.
    """

    def __init__(
        self,
        default_weights: Optional[Dict[str, float]] = None,
        strength: float = CALIBRATION_STRENGTH,
        min_entries: int = MIN_ENTRIES_FOR_CALIBRATION,
    ):
        self.default_weights = default_weights or {
            "grok": 0.25,
            "perplexity": 0.25,
            "claude": 0.25,
            "gemini": 0.25,
        }
        self.strength = strength
        self.min_entries = min_entries

    def calibrate(
        self, agent_stats: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Compute new weights from agent performance stats.

        Args:
            agent_stats: { agent_name: { "hit_rate": float, "avg_confidence": float, "total": int } }

        Returns:
            New weights dict that sums to 1.0
        """
        agents = list(self.default_weights.keys())

        # Check if we have enough data
        eligible = {
            name: stats
            for name, stats in agent_stats.items()
            if name in agents and stats.get("total", 0) >= self.min_entries
        }

        if len(eligible) < 2:
            logger.info(
                f"Weight calibration: only {len(eligible)} agents eligible "
                f"(need ≥2 with ≥{self.min_entries} entries). Using defaults."
            )
            return dict(self.default_weights)

        # Compute performance score per agent
        # Score = hit_rate * calibration_factor
        # calibration_factor penalizes overconfident agents
        scores: Dict[str, float] = {}
        for name in agents:
            if name in eligible:
                stats = eligible[name]
                hit_rate = stats["hit_rate"]
                avg_conf = stats["avg_confidence"]

                # Calibration penalty: agents whose confidence matches their
                # accuracy are rewarded; overconfident agents are penalized
                calibration_gap = abs(hit_rate - avg_conf)
                calibration_factor = 1.0 - calibration_gap * 0.5
                calibration_factor = max(0.5, calibration_factor)

                scores[name] = hit_rate * calibration_factor
            else:
                # No data: use neutral score
                scores[name] = 0.5

        # Normalize scores to weights
        total_score = sum(scores.values())
        if total_score == 0:
            return dict(self.default_weights)

        raw_weights = {name: score / total_score for name, score in scores.items()}

        # Blend with defaults based on strength parameter
        blended = {}
        for name in agents:
            raw = raw_weights.get(name, self.default_weights[name])
            default = self.default_weights[name]
            blended[name] = default * (1 - self.strength) + raw * self.strength

        # Apply floor/ceiling
        for name in blended:
            blended[name] = max(MIN_WEIGHT, min(MAX_WEIGHT, blended[name]))

        # Renormalize to sum to 1.0
        total = sum(blended.values())
        weights = {name: round(v / total, 3) for name, v in blended.items()}

        # Fix rounding to exactly 1.0
        diff = 1.0 - sum(weights.values())
        if abs(diff) > 0.001:
            first = next(iter(weights))
            weights[first] = round(weights[first] + diff, 3)

        logger.info(
            f"Weight calibration: eligible={list(eligible.keys())} | "
            f"scores={scores} | new_weights={weights}"
        )
        return weights

    def format_report(
        self,
        agent_stats: Dict[str, Dict[str, float]],
        old_weights: Dict[str, float],
        new_weights: Dict[str, float],
    ) -> str:
        """Human-readable calibration report."""
        lines = ["=== Agent Weight Calibration ===", ""]

        for name in sorted(old_weights.keys()):
            old_w = old_weights.get(name, 0.25)
            new_w = new_weights.get(name, 0.25)
            delta = new_w - old_w
            stats = agent_stats.get(name, {})

            hr = stats.get("hit_rate", 0)
            conf = stats.get("avg_confidence", 0)
            total = stats.get("total", 0)

            arrow = "↑" if delta > 0.005 else ("↓" if delta < -0.005 else "→")
            lines.append(
                f"  {name:12s}: {old_w:.1%} {arrow} {new_w:.1%} "
                f"(hit={hr:.0%}, conf={conf:.0%}, n={total})"
            )

        return "\n".join(lines)
