"""
Tests for Trade Journal
Verifies save, load, PnL, and statistics
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from journal.trade_journal import TradeJournal
from models.schemas import Signal, MarketEvent, RiskCheck
from council.aggregator import Aggregator


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def tmp_journal():
    """Creates journal with temporary file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = TradeJournal(journal_path=Path(tmpdir) / "test_trades.json")
        yield journal


@pytest.fixture
def sample_event():
    """Test event"""
    return MarketEvent(
        event_type="price_spike",
        instrument="BZ=F",
        severity=0.8,
        data={"price_change": 5.0, "current_price": 82.50}
    )


@pytest.fixture
def sample_response(sample_event):
    """Test council response"""
    signal = Signal(
        action="LONG", confidence=0.8,
        thesis="Test setup",
        invalidation_price=78.0,
        risk_notes="Test risk",
        sources=[]
    )

    aggregator = Aggregator()
    return aggregator.aggregate(
        event=sample_event,
        grok=signal, perplexity=signal,
        claude=signal, gemini=signal,
        prompt_hash="test_hash"
    )


@pytest.fixture
def sample_risk_check():
    """Test risk check"""
    return RiskCheck(
        allowed=True,
        reason="All checks passed",
        daily_alerts_count=1,
        cooldown_remaining_sec=0,
    )


# ==============================================================================
# TESTS
# ==============================================================================

def test_create_empty_journal(tmp_journal):
    """Creating an empty journal"""
    assert len(tmp_journal) == 0
    print("Empty journal created")


def test_add_entry(tmp_journal, sample_event, sample_response, sample_risk_check):
    """Adding an entry"""
    entry_id = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)

    assert entry_id is not None
    assert len(tmp_journal) == 1
    print(f"Entry added: {entry_id}")


def test_persistence(sample_event, sample_response, sample_risk_check):
    """Data persists to and loads from file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.json"

        # Write
        journal1 = TradeJournal(journal_path=path)
        journal1.add_entry(sample_event, sample_response, sample_risk_check)
        assert len(journal1) == 1

        # Read in new instance
        journal2 = TradeJournal(journal_path=path)
        assert len(journal2) == 1

    print("Persistence works")


def test_update_entry(tmp_journal, sample_event, sample_response, sample_risk_check):
    """Updating an entry (PnL, decision)"""
    entry_id = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)

    # Update
    result = tmp_journal.update_entry(
        entry_id,
        your_decision="LONG",
        entry_price=82.50,
        exit_price=84.50,
        pnl=0.02,
        outcome="Win!",
        lessons_learned="Good trade"
    )

    assert result is True

    # Verify
    recent = tmp_journal.get_recent(1)
    assert recent[0]["pnl"] == 0.02
    assert recent[0]["your_decision"] == "LONG"

    print("Entry updated")


def test_update_nonexistent(tmp_journal):
    """Updating a nonexistent entry"""
    result = tmp_journal.update_entry("fake_id", pnl=0.01)
    assert result is False
    print("Nonexistent update handled")


def test_daily_pnl(tmp_journal, sample_event, sample_response, sample_risk_check):
    """Calculating daily PnL"""
    id1 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)
    id2 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)
    id3 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)

    # Update PnL
    tmp_journal.update_entry(id1, pnl=0.02)   # +2%
    tmp_journal.update_entry(id2, pnl=-0.01)  # -1%
    tmp_journal.update_entry(id3, pnl=0.005)  # +0.5%

    daily_pnl = tmp_journal.get_daily_pnl()

    assert abs(daily_pnl - 0.015) < 0.001  # +1.5%
    print(f"Daily PnL: {daily_pnl:.3%}")


def test_get_recent(tmp_journal, sample_event, sample_response, sample_risk_check):
    """Getting recent entries"""
    for _ in range(5):
        tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)

    recent = tmp_journal.get_recent(3)
    assert len(recent) == 3

    # Verify newest is first
    assert recent[0]["timestamp"] >= recent[-1]["timestamp"]

    print("Recent entries retrieved")


def test_get_stats(tmp_journal, sample_event, sample_response, sample_risk_check):
    """Journal statistics"""
    id1 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)
    id2 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)
    id3 = tmp_journal.add_entry(sample_event, sample_response, sample_risk_check)

    tmp_journal.update_entry(id1, pnl=0.03)
    tmp_journal.update_entry(id2, pnl=-0.01)
    # id3 without PnL -- open position

    stats = tmp_journal.get_stats()

    assert stats["total_entries"] == 3
    assert stats["total_trades"] == 2  # Only with PnL
    assert stats["win_rate"] == 0.5  # 1 win / 2 trades
    assert abs(stats["total_pnl"] - 0.02) < 0.001

    print(f"Stats: {stats}")


def test_empty_stats(tmp_journal):
    """Stats on empty journal"""
    stats = tmp_journal.get_stats()

    assert stats["total_entries"] == 0
    assert stats["total_trades"] == 0
    assert stats["win_rate"] == 0.0

    print("Empty stats handled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
