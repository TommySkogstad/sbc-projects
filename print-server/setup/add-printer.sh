#!/usr/bin/env bash
# Automatisk printer-registrering via CUPS ved USB hot-plug.
# Kalles av 99-usb-printer.rules via systemd-run --no-block.
#
# Strategi:
# 1. Les USB VID/PID
# 2. VID-basert routing til riktig driver (HP/Canon/Brother/Epson/...)
# 3. Avvis kjent-ikke-støttede VID-er med tydelig melding
# 4. Fallback: IPP Everywhere → Foomatic-match → manuell PPD via web-UI
set -euo pipefail

LOCK_FILE="${LOCK_FILE:-/var/lock/add-printer.lock}"
LOG_FILE="${LOG_FILE:-/var/log/add-printer.log}"
RENDER_SH="${RENDER_SH:-/usr/local/bin/render-airprint.sh}"
SLEEP_SEC="${SLEEP_SEC:-2}"
PRINTER_NAME="${PRINTER_NAME:-auto-USB-Printer}"

log() { echo "[add-printer] $(date -Iseconds) $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[add-printer] $*"; }
die() { log "FEIL: $*"; exit 1; }

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
        die "CUPS ikke tilgjengelig etter 3 forsøk"
    fi
    sleep "$SLEEP_SEC"
done

# --------------------------------------------------------------------------
# Finn USB-printer-info via lpinfo og lsusb
# --------------------------------------------------------------------------
USB_URI=$(lpinfo -v 2>/dev/null | grep -m1 'usb://' | awk '{print $2}' || true)
if [[ -z "$USB_URI" ]]; then
    log "Ingen USB-printer funnet i lpinfo — avslutter"
    exit 0
fi

log "Fant printer-URI: $USB_URI"

# Hent VID/PID fra lsusb-output. Printere har typisk class 7 (printer) eller IPP-class.
USB_INFO=$(lsusb -v 2>/dev/null | awk '
    /^Bus / { busline=$0 }
    /bInterfaceClass.*7 Printer/ { print busline; exit }
' || true)

if [[ -z "$USB_INFO" ]]; then
    # Fallback: ta første printer fra lsusb basert på Device Descriptor
    USB_INFO=$(lsusb 2>/dev/null | head -1 || true)
fi

# Parse VID:PID — formatet er "ID xxxx:yyyy ..."
VID_PID=$(echo "$USB_INFO" | grep -oE 'ID [0-9a-fA-F]{4}:[0-9a-fA-F]{4}' | awk '{print $2}' || true)
VID="${VID_PID%%:*}"
PID="${VID_PID##*:}"
VID="0x${VID,,}"

# Modell-string fra USB-URI (etter usb://Vendor/Model?serial=...)
MODEL=$(echo "$USB_URI" | sed -E 's|usb://[^/]+/||; s|\?.*||; s|%20| |g')

log "Detektert VID=$VID, PID=$PID, modell=\"$MODEL\""

# --------------------------------------------------------------------------
# VID-basert routing
# --------------------------------------------------------------------------
DRIVER_STRATEGY=""
PPD_HINT=""
PRINTER_URI="$USB_URI"

case "$VID" in
    0x03f0)
        log "Vendor: HP — bruker HPLIP-discovery"
        DRIVER_STRATEGY="hplip"
        # HPLIP gir bedre URI via hp-makeuri
        if command -v hp-makeuri >/dev/null 2>&1; then
            HP_URI=$(hp-makeuri "$VID_PID" 2>/dev/null | tail -1 || true)
            [[ -n "$HP_URI" && "$HP_URI" =~ ^hp: ]] && PRINTER_URI="$HP_URI"
        fi
        ;;
    0x04a9)
        log "Vendor: Canon — IPP Everywhere først, UFRII LT-fallback ved kansellering"
        DRIVER_STRATEGY="canon"
        # Canon UFRII LT-modeller har "LBP" eller "MF" i modell-string
        if [[ "$MODEL" =~ ^(LBP|MF) ]] && [[ -f /usr/share/cups/model/CNRCUPSLBP161ZK.ppd ]]; then
            log "Modell \"$MODEL\" matcher UFRII LT-mønster — bruker ipp-usb-pipeline direkte"
            PRINTER_URI="ipp://localhost:60000/ipp/print"
            PPD_HINT="CNRCUPSLBP161ZK.ppd"
        fi
        ;;
    0x04f9)
        log "Vendor: Brother — bruker brlaser via Foomatic-match"
        DRIVER_STRATEGY="brother"
        ;;
    0x04b8)
        log "Vendor: Epson — bruker escpr"
        DRIVER_STRATEGY="epson"
        ;;
    0x04e8)
        log "Vendor: Samsung — bruker splix"
        DRIVER_STRATEGY="samsung"
        ;;
    0x06bc)
        log "Vendor: OKI — bruker oki-driver"
        DRIVER_STRATEGY="oki"
        ;;
    0x0922)
        log "Vendor: Dymo — bruker dymo-driver"
        DRIVER_STRATEGY="dymo"
        ;;
    0x043d)
        die "Vendor: Lexmark (VID 0x043d) — IKKE STØTTET. Lexmark Linux-driver er x86-only. Se kompatibilitetsmatrise i README."
        ;;
    0x0482)
        log "Vendor: Kyocera — KX-driver er x86-only. Forsøker Foomatic generic PostScript."
        log "ADVARSEL: hvis modellen ikke er PS-utstyrt, vil print feile. Se README."
        DRIVER_STRATEGY="postscript-generic"
        ;;
    *)
        log "Ukjent VID $VID — forsøker IPP Everywhere → Foomatic-fallback"
        DRIVER_STRATEGY="generic"
        ;;
