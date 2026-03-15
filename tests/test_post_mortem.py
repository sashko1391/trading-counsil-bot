"""Tests for Post-Mortem Feedback system."""

import pytest
from pathlib import Path
from metrics.post_mortem import PostMortemTracker, PostMortemEntry


@pytest.fixture
def tracker(tmp_path):
    return PostMortemTracker(path=tmp_path / "pm.json")


class TestPostMortemTracker:
    def test_record_outcome_correct(self, tracker):
        entry = tracker.record_outcome(
            agent_name="grok",
            instrument="BZ=F",
            event_type="price_spike",
            predicted_action="LONG",
            predicted_confidence=0.8,
            thesis="Test thesis",
            entry_price=80.0,
            actual_price=82.0,
        )
        assert entry.was_correct is True
        assert entry.price_change_pct > 0

    def test_record_outcome_wrong(self, tracker):
        entry = tracker.record_outcome(
            agent_name="claude",
            instrument="BZ=F",
            event_type="eia_report",
            predicted_action="LONG",
            predicted_confidence=0.75,
            thesis="Expected inventory draw",
            entry_price=80.0,
            actual_price=78.0,
            missed_factor="Imports surged unexpectedly",
        )
        assert entry.was_correct is False
        assert entry.missed_factor == "Imports surged unexpectedly"

    def test_wait_correct_when_flat(self, tracker):
        entry = tracker.record_outcome(
            agent_name="perplexity",
            instrument="LGO",
            event_type="news_event",
            predicted_action="WAIT",
            predicted_confidence=0.6,
            thesis="No clear signal",
            entry_price=700.0,
            actual_price=703.0,  # < 1% move
        )
        assert entry.was_correct is True

    def test_persistence(self, tracker, tmp_path):
        tracker.record_outcome(
            agent_name="grok",
            instrument="BZ=F",
            event_type="price_spike",
            predicted_action="LONG",
            predicted_confidence=0.8,
            thesis="Test",
            entry_price=80.0,
            actual_price=82.0,
        )
        # Reload
        tracker2 = PostMortemTracker(path=tmp_path / "pm.json")
        entries = tracker2.get_for_agent("grok", "BZ=F")
        assert len(entries) == 1

    def test_format_for_prompt(self, tracker):
        for i in range(3):
            tracker.record_outcome(
                agent_name="gemini",
                instrument="BZ=F",
                event_type="eia_report",
                predicted_action="LONG" if i % 2 == 0 else "SHORT",
                predicted_confidence=0.7,
                thesis=f"Test thesis {i}",
                entry_price=80.0,
                actual_price=82.0 if i % 2 == 0 else 78.0,
            )
        text = tracker.format_for_prompt("gemini", "BZ=F")
        assert "Точність" in text
        assert "ВІРНО" in text or "НЕВІРНО" in text

    def test_format_empty(self, tracker):
        text = tracker.format_for_prompt("unknown", "BZ=F")
        assert text == ""

    def test_filter_by_event_type(self, tracker):
        tracker.record_outcome(
            agent_name="grok", instrument="BZ=F", event_type="eia_report",
            predicted_action="LONG", predicted_confidence=0.7,
            thesis="EIA", entry_price=80, actual_price=82,
        )
        tracker.record_outcome(
            agent_name="grok", instrument="BZ=F", event_type="price_spike",
            predicted_action="SHORT", predicted_confidence=0.6,
            thesis="Spike", entry_price=80, actual_price=78,
        )
        eia_only = tracker.get_for_agent("grok", "BZ=F", "eia_report")
        assert len(eia_only) == 1
        assert eia_only[0].event_type == "eia_report"

    def test_agent_stats(self, tracker):
        for correct in [True, True, False]:
            actual = 82.0 if correct else 78.0
            tracker.record_outcome(
                agent_name="grok", instrument="BZ=F",
                event_type="price_spike",
                predicted_action="LONG", predicted_confidence=0.7,
                thesis="Test", entry_price=80.0, actual_price=actual,
            )
        stats = tracker.get_agent_stats()
        assert "grok" in stats
        assert abs(stats["grok"]["hit_rate"] - 2 / 3) < 0.01
