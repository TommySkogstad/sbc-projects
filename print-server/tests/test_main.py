"""Tester for print-server/web/main.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

MAIN_PY = Path(__file__).resolve().parent.parent / "web" / "main.py"
WEB_DIR = MAIN_PY.parent
REQUIREMENTS_TXT = WEB_DIR / "requirements.txt"


def test_no_utcnow_in_main():
    """main.py skal ikke bruke deprecated datetime.utcnow()."""
    source = MAIN_PY.read_text()
    assert "utcnow" not in source, "Fant deprecated datetime.utcnow() i main.py"


def _pinned_version(requirements_text: str, package: str) -> tuple[int, ...]:
    """Hent den `==`-pinnede versjonen for en pakke fra requirements.txt som int-tuple."""
    for line in requirements_text.splitlines():
        m = re.match(
            rf"^{re.escape(package)}(?:\[[^\]]*\])?==([0-9]+(?:\.[0-9]+)*)",
            line.strip(),
        )
        if m:
            return tuple(int(part) for part in m.group(1).split("."))
    raise AssertionError(f"Fant ingen '=='-pin for {package} i requirements.txt")


def test_requirements_pin_safe_dependency_versions():
    """requirements.txt skal pinne python-multipart og starlette til versjoner
    uten kjente HIGH-sårbarheter (OSV/GHSA, issue #63).

    Terskler avledet fra pip-audit sine fix-versjoner:
    - python-multipart >= 0.0.31 (CVE-2026-53538/53539/53540 m.fl.)
    - starlette        >= 1.3.1  (PYSEC-2026-249, GHSA-82w8-qh3p-5jfq m.fl.)
    """
    text = REQUIREMENTS_TXT.read_text()
    assert _pinned_version(text, "python-multipart") >= (0, 0, 31), (
        "python-multipart er pinnet til en versjon med kjente sårbarheter "
        "(krever >= 0.0.31, se issue #63)"
    )
    assert _pinned_version(text, "starlette") >= (1, 3, 1), (
        "starlette er pinnet til en versjon med kjente sårbarheter "
        "(krever >= 1.3.1, se issue #63)"
    )


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


def test_print_multipart_file_upload_happy_path(print_app, monkeypatch, tmp_path):
    """POST /print med gyldig PDF + multipart-parsing skal returnere 200 + job-id."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    # Mock subprosesser for lp og pdfinfo
    def mock_run(cmd, **kw):
        from subprocess import CompletedProcess  # noqa: PLC0415

        if cmd[0] == "pdfinfo":
            return CompletedProcess(cmd, 0, "Pages:                5\n", "")
        elif cmd[0] == "lp":
            return CompletedProcess(cmd, 0, "request id is lp-12345\n", "")
        elif cmd[0] == "lpstat":
            return CompletedProcess(cmd, 0, "printer auto-USB-Printer is idle\n", "")
        return CompletedProcess(cmd, 1, "", "Unknown command")

    monkeypatch.delenv("PRINT_PASSWORD", raising=False)
    monkeypatch.setattr("main.run", mock_run)

    # Minimal gyldig PDF header
    pdf_data = b"%PDF-1.4\n%Test\n" + b"x" * 1000

    with TestClient(print_app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/print",
            data={"copies": "1", "sides": "one-sided"},
            files={"file": ("test.pdf", pdf_data, "application/pdf")},
            headers={"Accept": "application/json"},  # Eksplisitt JSON-respons
        )

    assert resp.status_code == 200
    result = resp.json()
    assert "job" in result
    assert "lp-12345" in result["job"]


def test_print_multipart_rejects_oversized_file(print_app, monkeypatch):
    """POST /print skal avvise fil større enn MAX_UPLOAD_MB (413)."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    # Mock MAX_UPLOAD_MB i main-modulen
    monkeypatch.delenv("PRINT_PASSWORD", raising=False)
    monkeypatch.setattr("main.MAX_UPLOAD_MB", 1)

    # 2 MB fil (over limit) — vil bli avvist FØR pdfinfo-kall
    oversized_pdf = b"%PDF-1.4\n" + b"x" * (2 * 1024 * 1024)

    with TestClient(print_app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/print",
            files={"file": ("big.pdf", oversized_pdf, "application/pdf")},
            headers={"Accept": "application/json"},
        )

    # Forventet 413 fordi fil er større enn MAX_UPLOAD_MB (1 MB)
    assert resp.status_code == 413
    detail = resp.json()["detail"].lower()
    assert "fil" in detail


def test_print_multipart_rejects_non_pdf(print_app, monkeypatch):
    """POST /print skal avvise ikke-PDF (400) — verifiserer magic bytes."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    monkeypatch.delenv("PRINT_PASSWORD", raising=False)

    # Ikke PDF (mangler "%PDF-" magic)
    not_pdf = b"This is not a PDF file\n" + b"x" * 1000

    with TestClient(print_app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/print",
            data={"copies": "1", "sides": "one-sided"},
            files={"file": ("notpdf.txt", not_pdf, "text/plain")},
            headers={"Accept": "application/json"},
        )

    # Skal feile med 400 fordi magic bytes mangler (ikke PDF-start)
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "pdf" in detail


def test_print_multipart_parsing_enabled(print_app, monkeypatch):
    """python-multipart@>=0.0.21 lar FastAPI parse multipart/form-data riktig."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    def mock_run(cmd, **kw):
        from subprocess import CompletedProcess  # noqa: PLC0415

        if cmd[0] == "pdfinfo":
            return CompletedProcess(cmd, 0, "Pages:                10\n", "")
        elif cmd[0] == "lp":
            return CompletedProcess(cmd, 0, "request id is job-999\n", "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.delenv("PRINT_PASSWORD", raising=False)
    monkeypatch.setattr("main.run", mock_run)
    pdf_data = b"%PDF-1.4\n" + b"x" * 5000

    with TestClient(print_app, raise_server_exceptions=False) as client:
        # POST /print med multipart-data skal parse riktig
        resp = client.post(
            "/print",
            files={"file": ("document.pdf", pdf_data, "application/pdf")},
            headers={"Accept": "application/json"},
        )

    # Multipart-parsing skal fungere — job skal være opprettet
    assert resp.status_code == 200
    result = resp.json()
    assert result["ok"] is True
    assert "job" in result
    assert result["pages"] == 10
