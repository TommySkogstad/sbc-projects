"""Tester for print-server/web/main.py."""
from __future__ import annotations

import re
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / "web" / "main.py"


def test_no_utcnow_in_main():
    """main.py skal ikke bruke deprecated datetime.utcnow()."""
    source = MAIN_PY.read_text()
    assert "utcnow" not in source, "Fant deprecated datetime.utcnow() i main.py"


def test_timestamp_is_iso8601_utc_with_z_suffix():
    """Timestamp-format skal være ISO-8601 UTC med Z-suffiks (f.eks. 2024-01-15T10:30:00Z)."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), (
        f"Timestamp {ts!r} matcher ikke forventet ISO-8601 UTC Z-format"
    )
