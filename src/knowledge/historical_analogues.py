"""
Historical Analogues — matches current events to past oil market episodes.

Provides agents with historical precedent for similar situations,
including price impact, duration, and key differences.

P1.8 improvement: expected +7-9% forecast accuracy.
"""

from __future__ import annotations

from typing import List, Optional

from models.schemas import HistoricalAnalogue, MarketEvent


# ── Oil market historical episodes database ──────────────────────────────────

HISTORICAL_EPISODES: List[dict] = [
    # OPEC events
    {
        "event_name": "OPEC+ 2M bpd Cut",
        "year": 2022,
        "trigger": "OPEC+ announced 2M bpd production cut",
        "keywords": ["opec", "cut", "production"],
        "event_types": ["opec_event", "news_event"],
        "price_impact_pct": 8.5,
        "duration_days": 14,
        "resolution": "Brent rallied from $84 to $93 in 2 weeks",
        "key_difference": "Macro environment (recession fears vs current context)",
    },
    {
        "event_name": "OPEC+ Price War 2020",
        "year": 2020,
        "trigger": "Saudi-Russia price war after failed OPEC+ deal",
        "keywords": ["opec", "price war", "saudi", "russia"],
        "event_types": ["opec_event", "news_event", "geopolitical_alert"],
        "price_impact_pct": -45.0,
        "duration_days": 30,
        "resolution": "Brent crashed from $50 to $27, then OPEC+ agreed record 9.7M bpd cut",
        "key_difference": "COVID demand destruction amplified supply shock",
    },
    {
        "event_name": "OPEC Surprise No-Cut 2014",
        "year": 2014,
        "trigger": "OPEC refused to cut despite oversupply, defending market share",
        "keywords": ["opec", "no cut", "market share", "oversupply"],
        "event_types": ["opec_event"],
        "price_impact_pct": -40.0,
        "duration_days": 180,
        "resolution": "Brent fell from $85 to $50 over 6 months",
        "key_difference": "US shale boom was the structural driver",
    },
    # Geopolitical events
    {
        "event_name": "Russia-Ukraine Invasion",
        "year": 2022,
        "trigger": "Russian full-scale invasion of Ukraine",
        "keywords": ["russia", "ukraine", "invasion", "war", "sanctions"],
        "event_types": ["geopolitical_alert", "news_event"],
        "price_impact_pct": 30.0,
        "duration_days": 21,
        "resolution": "Brent spiked from $96 to $128, then gradually retreated",
        "key_difference": "SPR release and demand destruction capped upside",
    },
    {
        "event_name": "Iran Sanctions Reimposed",
        "year": 2018,
        "trigger": "US withdrew from Iran nuclear deal, reimposed oil sanctions",
        "keywords": ["iran", "sanctions", "nuclear"],
        "event_types": ["geopolitical_alert", "news_event"],
        "price_impact_pct": 15.0,
        "duration_days": 60,
        "resolution": "Brent rose from $70 to $85 as Iranian exports fell 1.5M bpd",
        "key_difference": "Waivers to major importers softened impact",
    },
    {
        "event_name": "Strait of Hormuz Tanker Attacks",
        "year": 2019,
        "trigger": "Attacks on oil tankers in Strait of Hormuz",
        "keywords": ["hormuz", "tanker", "attack", "strait"],
        "event_types": ["geopolitical_alert", "tanker_alert"],
        "price_impact_pct": 4.0,
        "duration_days": 5,
        "resolution": "Brief spike then fade — no sustained supply disruption",
        "key_difference": "Market has become desensitized to Hormuz threats",
    },
    {
        "event_name": "Saudi Aramco Attack (Abqaiq)",
        "year": 2019,
        "trigger": "Drone attack on Abqaiq processing facility, 5.7M bpd offline",
        "keywords": ["saudi", "aramco", "abqaiq", "attack", "drone"],
        "event_types": ["geopolitical_alert", "news_event"],
        "price_impact_pct": 15.0,
        "duration_days": 3,
        "resolution": "Brent jumped 15% in one day, fully reversed in 2 weeks",
        "key_difference": "Saudi restored production faster than expected",
    },
    # EIA / Inventory events
    {
        "event_name": "Record EIA Crude Draw (2023)",
        "year": 2023,
        "trigger": "EIA reported 17M bbl crude draw, largest in months",
        "keywords": ["eia", "draw", "inventory", "crude"],
        "event_types": ["eia_report"],
        "price_impact_pct": 3.5,
        "duration_days": 7,
        "resolution": "Brent rose $3 then consolidated",
        "key_difference": "Seasonal maintenance was key driver, not structural deficit",
    },
    {
        "event_name": "SPR Release 180M bbl",
        "year": 2022,
        "trigger": "US announced 180M bbl Strategic Petroleum Reserve release",
        "keywords": ["spr", "release", "strategic", "reserve"],
        "event_types": ["news_event", "eia_report"],
        "price_impact_pct": -15.0,
        "duration_days": 90,
        "resolution": "Brent fell from $120 to $100 over 3 months",
        "key_difference": "SPR now at lowest level since 1984",
    },
    # Demand events
    {
        "event_name": "China Zero-COVID Lockdowns",
        "year": 2022,
        "trigger": "Shanghai lockdown, China PMI collapsed below 47",
        "keywords": ["china", "lockdown", "pmi", "demand"],
        "event_types": ["news_event", "scheduled_event"],
        "price_impact_pct": -10.0,
        "duration_days": 45,
        "resolution": "Brent fell $10 as China demand dropped 1.5M bpd",
        "key_difference": "China no longer has zero-COVID policy",
    },
    {
        "event_name": "China Reopening Rally",
        "year": 2023,
        "trigger": "China abandoned zero-COVID, demand recovery expectations",
        "keywords": ["china", "reopening", "demand", "recovery"],
        "event_types": ["news_event"],
        "price_impact_pct": 8.0,
        "duration_days": 30,
        "resolution": "Brent rallied from $78 to $86 on reopening optimism",
        "key_difference": "Recovery was slower than expected",
    },
    # Price structure events
    {
        "event_name": "Brent Contango Blowout 2020",
        "year": 2020,
        "trigger": "COVID demand crash, storage filling up, super contango",
        "keywords": ["contango", "storage", "spread", "curve"],
        "event_types": ["spread_change", "price_spike"],
        "price_impact_pct": -25.0,
        "duration_days": 60,
        "resolution": "Record contango of $13 M1-M6, storage trade of the decade",
        "key_difference": "Current storage levels much lower",
    },
    {
        "event_name": "Gasoil Crack Surge (2022 Diesel Crisis)",
        "year": 2022,
        "trigger": "European diesel shortage post-Russia sanctions",
        "keywords": ["gasoil", "diesel", "crack", "spread", "refinery"],
        "event_types": ["spread_change", "news_event"],
        "price_impact_pct": 40.0,
        "duration_days": 90,
        "resolution": "Gasoil crack hit $60/bbl, 3x normal level",
        "key_difference": "New refinery capacity has since come online",
    },
    # Weather / seasonal
    {
        "event_name": "Hurricane Ida Refinery Shutdown",
        "year": 2021,
        "trigger": "Hurricane Ida shut 2M bpd Gulf Coast refining capacity",
        "keywords": ["hurricane", "weather", "refinery", "gulf"],
        "event_types": ["weather_event", "news_event"],
        "price_impact_pct": 5.0,
        "duration_days": 21,
        "resolution": "Products spiked, crude dipped due to reduced processing demand",
        "key_difference": "Product vs crude divergence is the key",
    },
]


