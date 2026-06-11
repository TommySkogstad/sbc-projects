from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import geoloop.web.app as appmod
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

    def test_limit_above_max_returns_422(self, client):
        resp = client.get("/api/log?limit=999999")
        assert resp.status_code == 422

    def test_limit_zero_returns_422(self, client):
        resp = client.get("/api/log?limit=0")
        assert resp.status_code == 422


_TEST_PW = "hemmelig-passord-123"
_TEST_HASH = hashlib.sha256(_TEST_PW.encode()).hexdigest()


@pytest.fixture
def auth_client(monkeypatch):
    """Klient med auth-middleware AKTIVERT.

    `_PASSWORD`/`_AUTH_TOKEN` leses ved import-tid, så env-variabler hjelper
    ikke — vi må patche modul-globalene direkte.
    """
    store = Store(":memory:")
    met_client = MetClient("test/1.0")
    controller = StubController()
    configure(
        met_client=met_client,
        store=store,
        lat=59.91,
        lon=10.75,
        sensors={"tank": StubSensor("tank", 40.0)},
        controller=controller,
    )

    monkeypatch.setattr(appmod, "_PASSWORD", _TEST_PW)
    monkeypatch.setattr(appmod, "_AUTH_TOKEN", _TEST_HASH)
    # `_login_attempts` er en delt modul-global — nullstill mellom tester.
    appmod._login_attempts.clear()

    with patch.object(met_client, "fetch_forecast", new_callable=AsyncMock, return_value=_sample_forecast()):
        yield TestClient(app, raise_server_exceptions=False)


class TestAuthAndCsrf:
    def test_post_without_auth_returns_401(self, auth_client):
        resp = auth_client.post("/api/heating/on")
        assert resp.status_code == 401

    def test_login_wrong_password_returns_401(self, auth_client):
        resp = auth_client.post("/api/login", json={"password": "feil"})
        assert resp.status_code == 401

    def test_login_correct_password_sets_cookies(self, auth_client):
        resp = auth_client.post("/api/login", json={"password": _TEST_PW})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "csrf_token" in body
        assert appmod._AUTH_COOKIE in resp.cookies
        assert appmod._CSRF_COOKIE in resp.cookies

    def test_post_with_auth_but_no_csrf_returns_403(self, auth_client):
        login = auth_client.post("/api/login", json={"password": _TEST_PW})
        assert login.status_code == 200
        # Auth-cookie beholdes av TestClient, men ingen x-csrf-token sendes.
        resp = auth_client.post("/api/heating/on")
        assert resp.status_code == 403

    def test_post_with_valid_csrf_succeeds(self, auth_client):
        login = auth_client.post("/api/login", json={"password": _TEST_PW})
        csrf = login.json()["csrf_token"]
        resp = auth_client.post("/api/heating/on", headers={appmod._CSRF_HEADER: csrf})
        assert resp.status_code == 200
        assert resp.json()["heating"]["on"] is True

    def test_non_string_password_does_not_crash(self, auth_client):
        # JSON kan sende ikke-str; skal gi 401, ikke 500
        # (en naiv compare_digest uten type-guard ville kastet → 500).
        resp = auth_client.post("/api/login", json={"password": 12345})
        assert resp.status_code == 401

    def test_non_ascii_password_does_not_crash(self, auth_client):
        # Ikke-ASCII passord skal gi 401, ikke 500
        # (compare_digest på ikke-ASCII str kaster TypeError → 500 uten normalisering).
        resp = auth_client.post("/api/login", json={"password": "feil-æøå-pæssord"})
        assert resp.status_code == 401


class TestSystemEndpoint:
    def test_should_return_database_stats(self, client):
        """Database-statistikk fra /api/system skal telle faktiske rader."""
        store = appmod._store
        store.log_sensor("loop_inlet", 20.0)
        store.log_sensor("loop_inlet", 21.0)
        store.log_weather(temperature=5.0)
        store.log_event("test_event", "msg")

        resp = client.get("/api/system")
        assert resp.status_code == 200
        data = resp.json()
        db = data["database"]
        assert db["sensor_readings"] == 2
        assert db["weather_readings"] == 1
        assert db["events"] == 1

    def test_should_return_zero_counts_for_empty_store(self, client):
        resp = client.get("/api/system")
        assert resp.status_code == 200
        data = resp.json()
        db = data["database"]
        assert db["sensor_readings"] == 0
        assert db["weather_readings"] == 0
        assert db["events"] == 0

    def test_should_return_version_and_location(self, client):
        resp = client.get("/api/system")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert data["location"]["lat"] == pytest.approx(59.91)
        assert data["location"]["lon"] == pytest.approx(10.75)


class TestHistoryEndpoint:
    def test_should_return_sensor_history(self, client):
        store = appmod._store
        store.log_sensor("loop_inlet", 22.5)
        store.log_sensor("tank", 41.0)

        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "sensors" in data
        assert "heating_periods" in data
        assert "heating_on" in data

    def test_should_return_empty_when_no_data(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensors"] == []
        assert data["heating_periods"] == []

    def test_should_include_heating_periods_after_events(self, client):
        client.post("/api/heating/on")
        client.post("/api/heating/off")

        resp = client.get("/api/history")
        assert resp.status_code == 200
        periods = resp.json()["heating_periods"]
        event_types = [p["event_type"] for p in periods]
        assert "manual_on" in event_types
        assert "manual_off" in event_types

    def test_should_reject_hours_above_max(self, client):
        resp = client.get("/api/history?hours=999999")
        assert resp.status_code == 422

    def test_should_reject_hours_zero(self, client):
        resp = client.get("/api/history?hours=0")
        assert resp.status_code == 422

    def test_should_reject_limit_above_max(self, client):
        resp = client.get("/api/history?limit=9999")
        assert resp.status_code == 422
