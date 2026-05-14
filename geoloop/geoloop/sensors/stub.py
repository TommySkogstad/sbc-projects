from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StubSensor:
    """Stub-sensor for utvikling og testing uten hardware.

    Returnerer en konfigurerbar temperaturverdi.
    """

    def __init__(self, sensor_id: str, value: float | None = 20.0) -> None:
        self.sensor_id = sensor_id
        self.value = value

    async def read(self) -> float | None:
        """Returnerer den konfigurerte verdien."""
        logger.debug("StubSensor %s: %.1f°C", self.sensor_id, self.value or 0)
        return self.value
