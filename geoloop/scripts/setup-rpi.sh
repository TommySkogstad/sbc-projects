#!/usr/bin/env bash
# ============================================================
# GeoLoop — Fullstendig oppsett av Raspberry Pi
# ============================================================
# Kjør på en fersk RPi (Raspberry Pi OS Lite 64-bit):
#   curl -fsSL https://raw.githubusercontent.com/TommySkogstad/GeoLoop/main/scripts/setup-rpi.sh | bash
#
# Eller manuelt:
#   git clone https://github.com/TommySkogstad/GeoLoop.git
#   cd GeoLoop && bash scripts/setup-rpi.sh
#
# Forutsetninger:
#   - Raspberry Pi 3B+ eller nyere
#   - Raspberry Pi OS Lite (64-bit) med SSH aktivert
#   - Internettilgang
#   - DS18B20-sensorer koblet til GPIO4 (1-Wire)
#   - Relékort koblet til GPIO 26, 20, 21
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[FEIL]${NC}  $*"; exit 1; }

INSTALL_DIR="${GEOLOOP_DIR:-/opt/geoloop}"
REPO_URL="https://github.com/TommySkogstad/GeoLoop.git"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       GeoLoop — RPi Oppsett v1.0         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ----------------------------------------------------------
# 1. Sjekk at vi kjører på RPi med riktige rettigheter
# ----------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    error "Kjør som root: sudo bash $0"
fi

info "Sjekker system..."
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "armv7l" ]]; then
    warn "Uventet arkitektur: $ARCH (forventet aarch64/armv7l)"
    read -rp "Fortsette likevel? [j/N] " yn
    [[ "$yn" =~ ^[jJyY]$ ]] || exit 0
fi
ok "Arkitektur: $ARCH"

# ----------------------------------------------------------
# 2. Oppdater system og installer grunnpakker
# ----------------------------------------------------------
info "Oppdaterer system..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq git gpg curl

ok "System oppdatert"

# ----------------------------------------------------------
# 3. Aktiver 1-Wire for DS18B20-sensorer
# ----------------------------------------------------------
info "Aktiverer 1-Wire (GPIO4 for DS18B20)..."

CONFIG_FILE="/boot/firmware/config.txt"
[[ -f "$CONFIG_FILE" ]] || CONFIG_FILE="/boot/config.txt"

if ! grep -q "^dtoverlay=w1-gpio" "$CONFIG_FILE" 2>/dev/null; then
    echo "" >> "$CONFIG_FILE"
    echo "# GeoLoop: 1-Wire for DS18B20 temperatursensorer" >> "$CONFIG_FILE"
    echo "dtoverlay=w1-gpio,gpiopin=4" >> "$CONFIG_FILE"
    REBOOT_NEEDED=true
    ok "1-Wire aktivert i $CONFIG_FILE"
else
    ok "1-Wire allerede aktivert"
fi

# Last moduler nå (hvis de finnes)
modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

# ----------------------------------------------------------
# 4. Installer Docker
# ----------------------------------------------------------
if command -v docker &>/dev/null; then
    ok "Docker allerede installert: $(docker --version)"
else
    info "Installerer Docker..."
    curl -fsSL https://get.docker.com | sh
    ok "Docker installert"
fi

# Legg til bruker i docker-gruppen (for den som SSH-er inn)
REAL_USER="${SUDO_USER:-pi}"
if id "$REAL_USER" &>/dev/null; then
    usermod -aG docker "$REAL_USER"
    ok "$REAL_USER lagt til i docker-gruppen"
fi

# Aktiver Docker ved boot
systemctl enable docker
systemctl start docker

# ----------------------------------------------------------
# 5. Klon repo (eller bruk eksisterende)
# ----------------------------------------------------------
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "GeoLoop allerede klonet i $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "Kunne ikke oppdatere — sjekk manuelt"
else
    info "Kloner GeoLoop til $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    ok "Klonet til $INSTALL_DIR"
fi

# ----------------------------------------------------------
# 6. git-crypt: Lås opp krypterte filer
# ----------------------------------------------------------
info "Sjekker git-crypt..."

if ! command -v git-crypt &>/dev/null; then
    apt-get install -y -qq git-crypt
fi

# Sjekk om .env er kryptert (binært innhold)
if file "$INSTALL_DIR/.env" | grep -q "text"; then
    ok ".env er allerede dekryptert"
else
    info "Krypterte filer oppdaget — trenger GPG-nøkkel for å låse opp"
    echo ""
    echo -e "${YELLOW}For å låse opp trenger du GPG-nøkkelen.${NC}"
    echo "Kopier den private nøkkelen fra en maskin som har den:"
    echo ""
    echo "  # På kildemaskin:"
    echo "  gpg --export-secret-keys CA1E41D13067550891949E067F35459C441CBC8B > /tmp/geoloop.gpg"
    echo "  scp /tmp/geoloop.gpg pi@<rpi-ip>:/tmp/"
    echo ""
    echo "  # Deretter kjør dette skriptet på nytt, eller:"
    echo "  gpg --import /tmp/geoloop.gpg"
    echo "  cd $INSTALL_DIR && git-crypt unlock"
    echo ""

    if [[ -f /tmp/geoloop.gpg ]]; then
        info "Fant /tmp/geoloop.gpg — importerer..."
        gpg --import /tmp/geoloop.gpg
        git-crypt unlock
        rm -f /tmp/geoloop.gpg
        ok "git-crypt låst opp"
    else
        read -rp "Har du allerede importert GPG-nøkkelen? [j/N] " yn
        if [[ "$yn" =~ ^[jJyY]$ ]]; then
            git-crypt unlock || error "Kunne ikke låse opp git-crypt. Importer GPG-nøkkel først."
            ok "git-crypt låst opp"
        else
            warn "Hopper over git-crypt — kjør 'git-crypt unlock' manuelt etterpå"
        fi
    fi
