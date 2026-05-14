#!/usr/bin/env bats

# Tester for first-boot bundle — armbian_first_run.txt, first-boot.service, first-boot.sh, cupsd.conf
# Kjøres lokalt med: bats print-server/tests/test_first_boot.bats
# Forutsetter bats-core >= 1.5.0

SETUP_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/setup"
FIRST_BOOT_SH="$SETUP_DIR/first-boot.sh"

# ---------------------------------------------------------------------------
# Shellcheck-tester
# ---------------------------------------------------------------------------

@test "shellcheck — first-boot.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$FIRST_BOOT_SH"
    [ "$status" -eq 0 ]
}

@test "shellcheck — wifi-check.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$SETUP_DIR/wifi-check.sh"
    [ "$status" -eq 0 ]
}

@test "shellcheck — add-printer.sh har ingen feil" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck ikke installert"
    run shellcheck -S error "$SETUP_DIR/add-printer.sh"
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Innholds-tester: first-boot.sh
# ---------------------------------------------------------------------------

@test "first-boot.sh sjekker sentinel-fil /.first-boot-done" {
    grep -q '\.first-boot-done' "$FIRST_BOOT_SH"
}

@test "first-boot.sh installerer cups" {
    grep -q 'cups' "$FIRST_BOOT_SH"
}

@test "first-boot.sh installerer avahi-daemon" {
    grep -q 'avahi-daemon' "$FIRST_BOOT_SH"
}

@test "first-boot.sh installerer hplip" {
    grep -q 'hplip' "$FIRST_BOOT_SH"
}

@test "first-boot.sh installerer unattended-upgrades" {
    grep -q 'unattended-upgrades' "$FIRST_BOOT_SH"
}

@test "first-boot.sh setter hostname" {
    grep -q 'hostnamectl\|hostname' "$FIRST_BOOT_SH"
}

@test "first-boot.sh logger til /var/log/first-boot.log" {
    grep -q '/var/log/first-boot.log' "$FIRST_BOOT_SH"
}

@test "first-boot.sh disabler seg selv til slutt" {
    grep -q 'systemctl disable first-boot\|first-boot-done' "$FIRST_BOOT_SH"
}

# ---------------------------------------------------------------------------
# Innholds-tester: first-boot.service
# ---------------------------------------------------------------------------

@test "first-boot.service har After=armbian-firstrun.service" {
    grep -q 'armbian-firstrun.service' "$SETUP_DIR/first-boot.service"
}

@test "first-boot.service er Type=oneshot" {
    grep -q 'Type=oneshot' "$SETUP_DIR/first-boot.service"
}

# ---------------------------------------------------------------------------
# Innholds-tester: cupsd.conf
# ---------------------------------------------------------------------------

@test "cupsd.conf eksisterer" {
    [ -f "$SETUP_DIR/cupsd.conf" ]
}

@test "cupsd.conf tillater remote-admin" {
    grep -qi 'Allow\s*All\|Allow @LOCAL\|WebInterface Yes' "$SETUP_DIR/cupsd.conf"
}

@test "cupsd.conf har Browsing On eller share-printers" {
    grep -qi 'Browsing\|ServerAlias' "$SETUP_DIR/cupsd.conf"
}

# ---------------------------------------------------------------------------
# Innholds-tester: airprint.service
# ---------------------------------------------------------------------------

@test "airprint.service har PRINTER_NAME placeholder" {
    grep -q 'PRINTER_NAME' "$SETUP_DIR/airprint.service"
}
