"""Tests for Weather / Hurricane Watcher."""

import pytest
from datetime import date

from watchers.weather_watcher import (
    WeatherSnapshot,
    TropicalSystem,
    WeatherWatcher,
)


class TestWeatherSnapshot:
    def test_basic_snapshot_no_storms(self):
        snap = WeatherSnapshot(is_hurricane_season=True)
        text = snap.to_prompt_text()
        assert "Погодний контекст" in text
        assert "АКТИВНИЙ" in text
        assert "немає" in text

    def test_snapshot_outside_hurricane_season(self):
        snap = WeatherSnapshot(is_hurricane_season=False)
        text = snap.to_prompt_text()
        assert "неактивний" in text

    def test_snapshot_with_storm(self):
        storm = TropicalSystem(
            name="Helene",
            category="Cat3",
            max_wind_mph=120,
            threatens_gulf=True,
            summary="Heading toward Gulf Coast",
        )
        snap = WeatherSnapshot(
            is_hurricane_season=True,
            active_storms=[storm],
            gulf_threat_level="active",
            gulf_threat_summary="1 система загрожує",
        )
        text = snap.to_prompt_text()
        assert "Helene" in text
        assert "Cat3" in text
        assert "120 mph" in text
        assert "ЗАГРОЗА" in text
        assert "АКТИВНИЙ УДАР" in text

    def test_cold_snap_warning(self):
        snap = WeatherSnapshot(cold_snap_risk=True)
        text = snap.to_prompt_text()
        assert "холодної хвилі" in text
        assert "мазут" in text

    def test_heat_wave_warning(self):
        snap = WeatherSnapshot(heat_wave_risk=True)
        text = snap.to_prompt_text()
        assert "спекотної хвилі" in text

    def test_gulf_warning_has_guidance(self):
        snap = WeatherSnapshot(
            active_storms=[TropicalSystem(name="Test", threatens_gulf=True, max_wind_mph=80)],
            gulf_threat_level="active",
        )
        text = snap.to_prompt_text()
        assert "2-5M bpd" in text


class TestWeatherWatcherHelpers:
    def test_hurricane_season_june(self):
        assert WeatherWatcher._is_hurricane_season(date(2026, 7, 15)) is True

    def test_not_hurricane_season_january(self):
        assert WeatherWatcher._is_hurricane_season(date(2026, 1, 15)) is False

    def test_hurricane_season_boundary_start(self):
        assert WeatherWatcher._is_hurricane_season(date(2026, 6, 1)) is True

    def test_hurricane_season_boundary_end(self):
        assert WeatherWatcher._is_hurricane_season(date(2026, 11, 30)) is True

    def test_not_hurricane_season_december(self):
        assert WeatherWatcher._is_hurricane_season(date(2026, 12, 1)) is False

    def test_threatens_gulf_inside(self):
        assert WeatherWatcher._threatens_gulf(25.0, -90.0) is True

    def test_threatens_gulf_outside(self):
        assert WeatherWatcher._threatens_gulf(40.0, -70.0) is False

    def test_threatens_gulf_caribbean_moving_west(self):
        assert WeatherWatcher._threatens_gulf(20.0, -75.0, "NW at 15 mph") is True

    def test_threatens_gulf_caribbean_moving_east(self):
        assert WeatherWatcher._threatens_gulf(20.0, -75.0, "NE at 10 mph") is False

    def test_assess_gulf_no_storms(self):
        assert WeatherWatcher._assess_gulf_threat([]) == "none"

    def test_assess_gulf_hurricane(self):
        storms = [TropicalSystem(name="X", max_wind_mph=100, threatens_gulf=True)]
        assert WeatherWatcher._assess_gulf_threat(storms) == "active"

    def test_assess_gulf_tropical_storm(self):
        storms = [TropicalSystem(name="X", max_wind_mph=50, threatens_gulf=True)]
        assert WeatherWatcher._assess_gulf_threat(storms) == "warning"

    def test_assess_gulf_disturbance(self):
        storms = [TropicalSystem(name="X", max_wind_mph=30, threatens_gulf=True)]
        assert WeatherWatcher._assess_gulf_threat(storms) == "watch"

    def test_assess_non_gulf_storm_ignored(self):
        storms = [TropicalSystem(name="X", max_wind_mph=120, threatens_gulf=False)]
        assert WeatherWatcher._assess_gulf_threat(storms) == "none"
