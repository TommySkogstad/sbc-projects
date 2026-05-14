from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

W1_DEVICES_PATH = Path("/sys/bus/w1/devices")


class DS18B20Sensor:
    """DS18B20 temperatursensor via 1-Wire.

    Leser fra ``/sys/bus/w1/devices/{sensor_id}/w1_slave``.
    """

    def __init__(self, sensor_id: str) -> None:
        self.sensor_id = sensor_id
        self._path = W1_DEVICES_PATH / sensor_id / "w1_slave"

    def _read_sync(self) -> float | None:
        """Synkron lesing av sensorverdi."""
        try:
            text = self._path.read_text()
        except OSError:
            logger.warning("Kan ikke lese sensor %s", self.sensor_id)
            return None

        lines = text.strip().splitlines()
        if len(lines) < 2:
            logger.warning("Uventet format fra sensor %s", self.sensor_id)
            return None

        # Linje 1: CRC-sjekk — slutter med YES eller NO
        if not lines[0].strip().endswith("YES"):
            logger.warning("CRC-feil fra sensor %s", self.sensor_id)
            return None

        # Linje 2: temperatur som t=XXXXX
        parts = lines[1].split("t=")
        if len(parts) != 2:
            logger.warning("Kan ikke parse temperatur fra sensor %s", self.sensor_id)
            return None

        try:
            return int(parts[1]) / 1000.0
        except ValueError:
            logger.warning("Ugyldig temperaturverdi fra sensor %s", self.sensor_id)
            return None

    async def read(self) -> float | None:
        """Les temperatur i grader Celsius. Returnerer None ved feil."""
        return await asyncio.to_thread(self._read_sync)
