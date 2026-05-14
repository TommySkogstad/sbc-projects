#!/bin/bash
# flash.sh — Klargjør et DietPi-flashet SD-kort for Spotify-spiller på Rock 3C
#
# Bruk:
#   ./spotify-spiller/flash.sh [valg] [mount-path]
#   ./spotify-spiller/flash.sh --dry-run
#   ./spotify-spiller/flash.sh --name "Kjøkken"
#   ./spotify-spiller/flash.sh /media/bruker/boot

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

DRY_RUN=false
LIBRESPOT_NAME="Rock"
MOUNT_PATH=""

# --- Argument-parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --name)
            if [[ -z "${2:-}" ]]; then
                echo "Feil: --name krever et argument" >&2
                exit 1
            fi
            LIBRESPOT_NAME="$2"
            shift 2
            ;;
        --name=*)
            LIBRESPOT_NAME="${1#*=}"
            shift
            ;;
        -*)
            echo "Ukjent flagg: $1" >&2
            echo "Bruk: $0 [--dry-run] [--name <navn>] [mount-path]" >&2
            exit 1
            ;;
        *)
            if [[ -n "$MOUNT_PATH" ]]; then
                echo "Feil: bare én mount-path tillatt" >&2
                exit 1
            fi
            MOUNT_PATH="$1"
            shift
            ;;
    esac
done

log()  { echo "  $*"; }
ok()   { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }
info() { echo "→ $*"; }

# --- Auto-detect SD-kortets boot-partisjon ---
detect_dietpi_mount() {
    local candidates=()

    while IFS= read -r line; do
        local mountpoint
        mountpoint=$(echo "$line" | awk '{print $3}')
        [[ -z "$mountpoint" || "$mountpoint" == "-" ]] && continue
        [[ -f "$mountpoint/dietpi.txt" || -f "$mountpoint/Automation_Custom_Script.sh" ]] && {
            candidates+=("$mountpoint")
        }
    done < <(lsblk -o NAME,LABEL,MOUNTPOINT -rn 2>/dev/null | grep -v "^$")

    # Søk også i /media og /mnt
    for base in /media /mnt; do
        [[ -d "$base" ]] || continue
        while IFS= read -r dir; do
            [[ -f "$dir/dietpi.txt" ]] && candidates+=("$dir")
        done < <(find "$base" -maxdepth 3 -name "dietpi.txt" -exec dirname {} \; 2>/dev/null)
    done

    # Dedupliser
    local seen=()
    local unique=()
    for c in "${candidates[@]}"; do
        local found=false
        for s in "${seen[@]:-}"; do [[ "$s" == "$c" ]] && found=true; done
        $found || { seen+=("$c"); unique+=("$c"); }
    done

    echo "${unique[@]:-}"
}

verify_dietpi_boot() {
    local path="$1"
    [[ -d "$path" ]] || return 1
    [[ -f "$path/dietpi.txt" ]] && return 0
    [[ -f "$path/Automation_Custom_Script.sh" ]] && return 0
    return 1
}

copy_file() {
    local src="$1"
    local dst="$2"
    local mode="${3:-644}"

    if $DRY_RUN; then
        log "[dry-run] ville skrevet: $dst (mode $mode)"
        return
    fi
    cp "$src" "$dst"
    chmod "$mode" "$dst"
    ok "Kopiert: $dst"
}

# --- Finn mount-path ---
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Spotify-spiller SD-flash               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [[ -n "$MOUNT_PATH" ]]; then
    info "Bruker oppgitt mount-path: $MOUNT_PATH"
    verify_dietpi_boot "$MOUNT_PATH" || fail "Ser ikke ut som DietPi-boot: $MOUNT_PATH (mangler dietpi.txt)"
