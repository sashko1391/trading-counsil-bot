"""Tests for Refinery Margins Watcher."""

import pytest

from watchers.refinery_margins import (
    RefineryMargins,
    RefineryMarginsWatcher,
    GALLONS_PER_BARREL,
)


class TestRefineryMargins:
    def test_empty_margins_returns_empty_text(self):
        m = RefineryMargins()
        assert m.to_prompt_text() == ""

    def test_basic_margins_text(self):
        m = RefineryMargins(
            brent_price=80.0,
            gasoline_price=2.50,
            gasoline_crack=25.0,
            gasoline_crack_20d=22.0,
            heating_oil_price=2.80,
            heating_oil_crack=37.6,
            heating_oil_crack_20d=35.0,
            crack_321=29.2,
            crack_321_20d=26.3,
            margin_regime="elevated",
        )
        text = m.to_prompt_text()
        assert "Маржі нафтопереробки" in text
        assert "$80.00" in text
        assert "3-2-1" in text
        assert "29.2" in text or "29.20" in text
        assert "ПІДВИЩЕНІ" in text
        assert "попит на сиру зростає" in text

    def test_compressed_margins(self):
        m = RefineryMargins(
            brent_price=85.0,
            crack_321=5.0,
            margin_regime="compressed",
        )
        text = m.to_prompt_text()
        assert "СТИСНУТІ" in text
        assert "скоротити переробку" in text

    def test_extreme_margins(self):
        m = RefineryMargins(
            brent_price=90.0,
            crack_321=55.0,
            margin_regime="extreme",
        )
        text = m.to_prompt_text()
        assert "ЕКСТРЕМАЛЬНІ" in text

    def test_has_guidance_note(self):
        m = RefineryMargins(brent_price=80.0, margin_regime="normal")
        text = m.to_prompt_text()
        assert "Високі маржі" in text


class TestRefineryMarginsClassification:
    def test_unknown_zero(self):
        assert RefineryMarginsWatcher._classify_regime(0.0) == "unknown"

    def test_compressed(self):
        assert RefineryMarginsWatcher._classify_regime(5.0) == "compressed"

    def test_normal(self):
        assert RefineryMarginsWatcher._classify_regime(18.0) == "normal"

    def test_elevated(self):
        assert RefineryMarginsWatcher._classify_regime(30.0) == "elevated"

    def test_extreme(self):
        assert RefineryMarginsWatcher._classify_regime(45.0) == "extreme"

    def test_boundary_10(self):
        assert RefineryMarginsWatcher._classify_regime(10.0) == "normal"

    def test_boundary_25(self):
        assert RefineryMarginsWatcher._classify_regime(25.0) == "elevated"

    def test_boundary_40(self):
        assert RefineryMarginsWatcher._classify_regime(40.0) == "extreme"


class TestCrackSpreadCalculation:
    def test_gallons_per_barrel(self):
        assert GALLONS_PER_BARREL == 42.0

    def test_gasoline_crack_formula(self):
        # Gasoline at $2.50/gal, Brent at $80/bbl
        # Crack = 2.50 * 42 - 80 = 105 - 80 = $25/bbl
        gasoline_gal = 2.50
        brent = 80.0
        crack = gasoline_gal * GALLONS_PER_BARREL - brent
        assert crack == pytest.approx(25.0)

    def test_321_crack_formula(self):
        # 3-2-1: (2 * gasoline_bbl + 1 * HO_bbl) / 3 - crude
        gas_gal = 2.50   # $105/bbl
        ho_gal = 2.80     # $117.6/bbl
        brent = 80.0
        product_rev = (2 * gas_gal * 42 + 1 * ho_gal * 42) / 3
        crack_321 = product_rev - brent
        assert crack_321 == pytest.approx(29.2)
