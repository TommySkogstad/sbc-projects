#!/usr/bin/env bats

# Tester for WiFi-onboarding — wifi-check.sh, hostapd.conf, dnsmasq.conf,
# captive-portal.py, wifi-check.service.
# Kjøres lokalt med: bats print-server/tests/test_wifi_onboarding.bats

SETUP_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/setup"
WIFI_CHECK_SH="$SETUP_DIR/wifi-check.sh"
HOSTAPD_CONF="$SETUP_DIR/hostapd.conf"
DNSMASQ_CONF="$SETUP_DIR/dnsmasq.conf"
PORTAL_PY="$SETUP_DIR/captive-portal.py"
WIFI_SERVICE="$SETUP_DIR/wifi-check.service"

# ---------------------------------------------------------------------------
# Eksistens
# ---------------------------------------------------------------------------

@test "wifi-check.sh eksisterer og er kjørbar" {
    [ -f "$WIFI_CHECK_SH" ]
    [ -x "$WIFI_CHECK_SH" ]
}

@test "hostapd.conf eksisterer" {
    [ -f "$HOSTAPD_CONF" ]
}

@test "dnsmasq.conf eksisterer" {
    [ -f "$DNSMASQ_CONF" ]
}

@test "captive-portal.py eksisterer og er kjørbar" {
    [ -f "$PORTAL_PY" ]
    [ -x "$PORTAL_PY" ]
}

@test "wifi-check.service eksisterer" {
    [ -f "$WIFI_SERVICE" ]
}

# ---------------------------------------------------------------------------
# shellcheck
# ---------------------------------------------------------------------------

@test "shellcheck — wifi-check.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$WIFI_CHECK_SH"
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# wifi-check.sh — innhold
# ---------------------------------------------------------------------------

@test "wifi-check.sh venter på kjent nett via iwgetid" {
    grep -q 'iwgetid' "$WIFI_CHECK_SH"
}

@test "wifi-check.sh stopper wpa_supplicant før AP starter" {
    grep -qE 'pkill.*wpa_supplicant|systemctl stop wpa_supplicant|killall.*wpa_supplicant' "$WIFI_CHECK_SH"
}

@test "wifi-check.sh setter IP 192.168.4.1/24 på wlan0" {
    grep -q '192.168.4.1/24' "$WIFI_CHECK_SH"
}

@test "wifi-check.sh starter hostapd, dnsmasq og captive-portal" {
    grep -q 'hostapd' "$WIFI_CHECK_SH"
    grep -q 'dnsmasq' "$WIFI_CHECK_SH"
    grep -q 'captive-portal' "$WIFI_CHECK_SH"
}

@test "wifi-check.sh kjører rfkill unblock wifi" {
    grep -q 'rfkill' "$WIFI_CHECK_SH"
}

# ---------------------------------------------------------------------------
# hostapd.conf — innhold
# ---------------------------------------------------------------------------

@test "hostapd.conf har SSID=printer-rock-setup" {
    grep -q '^ssid=printer-rock-setup' "$HOSTAPD_CONF"
}

@test "hostapd.conf bruker channel 6" {
    grep -q '^channel=6' "$HOSTAPD_CONF"
}

@test "hostapd.conf er åpent nett (ingen WPA2)" {
    ! grep -qE '^wpa=|^wpa_passphrase=' "$HOSTAPD_CONF"
}

@test "hostapd.conf bruker wlan0 interface" {
    grep -q '^interface=wlan0' "$HOSTAPD_CONF"
}

# ---------------------------------------------------------------------------
# dnsmasq.conf — innhold
# ---------------------------------------------------------------------------

@test "dnsmasq.conf har DHCP-range 192.168.4.10-50" {
    grep -qE '^dhcp-range=192\.168\.4\.10,192\.168\.4\.50' "$DNSMASQ_CONF"
}

@test "dnsmasq.conf hijacker DNS til 192.168.4.1" {
    grep -q '^address=/#/192.168.4.1' "$DNSMASQ_CONF"
}

@test "dnsmasq.conf bind kun til wlan0" {
    grep -q '^interface=wlan0' "$DNSMASQ_CONF"
    grep -q '^bind-interfaces' "$DNSMASQ_CONF"
}

# ---------------------------------------------------------------------------
# wifi-check.service — innhold
# ---------------------------------------------------------------------------

@test "wifi-check.service har After=network.target" {
    grep -q 'After=network.target' "$WIFI_SERVICE"
}

@test "wifi-check.service kaller wifi-check.sh" {
    grep -q 'wifi-check.sh' "$WIFI_SERVICE"
}

@test "wifi-check.service har [Install] WantedBy" {
    grep -q '^\[Install\]' "$WIFI_SERVICE"
    grep -q '^WantedBy=' "$WIFI_SERVICE"
}

# ---------------------------------------------------------------------------
# captive-portal.py — innhold (statisk sjekk uten å kjøre)
# ---------------------------------------------------------------------------

@test "captive-portal.py importerer Flask" {
    grep -qE 'from flask import|import flask' "$PORTAL_PY"
}

@test "captive-portal.py lytter på port 80" {
    grep -qE 'port=80|host=.0\.0\.0\.0.*80|host=.192\.168\.4\.1.*80' "$PORTAL_PY"
}

@test "captive-portal.py har validate_ssid-funksjon" {
    grep -q 'def validate_ssid' "$PORTAL_PY"
}

@test "captive-portal.py har validate_psk-funksjon" {
    grep -q 'def validate_psk' "$PORTAL_PY"
}

@test "captive-portal.py bruker subprocess (argv-liste, ikke os.system)" {
    ! grep -q 'os.system' "$PORTAL_PY"
    grep -q 'subprocess' "$PORTAL_PY"
}

@test "captive-portal.py har inline CSS i HTML-template (iOS WebView)" {
    grep -qE '<style|style=' "$PORTAL_PY"
}

# ---------------------------------------------------------------------------
# first-boot.sh — installerer wifi-check.service
# ---------------------------------------------------------------------------

@test "first-boot.sh kopierer wifi-check.service" {
    grep -q 'wifi-check.service' "$SETUP_DIR/first-boot.sh"
}

@test "first-boot.sh kopierer captive-portal.py" {
    grep -q 'captive-portal.py' "$SETUP_DIR/first-boot.sh"
}

@test "first-boot.sh kopierer hostapd.conf" {
    grep -q 'hostapd.conf' "$SETUP_DIR/first-boot.sh"
}

@test "first-boot.sh kopierer dnsmasq.conf" {
    grep -q 'dnsmasq.conf' "$SETUP_DIR/first-boot.sh"
}
