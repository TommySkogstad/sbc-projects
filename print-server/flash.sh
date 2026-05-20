#!/usr/bin/env bash
# flash.sh — Klargjør et Armbian-flashet SD-kort for print-server på Rock 3C
#
# Bruk:
#   sudo ./flash.sh --install-deps              Installer prereqs (Ubuntu/Debian)
#   sudo ./flash.sh --download                  Vis Armbian-nedlastingsinstruks
#   sudo ./flash.sh [valg] [--mountpoint STI]   Injiser config på flashet SD
#
# Eksempler:
#   sudo ./flash.sh --name kontor                Hostname blir printer-kontor
#   sudo ./flash.sh --dry-run                    Forhåndsvis uten å skrive
#   sudo ./flash.sh --mountpoint /mnt/sd         Bruk allerede-montert SD-rot
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"
DRIVERS_DIR="$SCRIPT_DIR/drivers"
WEB_DIR="$SCRIPT_DIR/web"

ARMBIAN_URL="https://www.armbian.com/rock-3c/"

DRY_RUN=false
INSTALL_DEPS=false
SHOW_DOWNLOAD=false
PRINTER_LABEL=""
MOUNTPOINT=""

validate_name() {
    [[ "$1" =~ ^[a-z0-9-]+$ ]] \
        || { echo "Ugyldig --name: '$1' — kun små bokstaver, sifre og bindestrek tillatt" >&2; exit 1; }
}

usage() {
    cat <<EOF
Bruk: sudo $0 [valg]

  --install-deps      Installer prereqs (xz-utils, curl) — Ubuntu/Debian
  --download          Vis Armbian-nedlastingsinstruks
  --dry-run           Logg hva som ville blitt gjort, ingen skriving
  --name LABEL        Hostname blir 'printer-LABEL' (standard: 'rock')
  --mountpoint STI    Bruk allerede-montert SD-rot

EOF
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)          DRY_RUN=true; shift ;;
        --install-deps)     INSTALL_DEPS=true; shift ;;
        --download)         SHOW_DOWNLOAD=true; shift ;;
        --name)             [[ -z "${2:-}" ]] && usage 1
                            PRINTER_LABEL="$2"
                            validate_name "$PRINTER_LABEL"
                            shift 2 ;;
        --name=*)           PRINTER_LABEL="${1#*=}"
                            validate_name "$PRINTER_LABEL"
                            shift ;;
        --mountpoint)       [[ -z "${2:-}" ]] && usage 1
                            MOUNTPOINT="$2"; shift 2 ;;
        -h|--help)          usage 0 ;;
        *)                  usage 1 ;;
    esac
done

log()  { echo "[flash.sh] $*"; }
die()  { echo "[FEIL] $*" >&2; exit 1; }

maybe_sudo() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        command -v sudo >/dev/null 2>&1 || die "sudo ikke tilgjengelig"
        sudo "$@"
    fi
}

