#!/bin/bash
# flash.sh — Klargjør et DietPi-flashet SD-kort for Spotify-spiller på Rock 3C
#
# Bruk:
#   ./spotify-spiller/flash.sh --install-deps           Installer Etcher + grunnverktøy (Ubuntu/Debian)
#   ./spotify-spiller/flash.sh --download               Vis nedlastingslenke for DietPi Rock 3C-image
#   ./spotify-spiller/flash.sh [valg] [mount-path]      Injiser config på flashet SD-kort
#   ./spotify-spiller/flash.sh --dry-run
#   ./spotify-spiller/flash.sh --name "Kjøkken"
#   ./spotify-spiller/flash.sh /media/bruker/boot

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

DIETPI_IMAGES_URL="https://dietpi.com/downloads/images/"
# DietPi har ikke et dedikert ROCK3C-image. Quartz64B (RK3566) er bekreftet kompatibel
# (dietpi/DietPi#7057). Brukes inntil et offisielt ROCK3C-image er tilgjengelig.
DIETPI_IMAGE_FILE="DietPi_Quartz64B-ARMv8-Bookworm.img.xz"

DRY_RUN=false
INSTALL_DEPS=false
SHOW_DOWNLOAD=false
ASSUME_YES=false
LIBRESPOT_NAME="Rock"
MOUNT_PATH=""

validate_name() {
    [[ "$1" =~ ^[A-Za-z0-9æøåÆØÅ\ \-]+$ ]] \
        || { echo "Ugyldig --name: '$1' — kun bokstaver, sifre, mellomrom og bindestrek tillatt" >&2; exit 1; }
}

# --- Argument-parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --install-deps)
            INSTALL_DEPS=true
            shift
            ;;
        --download)
            SHOW_DOWNLOAD=true
            shift
            ;;
        --yes|-y)
            ASSUME_YES=true
            shift
            ;;
        --name)
            if [[ -z "${2:-}" ]]; then
                echo "Feil: --name krever et argument" >&2
                exit 1
            fi
            LIBRESPOT_NAME="$2"
            validate_name "$LIBRESPOT_NAME"
            shift 2
            ;;
        --name=*)
            LIBRESPOT_NAME="${1#*=}"
            validate_name "$LIBRESPOT_NAME"
            shift
            ;;
        -h|--help)
            sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*)
            echo "Ukjent flagg: $1" >&2
            echo "Bruk: $0 [--install-deps|--download|--dry-run] [--name <navn>] [mount-path]" >&2
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
warn() { echo "⚠ $*" >&2; }

# --- Sjekk om vi er på Debian/Ubuntu (apt) ---
require_apt() {
    command -v apt-get >/dev/null 2>&1 \
        || fail "--install-deps krever apt (Debian/Ubuntu). På andre distroer: installer balena-etcher manuelt."
}

# --- Sudo-wrapper (tom hvis vi allerede er root) ---
maybe_sudo() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        command -v sudo >/dev/null 2>&1 || fail "sudo ikke tilgjengelig — kjør som root eller installer sudo"
        sudo "$@"
    fi
}

