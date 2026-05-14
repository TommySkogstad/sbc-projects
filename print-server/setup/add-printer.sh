#!/usr/bin/env bash
# Automatisk printer-registrering via CUPS ved USB hot-plug.
# Kalles av 99-usb-printer.rules via systemd-run --no-block.
set -euo pipefail

LOCK_FILE="${LOCK_FILE:-/var/lock/add-printer.lock}"
LOG_FILE="${LOG_FILE:-/var/log/add-printer.log}"
RENDER_SH="${RENDER_SH:-/usr/local/bin/render-airprint.sh}"
SLEEP_SEC="${SLEEP_SEC:-2}"
PRINTER_NAME="auto-USB-Printer"

log() { echo "[add-printer] $(date -Iseconds) $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[add-printer] $*"; }

# flock for debounce — udev sender gjerne flere add-events ved plug
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "Allerede pågående — hopper over duplikat-event"
    exit 0
fi

# Vent til CUPS er klar (retry 3 ganger, 2s mellom)
for i in 1 2 3; do
    if lpstat -H >/dev/null 2>&1; then
        break
    fi
    log "CUPS ikke klar, forsøk $i/3..."
    if [[ $i -eq 3 ]]; then
        log "CUPS ikke tilgjengelig etter 3 forsøk — avslutter"
        exit 1
    fi
    sleep "$SLEEP_SEC"
done

# Finn USB-printer-URI
USB_URI=$(lpinfo -v 2>/dev/null | grep -m1 'usb://' | awk '{print $2}')
if [[ -z "$USB_URI" ]]; then
    log "Ingen USB-printer funnet — avslutter"
    exit 0
fi

log "Fant printer-URI: $USB_URI"

# Registrer printer i CUPS med IPP Everywhere (driverløs)
lpadmin -p "$PRINTER_NAME" -E -v "$USB_URI" -m everywhere --enable
log "Printer $PRINTER_NAME registrert på $USB_URI"

# Oppdater Avahi AirPrint-tjeneste
export PRINTER_NAME
if [[ -x "$RENDER_SH" ]]; then
    "$RENDER_SH"
    systemctl reload avahi-daemon
    log "Avahi AirPrint-tjeneste oppdatert"
fi
