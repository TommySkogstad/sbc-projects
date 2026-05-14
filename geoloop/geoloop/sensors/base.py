from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TemperatureSensor(Protocol):
    """Protokoll for temperatursensorer."""

    sensor_id: str

    async def read(self) -> float | None:
        """Les temperatur i grader Celsius. Returnerer None ved feil."""
        ...
