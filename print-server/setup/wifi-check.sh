#!/usr/bin/env bash
# WiFi-sjekk og AP-fallback for Rock 3C print-server.
#
# Ved boot: vent inntil 15 sek på at wlan0 assosierer med et kjent nett.
# Hvis ikke -> stopp wpa_supplicant, sett statisk IP 192.168.4.1/24,
# start hostapd + dnsmasq + captive-portal slik at bruker kan velge SSID
# fra mobilen via "printer-rock-setup".
#
# Kjent nett bevares mellom kjøringer (captive-portal skriver til
# wpa_supplicant.conf og bevarer eksisterende network={} -blokker).

set -euo pipefail

WLAN_IFACE="wlan0"
AP_IP="192.168.4.1/24"
LOG="/var/log/wifi-check.log"
WAIT_SECONDS=15

log() { echo "[wifi-check] $(date -Iseconds) $*" | tee -a "$LOG"; }

# rfkill kan soft-blokkere WiFi etter cold boot
rfkill unblock wifi 2>/dev/null || true

log "Venter inntil ${WAIT_SECONDS}s på assosiering med kjent nett..."
for _ in $(seq 1 "$WAIT_SECONDS"); do
    if iwgetid -r "$WLAN_IFACE" >/dev/null 2>&1; then
        ssid="$(iwgetid -r "$WLAN_IFACE" 2>/dev/null || true)"
        if [[ -n "$ssid" ]]; then
            log "Koblet til kjent nett: $ssid — ingen AP-fallback nødvendig."
            exit 0
        fi
    fi
    sleep 1
done

log "Ingen kjent WiFi funnet — starter AP-fallback (printer-rock-setup)."

# hostapd og wpa_supplicant kan ikke kjøre samtidig på samme interface.
systemctl stop wpa_supplicant 2>/dev/null || true
pkill -f "wpa_supplicant.*${WLAN_IFACE}" 2>/dev/null || true

# Rydd interface og sett statisk AP-IP
ip link set "$WLAN_IFACE" down 2>/dev/null || true
ip addr flush dev "$WLAN_IFACE" 2>/dev/null || true
ip link set "$WLAN_IFACE" up
ip addr add "$AP_IP" dev "$WLAN_IFACE"

# Start AP-stack. Captive-portal lytter på port 80 og redirecter alt til /portal.
systemctl start hostapd
systemctl start dnsmasq
systemctl start captive-portal

log "AP-fallback aktiv: SSID=printer-rock-setup, captive-portal på http://192.168.4.1/"
