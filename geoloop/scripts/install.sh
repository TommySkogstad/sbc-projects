#!/usr/bin/env bash
# Installer GeoLoop som systemd-tjeneste på Raspberry Pi.
# Kjør som: sudo bash scripts/install.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/geoloop.service"

echo "==> Installerer GeoLoop fra $APP_DIR"

# Opprett virtualenv hvis den ikke finnes
if [ ! -d "$VENV_DIR" ]; then
    echo "==> Oppretter virtualenv"
    python3 -m venv "$VENV_DIR"
fi

echo "==> Installerer avhengigheter"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$APP_DIR"

# Kopier eksempelkonfig hvis config.yaml ikke finnes
if [ ! -f "$APP_DIR/config.yaml" ]; then
    echo "==> Kopierer config.example.yaml -> config.yaml (rediger denne!)"
    cp "$APP_DIR/config.example.yaml" "$APP_DIR/config.yaml"
fi

# Installer systemd-service
echo "==> Installerer systemd-tjeneste"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=GeoLoop - Styring av vannbåren varme
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(logname)
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m geoloop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable geoloop.service
echo "==> Tjeneste installert og aktivert."
echo ""
echo "Neste steg:"
echo "  1. Rediger $APP_DIR/config.yaml med dine innstillinger"
echo "  2. Start tjenesten: sudo systemctl start geoloop"
echo "  3. Sjekk status: sudo systemctl status geoloop"
echo "  4. Se logger: journalctl -u geoloop -f"
