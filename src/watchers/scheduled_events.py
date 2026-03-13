"""
Scheduled Events Manager — recurring oil-market calendar events.

Phase 3B: Config-driven from settings.SCHEDULED_EVENTS.
Supports weekly, monthly, monthly_first_friday schedule types.
11 events total (6 original + 5 Phase 3A).
"""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from loguru import logger


ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def _next_weekday(start: datetime, weekday: int) -> datetime:
    """Return the next occurrence of *weekday* (0=Mon … 6=Sun) on or after *start*."""
    days_ahead = (weekday - start.weekday()) % 7
    if days_ahead == 0 and start.hour >= 23:
        days_ahead = 7
    return start + timedelta(days=days_ahead)


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> datetime:
    """Return the *n*-th occurrence (1-based) of *weekday* in the given month."""
    first = datetime(year, month, 1, tzinfo=ET)
    first_occ = _next_weekday(first, weekday)
    if first_occ.month != month:
        first_occ += timedelta(days=7)
    result = first_occ + timedelta(weeks=n - 1)
    return result


def _load_events_config() -> list[dict]:
    """Load events from settings, fallback to empty."""
    try:
        from src.config.settings import get_settings
        return get_settings().SCHEDULED_EVENTS
    except Exception:
        return []


class ScheduledEvent:
    """A single scheduled calendar event."""

    def __init__(self, name: str, impact_level: str, description: str):
        self.name = name
        self.impact_level = impact_level
        self.description = description

    def to_dict(self, dt: datetime) -> dict:
        return {
            "name": self.name,
            "datetime": dt.isoformat(),
            "impact_level": self.impact_level,
            "description": self.description,
        }


class ScheduledEventsManager:
    """
    Config-driven calendar of recurring oil-market events.

    Parameters
    ----------
    events_config : list of event dicts (overrides settings for testing)
    opec_meeting_dates : list of datetime objects for known OPEC+ meetings
    now_func : callable returning current datetime (for testing)
    """

    def __init__(
        self,
        events_config: Optional[list[dict]] = None,
        opec_meeting_dates: Optional[list[datetime]] = None,
        now_func=None,
    ):
        self.events_config = events_config if events_config is not None else _load_events_config()
        self.opec_meeting_dates: list[datetime] = opec_meeting_dates or []
        self._now_func = now_func or (lambda: datetime.now(tz=ET))

    def _now(self) -> datetime:
        return self._now_func()

    # ----------------------------------------------------------
    # Generate events by schedule type
    # ----------------------------------------------------------

    def _generate_weekly(
        self, cfg: dict, now: datetime, horizon: datetime
    ) -> list[tuple[datetime, ScheduledEvent]]:
        """Generate weekly recurring events."""
        weekday = cfg.get("day", 1) - 1  # settings: 1=Mon, Python: 0=Mon
        hour = cfg.get("utc_hour", 12)
        minute = cfg.get("utc_min", 0)
        tz = ZoneInfo(cfg["timezone"]) if "timezone" in cfg else UTC

        event = ScheduledEvent(
            name=cfg["name"],
            impact_level=cfg.get("impact", "medium"),
            description=cfg.get("note", ""),
        )

        results = []
        dt = _next_weekday(now.replace(hour=0, minute=0, second=0, microsecond=0), weekday)
        dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=tz)
        if dt < now:
            dt += timedelta(weeks=1)
        while dt <= horizon:
            results.append((dt, event))
            dt += timedelta(weeks=1)
        return results

    def _generate_monthly(
        self, cfg: dict, now: datetime, horizon: datetime
    ) -> list[tuple[datetime, ScheduledEvent]]:
        """Generate monthly events on a specific day of month."""
        day_of_month = cfg.get("day_of_month", 15)
        hour = cfg.get("utc_hour", 10)
        minute = cfg.get("utc_min", 0)

        event = ScheduledEvent(
            name=cfg["name"],
            impact_level=cfg.get("impact", "medium"),
            description=cfg.get("note", ""),
        )

        results = []
        for month_offset in range(3):
            year = now.year
            month = now.month + month_offset
            if month > 12:
                year += 1
                month -= 12
            try:
                dt = datetime(year, month, day_of_month, hour, minute, 0, tzinfo=ET)
            except ValueError:
                # e.g., day 31 in a 30-day month — skip
                continue
            if now <= dt <= horizon:
                results.append((dt, event))
        return results

    def _generate_monthly_first_friday(
        self, cfg: dict, now: datetime, horizon: datetime
    ) -> list[tuple[datetime, ScheduledEvent]]:
        """Generate events on the first Friday of each month."""
        hour = cfg.get("utc_hour", 12)
        minute = cfg.get("utc_min", 30)

        event = ScheduledEvent(
            name=cfg["name"],
            impact_level=cfg.get("impact", "high"),
            description=cfg.get("note", ""),
        )

        results = []
        for month_offset in range(3):
            year = now.year
            month = now.month + month_offset
            if month > 12:
                year += 1
                month -= 12
            first_friday = _nth_weekday_of_month(year, month, 4, 1)  # 4 = Friday
            dt = first_friday.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now <= dt <= horizon:
                results.append((dt, event))
        return results

    def _generate_all(
        self, now: datetime, horizon: datetime
    ) -> list[tuple[datetime, ScheduledEvent]]:
        """Generate all events from config within [now, horizon]."""
        results: list[tuple[datetime, ScheduledEvent]] = []

        for cfg in self.events_config:
            schedule = cfg.get("schedule", "weekly")
            if schedule == "weekly":
                results.extend(self._generate_weekly(cfg, now, horizon))
            elif schedule == "monthly":
                results.extend(self._generate_monthly(cfg, now, horizon))
            elif schedule == "monthly_first_friday":
                results.extend(self._generate_monthly_first_friday(cfg, now, horizon))
            else:
                logger.warning(f"Unknown schedule type: {schedule} for {cfg.get('name')}")

        # OPEC meetings from explicit dates
        if self.opec_meeting_dates:
            opec_event = ScheduledEvent(
                "OPEC+ Meeting", "high",
                "OPEC+ ministerial meeting — production quotas and policy",
            )
            for dt in self.opec_meeting_dates:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ET)
                if now <= dt <= horizon:
                    results.append((dt, opec_event))

        return results

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[dict]:
        """Return all scheduled events within the next *hours_ahead* hours, sorted."""
        now = self._now()
        horizon = now + timedelta(hours=hours_ahead)
        all_events = self._generate_all(now, horizon)
        all_events.sort(key=lambda x: x[0])
        return [evt.to_dict(dt) for dt, evt in all_events]

    def is_event_window(
        self,
        event_name: str,
        minutes_before: int = 30,
        minutes_after: int = 60,
    ) -> bool:
        """Check whether we are currently inside the window around an event."""
        now = self._now()
        search_start = now - timedelta(minutes=minutes_after)
        horizon = now + timedelta(days=7)
        all_events = self._generate_all(search_start, horizon)

        for dt, evt in all_events:
            if evt.name != event_name:
                continue
            window_start = dt - timedelta(minutes=minutes_before)
            window_end = dt + timedelta(minutes=minutes_after)
            if window_start <= now <= window_end:
                return True
        return False

    def next_event(self) -> Optional[dict]:
        """Return the single nearest upcoming event, or None."""
        events = self.get_upcoming_events(hours_ahead=168)  # 7 days
        return events[0] if events else None
