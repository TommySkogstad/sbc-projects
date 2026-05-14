#!/usr/bin/env bash
# Renderer airprint.service.tmpl til /etc/avahi/services/airprint.service
# via envsubst. Kalles av add-printer.sh med PRINTER_NAME satt i miljøet.
set -euo pipefail

TMPL="${AIRPRINT_TMPL:-/usr/local/share/print-server/airprint.service.tmpl}"
OUT="${AIRPRINT_OUT:-/etc/avahi/services/airprint.service}"

PRINTER_NAME="${PRINTER_NAME:-auto-USB-Printer}" envsubst '$PRINTER_NAME' < "$TMPL" > "$OUT"

if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "$OUT"
fi