else
    info "Auto-detekterer DietPi SD-boot..."
    mapfile -t found < <(detect_dietpi_mount | tr ' ' '\n' | sort -u | grep -v '^$' || true)

    if [[ ${#found[@]} -eq 0 ]]; then
        echo ""
        echo "Ingen DietPi-boot-partisjon funnet automatisk."
        echo "Oppgi mount-path manuelt (f.eks. /media/bruker/boot):"
        read -r MOUNT_PATH
        [[ -n "$MOUNT_PATH" ]] || fail "Ingen path oppgitt."
        verify_dietpi_boot "$MOUNT_PATH" || fail "Ser ikke ut som DietPi-boot: $MOUNT_PATH"
    elif [[ ${#found[@]} -eq 1 ]]; then
        MOUNT_PATH="${found[0]}"
        ok "Fant DietPi-boot: $MOUNT_PATH"
    else
        echo ""
        echo "Fant flere kandidater:"
        for i in "${!found[@]}"; do
            echo "  $((i+1))) ${found[$i]}"
        done
        echo ""
        echo "Velg nummer (1–${#found[@]}):"
        read -r choice
        [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le ${#found[@]} ]] \
            || fail "Ugyldig valg: $choice"
        MOUNT_PATH="${found[$((choice-1))]}"
        ok "Valgt: $MOUNT_PATH"
    fi
fi

echo ""
info "SD-kortets boot-path: $MOUNT_PATH"
info "Spotify Connect-navn: $LIBRESPOT_NAME"
$DRY_RUN && info "*** DRY-RUN — ingen filer skrives ***"
echo ""

# --- Verifiser setup/-mappen ---
[[ -d "$SETUP_DIR" ]] || fail "setup/-mappen mangler: $SETUP_DIR"
[[ -f "$SETUP_DIR/dietpi.txt" ]] || fail "setup/dietpi.txt mangler"
[[ -f "$SETUP_DIR/Automation_Custom_Script.sh" ]] || fail "setup/Automation_Custom_Script.sh mangler"

# --- Skriv dietpi.txt ---
info "Skriver dietpi.txt..."

if $DRY_RUN; then
    log "[dry-run] ville skrevet: $MOUNT_PATH/dietpi.txt"
else
    cp "$SETUP_DIR/dietpi.txt" "$MOUNT_PATH/dietpi.txt"

    # Injiser LIBRESPOT_NAME som input til Automation_Custom_Script
    # DietPi sender dette som $1 til scriptet
    if ! grep -q "^Automation_Custom_Script_Inputs=" "$MOUNT_PATH/dietpi.txt"; then
        echo "Automation_Custom_Script_Inputs=$LIBRESPOT_NAME" >> "$MOUNT_PATH/dietpi.txt"
    else
        sed -i "s|^Automation_Custom_Script_Inputs=.*|Automation_Custom_Script_Inputs=$LIBRESPOT_NAME|" \
            "$MOUNT_PATH/dietpi.txt"
    fi
    ok "Skrevet: $MOUNT_PATH/dietpi.txt"
fi

# --- Skriv Automation_Custom_Script.sh ---
info "Skriver Automation_Custom_Script.sh..."
copy_file "$SETUP_DIR/Automation_Custom_Script.sh" \
          "$MOUNT_PATH/Automation_Custom_Script.sh" \
          755

# --- Suksess ---
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   SD-kortet er klart!                    ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Neste steg:"
echo "  1. Eject SD-kortet trygt"
echo "  2. Sett SD-kortet i Rock 3C"
echo "  3. Koble til: strøm (USB-C 5V/3A) + ethernet + 3.5mm AUX"
echo "  4. Vent 5–10 min ved første boot (DietPi henter pakker og installerer raspotify)"
echo ""
echo "  '${LIBRESPOT_NAME}' skal så dukke opp i Spotify-appen."
echo ""
echo "  Etter boot:"
echo "    SSH:  ssh root@spotify-rock.local  (passord: dietpi — bytt umiddelbart!)"
echo "    Lyd:  speaker-test -c 2 -t wav"
echo ""
