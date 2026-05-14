from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HeatingController(Protocol):
    """Protokoll for styring av varmesystemet."""

    async def turn_on(self) -> None: ...

    async def turn_off(self) -> None: ...

    async def is_on(self) -> bool: ...
