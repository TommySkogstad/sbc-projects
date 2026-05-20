#!/usr/bin/env bash
# Første-boot provisioning for Rock 3C print-server
#
# Forutsetter at flash.sh allerede har lagt setup-filer i standard-stier:
#   - /etc/systemd/system/*.service (first-boot, wifi-check, captive-portal, printer-web)
#   - /usr/local/bin/add-printer.sh, render-airprint.sh, wifi-check.sh, captive-portal.py
#   - /usr/local/share/print-server/airprint.service.tmpl (mal for render-airprint.sh)
#   - /etc/avahi/services/airprint.service
#   - /etc/cups/cupsd.conf
#   - /etc/udev/rules.d/99-usb-printer.rules
#   - /etc/hostapd/hostapd.conf, /etc/dnsmasq.conf
#   - /usr/local/share/print-server/drivers/cnrdrvcups-ufr2-uk_*.deb
#   - /opt/printer-web/{main.py,requirements.txt}
#
# Denne tjenesten:
#   1. Installerer apt-pakker (bred driver-bundle, ~580 MB)
#   2. Installerer Canon UFRII-driver fra forhåndsbundlet .deb
#   3. Setter opp Python-venv og pip-install for printer-web
#   4. Aktiverer alle relevante systemd-tjenester
#
# Forventet kjøretid: 8–10 min ved første boot.
set -euo pipefail

SENTINEL="/.first-boot-done"
LOGFILE="/var/log/first-boot.log"
HOSTNAME_TARGET="$(cat /etc/hostname 2>/dev/null | tr -d '[:space:]')"
HOSTNAME_TARGET="${HOSTNAME_TARGET:-printer-rock}"

log() { echo "[first-boot] $(date -Iseconds) $*" | tee -a "$LOGFILE"; }
die() { log "FEIL: $*"; exit 1; }

# Idempotent: hopp over hvis allerede kjørt
if [[ -f "$SENTINEL" ]]; then
    log "Sentinel $SENTINEL funnet — hopper over (allerede provisjonert)"
    exit 0
fi

log "=== Rock 3C first-boot provisioning startet ==="
log "Hostname: $HOSTNAME_TARGET"

# --------------------------------------------------------------------------
# Hostname
# --------------------------------------------------------------------------
hostnamectl set-hostname "$HOSTNAME_TARGET"
if grep -q "127.0.1.1" /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$HOSTNAME_TARGET/" /etc/hosts
else
    echo -e "127.0.1.1\t$HOSTNAME_TARGET" >> /etc/hosts
fi

# --------------------------------------------------------------------------
# Pakkeinstallasjon — bred driver-bundle
# --------------------------------------------------------------------------
log "Oppdaterer pakkelister..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >> "$LOGFILE" 2>&1

log "Installerer print-stack og driver-bundle (~580 MB, forventet 8–10 min)..."
apt-get install -y \
    cups \
    cups-filters \
    cups-bsd \
    cups-browsed \
    avahi-daemon \
    ipp-usb \
    ghostscript \
    libjpeg62 \
    libjbig0 \
    lsb-release \
    printer-driver-all \
    hplip \
    hplip-data \
    printer-driver-brlaser \
    printer-driver-escpr \
    printer-driver-foo2zjs \
    printer-driver-splix \
    printer-driver-foomatic-db \
    foomatic-db-engine \
    hostapd \
    dnsmasq \
    python3 \
    python3-flask \
    python3-venv \
    python3-pip \
    unattended-upgrades \
    apt-listchanges \
    poppler-utils \
    >> "$LOGFILE" 2>&1

# printer-driver-escpr2 ikke alltid tilgjengelig — ikke kritisk
apt-get install -y printer-driver-escpr2 >> "$LOGFILE" 2>&1 || \
    log "printer-driver-escpr2 ikke tilgjengelig — escpr dekker de fleste Epson-modeller"

# --------------------------------------------------------------------------
# Canon UFRII-driver fra forhåndsbundlet .deb
# --------------------------------------------------------------------------
CANON_DEB="/usr/local/share/print-server/drivers/cnrdrvcups-ufr2-uk_6.20-1.20_arm64.deb"
if [[ -f "$CANON_DEB" ]]; then
    log "Installerer Canon UFRII-driver fra forhåndsbundlet .deb..."
    dpkg -i "$CANON_DEB" >> "$LOGFILE" 2>&1 || apt-get install -f -y >> "$LOGFILE" 2>&1
    log "Canon UFRII-driver installert"
else
    log "Canon UFRII .deb ikke funnet på $CANON_DEB — hopper over"
fi

# --------------------------------------------------------------------------
# CUPS-konfigurasjon
# --------------------------------------------------------------------------
log "Konfigurerer CUPS..."
cupsctl --remote-admin --remote-any --share-printers >> "$LOGFILE" 2>&1 || true

# --------------------------------------------------------------------------
# Web-UI (FastAPI + uvicorn) — opprett venv og installer requirements
# --------------------------------------------------------------------------
if [[ -f /opt/printer-web/main.py && -f /opt/printer-web/requirements.txt ]]; then
    log "Setter opp printer-web venv..."
    useradd --system --no-create-home --shell /usr/sbin/nologin printer-web 2>/dev/null || true
    usermod -aG lp printer-web 2>/dev/null || true

    python3 -m venv /opt/printer-web/venv
    /opt/printer-web/venv/bin/pip install --quiet --no-cache-dir \
        -r /opt/printer-web/requirements.txt >> "$LOGFILE" 2>&1

    chown -R printer-web:printer-web /opt/printer-web
    touch /var/log/printer-web.log
    chown printer-web:printer-web /var/log/printer-web.log
    log "printer-web venv klar"
fi

# --------------------------------------------------------------------------
# hostapd default-config peker på riktig path (Armbian masker hostapd)
# --------------------------------------------------------------------------
if [[ -f /etc/hostapd/hostapd.conf ]]; then
    sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' \
        /etc/default/hostapd 2>/dev/null || true
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
systemctl enable cups-browsed
systemctl enable ipp-usb
systemctl enable unattended-upgrades
systemctl enable wifi-check.service 2>/dev/null || true
systemctl enable printer-web.service 2>/dev/null || log "printer-web.service ikke installert"

systemctl start cups || true
systemctl start avahi-daemon || true
systemctl start cups-browsed || true
systemctl start ipp-usb || true
systemctl start printer-web.service 2>/dev/null || true

# AP-fallback-tjenester startes kun av wifi-check ved behov
systemctl disable dnsmasq 2>/dev/null || true
systemctl disable hostapd 2>/dev/null || true
systemctl disable captive-portal.service 2>/dev/null || true
systemctl unmask hostapd 2>/dev/null || true

# --------------------------------------------------------------------------
# Skriv sentinel og deaktiver denne tjenesten
# --------------------------------------------------------------------------
log "Skriver sentinel $SENTINEL..."
touch "$SENTINEL"

log "Deaktiverer first-boot.service..."
systemctl disable first-boot.service || true
rm -f /etc/systemd/system/multi-user.target.wants/first-boot.service

log "=== Rock 3C first-boot provisioning fullført ==="
