from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RelayController:
    """Styrer varmepumpe (K1) og sirkulasjonspumpe (K2) via GPIO-relé.

    K2 følger alltid K1 — begge slås av/på samtidig.
    Krever ``gpiozero`` — installer med ``pip install geoloop[rpi]``.
    """

    def __init__(
        self,
        heat_pump_pin: int,
        circulation_pump_pin: int,
        active_high: bool = True,
    ) -> None:
        from gpiozero import OutputDevice

        self._k1 = OutputDevice(
            heat_pump_pin, active_high=active_high, initial_value=False
        )
        self._k2 = OutputDevice(
            circulation_pump_pin, active_high=active_high, initial_value=False
        )
        self._on = False
        logger.info(
            "RelayController initialisert: K1=GPIO%d, K2=GPIO%d",
            heat_pump_pin,
            circulation_pump_pin,
        )

    async def turn_on(self) -> None:
        """Slå på varmepumpe og sirkulasjonspumpe."""
        self._k1.on()
        self._k2.on()
        self._on = True
        logger.info("Relé PÅ (K1 + K2)")

    async def turn_off(self) -> None:
        """Slå av varmepumpe og sirkulasjonspumpe."""
        self._k1.off()
        self._k2.off()
        self._on = False
        logger.info("Relé AV (K1 + K2)")

    async def is_on(self) -> bool:
        """Sjekk om varmesystemet er på."""
        return self._on

    def close(self) -> None:
        """Frigjør GPIO-ressurser."""
        self._k1.close()
        self._k2.close()
        logger.info("GPIO-ressurser frigjort")
