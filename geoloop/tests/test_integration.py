from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from geoloop.controller.stub import StubController
from geoloop.db.store import Store
from geoloop.engine.models import HeatingDecision
from geoloop.main import _control_loop, _read_all_sensors, _sensor_poll
from geoloop.sensors.stub import StubSensor
from geoloop.weather.met_client import MetClient, WeatherForecast, WeatherSnapshot


def _warm_forecast() -> WeatherForecast:
    """Prognose uten isrisiko."""
    base = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        WeatherSnapshot(time=base.replace(hour=i), air_temperature=15.0, precipitation_amount=0.0)
        for i in range(24)
    ]
    return WeatherForecast(current=snapshots[0], timeseries=snapshots[1:])


def _cold_forecast() -> WeatherForecast:
    """Prognose med høy isrisiko (nedbør nær 0°C)."""
    base = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        WeatherSnapshot(time=base.replace(hour=i), air_temperature=0.5, precipitation_amount=1.0)
        for i in range(24)
    ]
    return WeatherForecast(current=snapshots[0], timeseries=snapshots[1:])


@pytest.fixture
def sensors():
    return {
        "loop_inlet": StubSensor("loop_inlet", 25.0),
        "loop_outlet": StubSensor("loop_outlet", 22.0),
    }


@pytest.fixture
def controller():
    return StubController()


@pytest.fixture
def store():
    return Store(":memory:")


class TestReadAllSensors:
    async def test_should_read_all_sensors(self, sensors):
        readings = await _read_all_sensors(sensors)
        assert readings.loop_inlet == pytest.approx(25.0)
        assert readings.loop_outlet == pytest.approx(22.0)
        assert readings.tank is None


class TestControlLoop:
    async def test_should_turn_on_when_ice_risk_high(self, sensors, controller, store):
        met_client = MetClient("test/1.0")
        with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_cold_forecast()):
            await _control_loop(met_client, store, controller, sensors, 59.91, 10.75)
        assert await controller.is_on() is True
        events = store.get_events()
        assert any(e["event_type"] == "heating_on" for e in events)

    async def test_should_turn_off_when_no_risk(self, sensors, controller, store):
        met_client = MetClient("test/1.0")
        # Først slå på
        await controller.turn_on()
        with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_warm_forecast()):
            await _control_loop(met_client, store, controller, sensors, 59.91, 10.75)
        assert await controller.is_on() is False
        events = store.get_events()
        assert any(e["event_type"] == "heating_off" for e in events)

    async def test_should_not_toggle_when_already_correct(self, sensors, controller, store):
        met_client = MetClient("test/1.0")
        # Allerede av + ingen risiko → ingen endring
        with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_warm_forecast()):
            await _control_loop(met_client, store, controller, sensors, 59.91, 10.75)
        assert await controller.is_on() is False
        events = store.get_events()
        assert not any(e["event_type"] in ("heating_on", "heating_off") for e in events)

    async def test_should_log_weather_data(self, sensors, controller, store):
        met_client = MetClient("test/1.0")
        with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_warm_forecast()):
            await _control_loop(met_client, store, controller, sensors, 59.91, 10.75)
        weather_log = store.get_weather_log()
        assert len(weather_log) == 1
        assert weather_log[0]["temperature"] == pytest.approx(15.0)

    async def test_should_log_sensor_data(self, sensors, controller, store):
        await _sensor_poll(store, sensors)
        sensor_log = store.get_sensor_log()
        assert len(sensor_log) >= 2

    async def test_should_handle_errors_gracefully(self, sensors, controller, store):
        met_client = MetClient("test/1.0")
        with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, side_effect=Exception("API feil")):
            await _control_loop(met_client, store, controller, sensors, 59.91, 10.75)
        events = store.get_events()
        assert any(e["event_type"] == "error" for e in events)
