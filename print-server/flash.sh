#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

DRY_RUN=false
MOUNTPOINT=""

usage() {
    cat <<EOF
Bruk: sudo $0 [--dry-run] [--mountpoint STI]

  --dry-run           Logg hva som ville blitt gjort, ingen skriving
  --mountpoint STI    Bruk allerede-montert SD-rot (hopper over auto-detect)
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)          DRY_RUN=true ;;
        --mountpoint)       MOUNTPOINT="${2:-}"; shift ;;
        -h|--help)          usage ;;
        *)                  usage ;;
    esac
    shift
done

log() { echo "[flash.sh] $*"; }
die() { echo "[FEIL] $*" >&2; exit 1; }

# FLASH_TEST_MODE=1 hopper over root-sjekk og chown (for enhetstesting)
if [[ "${FLASH_TEST_MODE:-}" != "1" ]]; then
    [[ $EUID -eq 0 ]] || die "flash.sh må kjøres som root (sudo ./flash.sh)"
fi

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

do_chown() {
    local owner="$1" path="$2"
    if $DRY_RUN; then
        log "DRY: chown $owner $path"
        return
    fi
    [[ "${FLASH_TEST_MODE:-}" != "1" ]] && chown "$owner" "$path" || true
}

# Bruk python3 + lsblk JSON for robust parsing av block device-info
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

# Fil-til-SD-mapping: kildefil:destinasjon:modus:eier
declare -a FILES=(
    "armbian_first_run.txt:/boot/armbian_first_run.txt:600:root:root"
    "first-boot.service:/etc/systemd/system/first-boot.service:644:root:root"
    "first-boot.sh:/usr/local/bin/first-boot.sh:755:root:root"
    "wifi-check.sh:/usr/local/bin/wifi-check.sh:755:root:root"
    "hostapd.conf:/etc/hostapd/hostapd.conf:600:root:root"
    "dnsmasq.conf:/etc/dnsmasq.conf:644:root:root"
    "captive-portal.py:/usr/local/bin/captive-portal.py:755:root:root"
    "airprint.service:/etc/avahi/services/airprint.service:644:root:root"
    "add-printer.sh:/usr/local/bin/add-printer.sh:755:root:root"
    "99-usb-printer.rules:/etc/udev/rules.d/99-usb-printer.rules:644:root:root"
)

# === HOVED ===

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

# Kopier alle setup/-filer
for entry in "${FILES[@]}"; do
    IFS=: read -r src_name dst_path mode owner group <<< "$entry"
    src="$SETUP_DIR/$src_name"
    dst="$MNT$dst_path"

    [[ -f "$src" ]] || die "Mangler kildefil: $src"
    do_cp "$src" "$dst" "$mode"
    do_chown "$owner:$group" "$dst"
done

# Aktiver first-boot.service via symlink (chroot-fri metode)
WANTS_DIR="$MNT/etc/systemd/system/multi-user.target.wants"
SVC_LINK="$WANTS_DIR/first-boot.service"
SVC_TARGET="/etc/systemd/system/first-boot.service"

if $DRY_RUN; then
    log "DRY: ln -sf $SVC_TARGET $SVC_LINK"
elif [[ -L "$SVC_LINK" ]]; then
    log "Symlink eksisterer allerede — idempotent, hopper over."
else
    mkdir -p "$WANTS_DIR"
    ln -sf "$SVC_TARGET" "$SVC_LINK"
    log "first-boot.service aktivert i multi-user.target.wants/."
fi

if ! $DRY_RUN; then
    log "Synkroniserer til SD..."
    sync 2>/dev/null || true
fi

cat <<'EOF'

=============================================
 flash.sh fullført!
=============================================
Neste steg:
  1. Ta ut microSD fra laptop
  2. Sett SD i Rock 3C
  3. Koble til strøm (USB-C 5V/3A)
  4. Vent ~2-3 minutter på første boot
  5. Finn IP: arp -a | grep -i rock
     eller: ssh root@printer.local
  6. SSH inn: ssh root@<IP>

Første boot kjører first-boot.sh automatisk:
  - Setter hostname til "printer"
  - Installerer CUPS, Avahi, ipp-usb
  - Kobler til WiFi fra armbian_first_run.txt
EOF
