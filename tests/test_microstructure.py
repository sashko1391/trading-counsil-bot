"""Tests for Market Microstructure provider."""

import pytest
from watchers.microstructure import MicrostructureData, MicrostructureProvider


class TestMicrostructureData:
    def test_to_prompt_text_basic(self):
        data = MicrostructureData(
            instrument="BZ=F",
            front_month_price=80.0,
            second_month_price=81.0,
            sixth_month_price=83.0,
            m1_m2_spread=-1.0,
            m1_m6_spread=-3.0,
            curve_shape="contango",
            volume_ratio=1.3,
        )
        text = data.to_prompt_text()
        assert "BZ=F" in text
        assert "$80.00" in text
        assert "контанго" in text
        assert "нормальний" in text  # vol ratio 1.3 is normal

    def test_to_prompt_text_backwardation(self):
        data = MicrostructureData(
            instrument="BZ=F",
            front_month_price=85.0,
            m1_m6_spread=3.0,
            curve_shape="backwardation",
        )
        text = data.to_prompt_text()
        assert "бекуордація" in text

    def test_to_prompt_text_high_volume(self):
        data = MicrostructureData(
            instrument="BZ=F",
            front_month_price=80.0,
            volume_ratio=2.5,
        )
        text = data.to_prompt_text()
        assert "підвищений" in text

class TestMicrostructureProvider:
    def test_format_for_prompt_empty(self):
        provider = MicrostructureProvider()
        text = provider.format_for_prompt({})
        assert text == ""

    def test_format_for_prompt_with_data(self):
        provider = MicrostructureProvider()
        data = {
            "BZ=F": MicrostructureData(instrument="BZ=F", front_month_price=80.0),
        }
        text = provider.format_for_prompt(data)
        assert "Мікроструктура" in text
        assert "BZ=F" in text
