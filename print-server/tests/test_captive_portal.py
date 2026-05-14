"""Tester for captive-portal.py (Flask captive portal for Rock 3C WiFi-onboarding).

Kjøres lokalt med: pytest print-server/tests/test_captive_portal.py
Forutsetter: pip install flask pytest
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SETUP_DIR = Path(__file__).resolve().parent.parent / "setup"
PORTAL_PATH = SETUP_DIR / "captive-portal.py"


def _load_portal_module():
    """Last captive-portal.py som modul (filnavnet inneholder bindestrek)."""
    spec = importlib.util.spec_from_file_location("captive_portal", PORTAL_PATH)
    assert spec and spec.loader, "Kunne ikke laste captive-portal.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["captive_portal"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def portal():
    pytest.importorskip("flask")
    return _load_portal_module()


@pytest.fixture
def client(portal, tmp_path, monkeypatch):
    wpa_conf = tmp_path / "wpa_supplicant.conf"
    wpa_conf.write_text(
        'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n'
        'update_config=1\n'
        'country=NO\n\n'
        'network={\n'
        '    ssid="venn 1"\n'
        '    psk="hemmelig"\n'
        '}\n'
    )
    monkeypatch.setattr(portal, "WPA_SUPPLICANT_CONF", str(wpa_conf))
    portal.app.config["TESTING"] = True
    return portal.app.test_client()


# ---------------------------------------------------------------------------
# iOS captive-popup-trigger: GET / må returnere 302, ikke 200 med "Success"
# ---------------------------------------------------------------------------

def test_root_returns_302(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert b"Success" not in resp.data


def test_ios_probe_endpoints_redirect(client):
    """Apple/Android/MS captive-detect-paths skal alle redirecte."""
    for path in ("/hotspot-detect.html", "/generate_204", "/ncsi.txt"):
        resp = client.get(path)
        assert resp.status_code in (302, 303), f"{path} returnerte {resp.status_code}"


# ---------------------------------------------------------------------------
# /scan: returnerer JSON med SSID-er fra iwlist
# ---------------------------------------------------------------------------

def test_scan_returns_json_list(client):
    fake_iwlist = (
        "wlan0  Scan completed :\n"
        '          Cell 01 - Address: AA:BB:CC:DD:EE:FF\n'
        '                    ESSID:"venn 1"\n'
        '                    Quality=70/70  Signal level=-40 dBm\n'
        '          Cell 02 - Address: 11:22:33:44:55:66\n'
        '                    ESSID:"naboen"\n'
        '                    Quality=40/70  Signal level=-70 dBm\n'
    )
    with patch("subprocess.run") as mrun:
        mrun.return_value = MagicMock(stdout=fake_iwlist, returncode=0)
        resp = client.get("/scan")
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    ssids = [n["ssid"] for n in data]
    assert "venn 1" in ssids
    assert "naboen" in ssids


# ---------------------------------------------------------------------------
# POST /save: validerer input, skriver wpa_supplicant.conf, svarer 200 først
# ---------------------------------------------------------------------------

def test_save_writes_wpa_supplicant_conf(client, portal, monkeypatch):
    """Lagrer SSID+passord til wpa_supplicant.conf og bevarer kjente nett."""
    reconnect_calls = []
    monkeypatch.setattr(portal, "schedule_reconnect",
                        lambda delay=3: reconnect_calls.append(delay))

    resp = client.post("/save", data={"ssid": "nytt-nett", "psk": "passord123"})
    assert resp.status_code == 200

    content = Path(portal.WPA_SUPPLICANT_CONF).read_text()
    # Nytt nett skrevet
    assert 'ssid="nytt-nett"' in content
    assert 'psk="passord123"' in content
    # Eksisterende nett bevart (venn 1)
    assert 'ssid="venn 1"' in content
    # Reconnect schedulert med 3s delay
    assert reconnect_calls == [3]


def test_save_rejects_too_short_psk(client):
    resp = client.post("/save", data={"ssid": "test", "psk": "kort"})
    assert resp.status_code == 400


def test_save_rejects_too_long_ssid(client):
    resp = client.post("/save", data={"ssid": "a" * 33, "psk": "passord123"})
    assert resp.status_code == 400


def test_save_rejects_ssid_with_dangerous_chars(client):
    for bad in ('ssid"injection', 'ssid\\back', "ssid\nnewline", "ssid$var"):
        resp = client.post("/save", data={"ssid": bad, "psk": "passord123"})
        assert resp.status_code == 400, f"SSID {bad!r} burde vært avvist"


def test_save_accepts_64_hex_psk(client):
    psk = "a" * 64
    resp = client.post("/save", data={"ssid": "hex-net", "psk": psk})
    assert resp.status_code == 200


def test_save_rejects_missing_fields(client):
    assert client.post("/save", data={"ssid": "x"}).status_code == 400
    assert client.post("/save", data={"psk": "passord123"}).status_code == 400


# ---------------------------------------------------------------------------
# Validerings-funksjoner (rene, ingen subprocess)
# ---------------------------------------------------------------------------

def test_validate_ssid_accepts_normal(portal):
    assert portal.validate_ssid("mitt-nett") == "mitt-nett"
    assert portal.validate_ssid("venn 1") == "venn 1"


def test_validate_ssid_rejects_dangerous(portal):
    for bad in ('a"b', "a\\b", "a\nb", "a`b", "a$b", "", "a" * 33):
        with pytest.raises(ValueError):
            portal.validate_ssid(bad)


def test_validate_psk_accepts_ascii(portal):
    assert portal.validate_psk("passord123") == "passord123"


def test_validate_psk_accepts_hex64(portal):
    assert portal.validate_psk("a" * 64) == "a" * 64


def test_validate_psk_rejects_short(portal):
    with pytest.raises(ValueError):
        portal.validate_psk("kort")


def test_validate_psk_rejects_long(portal):
    with pytest.raises(ValueError):
        portal.validate_psk("a" * 65)  # 65 ascii = ugyldig (max 63 ascii, ellers 64 hex)
