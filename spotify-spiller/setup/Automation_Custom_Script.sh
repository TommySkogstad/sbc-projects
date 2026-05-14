#!/bin/bash
# DietPi Automation_Custom_Script — kjøres automatisk ved første boot
# Konfigurerer raspotify og ALSA for Rock 3C AUX-utgang

set -euo pipefail

# LIBRESPOT_NAME kan overstyres fra dietpi.txt via Automation_Custom_Script_Inputs
# Format i dietpi.txt: Automation_Custom_Script_Inputs=Rock
LIBRESPOT_NAME="${1:-Rock}"

log() { echo "[spotify-spiller] $*"; }

log "Starter konfigurasjon av raspotify og ALSA (navn: $LIBRESPOT_NAME)"

# --- ALSA: sett RK3566 onboard AUX (card 0) som standard ---
cat > /etc/asound.conf <<ALSA
defaults.pcm.card 0
defaults.ctl.card 0
ALSA

log "ALSA defaults satt til card 0 (RK3566 onboard)"

# --- Raspotify-konfig ---
# Vent til raspotify er installert (dietpi-software kjøres asynkront)
TIMEOUT=300
ELAPSED=0
while [ ! -f /etc/raspotify/conf ] && [ $ELAPSED -lt $TIMEOUT ]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ ! -f /etc/raspotify/conf ]; then
    log "FEIL: /etc/raspotify/conf ikke funnet etter ${TIMEOUT}s — hopper over konfig"
    exit 1
fi

cat > /etc/raspotify/conf <<CONF
LIBRESPOT_NAME="${LIBRESPOT_NAME}"
LIBRESPOT_BITRATE="320"
LIBRESPOT_INITIAL_VOLUME="60"
LIBRESPOT_DEVICE_TYPE="speaker"
LIBRESPOT_BACKEND="alsa"
LIBRESPOT_DEVICE="default"
CONF

log "Raspotify konfig skrevet til /etc/raspotify/conf"

# --- Restart raspotify ---
if systemctl is-enabled raspotify &>/dev/null; then
    systemctl restart raspotify
    log "raspotify restartet"
else
    log "raspotify ikke aktivert ennå — starter tjenesten"
    systemctl enable --now raspotify || true
fi

log "Konfigurasjon fullført. '${LIBRESPOT_NAME}' skal nå vises i Spotify-appen."
