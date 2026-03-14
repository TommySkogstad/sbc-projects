from __future__ import annotations

import hashlib
import logging
import os
import secrets
import socket
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from geoloop.config import AppConfig
    from geoloop.controller.base import HeatingController
    from geoloop.db.store import Store
    from geoloop.sensors.base import TemperatureSensor
    from geoloop.weather.met_client import MetClient, WeatherForecast

from geoloop import notify

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"

_PASSWORD = os.environ.get("GEOLOOP_PASSWORD", "")
_AUTH_TOKEN = hashlib.sha256(_PASSWORD.encode()).hexdigest() if _PASSWORD else ""
_AUTH_COOKIE = "geoloop_auth"
_CSRF_COOKIE = "geoloop_csrf"
_CSRF_HEADER = "x-csrf-token"

# Rate limiting for login: max 5 forsøk per IP per 5 minutter
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 300  # sekunder

# CSRF tokens per session
_csrf_tokens: dict[str, str] = {}

app = FastAPI(title="GeoLoop", version="0.1.0")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


def _get_client_ip(request: Request) -> str:
    """Hent klient-IP (bak Cloudflare Tunnel)."""
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


def _check_rate_limit(ip: str) -> bool:
    """Sjekk om IP har overskredet rate limit. Returnerer True hvis blokkert."""
    now = time.monotonic()
    attempts = _login_attempts[ip]
    # Fjern gamle forsøk
    _login_attempts[ip] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    return len(_login_attempts[ip]) >= _RATE_LIMIT_MAX


def _verify_csrf(request: Request) -> bool:
    """Verifiser CSRF-token fra header mot cookie."""
    cookie_token = request.cookies.get(_CSRF_COOKIE, "")
    header_token = request.headers.get(_CSRF_HEADER, "")
    return bool(cookie_token and cookie_token == header_token)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Passord-beskyttelse via cookie + CSRF på POST."""
    if not _PASSWORD:
        return await call_next(request)

    path = request.url.path
    # Tillat login, statiske filer og healthcheck uten auth
    if path in ("/login", "/api/login") or path.startswith("/static/"):
        return await call_next(request)

    # /api/status tillates uten auth (brukes av healthcheck)
    if path == "/api/status":
        return await call_next(request)

    token = request.cookies.get(_AUTH_COOKIE)
    if token != _AUTH_TOKEN:
        if path.startswith("/api/"):
            return JSONResponse({"error": "Ikke autentisert"}, status_code=401)
        return RedirectResponse("/login")

    # CSRF-sjekk på muterende forespørsler
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not _verify_csrf(request):
            return JSONResponse({"error": "Ugyldig CSRF-token"}, status_code=403)

    return await call_next(request)

_met_client: MetClient | None = None
_store: Store | None = None
_lat: float = 0.0
_lon: float = 0.0
_sensors: dict[str, TemperatureSensor] = {}
_controller: HeatingController | None = None
_config: AppConfig | None = None

# Manuell overstyring: "on", "off", eller None (auto)
_manual_override: str | None = None

# Justerbare temperaturgrenser (runtime-state, initialiseres fra config)
_thresholds: dict[str, float] = {
    "ice_temp_min": -3.0,
    "ice_temp_max": 3.0,
    "critical_temp_min": -1.0,
    "critical_temp_max": 2.0,
}


def configure(
    met_client: MetClient,
    store: Store,
    lat: float,
    lon: float,
    sensors: dict[str, TemperatureSensor] | None = None,
    controller: HeatingController | None = None,
    config: AppConfig | None = None,
) -> None:
    """Sett opp delte avhengigheter for ruter."""
    global _met_client, _store, _lat, _lon, _sensors, _controller, _config, _thresholds
    _met_client = met_client
    _store = store
    _lat = lat
    _lon = lon
    _sensors = sensors or {}
    _controller = controller
    _config = config

    if config and config.thresholds:
        t = config.thresholds
        _thresholds["ice_temp_min"] = t.ice_temp_min
        _thresholds["ice_temp_max"] = t.ice_temp_max
        _thresholds["critical_temp_min"] = t.critical_temp_min
        _thresholds["critical_temp_max"] = t.critical_temp_max


@app.get("/login")
async def login_page() -> FileResponse:
    """Server login-side."""
    return FileResponse(_STATIC_DIR / "login.html")


@app.post("/api/login")
async def login(request: Request):
    """Verifiser passord og sett auth-cookie + CSRF-cookie."""
    ip = _get_client_ip(request)

    if _check_rate_limit(ip):
        return JSONResponse(
            {"error": "For mange forsøk. Prøv igjen om noen minutter."},
            status_code=429,
        )

    _login_attempts[ip].append(time.monotonic())

    body = await request.json()
    if body.get("password") == _PASSWORD:
        csrf_token = secrets.token_hex(32)
        response = JSONResponse({"ok": True, "csrf_token": csrf_token})
        response.set_cookie(
            _AUTH_COOKIE, _AUTH_TOKEN,
            httponly=True, samesite="strict", max_age=365 * 24 * 3600,
        )
        response.set_cookie(
            _CSRF_COOKIE, csrf_token,
            httponly=False, samesite="strict", max_age=365 * 24 * 3600,
        )
        # Nullstill rate limit ved vellykket innlogging
        _login_attempts.pop(ip, None)
        return response
    return JSONResponse({"error": "Feil passord"}, status_code=401)


@app.get("/")
async def index() -> FileResponse:
    """Server dashboard."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/info")
