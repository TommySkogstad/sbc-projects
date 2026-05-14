from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from geoloop.controller.stub import StubController
from geoloop.db.store import Store
from geoloop.sensors.stub import StubSensor
from geoloop.weather.met_client import MetClient, WeatherForecast, WeatherSnapshot
from geoloop.web.app import app, configure


def _sample_forecast() -> WeatherForecast:
    base = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        WeatherSnapshot(time=base.replace(hour=i), air_temperature=10.0 + i, precipitation_amount=0.0)
        for i in range(24)
    ]
    return WeatherForecast(current=snapshots[0], timeseries=snapshots[1:])


@pytest.fixture
def client():
    store = Store(":memory:")
    met_client = MetClient("test/1.0")
    sensors = {
        "loop_inlet": StubSensor("loop_inlet", 25.0),
        "tank": StubSensor("tank", 40.0),
    }
    controller = StubController()

    configure(
        met_client=met_client,
        store=store,
        lat=59.91,
        lon=10.75,
        sensors=sensors,
        controller=controller,
    )

    with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_sample_forecast()):
        yield TestClient(app)


class TestStatusEndpoint:
    def test_should_return_weather_and_heating(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "weather" in data
        assert "heating" in data
        assert data["heating"]["on"] is False

    def test_should_return_sensor_readings(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert "sensors" in data
        assert data["sensors"]["loop_inlet"] == pytest.approx(25.0)
        assert data["sensors"]["tank"] == pytest.approx(40.0)


class TestSensorsEndpoint:
    def test_should_return_all_sensors(self, client):
        resp = client.get("/api/sensors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensors"]["loop_inlet"] == pytest.approx(25.0)
        assert data["sensors"]["tank"] == pytest.approx(40.0)


class TestHeatingEndpoints:
    def test_should_turn_on(self, client):
        resp = client.post("/api/heating/on")
        assert resp.status_code == 200
        assert resp.json()["heating"]["on"] is True

    def test_should_turn_off(self, client):
        client.post("/api/heating/on")
        resp = client.post("/api/heating/off")
        assert resp.status_code == 200
        assert resp.json()["heating"]["on"] is False

    def test_status_should_reflect_manual_on(self, client):
        client.post("/api/heating/on")
        resp = client.get("/api/status")
        assert resp.json()["heating"]["on"] is True

    def test_should_log_manual_events(self, client):
        client.post("/api/heating/on")
        client.post("/api/heating/off")
        resp = client.get("/api/log")
        events = resp.json()["events"]
        types = [e["event_type"] for e in events]
        assert "manual_on" in types
        assert "manual_off" in types


class TestLogEndpoint:
    def test_should_return_logs(self, client):
        resp = client.get("/api/log")
        assert resp.status_code == 200
        data = resp.json()
        assert "weather" in data
        assert "sensors" in data
        assert "events" in data
