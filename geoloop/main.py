from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from geoloop.config import load_config
from geoloop.controller.stub import StubController
from geoloop.db.store import Store
from geoloop.engine.ice_risk import evaluate
from geoloop.engine.models import HeatingDecision, IceRiskLevel, SensorReadings
from geoloop import notify
from geoloop.sensors.stub import StubSensor
from geoloop.weather.met_client import MetClient
from geoloop.web.app import app, configure, get_manual_override, get_thresholds

if TYPE_CHECKING:
    from geoloop.config import AppConfig
    from geoloop.controller.base import HeatingController
    from geoloop.sensors.base import TemperatureSensor

logger = logging.getLogger("geoloop")


def _create_sensors(cfg: AppConfig) -> dict[str, TemperatureSensor]:
    """Opprett sensorer basert på config. Faller tilbake til stubs."""
    sensors: dict[str, TemperatureSensor] = {}

    if cfg.sensors is None:
        logger.info("Ingen sensorer konfigurert — bruker stubs")
        for name in ("loop_inlet", "loop_outlet", "hp_inlet", "hp_outlet", "tank"):
            sensors[name] = StubSensor(name)
        return sensors

    _stub_values: dict[str, float] = {
        "loop_inlet": 0.5,
        "loop_outlet": 4.2,
        "hp_inlet": 35.0,
        "hp_outlet": 45.8,
        "tank": 44.1,
    }

    try:
        from geoloop.sensors.ds18b20 import DS18B20Sensor

        for name, sensor_cfg in cfg.sensors.items():
            if "xxx" in sensor_cfg.id:
                sensors[name] = StubSensor(name, _stub_values.get(name, 20.0))
                logger.info("Sensor %s: plassholder-ID — bruker stub (%.1f°C)", name, _stub_values.get(name, 20.0))
            else:
                sensors[name] = DS18B20Sensor(sensor_cfg.id)
        logger.info("DS18B20-sensorer opprettet: %s", list(sensors.keys()))
    except Exception:
        logger.warning("Kan ikke opprette DS18B20-sensorer — bruker stubs")
        for name in cfg.sensors:
            sensors[name] = StubSensor(name, _stub_values.get(name, 20.0))

    return sensors


def _create_controller(cfg: AppConfig) -> HeatingController:
    """Opprett relékontroller. Faller tilbake til stub."""
    if cfg.relays is None:
        logger.info("Ingen reléer konfigurert — bruker StubController")
        return StubController()

    hp = cfg.relays.get("heat_pump")
    cp = cfg.relays.get("circulation_pump")
    if hp is None or cp is None:
        logger.warning("Mangler heat_pump/circulation_pump i config — bruker StubController")
        return StubController()

    try:
        from geoloop.controller.relay import RelayController

        ctrl = RelayController(
            heat_pump_pin=hp.gpio_pin,
            circulation_pump_pin=cp.gpio_pin,
            active_high=hp.active_high,
        )
        logger.info("RelayController opprettet (GPIO%d, GPIO%d)", hp.gpio_pin, cp.gpio_pin)
        return ctrl
    except Exception:
        logger.warning("Kan ikke opprette RelayController — bruker StubController")
        return StubController()


async def _read_all_sensors(
    sensors: dict[str, TemperatureSensor],
) -> SensorReadings:
    """Les alle sensorer og returner SensorReadings."""
    values: dict[str, float | None] = {}
    for name, sensor in sensors.items():
        values[name] = await sensor.read()
    return SensorReadings(
        loop_inlet=values.get("loop_inlet"),
        loop_outlet=values.get("loop_outlet"),
        hp_inlet=values.get("hp_inlet"),
        hp_outlet=values.get("hp_outlet"),
        tank=values.get("tank"),
    )


async def _sensor_poll(
    store: Store,
    sensors: dict[str, TemperatureSensor],
) -> None:
    """Les alle sensorer og logg til database (kjøres hvert minutt)."""
    try:
        cycle_ts = datetime.now(timezone.utc)
        for name, sensor in sensors.items():
            value = await sensor.read()
            if value is not None:
                store.log_sensor(name, value, timestamp=cycle_ts)
    except Exception:
        logger.exception("Feil i sensorpolling")


