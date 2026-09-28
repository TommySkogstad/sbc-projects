#!/bin/bash
# Valideringsskript for cloudflared-versjonsbump
# Verifiserer at docker-compose.yml er syntaksriktig og at image-tagen finnes
#
# Skriptet skriver aldri til geoloop/.env (sporet og git-crypt-kryptert).
# Validering skjer mot en midlertidig prosjektmappe med dummy-.env.

set -euo pipefail

GEOLOOP_DIR="$(cd "$(dirname "$0")/../geoloop" && pwd)"
COMPOSE_FILE="$GEOLOOP_DIR/docker-compose.yml"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "🔍 Validerer docker-compose.yml syntaks..."
cat > "$TMP_DIR/.env" <<'EOF'
CLOUDFLARE_TUNNEL_TOKEN=dummy_token_for_validation
HOST_IP=127.0.0.1
HOST_HOSTNAME=geoloop-test
WATCHDOG_NTFY_URL=https://ntfy.sh
WATCHDOG_NTFY_TOPIC=test
EOF

if docker compose --project-directory "$TMP_DIR" -f "$COMPOSE_FILE" config -q; then
  echo "✅ Syntaks OK"
else
  echo "❌ YAML-syntaks feil i docker-compose.yml"
  exit 1
fi

echo "🔍 Sjekker at cloudflared-image finnes på registry..."
CLOUDFLARED_TAG=$(grep -oP 'cloudflare/cloudflared:\K[^ ]+' "$COMPOSE_FILE")
echo "   Tag: $CLOUDFLARED_TAG"

if docker manifest inspect "cloudflare/cloudflared:$CLOUDFLARED_TAG" > /dev/null 2>&1; then
  echo "✅ Image finnes på registry: cloudflare/cloudflared:$CLOUDFLARED_TAG"
else
  echo "❌ Image finnes ikke på registry: cloudflare/cloudflared:$CLOUDFLARED_TAG"
  exit 1
fi

echo "✅ Alle valideringer bestått"
