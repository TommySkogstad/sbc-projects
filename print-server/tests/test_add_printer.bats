#!/usr/bin/env bats

# Tester for auto-USB-printer-detect:
# 99-usb-printer.rules, add-printer.sh, airprint.service.tmpl, render-airprint.sh
# Kjøres lokalt med: bats print-server/tests/test_add_printer.bats
# Forutsetter bats-core >= 1.5.0

SETUP_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/setup"
ADD_PRINTER_SH="$SETUP_DIR/add-printer.sh"
RENDER_SH_PATH="$SETUP_DIR/render-airprint.sh"
UDEV_RULES="$SETUP_DIR/99-usb-printer.rules"

setup() {
    FAKEBIN="$BATS_TEST_TMPDIR/bin"
    mkdir -p "$FAKEBIN"

    # Fake lpstat: CUPS klar (exit 0)
    printf '#!/bin/sh\nexit 0\n' > "$FAKEBIN/lpstat"
    chmod +x "$FAKEBIN/lpstat"

    # Fake lpinfo: returnerer én USB-URI
    printf '#!/bin/sh\necho "direct usb://TestMaker/TestModel?serial=001 TestMaker TestModel"\n' \
        > "$FAKEBIN/lpinfo"
    chmod +x "$FAKEBIN/lpinfo"

    # Fake lpadmin: logger argumentene til fil
    printf '#!/bin/sh\necho "$*" > "%s/lpadmin_args"\n' "$BATS_TEST_TMPDIR" \
        > "$FAKEBIN/lpadmin"
    chmod +x "$FAKEBIN/lpadmin"

    # Fake systemctl: gjør ingenting
    printf '#!/bin/sh\nexit 0\n' > "$FAKEBIN/systemctl"
    chmod +x "$FAKEBIN/systemctl"

    # Fake render-airprint.sh: skriver PRINTER_NAME til utfil
    printf '#!/bin/sh\necho "printer: ${PRINTER_NAME}" > "%s/airprint.service"\n' \
        "$BATS_TEST_TMPDIR" > "$FAKEBIN/render-airprint.sh"
    chmod +x "$FAKEBIN/render-airprint.sh"

    export PATH="$FAKEBIN:$PATH"
    export LOCK_FILE="$BATS_TEST_TMPDIR/add-printer.lock"
    export LOG_FILE="$BATS_TEST_TMPDIR/add-printer.log"
    export RENDER_SH="$FAKEBIN/render-airprint.sh"
    export SLEEP_SEC="0"
}

# ---------------------------------------------------------------------------
# Shellcheck
# ---------------------------------------------------------------------------

@test "shellcheck — add-printer.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$ADD_PRINTER_SH"
    [ "$status" -eq 0 ]
}

@test "shellcheck — render-airprint.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$RENDER_SH_PATH"
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Eksistens
# ---------------------------------------------------------------------------

@test "add-printer.sh eksisterer og er kjørbar" {
    [ -f "$ADD_PRINTER_SH" ]
    [ -x "$ADD_PRINTER_SH" ]
}

@test "render-airprint.sh eksisterer og er kjørbar" {
    [ -f "$RENDER_SH_PATH" ]
    [ -x "$RENDER_SH_PATH" ]
}

@test "airprint.service.tmpl eksisterer" {
    [ -f "$SETUP_DIR/airprint.service.tmpl" ]
}

# ---------------------------------------------------------------------------
# udev-regel: 99-usb-printer.rules
# ---------------------------------------------------------------------------

@test "99-usb-printer.rules bruker usb_interface subsystem (ikke usb)" {
    grep -q 'SUBSYSTEM=="usb_interface"' "$UDEV_RULES"
}

@test "99-usb-printer.rules bruker ATTR{bInterfaceClass}==\"07\"" {
    grep -q 'ATTR{bInterfaceClass}=="07"' "$UDEV_RULES"
}

@test "99-usb-printer.rules bruker systemd-run --no-block" {
    grep -q 'systemd-run' "$UDEV_RULES"
    grep -q '\-\-no-block' "$UDEV_RULES"
}

@test "99-usb-printer.rules kaller add-printer.sh" {
    grep -q 'add-printer.sh' "$UDEV_RULES"
}

# ---------------------------------------------------------------------------
# add-printer.sh — innhold
# ---------------------------------------------------------------------------