esac

# --------------------------------------------------------------------------
# Forsøk å registrere printeren basert på strategi
# --------------------------------------------------------------------------
register_printer() {
    local strategy="$1"
    log "Registrerer som $PRINTER_NAME med strategi '$strategy' (URI=$PRINTER_URI)"

    case "$strategy" in
        canon)
            if [[ -n "$PPD_HINT" ]]; then
                # Direkte UFRII-pipeline med pre-mappet PPD
                lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m "$PPD_HINT" --enable
                return 0
            fi
            # IPP Everywhere først — fallback håndteres separat hvis print kanselleres
            lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m everywhere --enable
            ;;
        hplip|brother|epson|samsung|oki|dymo|postscript-generic|generic)
            # Forsøk IPP Everywhere først (driverless)
            if lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m everywhere --enable 2>>"$LOG_FILE"; then
                return 0
            fi
            log "IPP Everywhere feilet — forsøker Foomatic-match på \"$MODEL\""
            # Søk Foomatic-database etter modell-treff
            local foomatic_match
            foomatic_match=$(lpinfo --make-and-model "$MODEL" -m 2>/dev/null | head -1 | awk '{print $1}' || true)
            if [[ -n "$foomatic_match" ]]; then
                log "Foomatic-match funnet: $foomatic_match"
                lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m "$foomatic_match" --enable
                return 0
            fi
            log "Ingen Foomatic-match — registrerer som ukjent (krever manuell driver-valg via web-UI)"
            lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" --enable
            return 1
            ;;
        *)
            die "Ukjent strategi: $strategy"
            ;;
    esac
}

if register_printer "$DRIVER_STRATEGY"; then
    log "Printer $PRINTER_NAME registrert OK"
else
    log "ADVARSEL: Printer registrert uten driver — brukeren må velge PPD via web-UI på http://$(hostname).local:8080"
fi

# --------------------------------------------------------------------------
# Oppdater Avahi AirPrint-tjeneste
# --------------------------------------------------------------------------
export PRINTER_NAME
if [[ -x "$RENDER_SH" ]]; then
    "$RENDER_SH"
    systemctl reload avahi-daemon 2>/dev/null || true
    log "Avahi AirPrint-tjeneste oppdatert"
fi

log "add-printer ferdig"
