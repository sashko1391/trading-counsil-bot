"""Tests for CFTC COT Client."""

import pytest
from watchers.cot_client import COTPosition, COTData, COTClient


class TestCOTPosition:
    def test_empty_position_returns_empty_text(self):
        pos = COTPosition(contract_name="WTI")
        assert pos.to_prompt_text() == ""

    def test_basic_position_text(self):
        pos = COTPosition(
            contract_name="WTI",
            report_date="2026-03-10",
            mm_long=350000,
            mm_short=120000,
            mm_net=230000,
            mm_net_change=15000,
            prod_long=200000,
            prod_short=350000,
            prod_net=-150000,
            open_interest=2000000,
            mm_net_pct_oi=11.5,
            percentile_52w=72.0,
        )
        text = pos.to_prompt_text()
        assert "WTI" in text
        assert "230,000" in text or "230000" in text
        assert "2026-03-10" in text
        assert "72%" in text
        assert "НЕЙТРАЛЬНИЙ" in text

    def test_extreme_long_position(self):
        pos = COTPosition(
            contract_name="Brent",
            report_date="2026-03-10",
            mm_net=400000,
            open_interest=2000000,
            mm_net_pct_oi=20.0,
            percentile_52w=95.0,
        )
        text = pos.to_prompt_text()
        assert "ЕКСТРЕМАЛЬНО ДОВГИЙ" in text
        assert "розворот" in text

    def test_extreme_short_position(self):
        pos = COTPosition(
            contract_name="WTI",
            report_date="2026-03-10",
            mm_net=-50000,
            open_interest=2000000,
            mm_net_pct_oi=-2.5,
            percentile_52w=5.0,
        )
        text = pos.to_prompt_text()
        assert "ЕКСТРЕМАЛЬНО КОРОТКИЙ" in text
        assert "short squeeze" in text

    def test_strong_long_buildup(self):
        pos = COTPosition(
            contract_name="WTI",
            report_date="2026-03-10",
            mm_net=300000,
            mm_net_change=12000,
            open_interest=2000000,
            percentile_52w=60.0,
        )
        text = pos.to_prompt_text()
        assert "нарощування лонгів" in text

    def test_strong_short_buildup(self):
        pos = COTPosition(
            contract_name="Brent",
            report_date="2026-03-10",
            mm_net=100000,
            mm_net_change=-8000,
            open_interest=1500000,
            percentile_52w=40.0,
        )
        text = pos.to_prompt_text()
        assert "скорочення лонгів" in text


class TestCOTData:
    def test_empty_data_returns_empty_text(self):
        data = COTData()
        assert data.to_prompt_text() == ""

    def test_data_with_positions(self):
        data = COTData(
            positions={
                "WTI": COTPosition(
                    contract_name="WTI",
                    report_date="2026-03-10",
                    mm_net=200000,
                    open_interest=2000000,
                    percentile_52w=60.0,
                ),
            }
        )
        text = data.to_prompt_text()
        assert "CFTC" in text
        assert "WTI" in text

    def test_extreme_position_warning(self):
        data = COTData(
            positions={
                "WTI": COTPosition(
                    contract_name="WTI",
                    mm_net=500000,
                    open_interest=2000000,
                    percentile_52w=92.0,
                ),
            }
        )
        text = data.to_prompt_text()
        assert "Екстремальне позиціонування" in text

    def test_no_warning_normal_positions(self):
        data = COTData(
            positions={
                "WTI": COTPosition(
                    contract_name="WTI",
                    mm_net=200000,
                    open_interest=2000000,
                    percentile_52w=50.0,
                ),
            }
        )
        text = data.to_prompt_text()
        assert "Екстремальне" not in text


class TestCOTClientCache:
    def test_client_creates(self):
        client = COTClient()
        assert client._cache is None
        assert client._cache_time is None