# ----------------------------------------------------------------------------
# --install-deps
# ----------------------------------------------------------------------------
if $INSTALL_DEPS; then
    command -v apt-get >/dev/null 2>&1 \
        || die "--install-deps krever apt (Debian/Ubuntu)."

    local_pkgs=()
    command -v xz    >/dev/null 2>&1 || local_pkgs+=("xz-utils")
    command -v curl  >/dev/null 2>&1 || local_pkgs+=("curl")
    command -v lsblk >/dev/null 2>&1 || local_pkgs+=("util-linux")

    if [[ ${#local_pkgs[@]} -gt 0 ]]; then
        log "Installerer fra apt: ${local_pkgs[*]}"
        maybe_sudo apt-get update -qq
        maybe_sudo apt-get install -y "${local_pkgs[@]}"
    else
        log "Alle prereqs (xz-utils, curl, util-linux) allerede til stede"
    fi

    cat <<EOF

Flash-strategi: dd (balena-etcher støttes ikke på Ubuntu 24.04+).
Last ned Armbian: $ARMBIAN_URL
Se: $0 --download for flash-kommandoer
EOF
    exit 0
fi

# ----------------------------------------------------------------------------
# --download
# ----------------------------------------------------------------------------
if $SHOW_DOWNLOAD; then
    cat <<EOF

╔══════════════════════════════════════════╗
║   Armbian Bookworm Minimal for Rock 3C   ║
╚══════════════════════════════════════════╝

1. Last ned fra: $ARMBIAN_URL
   Velg "Bookworm minimal / IOT" (CLI only).

2. Pakk ut og flash med dd:
   xz -d Armbian_*_Rock-3c_bookworm_*.img.xz
   sudo dd if=Armbian_*_Rock-3c_bookworm_*.img bs=4M status=progress oflag=sync of=/dev/sdX

   ⚠ Bytt /dev/sdX med faktisk SD-enhet (sjekk med lsblk).
   Feil enhet = data tap. Verifiser to ganger.

3. Monter SD-kortet:
   sudo mkdir -p /mnt/sd
   sudo mount /dev/sdX1 /mnt/sd

4. Kopier armbian_first_run.txt.example → armbian_first_run.txt og fyll ut:
   cp setup/armbian_first_run.txt.example setup/armbian_first_run.txt
   nano setup/armbian_first_run.txt

5. Kjør $0 med --name og --mountpoint:
   sudo $0 --name kontor --mountpoint /mnt/sd
EOF
    exit 0
fi

# ----------------------------------------------------------------------------
# Root-sjekk
# ----------------------------------------------------------------------------
if [[ "${FLASH_TEST_MODE:-}" != "1" ]]; then
    [[ $EUID -eq 0 ]] || die "flash.sh må kjøres som root (sudo ./flash.sh)"
fi

# ----------------------------------------------------------------------------
# Copy-helpers
# ----------------------------------------------------------------------------
do_cp() {
    local src="$1" dst="$2" mode="$3"
    if $DRY_RUN; then
        log "DRY: cp $(basename "$src") -> $dst (modus $mode)"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    chmod "$mode" "$dst"
}

do_cp_dir() {
    local src_dir="$1" dst_dir="$2"
    if $DRY_RUN; then
        log "DRY: cp -r $src_dir/* -> $dst_dir/"
        return
    fi
    mkdir -p "$dst_dir"
    cp -r "$src_dir"/* "$dst_dir/" 2>/dev/null || true
}

# ----------------------------------------------------------------------------
# SD-mount detection
# ----------------------------------------------------------------------------
detect_sd_partition() {
    local json
    json=$(lsblk -o NAME,LABEL,TYPE --json 2>/dev/null)
    python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
hits = []
def walk(devs):
    for d in devs:
        if d.get('type') == 'part' and 'armbi' in (d.get('label') or '').lower():
            hits.append(d['name'])
        walk(d.get('children') or [])
walk(data.get('blockdevices', []))
print('\n'.join(hits))
" <<< "$json"
}

mount_sd() {
    local mnt
    mnt=$(mktemp -d /tmp/flash-sd-XXXXXX)

    local candidates count
    candidates=$(detect_sd_partition)
    count=$(printf '%s' "$candidates" | grep -c '[^[:space:]]' 2>/dev/null || echo 0)

    local part
    if [[ $count -eq 0 ]]; then
        log "Ingen Armbian-partisjon funnet automatisk."
        log "Tilgjengelige enheter:"
        lsblk -o NAME,LABEL,TYPE,SIZE
        read -rp "Oppgi partisjonsnavn (f.eks. sdb2, mmcblk0p2): " part
    elif [[ $count -gt 1 ]]; then
        log "Flere Armbian-kandidater funnet:"
        echo "$candidates"
        read -rp "Velg partisjon: " part
    else
        part="$candidates"
        log "Auto-detektert: /dev/$part"
    fi

    mount "/dev/$part" "$mnt"
    echo "$mnt"
}

# ----------------------------------------------------------------------------
# Fil-til-SD-mapping
# ----------------------------------------------------------------------------
declare -a FILES=(
    "armbian_first_run.txt:/boot/armbian_first_run.txt:600"
    "first-boot.service:/etc/systemd/system/first-boot.service:644"
    "first-boot.sh:/usr/local/bin/first-boot.sh:755"
    "wifi-check.sh:/usr/local/bin/wifi-check.sh:755"
    "hostapd.conf:/etc/hostapd/hostapd.conf:600"
    "dnsmasq.conf:/etc/dnsmasq.conf:644"
    "captive-portal.py:/usr/local/bin/captive-portal.py:755"
    "airprint.service:/etc/avahi/services/airprint.service:644"
    "add-printer.sh:/usr/local/bin/add-printer.sh:755"
    "render-airprint.sh:/usr/local/bin/render-airprint.sh:755"
    "airprint.service.tmpl:/usr/local/share/print-server/airprint.service.tmpl:644"
    "99-usb-printer.rules:/etc/udev/rules.d/99-usb-printer.rules:644"
    "wifi-check.service:/etc/systemd/system/wifi-check.service:644"
    "captive-portal.service:/etc/systemd/system/captive-portal.service:644"
    "cupsd.conf:/etc/cups/cupsd.conf:640"
    "printer-web.service:/etc/systemd/system/printer-web.service:644"
)

# ----------------------------------------------------------------------------
# Hoved
# ----------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Print-server SD-provisioning           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

MNT=""
MOUNTED_BY_US=false

if [[ -n "$MOUNTPOINT" ]]; then
    MNT="$MOUNTPOINT"
else
    MNT=$(mount_sd)
    MOUNTED_BY_US=true
fi

cleanup() {
    if $MOUNTED_BY_US && [[ -n "$MNT" ]]; then
        sync 2>/dev/null || true
        umount "$MNT" 2>/dev/null || true
        rmdir "$MNT" 2>/dev/null || true
        log "SD unmontert."
    fi
}
trap cleanup EXIT

# Verifiser Armbian
ARMBIAN_RELEASE="$MNT/etc/armbian-release"
FIRST_RUN_TMPL="$MNT/boot/armbian_first_run.txt.template"

if [[ ! -f "$ARMBIAN_RELEASE" && ! -f "$FIRST_RUN_TMPL" ]]; then
    die "Kan ikke verifisere Armbian på $MNT. Avbryter."
fi
log "Armbian verifisert."

# Hostname-label
HOSTNAME_LABEL="${PRINTER_LABEL:-rock}"
log "Printer-label: $HOSTNAME_LABEL → hostname blir 'printer-$HOSTNAME_LABEL'"

# Skriv hostname til SD
if ! $DRY_RUN; then
    mkdir -p "$MNT/etc"
    echo "printer-$HOSTNAME_LABEL" > "$MNT/etc/hostname"
    chmod 644 "$MNT/etc/hostname"
else
    log "DRY: ville skrevet 'printer-$HOSTNAME_LABEL' til $MNT/etc/hostname"
fi

# Kopier alle setup/-filer
for entry in "${FILES[@]}"; do
    IFS=: read -r src_name dst_path mode <<< "$entry"
    src="$SETUP_DIR/$src_name"
    dst="$MNT$dst_path"

    if [[ ! -f "$src" ]]; then
        # printer-web.service og cupsd.conf er valgfrie hvis vi tester før de er på plass
        if [[ "$src_name" == "printer-web.service" || "$src_name" == "cupsd.conf" ]]; then
            log "Hopper over $src_name (ikke i setup/ enda)"
            continue
        fi
        die "Mangler kildefil: $src"
    fi
    do_cp "$src" "$dst" "$mode"
done

# Kopier drivers/ (Canon UFRII deb)
if [[ -d "$DRIVERS_DIR" ]]; then
    log "Kopierer drivers/ → /usr/local/share/print-server/drivers/"
    do_cp_dir "$DRIVERS_DIR" "$MNT/usr/local/share/print-server/drivers"
fi

# Kopier web/ (FastAPI-app)
if [[ -d "$WEB_DIR" ]]; then
    log "Kopierer web/ → /opt/printer-web/"
    do_cp_dir "$WEB_DIR" "$MNT/opt/printer-web"
fi

# Aktiver first-boot.service via symlink
WANTS_DIR="$MNT/etc/systemd/system/multi-user.target.wants"
SVC_LINK="$WANTS_DIR/first-boot.service"
SVC_TARGET="/etc/systemd/system/first-boot.service"

if $DRY_RUN; then
    log "DRY: ln -sf $SVC_TARGET $SVC_LINK"
elif [[ -L "$SVC_LINK" ]]; then
    log "Symlink eksisterer allerede — idempotent, hopper over"
else
    mkdir -p "$WANTS_DIR"
    ln -sf "$SVC_TARGET" "$SVC_LINK"
    log "first-boot.service aktivert i multi-user.target.wants/"
fi

if ! $DRY_RUN; then
    log "Synkroniserer..."
    sync 2>/dev/null || true
fi

cat <<EOF

=============================================
 flash.sh fullført!
=============================================
Neste steg:
  1. Eject SD-kortet trygt
  2. Sett SD i Rock 3C
  3. Koble til strøm (USB-C 5V/3A)
  4. Vent 8–10 min på første boot (driver-install)

Etter boot:
  SSH:    ssh root@printer-${HOSTNAME_LABEL}.local
  Logg:   tail -f /var/log/first-boot.log
  Web-UI: http://printer-${HOSTNAME_LABEL}.local:8080
  CUPS:   http://printer-${HOSTNAME_LABEL}.local:631
  mDNS:   printer.local er alias for printer-${HOSTNAME_LABEL}.local

Koble til USB-printer når first-boot er ferdig — add-printer.sh
detekterer VID/PID og velger driver automatisk.
EOF