class HistoricalAnalogueFinder:
    """
    Matches current market events to historical episodes.

    Uses keyword matching and event type overlap to find similar past situations.
    """

    def __init__(self, episodes: Optional[List[dict]] = None):
        self.episodes = episodes or HISTORICAL_EPISODES

    def find(
        self,
        event: MarketEvent,
        headline: str = "",
        max_results: int = 3,
    ) -> List[HistoricalAnalogue]:
        """
        Find historical analogues for a given market event.

        Args:
            event: Current market event
            headline: Optional headline/description text for better matching
            max_results: Maximum number of analogues to return

        Returns:
            List of HistoricalAnalogue sorted by similarity score
        """
        search_text = (
            f"{event.event_type} {event.instrument} {headline} "
            f"{event.headline}"
        ).lower()

        scored: List[tuple[float, dict]] = []

        for ep in self.episodes:
            score = 0.0

            # Event type match (strong signal)
            type_overlap = len(
                set(ep["event_types"]) & {event.event_type}
            )
            score += type_overlap * 0.4

            # Keyword match
            keywords_found = sum(
                1 for kw in ep["keywords"]
                if kw.lower() in search_text
            )
            total_keywords = len(ep["keywords"])
            if total_keywords > 0:
                score += (keywords_found / total_keywords) * 0.5

            # Trigger text similarity (basic word overlap)
            trigger_words = set(ep["trigger"].lower().split())
            search_words = set(search_text.split())
            if trigger_words:
                word_overlap = len(trigger_words & search_words) / len(trigger_words)
                score += word_overlap * 0.1

            if score > 0.1:
                scored.append((score, ep))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[HistoricalAnalogue] = []
        for score, ep in scored[:max_results]:
            results.append(
                HistoricalAnalogue(
                    event_name=ep["event_name"],
                    year=ep["year"],
                    trigger=ep["trigger"],
                    similarity_score=round(min(score, 1.0), 2),
                    price_impact_pct=ep["price_impact_pct"],
                    duration_days=ep["duration_days"],
                    resolution=ep["resolution"],
                    key_difference=ep["key_difference"],
                )
            )

        return results

    def format_for_prompt(
        self,
        analogues: List[HistoricalAnalogue],
    ) -> str:
        """Format historical analogues as context block for agent prompts."""
        if not analogues:
            return ""

        lines = [
            "## Історичні аналогії",
            "Схожі ситуації в минулому (від найбільш до найменш схожих):",
            "",
        ]
        for a in analogues:
            lines.append(
                f"• {a.event_name} ({a.year}): схожість {a.similarity_score:.0%}"
            )
            lines.append(f"  Тригер: {a.trigger}")
            lines.append(f"  Вплив на ціну: {a.price_impact_pct:+.1f}% за {a.duration_days} днів")
            lines.append(f"  Результат: {a.resolution}")
            lines.append(f"  Ключова різниця з сьогодні: {a.key_difference}")
            lines.append("")

        lines.append(
            "Враховуй ці прецеденти, але пам'ятай про ключові різниці. "
            "Історія не повторюється, але часто римується."
        )
        return "\n".join(lines)
