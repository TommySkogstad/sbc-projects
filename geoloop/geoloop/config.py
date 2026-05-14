from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LocationConfig:
    lat: float
    lon: float


@dataclass
class WeatherConfig:
    user_agent: str
    poll_interval_minutes: int = 30


@dataclass
class DatabaseConfig:
    path: str = "geoloop.db"


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class RelayConfig:
    gpio_pin: int
    active_high: bool = True


@dataclass
class SensorConfig:
    id: str


@dataclass
class GroundLoopConfig:
    loops: int = 8
    total_length_m: int = 900
    pipe_outer_mm: int = 20
    pipe_wall_mm: int = 2


@dataclass
class TankConfig:
    volume_liters: int = 200


@dataclass
class ThresholdsConfig:
    ice_temp_min: float = -3.0
    ice_temp_max: float = 3.0
    critical_temp_min: float = -1.0
    critical_temp_max: float = 2.0


@dataclass
class AppConfig:
    location: LocationConfig
    weather: WeatherConfig
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    web: WebConfig = field(default_factory=WebConfig)
    relays: dict[str, RelayConfig] | None = None
    sensors: dict[str, SensorConfig] | None = None
    ground_loop: GroundLoopConfig | None = None
    tank: TankConfig | None = None
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Last konfigurasjon fra YAML-fil.

    Prøver ``config.yaml`` først, deretter ``config.example.yaml``.
    """
    if path is None:
        root = Path.cwd()
        candidates = [root / "config.yaml", root / "config.example.yaml"]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        if path is None:
            raise FileNotFoundError(
                "Fant verken config.yaml eller config.example.yaml"
            )

    raw = yaml.safe_load(path.read_text())

    relays = None
    if "relays" in raw:
        relays = {
            name: RelayConfig(**cfg) for name, cfg in raw["relays"].items()
        }

    sensors = None
    if "sensors" in raw:
        sensors = {
            name: SensorConfig(**cfg) for name, cfg in raw["sensors"].items()
        }

    ground_loop = None
    if "ground_loop" in raw:
        ground_loop = GroundLoopConfig(**raw["ground_loop"])

    tank = None
    if "tank" in raw:
        tank = TankConfig(**raw["tank"])

    thresholds = ThresholdsConfig(**raw.get("thresholds", {}))

    return AppConfig(
        location=LocationConfig(**raw["location"]),
        weather=WeatherConfig(**raw["weather"]),
        database=DatabaseConfig(**raw.get("database", {})),
        web=WebConfig(**raw.get("web", {})),
        relays=relays,
        sensors=sensors,
        ground_loop=ground_loop,
        tank=tank,
        thresholds=thresholds,
    )
