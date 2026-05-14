#!/usr/bin/env python3
"""Captive portal for Rock 3C print-server WiFi-onboarding.

Lytter på 192.168.4.1:80 mens hostapd kjører AP "printer-rock-setup".
- GET /  -> 302 redirect (trigger iOS captive popup; aldri "Success"-tekst)
- GET /portal -> HTML-skjema med inline CSS/JS
- GET /scan  -> JSON med tilgjengelige SSID-er fra `iwlist wlan0 scan`
- POST /save -> validerer SSID/PSK, atomisk skriv til wpa_supplicant.conf,
                svarer 200 FØRST, deretter reconnect i bakgrunnen (3s delay).

Kjøres som systemd-unit (captive-portal.service) startet av wifi-check.sh
når AP-fallback er aktiv.
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, request

app = Flask(__name__)

WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"
WLAN_IFACE = "wlan0"

# IEEE 802.11: SSID 1-32 bytes. Vi begrenser til printable ASCII for å unngå
# escaping-problemer i wpa_supplicant.conf. Ulovlige tegn: ", \, $, `, newline, nul.
_SSID_LEN_RE = re.compile(r"^[\x20-\x7E]{1,32}$")
_FORBIDDEN_SSID_CHARS = set('"\\$`\n\r\x00')

# WPA2-PSK: 8-63 printable ASCII, eller nøyaktig 64 hex.
_PSK_ASCII_RE = re.compile(r"^[\x20-\x7E]{8,63}$")
_PSK_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def validate_ssid(ssid: str) -> str:
    if not isinstance(ssid, str) or not ssid:
        raise ValueError("SSID mangler")
    if any(c in ssid for c in _FORBIDDEN_SSID_CHARS):
        raise ValueError("SSID inneholder ulovlige tegn")
    if not _SSID_LEN_RE.match(ssid):
        raise ValueError("SSID må være 1-32 printable ASCII-tegn")
    return ssid


def validate_psk(psk: str) -> str:
    if not isinstance(psk, str):
        raise ValueError("PSK mangler")
    if _PSK_HEX_RE.match(psk) or _PSK_ASCII_RE.match(psk):
        return psk
    raise ValueError("PSK må være 8-63 printable ASCII eller 64 hex-tegn")


_WPA_HEADER = (
    "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
    "update_config=1\n"
    "country=NO\n"
)


def _read_existing_networks(path: str) -> list[str]:
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return []
    blocks: list[str] = []
    depth = 0
    buf: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if depth == 0 and stripped.startswith("network={"):
            depth = 1
            buf = [line]
            continue
        if depth > 0:
            buf.append(line)
            if "{" in stripped and not stripped.startswith("network={"):
                depth += 1
            if "}" in stripped:
                depth -= 1
                if depth == 0:
                    blocks.append("".join(buf))
                    buf = []
    return blocks


def _format_network_block(ssid: str, psk: str) -> str:
    # 64-tegns hex PSK skal IKKE ha anførselstegn — wpa_supplicant tolker
    # det ellers som ASCII-passphrase, og koblingen feiler.
    if _PSK_HEX_RE.match(psk):
        psk_line = f"    psk={psk}\n"
    else:
        psk_line = f'    psk="{psk}"\n'
    return f'network={{\n    ssid="{ssid}"\n{psk_line}}}\n'


def write_wpa_supplicant(ssid: str, psk: str, path: str | None = None) -> None:
    """Atomisk skriv wpa_supplicant.conf med ny SSID + bevarte eksisterende nett."""
    target = path or WPA_SUPPLICANT_CONF
    existing = _read_existing_networks(target)
    keep = [b for b in existing if f'ssid="{ssid}"' not in b]

    content = _WPA_HEADER + "\n" + _format_network_block(ssid, psk)
    for block in keep:
        content += "\n" + block

    target_path = Path(target)
    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
    try:
        tmp.write_text(content)
        try:
            os.chmod(tmp, 0o600)
        except PermissionError:
            pass
        os.replace(tmp, target_path)
    except OSError:
        # Rydd opp tmp-fil hvis rename feiler — ellers blir den liggende.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _do_reconnect() -> None:
    """Stopp AP-stack, start wpa_supplicant. Hvis kobling feiler -> restart AP."""
    subprocess.run(["systemctl", "stop", "hostapd"], check=False)
    subprocess.run(["systemctl", "stop", "dnsmasq"], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", WLAN_IFACE], check=False)
    subprocess.run(
        ["wpa_supplicant", "-B", "-i", WLAN_IFACE,
         "-c", WPA_SUPPLICANT_CONF, "-D", "nl80211"],
        check=False,
    )
    subprocess.run(["dhclient", WLAN_IFACE], check=False, timeout=30)

    for _ in range(30):
        result = subprocess.run(
            ["iwgetid", "-r", WLAN_IFACE],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return
        time.sleep(1)

    subprocess.run(["systemctl", "restart", "wifi-check.service"], check=False)


def schedule_reconnect(delay: int = 3) -> None:
    """Schedulér reconnect i bakgrunnstråd så HTTP-respons rekker å gå ut."""
    def runner() -> None:
        time.sleep(delay)
        try:
            _do_reconnect()
        except Exception:  # pragma: no cover
            pass

    threading.Thread(target=runner, daemon=True).start()


_IWLIST_ESSID_RE = re.compile(r'ESSID:"([^"]+)"')
_IWLIST_SIGNAL_RE = re.compile(r"Signal level=(-?\d+)\s*dBm")


def scan_networks() -> list[dict]:
    """Parse `iwlist wlan0 scan` output. Returner liste av {ssid, signal_dbm}."""
    try:
        result = subprocess.run(
            ["iwlist", WLAN_IFACE, "scan"],
            capture_output=True, text=True, check=False, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    cells = re.split(r"\bCell \d+ - ", result.stdout)
    networks: list[dict] = []
    seen: set[str] = set()
    for cell in cells[1:]:
        m_ssid = _IWLIST_ESSID_RE.search(cell)
        if not m_ssid:
            continue
        ssid = m_ssid.group(1)
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        m_sig = _IWLIST_SIGNAL_RE.search(cell)
        signal = int(m_sig.group(1)) if m_sig else None
        networks.append({"ssid": ssid, "signal_dbm": signal})
    networks.sort(key=lambda n: n["signal_dbm"] or -999, reverse=True)
    return networks


# Inline CSS — iOS captive WebView laster ikke ekstern assets.
_PORTAL_HTML = """<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Printer-Rock — WiFi-oppsett</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; margin: 0;
       padding: 2em 1em; background: #f5f5f7; color: #1d1d1f; }
