"""Regresjonstester for låste avhengigheter i requirements*.lock (issue #87)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOCK_FILES = [
    PROJECT_DIR / "requirements.lock",
    PROJECT_DIR / "requirements-dev.lock",
]

# Laveste versjon uten kjente sårbarheter (fix-versjon fra OSV/GHSA).
MIN_SAFE_VERSIONS = {
    "anyio": (4, 14, 2),  # GHSA-82r6-8w77-94w6, GHSA-5p39-cfhj-2xmp
    "starlette": (1, 3, 1),  # GHSA-82w8-qh3p-5jfq
    "certifi": (2026, 10, 19),  # GHSA-6q48-6c7w-9gw2
}


def _locked_version(lock_text: str, package: str) -> tuple[int, ...]:
    """Hent den `==`-låste versjonen for en pakke fra en lock-fil som int-tuple."""
    for line in lock_text.splitlines():
        m = re.match(rf"^{re.escape(package)}==([0-9]+(?:\.[0-9]+)*)", line)
        if m:
            return tuple(int(part) for part in m.group(1).split("."))
    raise AssertionError(f"Fant ingen '=='-pin for {package}")


@pytest.mark.parametrize("lock_file", LOCK_FILES, ids=lambda p: p.name)
@pytest.mark.parametrize("package", sorted(MIN_SAFE_VERSIONS))
def test_lock_pins_safe_dependency_versions(lock_file: Path, package: str) -> None:
    """Lock-filene skal låse anyio, starlette og certifi til versjoner uten kjente sårbarheter.

    requirements.lock brukes i prod av Dockerfile og scripts/install.sh, og
    requirements-dev.lock er det CI tester mot. OSV-Scanner i security-weekly
    leser ikke *.lock-filer, så sårbare versjoner her ble ikke fanget (issue #87).
    """
    minimum = MIN_SAFE_VERSIONS[package]
    locked = _locked_version(lock_file.read_text(), package)
    assert locked >= minimum, (
        f"{lock_file.name} låser {package} til {'.'.join(map(str, locked))}, som har "
        f"kjente sårbarheter (krever >= {'.'.join(map(str, minimum))}, se issue #87)"
    )
