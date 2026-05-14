from __future__ import annotations

from datetime import datetime, timezone

import pytest

from geoloop.engine.ice_risk import evaluate
from geoloop.engine.models import HeatingDecision, IceRiskLevel, SensorReadings
from geoloop.weather.met_client import WeatherForecast, WeatherSnapshot


def _make_forecast(
    temps: list[float],
    precips: list[float | None] | None = None,
) -> WeatherForecast:
    """Opprett en WeatherForecast fra temperaturliste."""
    base = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    if precips is None:
        precips = [None] * len(temps)

    snapshots = []
    for i, (t, p) in enumerate(zip(temps, precips)):
        snapshots.append(
            WeatherSnapshot(
                time=base.replace(hour=i % 24),
                air_temperature=t,
                precipitation_amount=p,
            )
        )

    return WeatherForecast(
        current=snapshots[0],
        timeseries=snapshots[1:] if len(snapshots) > 1 else [],
    )


class TestHighRisk:
    def test_should_turn_on_when_precip_near_zero(self):
        """Nedbør nær 0°C → HIGH → TURN_ON."""
        temps = [0.5] * 6 + [5.0] * 18
        precips = [0.5] * 6 + [0.0] * 18
        result = evaluate(_make_forecast(temps, precips))
        assert result.risk_level == IceRiskLevel.HIGH
        assert result.decision == HeatingDecision.TURN_ON

    def test_should_turn_on_when_many_critical_hours(self):
        """4+ timer i [-1°C, +2°C] → HIGH → TURN_ON."""
        temps = [0.0, 0.5, 1.0, 1.5, 1.0] + [10.0] * 19
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.HIGH
        assert result.decision == HeatingDecision.TURN_ON

    def test_should_turn_on_regardless_of_current_state(self):
        """HIGH risiko slår alltid PÅ."""
        temps = [0.0] * 5 + [10.0] * 19
        result = evaluate(_make_forecast(temps), currently_on=False)
        assert result.decision == HeatingDecision.TURN_ON

        result = evaluate(_make_forecast(temps), currently_on=True)
        assert result.decision == HeatingDecision.TURN_ON


class TestModerateRisk:
    def test_should_turn_on_when_many_ice_zone_hours(self):
        """6+ timer i [-5°C, +5°C] → MODERATE → TURN_ON."""
        temps = [3.0] * 7 + [15.0] * 17
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.MODERATE
        assert result.decision == HeatingDecision.TURN_ON

    def test_should_turn_on_with_safety_bias(self):
        """MODERATE → alltid TURN_ON (sikkerhetsbias)."""
        temps = [2.5] * 7 + [15.0] * 17
        result = evaluate(_make_forecast(temps), currently_on=False)
        assert result.decision == HeatingDecision.TURN_ON


class TestLowRisk:
    def test_should_keep_current_state_when_low_risk(self):
        """2-5 timer i faresonen → LOW → KEEP."""
        temps = [3.0] * 3 + [15.0] * 21
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.LOW
        assert result.decision == HeatingDecision.KEEP

    def test_should_keep_on_when_already_on(self):
        """LOW + allerede PÅ → KEEP (hysterese)."""
        temps = [3.0] * 3 + [15.0] * 21
        result = evaluate(_make_forecast(temps), currently_on=True)
        assert result.decision == HeatingDecision.KEEP
        assert "på" in result.reason

    def test_should_keep_off_when_already_off(self):
        """LOW + allerede AV → KEEP (hysterese)."""
        temps = [3.0] * 3 + [15.0] * 21
        result = evaluate(_make_forecast(temps), currently_on=False)
        assert result.decision == HeatingDecision.KEEP
        assert "av" in result.reason


class TestNoRisk:
    def test_should_turn_off_when_warm(self):
        """Alle timer over 5°C → NONE → TURN_OFF."""
        temps = [15.0] * 24
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.NONE
        assert result.decision == HeatingDecision.TURN_OFF

    def test_should_turn_off_when_very_cold(self):
        """Alle timer under -5°C → NONE → TURN_OFF (for kaldt for is)."""
        temps = [-10.0] * 24
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.NONE
        assert result.decision == HeatingDecision.TURN_OFF

    def test_should_turn_off_when_few_ice_zone_hours(self):
        """1 time i faresonen → NONE → TURN_OFF."""
        temps = [3.0] + [15.0] * 23
        result = evaluate(_make_forecast(temps))
        assert result.risk_level == IceRiskLevel.NONE
        assert result.decision == HeatingDecision.TURN_OFF


class TestEdgeCases:
    def test_should_handle_empty_timeseries(self):
        """Tom prognose → NONE → TURN_OFF."""
        forecast = WeatherForecast(
            current=WeatherSnapshot(
                time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
                air_temperature=5.0,
            ),
            timeseries=[],
        )
        result = evaluate(forecast)
        assert result.risk_level == IceRiskLevel.NONE
        assert result.decision == HeatingDecision.TURN_OFF

    def test_should_handle_none_temperatures(self):
        """None-temperaturer ignoreres."""
        snapshots = [
            WeatherSnapshot(
                time=datetime(2026, 1, 15, i, 0, tzinfo=timezone.utc),
                air_temperature=None,
            )
            for i in range(24)
        ]
        forecast = WeatherForecast(current=snapshots[0], timeseries=snapshots[1:])
        result = evaluate(forecast)
        assert result.risk_level == IceRiskLevel.NONE

    def test_should_include_details_in_result(self):
        """Resultatet inneholder detaljer for logging."""
        temps = [0.5] * 10 + [15.0] * 14
        result = evaluate(_make_forecast(temps))
        assert "ice_zone_hours" in result.details
        assert "critical_hours" in result.details
        assert "precip_near_zero_hours" in result.details

    def test_should_accept_sensor_readings(self):
        """SensorReadings aksepteres (fremtidig bruk)."""
        temps = [15.0] * 24
        readings = SensorReadings(loop_inlet=25.0, tank=40.0)
        result = evaluate(_make_forecast(temps), sensor_readings=readings)
        assert result.decision == HeatingDecision.TURN_OFF

    def test_boundary_temp_minus_3_is_in_ice_zone(self):
        """-3.0°C er innenfor faresonen."""
        temps = [-3.0] * 7 + [15.0] * 17
        result = evaluate(_make_forecast(temps))
        assert result.details["ice_zone_hours"] >= 6

    def test_boundary_temp_plus_3_is_in_ice_zone(self):
        """+3.0°C er innenfor faresonen."""
        temps = [3.0] * 7 + [15.0] * 17
        result = evaluate(_make_forecast(temps))
        assert result.details["ice_zone_hours"] >= 6