async def info_page() -> FileResponse:
    """Server informasjonsside."""
    return FileResponse(_STATIC_DIR / "info.html")


_HOST_IP = os.environ.get("HOST_IP", "")
_HOST_HOSTNAME = os.environ.get("HOST_HOSTNAME", "")


@app.get("/api/system")
async def system_info() -> dict:
    """Systeminformasjon og konfigurasjon."""
    info: dict = {
        "version": "0.1.0",
        "location": {"lat": _lat, "lon": _lon},
        "network": {
            "hostname": _HOST_HOSTNAME or socket.gethostname(),
            "local_ip": _HOST_IP or "ikke konfigurert",
        },
    }

    if _config:
        info["weather"] = {
            "poll_interval_minutes": _config.weather.poll_interval_minutes,
        }
        info["web"] = {
            "host": _config.web.host,
            "port": _config.web.port,
        }
        if _config.ground_loop:
            gl = _config.ground_loop
            inner_d = gl.pipe_outer_mm - 2 * gl.pipe_wall_mm
            volume = (3.14159 * (inner_d / 2000) ** 2) * gl.total_length_m * 1000
            info["ground_loop"] = {
                "loops": gl.loops,
                "total_length_m": gl.total_length_m,
                "pipe_outer_mm": gl.pipe_outer_mm,
                "pipe_wall_mm": gl.pipe_wall_mm,
                "volume_liters": round(volume),
            }
        if _config.tank:
            info["tank"] = {"volume_liters": _config.tank.volume_liters}
        if _config.relays:
            info["relays"] = {
                name: {"gpio_pin": r.gpio_pin, "active_high": r.active_high}
                for name, r in _config.relays.items()
            }
        if _config.sensors:
            info["sensors"] = {
                name: {"id": s.id} for name, s in _config.sensors.items()
            }

    # Database stats
    if _store:
        info["database"] = {
            "sensor_readings": len(_store.get_sensor_log(limit=999999)),
            "weather_readings": len(_store.get_weather_log(limit=999999)),
            "events": len(_store.get_events(limit=999999)),
        }

    return info


@app.get("/api/status")
async def status() -> dict:
    weather: WeatherForecast | None = None
    if _met_client:
        weather = await _met_client.fetch_forecast(_lat, _lon)

    current = None
    if weather:
        c = weather.current
        current = {
            "air_temperature": c.air_temperature,
            "precipitation_amount": c.precipitation_amount,
            "relative_humidity": c.relative_humidity,
            "wind_speed": c.wind_speed,
        }

    heating = None
    if _controller:
        heating = {
            "on": await _controller.is_on(),
            "mode": "auto" if _manual_override is None else _manual_override,
        }

    sensor_data = {}
    for name, sensor in _sensors.items():
        sensor_data[name] = await sensor.read()

    return {
        "weather": current,
        "heating": heating,
        "sensors": sensor_data,
        "thresholds": dict(_thresholds),
    }


@app.get("/api/weather")
async def weather() -> dict:
    if not _met_client:
        return {"error": "Værklient ikke konfigurert"}

    forecast = await _met_client.fetch_forecast(_lat, _lon)
    current = forecast.current

    return {
        "current": {
            "time": current.time.isoformat(),
            "air_temperature": current.air_temperature,
            "precipitation_amount": current.precipitation_amount,
            "relative_humidity": current.relative_humidity,
            "wind_speed": current.wind_speed,
        },
        "forecast": [
            {
                "time": s.time.isoformat(),
                "air_temperature": s.air_temperature,
                "precipitation_amount": s.precipitation_amount,
                "relative_humidity": s.relative_humidity,
                "wind_speed": s.wind_speed,
            }
            for s in forecast.timeseries[:24]
        ],
    }


