from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StubController:
    """Stub-controller for utvikling og testing uten hardware.

    Holder tilstand i minnet.
    """

    def __init__(self) -> None:
        self._on = False

    async def turn_on(self) -> None:
        self._on = True
        logger.info("StubController: PÅ")

    async def turn_off(self) -> None:
        self._on = False
        logger.info("StubController: AV")

    async def is_on(self) -> bool:
        return self._on