@test "add-printer.sh bruker flock for debounce" {
    grep -q 'flock' "$ADD_PRINTER_SH"
}

@test "add-printer.sh har retry-loop på CUPS-tilkobling" {
    grep -qE 'for.*1.*2.*3|seq.*3|for i in' "$ADD_PRINTER_SH"
    grep -q 'lpstat' "$ADD_PRINTER_SH"
}

@test "add-printer.sh bruker lpinfo for å finne USB-URI" {
    grep -q 'lpinfo' "$ADD_PRINTER_SH"
    grep -q 'usb' "$ADD_PRINTER_SH"
}

@test "add-printer.sh registrerer auto-USB-Printer via lpadmin" {
    grep -q 'lpadmin' "$ADD_PRINTER_SH"
    grep -q 'auto-USB-Printer' "$ADD_PRINTER_SH"
    grep -q 'everywhere' "$ADD_PRINTER_SH"
}

@test "add-printer.sh kaller systemctl reload avahi-daemon" {
    grep -qE 'systemctl.*reload.*avahi|reload.*avahi' "$ADD_PRINTER_SH"
}

# ---------------------------------------------------------------------------
# add-printer.sh — atferd (kjøres med mock-avhengigheter)
# ---------------------------------------------------------------------------

@test "add-printer.sh kaller lpadmin med -p auto-USB-Printer og USB-URI" {
    run "$ADD_PRINTER_SH"
    [ "$status" -eq 0 ]
    [ -f "$BATS_TEST_TMPDIR/lpadmin_args" ]
    grep -q '\-p auto-USB-Printer' "$BATS_TEST_TMPDIR/lpadmin_args"
    grep -q '\-v usb://' "$BATS_TEST_TMPDIR/lpadmin_args"
    grep -q 'everywhere' "$BATS_TEST_TMPDIR/lpadmin_args"
    grep -q '\-E' "$BATS_TEST_TMPDIR/lpadmin_args"
}

# ---------------------------------------------------------------------------
# airprint.service.tmpl — innhold
# ---------------------------------------------------------------------------

@test "airprint.service.tmpl har korrekte TXT-records for AirPrint" {
    grep -q 'rp=printers/' "$SETUP_DIR/airprint.service.tmpl"
    grep -q 'pdl=' "$SETUP_DIR/airprint.service.tmpl"
    grep -q 'URF=' "$SETUP_DIR/airprint.service.tmpl"
}

@test "airprint.service.tmpl bruker envsubst-variabel \${PRINTER_NAME}" {
    grep -q '\${PRINTER_NAME}' "$SETUP_DIR/airprint.service.tmpl"
}

# ---------------------------------------------------------------------------
# render-airprint.sh — atferd
# ---------------------------------------------------------------------------

@test "render-airprint.sh genererer airprint.service med korrekt PRINTER_NAME" {
    OUT="$BATS_TEST_TMPDIR/airprint-render.service"
    run env PRINTER_NAME="test-printer-123" \
        AIRPRINT_TMPL="$SETUP_DIR/airprint.service.tmpl" \
        AIRPRINT_OUT="$OUT" \
        "$RENDER_SH_PATH"
    [ "$status" -eq 0 ]
    [ -f "$OUT" ]
    grep -q 'test-printer-123' "$OUT"
}

@test "render-airprint.sh erstatter ikke andre variabler i malen" {
    OUT="$BATS_TEST_TMPDIR/airprint-noexpand.service"
    run env PRINTER_NAME="my-printer" \
        AIRPRINT_TMPL="$SETUP_DIR/airprint.service.tmpl" \
        AIRPRINT_OUT="$OUT" \
        "$RENDER_SH_PATH"
    [ "$status" -eq 0 ]
    # AirPrint-typen skal fortsatt være med (ikke expandert bort)
    grep -q '_ipp._tcp' "$OUT"
}

# ---------------------------------------------------------------------------
# first-boot.sh — kopierer nye filer
# ---------------------------------------------------------------------------

@test "first-boot.sh kopierer render-airprint.sh" {
    grep -q 'render-airprint.sh' "$SETUP_DIR/first-boot.sh"
}

@test "first-boot.sh kopierer airprint.service.tmpl" {
    grep -q 'airprint.service.tmpl' "$SETUP_DIR/first-boot.sh"
}
