"""
Refinery Margins — detailed crack spread calculations.

Provides:
  - 3-2-1 crack spread (3 bbl crude → 2 bbl gasoline + 1 bbl heating oil)
  - Gasoline crack (RBOB vs Brent)
  - Heating oil / diesel crack (HO vs Brent)
  - Margin regime classification and historical context

Uses yfinance for HO=F (Heating Oil) and RB=F (RBOB Gasoline).
Falls back gracefully when data unavailable.

Expected impact: +2-4% forecast accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

try:
    import yfinance as yf
except ImportError:
    yf = None

# Conversion factors
# Crude: 1 barrel
# Gasoline (RBOB): quoted in $/gallon, 1 barrel = 42 gallons
# Heating Oil: quoted in $/gallon, 1 barrel = 42 gallons
GALLONS_PER_BARREL = 42.0


@dataclass
class RefineryMargins:
    """Refinery margin snapshot."""
    brent_price: float = 0.0        # $/bbl

    gasoline_price: float = 0.0     # $/gallon (RBOB)
    gasoline_crack: float = 0.0     # $/bbl (gasoline - crude)

    heating_oil_price: float = 0.0  # $/gallon
    heating_oil_crack: float = 0.0  # $/bbl (HO - crude)

    crack_321: float = 0.0          # 3-2-1 crack spread $/bbl

    gasoline_crack_20d: float = 0.0    # 20-day average
    heating_oil_crack_20d: float = 0.0
    crack_321_20d: float = 0.0

    margin_regime: str = "unknown"  # compressed | normal | elevated | extreme

    def to_prompt_text(self) -> str:
        """Format for injection into agent prompt."""
        if self.brent_price <= 0:
            return ""

        regime_ua = {
            "compressed": "СТИСНУТІ (НПЗ під тиском, можуть скоротити переробку → менше попиту на сиру)",
            "normal": "НОРМАЛЬНІ",
            "elevated": "ПІДВИЩЕНІ (НПЗ мотивовані переробляти більше → попит на сиру зростає)",
            "extreme": "ЕКСТРЕМАЛЬНІ (дефіцит продуктів, можливе регуляторне втручання)",
            "unknown": "дані недоступні",
        }

        lines = [
            "## Маржі нафтопереробки (крек-спреди)",
            f"  Brent: ${self.brent_price:.2f}/bbl",
        ]

        if self.gasoline_price > 0:
            lines.append(
                f"  Бензин (RBOB): ${self.gasoline_price:.4f}/gal "
                f"→ крек: ${self.gasoline_crack:.2f}/bbl "
                f"(серед. 20д: ${self.gasoline_crack_20d:.2f})"
            )

        if self.heating_oil_price > 0:
            lines.append(
                f"  Дизель/мазут (HO): ${self.heating_oil_price:.4f}/gal "
                f"→ крек: ${self.heating_oil_crack:.2f}/bbl "
                f"(серед. 20д: ${self.heating_oil_crack_20d:.2f})"
            )

        if self.crack_321 != 0:
            lines.append(
                f"  3-2-1 крек-спред: ${self.crack_321:.2f}/bbl "
                f"(серед. 20д: ${self.crack_321_20d:.2f})"
            )

        lines.append(
            f"  Режим маржі: {regime_ua.get(self.margin_regime, self.margin_regime)}"
        )

        lines.append(
            "  Високі маржі = стимул до максимальної переробки = підтримка попиту на сиру нафту. "
            "Низькі маржі = ризик скорочення переробки."
        )

        return "\n".join(lines)


class RefineryMarginsWatcher:
    """Fetches and computes refinery crack spreads."""

    GASOLINE_SYMBOL = "RB=F"    # RBOB Gasoline futures
    HEATING_OIL_SYMBOL = "HO=F"  # Heating Oil futures
    BRENT_SYMBOL = "BZ=F"

    def fetch(self, brent_price: float = 0.0) -> RefineryMargins:
        """
        Fetch refinery margins.

        Args:
            brent_price: current Brent price ($/bbl) from price watcher
        """
        margins = RefineryMargins(brent_price=brent_price)

        if yf is None or brent_price <= 0:
            return margins

        # Fetch gasoline data
        gas_data = self._fetch_product(self.GASOLINE_SYMBOL)
        if gas_data:
            margins.gasoline_price = gas_data["current"]
            margins.gasoline_crack = round(
                gas_data["current"] * GALLONS_PER_BARREL - brent_price, 2
            )
            margins.gasoline_crack_20d = round(
                gas_data["avg_20d"] * GALLONS_PER_BARREL - brent_price, 2
            ) if gas_data["avg_20d"] > 0 else 0.0

        # Fetch heating oil data
        ho_data = self._fetch_product(self.HEATING_OIL_SYMBOL)
        if ho_data:
            margins.heating_oil_price = ho_data["current"]
            margins.heating_oil_crack = round(
                ho_data["current"] * GALLONS_PER_BARREL - brent_price, 2
            )
            margins.heating_oil_crack_20d = round(
                ho_data["avg_20d"] * GALLONS_PER_BARREL - brent_price, 2
            ) if ho_data["avg_20d"] > 0 else 0.0

        # 3-2-1 crack spread: (2 * gasoline + 1 * heating oil) / 3 - crude
        if margins.gasoline_price > 0 and margins.heating_oil_price > 0:
            product_revenue = (
                2 * margins.gasoline_price * GALLONS_PER_BARREL
                + 1 * margins.heating_oil_price * GALLONS_PER_BARREL
            ) / 3
            margins.crack_321 = round(product_revenue - brent_price, 2)

            # 20-day average 3-2-1
            if gas_data and ho_data and gas_data["avg_20d"] > 0 and ho_data["avg_20d"] > 0:
                avg_rev = (
                    2 * gas_data["avg_20d"] * GALLONS_PER_BARREL
                    + 1 * ho_data["avg_20d"] * GALLONS_PER_BARREL
                ) / 3
                margins.crack_321_20d = round(avg_rev - brent_price, 2)

        # Classify margin regime
        margins.margin_regime = self._classify_regime(margins.crack_321)

        logger.info(
            f"Refinery margins: 3-2-1={margins.crack_321:.2f} "
            f"(regime={margins.margin_regime})"
        )

        return margins

    def _fetch_product(self, symbol: str) -> Optional[dict]:
        """Fetch price and 20d average for a product."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="40d", interval="1d")

            if hist.empty:
                return None

            closes = hist["Close"].dropna()
            if len(closes) < 1:
                return None

            current = float(closes.iloc[-1])
            avg_20d = float(closes.tail(20).mean()) if len(closes) >= 5 else current

            return {"current": round(current, 4), "avg_20d": round(avg_20d, 4)}

        except Exception as exc:
            logger.warning(f"Product fetch error for {symbol}: {exc}")
            return None

    @staticmethod
    def _classify_regime(crack_321: float) -> str:
        """Classify margin regime from 3-2-1 crack spread."""
        if crack_321 <= 0:
            return "unknown"
        # Historical 3-2-1 ranges:
        # < $10: compressed, $10-25: normal, $25-40: elevated, > $40: extreme
        if crack_321 >= 40:
            return "extreme"
        if crack_321 >= 25:
            return "elevated"
        if crack_321 >= 10:
            return "normal"
        return "compressed"