# --- Installer balena-etcher + grunnverktøy ---
install_deps() {
    require_apt

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   Installerer prereqs (Ubuntu/Debian)    ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    # Grunnpakker fra Ubuntu-repo
    local apt_pkgs=()
    command -v xz       >/dev/null 2>&1 || apt_pkgs+=("xz-utils")
    command -v curl     >/dev/null 2>&1 || apt_pkgs+=("curl")
    command -v lsblk    >/dev/null 2>&1 || apt_pkgs+=("util-linux")

    if [[ ${#apt_pkgs[@]} -gt 0 ]]; then
        info "Installerer fra apt: ${apt_pkgs[*]}"
        maybe_sudo apt-get update -qq
        maybe_sudo apt-get install -y "${apt_pkgs[@]}"
        ok "Grunnpakker installert"
    else
        ok "Grunnpakker (xz-utils, curl, util-linux) allerede til stede"
    fi

    # balena-etcher fra Cloudsmith (offisiell repo)
    # NB: Etcher avhenger av gconf-pakker som ikke lenger er tilgjengelig på Ubuntu 24.04+.
    # Bruk dd i stedet (se --download for instruksjoner).
    local ubuntu_version
    ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "0")
    if [[ $(echo "$ubuntu_version >= 24.04" | bc -l 2>/dev/null) -eq 1 ]]; then
        warn "Ubuntu ${ubuntu_version}: balena-etcher støttes ikke (mangler gconf). Bruk dd i stedet."
        warn "Se: $0 --download"
    elif command -v balena-etcher >/dev/null 2>&1 || command -v balena-etcher-electron >/dev/null 2>&1; then
        ok "balena-etcher allerede installert"
    else
        info "Legger til Balena Cloudsmith apt-repo for Etcher..."
        local setup_url="https://dl.cloudsmith.io/public/balena/etcher/setup.deb.sh"

        if ! $ASSUME_YES; then
            echo ""
            echo "Vil legge til ekstern apt-repo: $setup_url"
            read -r -p "Fortsette? [y/N] " resp
            [[ "$resp" =~ ^[Yy]$ ]] || { warn "Avbrutt — Etcher ikke installert"; return 0; }
        fi

        curl -1sLf "$setup_url" | maybe_sudo -E bash
        maybe_sudo apt-get install -y balena-etcher
        ok "balena-etcher installert"
    fi

    echo ""
    echo "Klar. Neste steg:"
    echo "  1. Last ned DietPi-image: $0 --download"
    echo "  2. Flash til SD-kort (dd anbefalt, se --download)"
    echo "  3. Kjør $0 /mnt/sdboot for å injisere config"
    echo ""
}

# --- Skriv ut DietPi-nedlastingsinfo ---
show_download() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   DietPi-image for Rock 3C               ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    echo "DietPi har ikke et dedikert ROCK3C-image, men Quartz64B (samme RK3566-brikke)"
    echo "er bekreftet kompatibel (github.com/MichaIng/DietPi/issues/7057)."
    echo ""
    echo "Last ned Quartz64B Bookworm-image:"
    echo "  ${DIETPI_IMAGES_URL}${DIETPI_IMAGE_FILE}"
    echo ""
    echo "Pakk ut og flash med dd (Etcher støttes ikke på Ubuntu 24.04):"
    echo "  xz -d ${DIETPI_IMAGE_FILE}"
    echo "  sudo dd if=\${HOME}/Downloads/\${DIETPI_IMAGE_FILE%.xz} bs=4M status=progress oflag=sync of=/dev/sdX"
    echo ""
    echo "Monter boot-partisjonen og kjør config-injeksjon:"
    echo "  sudo mkdir -p /mnt/sdboot && sudo mount /dev/sdX1 /mnt/sdboot"
    echo "  ./spotify-spiller/flash.sh /mnt/sdboot"
    echo ""
}

# --- Preflight: varsle om manglende verktøy uten å feile ---
preflight() {
    local has_etcher=false
    command -v balena-etcher          >/dev/null 2>&1 && has_etcher=true
    command -v balena-etcher-electron >/dev/null 2>&1 && has_etcher=true

    if ! $has_etcher; then
        warn "balena-etcher er ikke installert — kjør '$0 --install-deps' hvis du trenger å flashe et nytt SD-kort."
        warn "(Dette scriptet kan fortsatt injisere config på et SD-kort som allerede er flashet.)"
        echo ""
    fi
}

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

    printf '%s\n' "${unique[@]}"
}

verify_dietpi_boot() {
    local path="$1"
    [[ -d "$path" ]] || return 1
    [[ -f "$path/dietpi.txt" ]] && return 0
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

# --- Dispatch på spesialmoduser ---
if $INSTALL_DEPS; then
    install_deps
    exit 0
fi

if $SHOW_DOWNLOAD; then
    show_download
    exit 0
fi

# --- Finn mount-path ---
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Spotify-spiller SD-flash               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

preflight

if [[ -n "$MOUNT_PATH" ]]; then
    info "Bruker oppgitt mount-path: $MOUNT_PATH"
    verify_dietpi_boot "$MOUNT_PATH" || fail "Ser ikke ut som DietPi-boot: $MOUNT_PATH (mangler dietpi.txt)"
else
    info "Auto-detekterer DietPi SD-boot..."
    mapfile -t found < <(detect_dietpi_mount | sort -u | grep -v '^$' || true)

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
