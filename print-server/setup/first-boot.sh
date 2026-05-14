#!/usr/bin/env bash
# Første-boot provisioning for Rock 3C print-server
set -euo pipefail

SENTINEL="/.first-boot-done"
LOGFILE="/var/log/first-boot.log"
HOSTNAME_TARGET="printer-rock"

log() { echo "[first-boot] $*" | tee -a "$LOGFILE"; }
die() { log "FEIL: $*"; exit 1; }

# Idempotent: hopp over hvis allerede kjørt (f.eks. etter strømbrudd under install)
if [[ -f "$SENTINEL" ]]; then
    log "Sentinel $SENTINEL funnet — hopper over (allerede provisjonert)"
    exit 0
fi

log "=== Rock 3C first-boot provisioning startet $(date) ==="

# --------------------------------------------------------------------------
# Hostname
# --------------------------------------------------------------------------
log "Setter hostname: $HOSTNAME_TARGET"
hostnamectl set-hostname "$HOSTNAME_TARGET"
echo "$HOSTNAME_TARGET" > /etc/hostname
# Oppdater /etc/hosts slik at lokal oppslag fungerer
if grep -q "127.0.1.1" /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$HOSTNAME_TARGET/" /etc/hosts
else
    echo -e "127.0.1.1\t$HOSTNAME_TARGET" >> /etc/hosts
fi

# --------------------------------------------------------------------------
# Pakkeinstallasjon
# --------------------------------------------------------------------------
log "Oppdaterer pakkelister..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >> "$LOGFILE" 2>&1

log "Installerer print-stack og avhengigheter (kan ta 5-15 min på SD)..."
apt-get install -y \
    avahi-daemon \
    cups \
    cups-filters \
    cups-bsd \
    printer-driver-all \
    hplip \
    ipp-usb \
    ghostscript \
    hostapd \
    dnsmasq \
    python3-flask \
    python3-cups \
    unattended-upgrades \
    apt-listchanges \
    >> "$LOGFILE" 2>&1

# --------------------------------------------------------------------------
# CUPS-konfigurasjon
# --------------------------------------------------------------------------
log "Kopierer cupsd.conf..."
if [[ -f /tmp/setup/cupsd.conf ]]; then
    cp /tmp/setup/cupsd.conf /etc/cups/cupsd.conf
    chmod 640 /etc/cups/cupsd.conf
fi

# --------------------------------------------------------------------------
# Avahi AirPrint-tjeneste
# --------------------------------------------------------------------------
log "Kopierer Avahi AirPrint-tjenestebeskrivelse..."
if [[ -f /tmp/setup/airprint.service ]]; then
    mkdir -p /etc/avahi/services
    cp /tmp/setup/airprint.service /etc/avahi/services/airprint.service
fi

# --------------------------------------------------------------------------
# udev-regel for USB-printer
# --------------------------------------------------------------------------
if [[ -f /tmp/setup/99-usb-printer.rules ]]; then
    cp /tmp/setup/99-usb-printer.rules /etc/udev/rules.d/99-usb-printer.rules
fi

# --------------------------------------------------------------------------
# WiFi-feilsikring
# --------------------------------------------------------------------------
if [[ -f /tmp/setup/wifi-check.sh ]]; then
    cp /tmp/setup/wifi-check.sh /usr/local/bin/wifi-check.sh
    chmod 755 /usr/local/bin/wifi-check.sh
fi

if [[ -f /tmp/setup/add-printer.sh ]]; then
    cp /tmp/setup/add-printer.sh /usr/local/bin/add-printer.sh
    chmod 755 /usr/local/bin/add-printer.sh
fi

# --------------------------------------------------------------------------
# Auto-oppdatering (unattended-upgrades)
# --------------------------------------------------------------------------
log "Aktiverer unattended-upgrades..."
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# --------------------------------------------------------------------------
# Aktiver tjenester
# --------------------------------------------------------------------------
log "Aktiverer og starter tjenester..."
systemctl enable cups
systemctl enable avahi-daemon
systemctl enable unattended-upgrades

systemctl start cups || true
systemctl start avahi-daemon || true

# Dnsmasq og hostapd startes kun av wifi-check ved AP-fallback
systemctl disable dnsmasq || true
systemctl disable hostapd || true

# --------------------------------------------------------------------------
# Skriv sentinel og deaktiver denne tjenesten
# --------------------------------------------------------------------------
log "Skriver sentinel $SENTINEL..."
touch "$SENTINEL"

log "Deaktiverer first-boot.service..."
systemctl disable first-boot.service || true
# Fjern symlink direkte for å unngå at tjenesten kjøres igjen ved reboot
rm -f /etc/systemd/system/multi-user.target.wants/first-boot.service

log "=== Rock 3C first-boot provisioning fullført $(date) ==="
