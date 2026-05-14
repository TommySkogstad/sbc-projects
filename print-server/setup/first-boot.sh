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

if [[ -f /tmp/setup/render-airprint.sh ]]; then
    cp /tmp/setup/render-airprint.sh /usr/local/bin/render-airprint.sh
    chmod 755 /usr/local/bin/render-airprint.sh
fi

if [[ -f /tmp/setup/airprint.service.tmpl ]]; then
    mkdir -p /usr/local/share/print-server
    cp /tmp/setup/airprint.service.tmpl /usr/local/share/print-server/airprint.service.tmpl
fi

# --------------------------------------------------------------------------
# WiFi-onboarding (captive portal + AP-fallback)
# --------------------------------------------------------------------------
if [[ -f /tmp/setup/captive-portal.py ]]; then
    cp /tmp/setup/captive-portal.py /usr/local/bin/captive-portal.py
    chmod 755 /usr/local/bin/captive-portal.py
fi

if [[ -f /tmp/setup/hostapd.conf ]]; then
    cp /tmp/setup/hostapd.conf /etc/hostapd/hostapd.conf
    chmod 644 /etc/hostapd/hostapd.conf
    # hostapd default-config peker på DAEMON_CONF=/etc/hostapd/hostapd.conf
    sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' \
        /etc/default/hostapd 2>/dev/null || true
fi

if [[ -f /tmp/setup/dnsmasq.conf ]]; then
    cp /tmp/setup/dnsmasq.conf /etc/dnsmasq.d/captive-portal.conf
fi

if [[ -f /tmp/setup/wifi-check.service ]]; then
    cp /tmp/setup/wifi-check.service /etc/systemd/system/wifi-check.service
fi

if [[ -f /tmp/setup/captive-portal.service ]]; then
    cp /tmp/setup/captive-portal.service /etc/systemd/system/captive-portal.service
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
systemctl daemon-reload || true
systemctl enable cups
systemctl enable avahi-daemon
systemctl enable unattended-upgrades
systemctl enable wifi-check.service || true

systemctl start cups || true
systemctl start avahi-daemon || true

# Dnsmasq, hostapd og captive-portal startes kun av wifi-check ved AP-fallback
systemctl disable dnsmasq || true
systemctl disable hostapd || true
systemctl disable captive-portal.service || true
# Unmask hostapd (Armbian masker den som default)
systemctl unmask hostapd 2>/dev/null || true

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
