"""Tester for print-server/web/main.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

MAIN_PY = Path(__file__).resolve().parent.parent / "web" / "main.py"
WEB_DIR = MAIN_PY.parent


def test_no_utcnow_in_main():
    """main.py skal ikke bruke deprecated datetime.utcnow()."""
    source = MAIN_PY.read_text()
    assert "utcnow" not in source, "Fant deprecated datetime.utcnow() i main.py"


def test_timestamp_is_iso8601_utc_with_z_suffix():
    """Timestamp-format skal være ISO-8601 UTC med Z-suffiks (f.eks. 2024-01-15T10:30:00Z)."""
    sys.path.insert(0, str(WEB_DIR))
    from main import _iso_utc_now  # noqa: PLC0415

    ts = _iso_utc_now()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), (
        f"Timestamp {ts!r} matcher ikke forventet ISO-8601 UTC Z-format"
    )


@pytest.fixture(scope="module")
def print_app():
    pytest.importorskip("httpx")
    if str(WEB_DIR) not in sys.path:
        sys.path.insert(0, str(WEB_DIR))
    sys.modules.pop("main", None)
    import main as m  # noqa: PLC0415
    return m.app


def test_print_returns_401_without_credentials_when_password_set(print_app, monkeypatch):
    """POST /print skal returnere 401 når PRINT_PASSWORD er satt og ingen credentials er gitt."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    monkeypatch.setenv("PRINT_PASSWORD", "hemmelighetsord")
    with TestClient(print_app, raise_server_exceptions=False) as client:
        resp = client.post("/print")
    assert resp.status_code == 401


def test_queue_returns_401_without_credentials_when_password_set(print_app, monkeypatch):
    """GET /queue skal returnere 401 når PRINT_PASSWORD er satt og ingen credentials er gitt."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    monkeypatch.setenv("PRINT_PASSWORD", "hemmelighetsord")
    with TestClient(print_app, raise_server_exceptions=False) as client:
        resp = client.get("/queue")
    assert resp.status_code == 401


def test_print_accessible_without_credentials_when_no_password_set(print_app, monkeypatch):
    """POST /print skal IKKE kreve auth når PRINT_PASSWORD ikke er satt (bakoverkompatibilitet)."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    monkeypatch.delenv("PRINT_PASSWORD", raising=False)
    with TestClient(print_app, raise_server_exceptions=False) as client:
        # Ingen credentials, ingen fil — skal feile med 422 (validering), ikke 401
        resp = client.post("/print")
    assert resp.status_code != 401