h1 { font-size: 1.4em; margin-top: 0; }
.card { background: #fff; border-radius: 12px; padding: 1.2em;
        max-width: 480px; margin: 0 auto; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
label { display: block; margin: .8em 0 .3em; font-weight: 600; }
input, select { width: 100%; padding: .7em; font-size: 1em;
                border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; }
button { width: 100%; padding: .8em; font-size: 1em; margin-top: 1em;
         background: #007aff; color: #fff; border: 0; border-radius: 8px; }
.error { color: #c00; margin-top: .8em; }
</style>
</head>
<body>
<div class="card">
<h1>Koble printer-rock til WiFi</h1>
<p>Velg ditt hjemmenett og skriv inn passord.</p>
<form method="post" action="/save">
<label for="ssid">Nettverk (SSID)</label>
<input type="text" id="ssid" name="ssid" required maxlength="32"
       autocapitalize="off" autocorrect="off">
<label for="psk">Passord</label>
<input type="password" id="psk" name="psk" required minlength="8" maxlength="64">
<button type="submit">Lagre og koble til</button>
</form>
</div>
<script>
fetch("/scan").then(r => r.json()).then(nets => {
  if (!nets.length) return;
  var input = document.getElementById("ssid");
  var list = document.createElement("datalist");
  list.id = "ssid-list";
  nets.forEach(n => {
    var o = document.createElement("option");
    o.value = n.ssid;
    list.appendChild(o);
  });
  input.setAttribute("list", "ssid-list");
  input.parentNode.appendChild(list);
}).catch(() => {});
</script>
</body>
</html>
"""

_SAVED_HTML = """<!doctype html>
<html lang="no"><head><meta charset="utf-8">
<style>body{{font-family:-apple-system,sans-serif;padding:2em;text-align:center}}</style>
</head><body>
<h2>Lagret. Kobler til…</h2>
<p>Printer-rock prøver nå å koble seg til <b>{ssid}</b>. Du kan lukke dette vinduet.</p>
<p>Hvis kobling feiler, vises oppsetts-nettverket igjen om et minutt.</p>
</body></html>
"""


def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/")
def root():
    # iOS captive-detect: aldri svar 200 med "Success" — alltid redirect.
    return _no_cache(redirect("/portal", code=302))


@app.route("/hotspot-detect.html")
@app.route("/generate_204")
@app.route("/ncsi.txt")
@app.route("/connecttest.txt")
@app.route("/library/test/success.html")
def captive_probes():
    return _no_cache(redirect("/portal", code=302))


@app.route("/portal")
def portal():
    return _no_cache(app.response_class(_PORTAL_HTML, mimetype="text/html"))


@app.route("/scan")
def scan():
    return _no_cache(jsonify(scan_networks()))


@app.route("/save", methods=["POST"])
def save():
    raw_ssid = request.form.get("ssid")
    raw_psk = request.form.get("psk")
    if raw_ssid is None or raw_psk is None:
        abort(400)
    try:
        ssid = validate_ssid(raw_ssid)
        psk = validate_psk(raw_psk)
    except ValueError:
        abort(400)

    write_wpa_supplicant(ssid, psk)
    # Svar 200 FØRST, reconnect schedulert i bakgrunnstråd (3s delay)
    schedule_reconnect(3)
    # SSID kan inneholde HTML-spesialtegn (<, >, &) som passerer ASCII-regex
    # — escape før template-formatering for å unngå XSS.
    safe_ssid = html.escape(ssid)
    return _no_cache(
        app.response_class(_SAVED_HTML.format(ssid=safe_ssid), mimetype="text/html")
    )


if __name__ == "__main__":  # pragma: no cover
    # iOS ATS-unntak gjelder kun port 80 i captive WebView.
    app.run(host="192.168.4.1", port=80)
