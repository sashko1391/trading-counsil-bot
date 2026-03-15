"""
Seasonal Context — provides oil market seasonal patterns for current date.

Oil markets have strong seasonal patterns:
  - Q1 (Jan-Mar): Heating oil demand peak, refinery maintenance begins
  - Q2 (Apr-Jun): Refinery turnarounds, pre-driving season buildup
  - Q3 (Jul-Sep): Summer driving season peak, hurricane season
  - Q4 (Oct-Dec): Winter prep, OPEC year-end meetings

P2.9 improvement: expected +2-4% forecast accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class SeasonalContext:
    """Seasonal context for current date."""
    season: str            # e.g. "Q1 — heating demand"
    month_pattern: str     # what typically happens this month
    brent_bias: str        # bullish / bearish / neutral
    gasoil_bias: str       # bullish / bearish / neutral
    key_factors: list[str] # 2-3 seasonal factors to watch
    historical_avg_move: float  # avg monthly Brent move for this month (%)


# Monthly seasonal patterns for oil markets
MONTHLY_PATTERNS: dict[int, dict] = {
    1: {
        "season": "Q1 — пік опалювального сезону",
        "month_pattern": "Січень: зимовий попит на мазут/дизель високий. Refinery runs знижуються після свят. Часто бичачий для gasoil.",
        "brent_bias": "neutral",
        "gasoil_bias": "bullish",
        "key_factors": [
            "Зимовий попит на дизель/мазут (heating oil)",
            "Refinery utilization після свят",
            "Кітайський Новий рік — попит на перевезення",
        ],
        "historical_avg_move": 1.2,
    },
    2: {
        "season": "Q1 — опалювальний сезон + ремонти",
        "month_pattern": "Лютий: опалювальний попит ще сильний. Початок планування весняних ремонтів нафтопереробних заводів.",
        "brent_bias": "neutral",
        "gasoil_bias": "bullish",
        "key_factors": [
            "Залишки зимового попиту",
            "Оголошення про весняні turnarounds",
            "OPEC+ зустріч (часто в лютому-березні)",
        ],
        "historical_avg_move": 0.8,
    },
    3: {
        "season": "Q1→Q2 перехід — весняні ремонти",
        "month_pattern": "Березень: весняні ремонти НПЗ починаються. Попит на опалення знижується. Перехідний період.",
        "brent_bias": "bearish",
        "gasoil_bias": "neutral",
        "key_factors": [
            "Масові turnarounds НПЗ (зниження попиту на сиру нафту)",
            "Зниження опалювального попиту",
            "Перехід до літнього бензину (RVP switch)",
        ],
        "historical_avg_move": -0.5,
    },
    4: {
        "season": "Q2 — весняні ремонти + підготовка до driving season",
        "month_pattern": "Квітень: пік весняних ремонтів НПЗ. Запаси зростають. Ринок дивиться на літній сезон.",
        "brent_bias": "bearish",
        "gasoil_bias": "bearish",
        "key_factors": [
            "Пік turnarounds → менше переробки → зростання запасів сирої",
            "Будівництво запасів бензину до літа",
            "Зазвичай один з найслабших місяців для Brent",
        ],
        "historical_avg_move": -1.0,
    },
    5: {
        "season": "Q2 — передсезонне зростання",
        "month_pattern": "Травень: НПЗ виходять з ремонтів. Попит на бензин зростає. 'Sell in May and go away' іноді працює.",
        "brent_bias": "neutral",
        "gasoil_bias": "neutral",
        "key_factors": [
            "НПЗ відновлюють потужності після turnarounds",
            "Початок driving season (Memorial Day в США)",
            "Посівна кампанія → дизельний попит в с/г",
        ],
        "historical_avg_move": 0.5,
    },
    6: {
        "season": "Q2→Q3 — початок літнього сезону",
        "month_pattern": "Червень: літній driving season набирає обертів. Бензиновий попит на максимумі. Початок сезону ураганів.",
        "brent_bias": "bullish",
        "gasoil_bias": "neutral",
        "key_factors": [
            "Пік бензинового попиту (driving season)",
            "Початок сезону ураганів в Мексиканській затоці",
            "OPEC+ середньорічний огляд квот",
        ],
        "historical_avg_move": 1.5,
    },
    7: {
        "season": "Q3 — пік driving season + урагани",
        "month_pattern": "Липень: максимальний бензиновий попит. Сезон ураганів активний. Часто бичачий для нафти.",
        "brent_bias": "bullish",
        "gasoil_bias": "neutral",
        "key_factors": [
            "Пік driving season → максимальний refinery throughput",
            "Ризик ураганів в Мексиканській затоці",
            "Китайський літній попит на авіаПММ",
        ],
        "historical_avg_move": 1.8,
    },
    8: {
        "season": "Q3 — пізній літній сезон",
        "month_pattern": "Серпень: driving season спадає. Пік сезону ураганів. Нафтопереробники готуються до осінніх ремонтів.",
        "brent_bias": "neutral",
        "gasoil_bias": "neutral",
        "key_factors": [
            "Пік сезону ураганів (серпень-вересень)",
            "Driving season спадає після Labor Day",
            "Планування осінніх turnarounds",
        ],
        "historical_avg_move": 0.3,
    },
    9: {
        "season": "Q3→Q4 — перехід до зими",
        "month_pattern": "Вересень: осінні ремонти НПЗ починаються. Сезон ураганів ще активний. Перехід до дизельного/мазутного попиту.",
        "brent_bias": "bearish",
        "gasoil_bias": "bullish",
        "key_factors": [
            "Осінні turnarounds НПЗ",
            "Перехід від бензину до heating oil",
            "Будівництво зимових запасів дизелю/мазуту",
        ],
        "historical_avg_move": -0.8,
    },
    10: {
        "season": "Q4 — зимова підготовка",
        "month_pattern": "Жовтень: зимовий попит наростає. Gasoil/дизель починають ралі. OPEC зазвичай збирається.",
        "brent_bias": "neutral",
        "gasoil_bias": "bullish",
        "key_factors": [
            "Зростання попиту на дизель/мазут",
            "OPEC+ осіння зустріч (часто жовтень-листопад)",
            "Осінні turnarounds завершуються",
        ],
        "historical_avg_move": 0.5,
    },
    11: {
        "season": "Q4 — опалювальний сезон + OPEC",
        "month_pattern": "Листопад: опалювальний попит зростає. OPEC+ фінальна зустріч року. Часто визначає тренд на зиму.",
        "brent_bias": "neutral",
        "gasoil_bias": "bullish",
        "key_factors": [
            "OPEC+ грудневе рішення по квотах",
            "Зимовий попит на heating oil/diesel",
            "Будівництво запасів для зими",
        ],
        "historical_avg_move": 0.2,
    },
    12: {
        "season": "Q4 — зимовий пік + end-of-year",
        "month_pattern": "Грудень: низька ліквідність в кінці року. Tax-loss selling. Опалювальний попит високий, але обсяги торгів падають.",
        "brent_bias": "bearish",
        "gasoil_bias": "neutral",
        "key_factors": [
            "Низька ліквідність → підвищена волатильність",
            "Tax-loss selling → ведмежий тиск",
            "Зимовий погодний ризик (cold snap = bullish heating)",
        ],
        "historical_avg_move": -0.3,
    },
}


def get_seasonal_context(dt: Optional[date] = None) -> SeasonalContext:
    """Get seasonal context for a given date (defaults to today)."""
    if dt is None:
        dt = date.today()

    month = dt.month
    pattern = MONTHLY_PATTERNS[month]

    return SeasonalContext(
        season=pattern["season"],
        month_pattern=pattern["month_pattern"],
        brent_bias=pattern["brent_bias"],
        gasoil_bias=pattern["gasoil_bias"],
        key_factors=pattern["key_factors"],
        historical_avg_move=pattern["historical_avg_move"],
    )


def format_seasonal_for_prompt(ctx: SeasonalContext) -> str:
    """Format seasonal context for injection into agent prompt."""
    bias_ua = {"bullish": "БИЧАЧИЙ", "bearish": "ВЕДМЕЖИЙ", "neutral": "НЕЙТРАЛЬНИЙ"}

    lines = [
        f"## Сезонний контекст",
        f"Сезон: {ctx.season}",
        f"Патерн: {ctx.month_pattern}",
        f"Сезонний bias: Brent={bias_ua.get(ctx.brent_bias, ctx.brent_bias)}, "
        f"Gasoil={bias_ua.get(ctx.gasoil_bias, ctx.gasoil_bias)}",
        f"Історична середня зміна за цей місяць: {ctx.historical_avg_move:+.1f}%",
        "",
        "Ключові сезонні фактори:",
    ]
    for factor in ctx.key_factors:
        lines.append(f"  • {factor}")

    lines.append("")
    lines.append(
        "Враховуй сезонність, але не переоцінюй — фундаментальні фактори "
        "завжди переважають сезонні патерни."
    )
    return "\n".join(lines)