@app.get("/api/sensors")
async def sensors() -> dict:
    """Les alle sensorer."""
    data = {}
    for name, sensor in _sensors.items():
        data[name] = await sensor.read()
    return {"sensors": data}


@app.post("/api/heating/on")
async def heating_on() -> dict:
    """Manuell overstyring: slå på varme (persistent)."""
    global _manual_override
    if not _controller:
        return {"error": "Controller ikke konfigurert"}

    _manual_override = "on"
    await _controller.turn_on()
    if _store:
        _store.log_event("manual_on", "Manuell overstyring: varme PÅ (vedvarende)")
    logger.info("Manuell overstyring: varme PÅ (vedvarende)")
    await notify.send("Modus endret: PÅ", "Manuell overstyring: varme slått PÅ", tags="fire")
    return {"heating": {"on": True, "mode": "on"}}


@app.post("/api/heating/off")
async def heating_off() -> dict:
    """Manuell overstyring: slå av varme (persistent)."""
    global _manual_override
    if not _controller:
        return {"error": "Controller ikke konfigurert"}

    _manual_override = "off"
    await _controller.turn_off()
    if _store:
        _store.log_event("manual_off", "Manuell overstyring: varme AV (vedvarende)")
    logger.info("Manuell overstyring: varme AV (vedvarende)")
    await notify.send("Modus endret: AV", "Manuell overstyring: varme slått AV", tags="snowflake")
    return {"heating": {"on": False, "mode": "off"}}


@app.post("/api/heating/auto")
async def heating_auto() -> dict:
    """Tilbake til automatisk styring."""
    global _manual_override
    _manual_override = None
    on = False
    if _controller:
        on = await _controller.is_on()
    if _store:
        _store.log_event("auto_mode", "Tilbake til automatisk styring")
    logger.info("Tilbake til automatisk styring")
    await notify.send("Modus endret: AUTO", "Tilbake til automatisk styring", tags="robot_face")
    return {"heating": {"on": on, "mode": "auto"}}


def get_manual_override() -> str | None:
    """Hent gjeldende overstyringsstatus (brukes av kontrollsyklus)."""
    return _manual_override


def get_thresholds() -> dict[str, float]:
    """Hent gjeldende temperaturgrenser (brukes av kontrollsyklus)."""
    return dict(_thresholds)


@app.get("/api/thresholds")
async def get_thresholds_api() -> dict:
    """Hent gjeldende temperaturgrenser."""
    return dict(_thresholds)


@app.post("/api/thresholds")
async def set_thresholds_api(request: Request) -> dict:
    """Oppdater temperaturgrenser. Maks ±10 grader."""
    body = await request.json()
    for key in ("ice_temp_min", "ice_temp_max", "critical_temp_min", "critical_temp_max"):
        if key in body:
            val = float(body[key])
            if val < -10.0 or val > 10.0:
                return {"error": f"{key} må være mellom -10 og +10"}
            _thresholds[key] = val

    if _thresholds["ice_temp_min"] >= _thresholds["ice_temp_max"]:
        return {"error": "ice_temp_min må være lavere enn ice_temp_max"}
    if _thresholds["critical_temp_min"] >= _thresholds["critical_temp_max"]:
        return {"error": "critical_temp_min må være lavere enn critical_temp_max"}

    if _store:
        _store.log_event("thresholds_changed", f"Nye grenser: {_thresholds}")
    logger.info("Temperaturgrenser oppdatert: %s", _thresholds)
    await notify.send(
        "Temperaturgrenser endret",
        f"Faresone: {_thresholds['ice_temp_min']}°C til {_thresholds['ice_temp_max']}°C\n"
        f"Kritisk: {_thresholds['critical_temp_min']}°C til {_thresholds['critical_temp_max']}°C",
        tags="thermometer",
    )
    return dict(_thresholds)


@app.get("/api/history")
async def history(hours: int = 24, limit: int = 0) -> dict:
    """Sensorhistorikk og VP-perioder for tidsserie-graf."""
    if not _store:
        return {"error": "Database ikke konfigurert"}

    heating_on = False
    if _controller:
        heating_on = await _controller.is_on()

    return {
        "sensors": _store.get_sensor_history(hours=hours, limit=limit),
        "heating_periods": _store.get_heating_periods(hours=hours),
        "heating_on": heating_on,
    }


@app.get("/api/log")
async def log(limit: int = 50) -> dict:
    if not _store:
        return {"error": "Database ikke konfigurert"}

    return {
        "weather": _store.get_weather_log(limit=limit),
        "sensors": _store.get_sensor_log(limit=limit),
        "events": _store.get_events(limit=limit),
    }
