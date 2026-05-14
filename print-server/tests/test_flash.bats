#!/usr/bin/env bats

# Tester for flash.sh — laptop-side SD-provisioner
# Bruker FLASH_TEST_MODE=1 og --mountpoint for å unngå root-krav og loop-devices
# Forutsetter bats-core >= 1.5.0

FLASH_SH="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/flash.sh"
SETUP_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/setup"

setup() {
    MNT="$(mktemp -d /tmp/test-flash-mnt-XXXXXX)"

    # Simuler Armbian-rootfs-struktur
    mkdir -p "$MNT/etc/armbian-release"
    rmdir "$MNT/etc/armbian-release"
    echo "BOARD=rock-3c" > "$MNT/etc/armbian-release"

    mkdir -p \
        "$MNT/boot" \
        "$MNT/etc/systemd/system/multi-user.target.wants" \
        "$MNT/etc/hostapd" \
        "$MNT/etc/avahi/services" \
        "$MNT/etc/udev/rules.d" \
        "$MNT/usr/local/bin"

    export MNT
}

teardown() {
    rm -rf "$MNT"
}

@test "flash.sh eksisterer og er kjørbart" {
    [ -x "$FLASH_SH" ]
}

@test "alle setup-filer eksisterer" {
    for f in armbian_first_run.txt first-boot.service first-boot.sh \
              wifi-check.sh hostapd.conf dnsmasq.conf captive-portal.py \
              airprint.service add-printer.sh 99-usb-printer.rules; do
        [ -f "$SETUP_DIR/$f" ]
    done
}

@test "alle filer kopieres til riktig sti" {
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    [ "$status" -eq 0 ]
    [ -f "$MNT/boot/armbian_first_run.txt" ]
    [ -f "$MNT/etc/systemd/system/first-boot.service" ]
    [ -f "$MNT/usr/local/bin/first-boot.sh" ]
    [ -f "$MNT/usr/local/bin/wifi-check.sh" ]
    [ -f "$MNT/etc/hostapd/hostapd.conf" ]
    [ -f "$MNT/etc/dnsmasq.conf" ]
    [ -f "$MNT/usr/local/bin/captive-portal.py" ]
    [ -f "$MNT/etc/avahi/services/airprint.service" ]
    [ -f "$MNT/usr/local/bin/add-printer.sh" ]
    [ -f "$MNT/etc/udev/rules.d/99-usb-printer.rules" ]
}

@test "filmoduser er korrekte" {
    env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"

    run stat -c "%a" "$MNT/boot/armbian_first_run.txt"
    [ "$output" = "600" ]

    run stat -c "%a" "$MNT/etc/hostapd/hostapd.conf"
    [ "$output" = "600" ]

    run stat -c "%a" "$MNT/etc/systemd/system/first-boot.service"
    [ "$output" = "644" ]

    run stat -c "%a" "$MNT/etc/dnsmasq.conf"
    [ "$output" = "644" ]

    run stat -c "%a" "$MNT/etc/avahi/services/airprint.service"
    [ "$output" = "644" ]

    run stat -c "%a" "$MNT/etc/udev/rules.d/99-usb-printer.rules"
    [ "$output" = "644" ]

    run stat -c "%a" "$MNT/usr/local/bin/first-boot.sh"
    [ "$output" = "755" ]

    run stat -c "%a" "$MNT/usr/local/bin/wifi-check.sh"
    [ "$output" = "755" ]

    run stat -c "%a" "$MNT/usr/local/bin/captive-portal.py"
    [ "$output" = "755" ]

    run stat -c "%a" "$MNT/usr/local/bin/add-printer.sh"
    [ "$output" = "755" ]
}

@test "first-boot.service symlink opprettes i multi-user.target.wants" {
    env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"

    local link="$MNT/etc/systemd/system/multi-user.target.wants/first-boot.service"
    [ -L "$link" ]

    local target
    target=$(readlink "$link")
    [ "$target" = "/etc/systemd/system/first-boot.service" ]
}

@test "dry-run skriver ingen filer" {
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT" --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"DRY:"* ]]
    [ ! -f "$MNT/usr/local/bin/first-boot.sh" ]
    [ ! -L "$MNT/etc/systemd/system/multi-user.target.wants/first-boot.service" ]
}

@test "idempotent — andre kjøring gir ingen feil" {
    env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    [ "$status" -eq 0 ]
}

@test "feiler hvis armbian-release mangler" {
    rm -f "$MNT/etc/armbian-release"
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Kan ikke verifisere Armbian"* ]]
}

@test "godkjenner armbian_first_run.txt.template som alternativ verifikasjon" {
    rm -f "$MNT/etc/armbian-release"
    touch "$MNT/boot/armbian_first_run.txt.template"
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    [ "$status" -eq 0 ]
}

@test "neste-steg-instruksjoner vises ved suksess" {
    run env FLASH_TEST_MODE=1 bash "$FLASH_SH" --mountpoint "$MNT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"flash.sh"* ]]
    [[ "$output" == *"fullf"* ]]
    [[ "$output" == *"printer.local"* ]]
}