def _run_compaction(store: Store) -> None:
    """Kjør rullerende kompaktering av sensordata."""
    try:
        store.compact_sensor_data()
        logger.info("Kompaktering av sensordata fullført")
    except Exception:
        logger.exception("Feil i kompaktering")


async def _control_loop(
    met_client: MetClient,
    store: Store,
    controller: HeatingController,
    sensors: dict[str, TemperatureSensor],
    lat: float,
    lon: float,
) -> None:
    """Kontrollsyklus: les sensorer → hent vær → evaluer → handle → logg."""
    try:
        # Sjekk manuell overstyring
        override = get_manual_override()
        if override is not None:
            logger.info(
                "Kontrollsyklus: manuell overstyring aktiv (%s) — hopper over evaluering",
                override,
            )
            return

        # Les sensorer for evaluering (logging gjøres av _sensor_poll)
        readings = await _read_all_sensors(sensors)

        # Hent værdata
        forecast = await met_client.fetch_forecast(lat, lon)
        c = forecast.current
        store.log_weather(
            temperature=c.air_temperature,
            precipitation=c.precipitation_amount,
            humidity=c.relative_humidity,
            wind_speed=c.wind_speed,
        )

        # Hent gjeldende temperaturgrenser
        thresholds = get_thresholds()

        # Evaluer isrisiko
        currently_on = await controller.is_on()
        result = evaluate(
            forecast,
            readings,
            currently_on,
            ice_temp_min=thresholds["ice_temp_min"],
            ice_temp_max=thresholds["ice_temp_max"],
            critical_temp_min=thresholds["critical_temp_min"],
            critical_temp_max=thresholds["critical_temp_max"],
        )

        # Handle beslutning
        if result.decision == HeatingDecision.TURN_ON and not currently_on:
            await controller.turn_on()
            store.log_event("heating_on", result.reason)
            if result.risk_level == IceRiskLevel.HIGH:
                await notify.send(
                    "Isfare — varme PÅ",
                    f"Risikonivå: HØY\n{result.reason}",
                    priority="high",
                    tags="ice_cube,warning",
                )
        elif result.decision == HeatingDecision.TURN_OFF and currently_on:
            await controller.turn_off()
            store.log_event("heating_off", result.reason)

        logger.info(
            "Kontrollsyklus: %s (risiko=%s, beslutning=%s)",
            result.reason,
            result.risk_level.value,
            result.decision.value,
        )

    except Exception:
        logger.exception("Feil i kontrollsyklus")
        store.log_event("error", "Feil i kontrollsyklus")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    cfg = load_config()
    store = Store(cfg.database.path)
    met_client = MetClient(cfg.weather.user_agent)
    sensors = _create_sensors(cfg)
    controller = _create_controller(cfg)

    configure(
        met_client=met_client,
        store=store,
        lat=cfg.location.lat,
        lon=cfg.location.lon,
        sensors=sensors,
        controller=controller,
        config=cfg,
    )

    store.log_event("startup", "GeoLoop startet")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _sensor_poll,
        "interval",
        minutes=1,
        args=[store, sensors],
    )
    scheduler.add_job(
        _control_loop,
        "interval",
        minutes=10,
        args=[met_client, store, controller, sensors, cfg.location.lat, cfg.location.lon],
    )
    scheduler.add_job(
        _run_compaction,
        "interval",
        hours=1,
        args=[store],
    )
    scheduler.start()

    # Kjør sensorpolling og kontrollsyklus umiddelbart ved oppstart
    await _sensor_poll(store, sensors)
    await _control_loop(
        met_client, store, controller, sensors, cfg.location.lat, cfg.location.lon
    )

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=cfg.web.host,
            port=cfg.web.port,
            log_level="info",
        )
    )

    try:
        await server.serve()
    finally:
        scheduler.shutdown()
        if hasattr(controller, "close"):
            controller.close()
        store.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
