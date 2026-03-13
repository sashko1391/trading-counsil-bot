"""
Tests for ScheduledEventsManager — recurring oil-market calendar events.
Phase 3B: 11 events (6 original + 5 new).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.watchers.scheduled_events import ScheduledEventsManager, ET


# ============================================================
# Helpers
# ============================================================

def make_now(year, month, day, hour=12, minute=0):
    """Create a timezone-aware datetime in ET."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=ET)


# ============================================================
# Upcoming events detection (original 6)
# ============================================================

class TestUpcomingEvents:
    def test_wednesday_eia_shows_up(self):
        """On a Monday, the EIA report on Wednesday should appear in 50h lookahead."""
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=50)
        names = [e["name"] for e in events]
        assert "EIA Weekly Petroleum Status" in names

    def test_tuesday_api_shows_up(self):
        """On a Monday, the API report on Tuesday should appear in 48h."""
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=48)
        names = [e["name"] for e in events]
        assert "API Private Inventory Report" in names

    def test_friday_baker_hughes_shows_up(self):
        """On a Monday, Baker Hughes on Friday should appear in 120h."""
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=120)
        names = [e["name"] for e in events]
        assert "Baker Hughes Rig Count" in names

    def test_no_events_in_tiny_window(self):
        """On a Monday at 9AM, looking 1 hour ahead should find no events."""
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=1)
        assert len(events) == 0

    def test_opec_meeting_included(self):
        opec_date = make_now(2024, 6, 1, 10, 0)
        now = make_now(2024, 5, 31, 12, 0)
        mgr = ScheduledEventsManager(
            opec_meeting_dates=[opec_date],
            now_func=lambda: now,
        )
        events = mgr.get_upcoming_events(hours_ahead=48)
        names = [e["name"] for e in events]
        assert "OPEC+ Meeting" in names

    def test_events_are_sorted_chronologically(self):
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=120)
        datetimes = [e["datetime"] for e in events]
        assert datetimes == sorted(datetimes)

    def test_nfp_first_friday(self):
        """On 2024-02-01, NFP should be on 2024-02-02 (first Friday)."""
        now = make_now(2024, 2, 1, 7, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=48)
        names = [e["name"] for e in events]
        assert "US Non-Farm Payrolls" in names


# ============================================================
# New Phase 3A/3B events
# ============================================================

class TestNewEvents:
    def test_chinese_pmi_monthly_1st(self):
        """Chinese PMI on 1st of month, should appear when looking from end of prior month."""
        now = make_now(2024, 2, 29, 12, 0)  # Feb 29 (leap year)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=48)
        names = [e["name"] for e in events]
        assert "Chinese Manufacturing PMI" in names

    def test_fujairah_weekly_monday(self):
        """Fujairah storage on Monday should appear when looking from Sunday."""
        now = make_now(2024, 1, 7, 12, 0)  # Sunday
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=48)
        names = [e["name"] for e in events]
        assert "Fujairah Petroleum Storage" in names

    def test_eu_gie_weekly_thursday(self):
        """EU GIE on Thursday should appear when looking from Monday."""
        now = make_now(2024, 1, 8, 9, 0)  # Monday
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=120)
        names = [e["name"] for e in events]
        assert "EU Gas Storage Report (GIE)" in names

    def test_russian_oil_production_monthly_20th(self):
        """Russian Oil Production on 20th should appear mid-month."""
        now = make_now(2024, 1, 15, 12, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=168)  # 7 days
        names = [e["name"] for e in events]
        assert "Russian Oil Production Update" in names

    def test_indian_ppac_monthly_25th(self):
        """Indian PPAC data on 25th should appear around 20th."""
        now = make_now(2024, 1, 20, 12, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        events = mgr.get_upcoming_events(hours_ahead=168)
        names = [e["name"] for e in events]
        assert "Indian Oil Import Data (PPAC)" in names

    def test_all_11_events_present(self):
        """Over a full month, all 11 event types should appear at least once."""
        now = make_now(2024, 3, 1, 0, 0)  # Start of March
        mgr = ScheduledEventsManager(
            opec_meeting_dates=[make_now(2024, 3, 15, 10, 0)],
            now_func=lambda: now,
        )
        events = mgr.get_upcoming_events(hours_ahead=24 * 31)  # full month
        names = set(e["name"] for e in events)

        expected = {
            "EIA Weekly Petroleum Status",
            "API Private Inventory Report",
            "Baker Hughes Rig Count",
            "US Non-Farm Payrolls",
            "OPEC Monthly Oil Market Report",
            "IEA Oil Market Report",
            "Chinese Manufacturing PMI",
            "Fujairah Petroleum Storage",
            "EU Gas Storage Report (GIE)",
            "Russian Oil Production Update",
            "Indian Oil Import Data (PPAC)",
        }
        # OPEC+ Meeting is from explicit dates, not config
        assert expected.issubset(names), f"Missing: {expected - names}"


# ============================================================
# Event window detection
# ============================================================

class TestEventWindow:
    def test_inside_eia_window_before(self):
        """20 minutes before EIA report (Wed 10:10 AM) should be in window."""
        now = make_now(2024, 1, 10, 10, 10)  # Wednesday
        mgr = ScheduledEventsManager(now_func=lambda: now)
        assert mgr.is_event_window("EIA Weekly Petroleum Status", minutes_before=30) is True

    def test_inside_eia_window_after(self):
        """30 minutes after EIA report (Wed 11:00 AM) should be in window."""
        now = make_now(2024, 1, 10, 11, 0)  # Wednesday
        mgr = ScheduledEventsManager(now_func=lambda: now)
        assert mgr.is_event_window("EIA Weekly Petroleum Status", minutes_after=60) is True

    def test_outside_eia_window(self):
        """On Monday morning, EIA window should be False."""
        now = make_now(2024, 1, 8, 9, 0)  # Monday
        mgr = ScheduledEventsManager(now_func=lambda: now)
        assert mgr.is_event_window("EIA Weekly Petroleum Status") is False

    def test_nonexistent_event(self):
        """Querying a non-existent event name should return False."""
        now = make_now(2024, 1, 10, 10, 30)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        assert mgr.is_event_window("Nonexistent Event") is False


# ============================================================
# next_event
# ============================================================

class TestNextEvent:
    def test_next_event_returns_something(self):
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        nxt = mgr.next_event()
        assert nxt is not None
        assert "name" in nxt
        assert "datetime" in nxt
        assert "impact_level" in nxt

    def test_next_event_has_required_fields(self):
        now = make_now(2024, 1, 8, 9, 0)
        mgr = ScheduledEventsManager(now_func=lambda: now)
        nxt = mgr.next_event()
        assert "description" in nxt