fi

# ----------------------------------------------------------
# 7. Sett HOST_IP og HOST_HOSTNAME i .env
# ----------------------------------------------------------
info "Konfigurerer vertsinformasjon i .env..."

LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
LOCAL_HOSTNAME=$(hostname)

if [[ -f "$INSTALL_DIR/.env" ]] && file "$INSTALL_DIR/.env" | grep -q "text"; then
    # Fjern eksisterende HOST_IP/HOST_HOSTNAME hvis de finnes
    sed -i '/^HOST_IP=/d; /^HOST_HOSTNAME=/d' "$INSTALL_DIR/.env"
    echo "" >> "$INSTALL_DIR/.env"
    echo "# Vertsinformasjon (vises i dashboard-footer for feilsøking)" >> "$INSTALL_DIR/.env"
    echo "HOST_IP=${LOCAL_IP}" >> "$INSTALL_DIR/.env"
    echo "HOST_HOSTNAME=${LOCAL_HOSTNAME}" >> "$INSTALL_DIR/.env"
    ok "HOST_IP=$LOCAL_IP, HOST_HOSTNAME=$LOCAL_HOSTNAME"
else
    warn ".env ikke dekryptert ennå — sett HOST_IP og HOST_HOSTNAME manuelt etterpå"
fi

# ----------------------------------------------------------
# 8. Konfigurer sensorer
# ----------------------------------------------------------
echo ""
info "Sjekker DS18B20-sensorer..."

W1_DIR="/sys/bus/w1/devices"
if [[ -d "$W1_DIR" ]]; then
    SENSOR_IDS=$(ls "$W1_DIR" 2>/dev/null | grep "^28-" || true)
    if [[ -n "$SENSOR_IDS" ]]; then
        ok "Fant sensorer:"
        echo "$SENSOR_IDS" | while read -r sid; do
            TEMP=$(cat "$W1_DIR/$sid/temperature" 2>/dev/null || echo "?")
            if [[ "$TEMP" != "?" ]]; then
                TEMP_C=$(echo "scale=1; $TEMP / 1000" | bc 2>/dev/null || echo "?")
                echo "    $sid  →  ${TEMP_C}°C"
            else
                echo "    $sid"
            fi
        done
        echo ""
        echo -e "${YELLOW}Oppdater sensor-ID-ene i config.yaml:${NC}"
        echo "    $INSTALL_DIR/config.yaml"
    else
        warn "Ingen DS18B20-sensorer funnet. Sjekk kobling til GPIO4."
        if [[ "${REBOOT_NEEDED:-}" == "true" ]]; then
            warn "1-Wire ble nettopp aktivert — reboot nødvendig for å oppdage sensorer"
        fi
    fi
else
    warn "1-Wire ikke tilgjengelig ennå"
    if [[ "${REBOOT_NEEDED:-}" == "true" ]]; then
        warn "1-Wire ble nettopp aktivert — reboot nødvendig"
    fi
fi

# ----------------------------------------------------------
# 9. Sett riktig eierskap
# ----------------------------------------------------------
chown -R "$REAL_USER:$REAL_USER" "$INSTALL_DIR"

# ----------------------------------------------------------
# 10. Systemd-service for Docker Compose
# ----------------------------------------------------------
info "Installerer systemd-tjeneste..."

cat > /etc/systemd/system/geoloop.service << EOF
[Unit]
Description=GeoLoop — Styring av vannbåren varme
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose up -d --build

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable geoloop.service
ok "systemd-tjeneste installert og aktivert"

# ----------------------------------------------------------
# 11. Oppsummering
# ----------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         GeoLoop er installert!           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Installert i:  $INSTALL_DIR"
echo "  Bruker:         $REAL_USER"
echo ""

if [[ "${REBOOT_NEEDED:-}" == "true" ]]; then
    echo -e "${YELLOW}  ⚠  REBOOT NØDVENDIG for å aktivere 1-Wire${NC}"
    echo ""
fi

echo "  Neste steg:"
echo "  ─────────────────────────────────────────"

STEP=1
if file "$INSTALL_DIR/.env" | grep -qv "text"; then
    echo "  $STEP. Lås opp git-crypt (se instruksjoner over)"
    STEP=$((STEP + 1))
fi

echo "  $STEP. Rediger config.yaml med sensor-ID-er:"
echo "     nano $INSTALL_DIR/config.yaml"
STEP=$((STEP + 1))

if [[ "${REBOOT_NEEDED:-}" == "true" ]]; then
    echo "  $STEP. Reboot:  sudo reboot"
    STEP=$((STEP + 1))
    echo "  $STEP. Start etter reboot:  sudo systemctl start geoloop"
else
    echo "  $STEP. Start:  sudo systemctl start geoloop"
fi
STEP=$((STEP + 1))

echo "  $STEP. Sjekk status:  sudo systemctl status geoloop"
echo "     docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo ""
echo "  Dashboard: https://geoloop.tommytv.no (via Cloudflare Tunnel)"
echo ""
