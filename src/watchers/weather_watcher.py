"""
Weather / Hurricane Watcher — NOAA data for oil market impact.

Provides:
  - Active tropical cyclones in Atlantic/Gulf of Mexico (NHC)
  - Hurricane season status and risk level
  - Cold snap / heat wave alerts affecting demand
  - Gulf Coast refinery threat assessment

Data source: NOAA National Hurricane Center (NHC) — free, no API key.
API: https://www.nhc.noaa.gov/CurrentSummary.json (active storms)
     https://api.weather.gov (general weather alerts)

Expected impact: +3-5% accuracy (seasonally up to +10% during hurricane season).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import httpx
from loguru import logger


# NHC active cyclones feed
NHC_ACTIVE_STORMS_URL = "https://www.nhc.noaa.gov/CurrentSummary.json"
# NHC GIS data for active storms (more structured)
NHC_ACTIVE_CYCLONES_URL = "https://www.nhc.noaa.gov/gis/forecast/archive/"

# Alternative: NHC RSS for Atlantic
NHC_ATLANTIC_RSS = "https://www.nhc.noaa.gov/nhc_at5.xml"

# NOAA weather alerts for Gulf Coast refinery areas
WEATHER_ALERTS_URL = "https://api.weather.gov/alerts/active"

# Gulf Coast states relevant to oil infrastructure
GULF_STATES = ["TX", "LA", "MS", "AL", "FL"]

# Hurricane season: June 1 - November 30
HURRICANE_SEASON_START = (6, 1)
HURRICANE_SEASON_END = (11, 30)


@dataclass
class TropicalSystem:
    """A single tropical cyclone or disturbance."""
    name: str
    category: str = ""         # TD, TS, Cat1-Cat5, Post-Tropical
    max_wind_mph: int = 0
    movement: str = ""         # e.g. "NW at 12 mph"
    latitude: float = 0.0
    longitude: float = 0.0
    threatens_gulf: bool = False
    summary: str = ""


@dataclass
class WeatherSnapshot:
    """Weather context for oil market analysis."""
    # Hurricane/tropical data
    active_storms: List[TropicalSystem] = field(default_factory=list)
    is_hurricane_season: bool = False
    gulf_threat_level: str = "none"  # none | watch | warning | active
    gulf_threat_summary: str = ""

    # Weather alerts for refinery areas
    severe_alerts_gulf: int = 0
    cold_snap_risk: bool = False
    heat_wave_risk: bool = False

    def to_prompt_text(self) -> str:
        """Format for injection into agent prompt."""
        lines = ["## Погодний контекст (вплив на нафтовий ринок)"]

        # Hurricane season status
        if self.is_hurricane_season:
            lines.append("  Сезон ураганів: АКТИВНИЙ (червень-листопад)")
        else:
            lines.append("  Сезон ураганів: неактивний")

        # Active storms
        if self.active_storms:
            lines.append(f"  Активні тропічні системи: {len(self.active_storms)}")
            for storm in self.active_storms:
                threat = " ⚠ ЗАГРОЗА МЕКСИКАНСЬКІЙ ЗАТОЦІ" if storm.threatens_gulf else ""
                lines.append(
                    f"    • {storm.name} ({storm.category}, "
                    f"вітер {storm.max_wind_mph} mph){threat}"
                )
                if storm.summary:
                    lines.append(f"      {storm.summary[:200]}")
        else:
            if self.is_hurricane_season:
                lines.append("  Активні тропічні системи: немає (спокійно)")

        # Gulf threat
        threat_ua = {
            "none": "НЕМАЄ",
            "watch": "СПОСТЕРЕЖЕННЯ (можлива загроза за 48+ годин)",
            "warning": "ПОПЕРЕДЖЕННЯ (загроза за 24-48 годин)",
            "active": "АКТИВНИЙ УДАР (НПЗ можуть зупинятися)",
        }
        if self.gulf_threat_level != "none":
            lines.append(
                f"  Загроза Мексиканській затоці: "
                f"{threat_ua.get(self.gulf_threat_level, self.gulf_threat_level)}"
            )
            if self.gulf_threat_summary:
                lines.append(f"  {self.gulf_threat_summary}")

        # Severe weather alerts
        if self.severe_alerts_gulf > 0:
            lines.append(
                f"  Штормові попередження в зоні НПЗ (Мексиканська затока): "
                f"{self.severe_alerts_gulf}"
            )

        # Temperature extremes
        if self.cold_snap_risk:
            lines.append(
                "  ❄ Ризик холодної хвилі — підвищений попит на мазут/дизель, "
                "ризик freeze-off на видобувних об'єктах"
            )
        if self.heat_wave_risk:
            lines.append(
                "  🔥 Ризик спекотної хвилі — підвищений попит на електроенергію, "
                "можливе зниження нафтопереробки"
            )

        # Actionable guidance
        if self.gulf_threat_level in ("warning", "active"):
            lines.append(
                "\n  УВАГА: Урагани в Мексиканській затоці можуть зупинити 2-5M bpd "
                "переробки та 1-2M bpd видобутку. Очікуй зростання продуктів "
                "(бензин, дизель) та тимчасове зниження попиту на сиру нафту."
            )

        return "\n".join(lines)


class WeatherWatcher:
    """Fetches weather data relevant to oil markets."""

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout
        self._cache: Optional[WeatherSnapshot] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)

    def fetch(self) -> WeatherSnapshot:
        """Fetch weather data. Returns cached if fresh."""
        if self._cache and self._cache_time:
            age = datetime.now() - self._cache_time
            if age < self._cache_ttl:
                return self._cache

        snap = WeatherSnapshot()
        snap.is_hurricane_season = self._is_hurricane_season()

        # Fetch active tropical storms
        try:
            storms = self._fetch_active_storms()
            snap.active_storms = storms
            snap.gulf_threat_level = self._assess_gulf_threat(storms)
            if snap.gulf_threat_level != "none":
                gulf_storms = [s for s in storms if s.threatens_gulf]
                snap.gulf_threat_summary = (
                    f"{len(gulf_storms)} система(и) загрожують зоні НПЗ "
                    f"Мексиканської затоки"
                )
        except Exception as exc:
            logger.warning(f"NHC storm fetch error: {exc}")

        # Fetch NOAA weather alerts for Gulf states
        try:
            alerts = self._fetch_gulf_alerts()
            snap.severe_alerts_gulf = alerts.get("severe_count", 0)
            snap.cold_snap_risk = alerts.get("cold_snap", False)
            snap.heat_wave_risk = alerts.get("heat_wave", False)
        except Exception as exc:
            logger.warning(f"NOAA alerts fetch error: {exc}")

        self._cache = snap
        self._cache_time = datetime.now()

        if snap.active_storms or snap.gulf_threat_level != "none":
            logger.info(
                f"Weather: {len(snap.active_storms)} storms, "
                f"gulf_threat={snap.gulf_threat_level}"
            )

        return snap

    def _fetch_active_storms(self) -> List[TropicalSystem]:
        """Fetch active tropical cyclones from NHC."""
        storms: List[TropicalSystem] = []

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                NHC_ACTIVE_STORMS_URL,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return storms

            data = resp.json()

        # NHC CurrentSummary.json structure varies;
        # parse the active cyclones section
        active = data if isinstance(data, list) else data.get("activeStorms", [])

        for item in active:
            if isinstance(item, dict):
                storm = TropicalSystem(
                    name=item.get("name", "Unknown"),
                    category=item.get("classification", ""),
                    max_wind_mph=int(item.get("intensity", 0)),
                    movement=item.get("movement", ""),
                    latitude=float(item.get("latitude", 0)),
                    longitude=float(item.get("longitude", 0)),
                    summary=item.get("headline", ""),
                )
                # Gulf of Mexico roughly: lat 18-31, lon -80 to -98
                storm.threatens_gulf = self._threatens_gulf(
                    storm.latitude, storm.longitude, storm.movement
                )
                storms.append(storm)

        return storms

    def _fetch_gulf_alerts(self) -> Dict:
        """Fetch NOAA weather alerts for Gulf Coast states."""
        result = {"severe_count": 0, "cold_snap": False, "heat_wave": False}

        with httpx.Client(timeout=self._timeout) as client:
            # Fetch alerts for Gulf states
            for state in GULF_STATES:
                try:
                    resp = client.get(
                        WEATHER_ALERTS_URL,
                        params={"area": state, "status": "actual", "limit": 10},
                        headers={
                            "Accept": "application/geo+json",
                            "User-Agent": "(oil-trading-bot, contact@example.com)",
                        },
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    features = data.get("features", [])

                    for feat in features:
                        props = feat.get("properties", {})
                        event = props.get("event", "").lower()
                        severity = props.get("severity", "").lower()

                        if severity in ("extreme", "severe"):
                            result["severe_count"] += 1

                        # Cold snap detection
                        if any(kw in event for kw in [
                            "freeze", "cold", "winter storm",
                            "wind chill", "ice storm", "blizzard"
                        ]):
                            result["cold_snap"] = True

                        # Heat wave detection
                        if any(kw in event for kw in [
                            "heat", "excessive heat", "heat advisory"
                        ]):
                            result["heat_wave"] = True

                except Exception:
                    continue

        return result

    @staticmethod
    def _is_hurricane_season(dt: Optional[date] = None) -> bool:
        """Check if current date is in Atlantic hurricane season."""
        if dt is None:
            dt = date.today()
        start = date(dt.year, *HURRICANE_SEASON_START)
        end = date(dt.year, *HURRICANE_SEASON_END)
        return start <= dt <= end

    @staticmethod
    def _threatens_gulf(lat: float, lon: float, movement: str = "") -> bool:
        """Rough check if a storm could threaten Gulf of Mexico."""
        # In or near Gulf of Mexico
        if 18 <= lat <= 32 and -98 <= lon <= -80:
            return True
        # Caribbean approaching Gulf
        if 10 <= lat <= 25 and -90 <= lon <= -60:
            if "nw" in movement.lower() or "w" in movement.lower():
                return True
        return False

    @staticmethod
    def _assess_gulf_threat(storms: List[TropicalSystem]) -> str:
        """Assess overall Gulf threat level from active storms."""
        if not storms:
            return "none"

        gulf_storms = [s for s in storms if s.threatens_gulf]
        if not gulf_storms:
            return "none"

        max_wind = max(s.max_wind_mph for s in gulf_storms)
        if max_wind >= 74:  # Hurricane force
            return "active"
        if max_wind >= 39:  # Tropical storm
            return "warning"
        return "watch"
