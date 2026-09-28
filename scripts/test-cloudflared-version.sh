#!/bin/bash
# Valideringsskript for cloudflared-versjonsbump
# Verifiserer at docker-compose.yml er syntaksriktig og at image-tagen finnes

set -e

cd "$(dirname "$0")/../geoloop"

echo "🔍 Validerer docker-compose.yml syntaks..."
# Lag dummy .env for validering
SAVED_ENV=""
if [ -f .env ]; then
  SAVED_ENV=$(cat .env)
fi

cat > .env <<'EOF'
CLOUDFLARE_TUNNEL_TOKEN=dummy_token_for_validation
HOST_IP=127.0.0.1
HOST_HOSTNAME=geoloop-test
WATCHDOG_NTFY_URL=https://ntfy.sh
WATCHDOG_NTFY_TOPIC=test
EOF

if docker compose config > /dev/null 2>&1; then
  echo "✅ Syntaks OK"
else
  echo "❌ YAML-syntaks feil i docker-compose.yml"
  exit 1
fi

# Gjenopprett original .env
if [ -n "$SAVED_ENV" ]; then
  echo "$SAVED_ENV" > .env
else
  rm .env
  git checkout .env 2>/dev/null || true
fi

echo "🔍 Sjekker at cloudflared-image finnes på registry..."
CLOUDFLARED_TAG=$(grep -oP 'cloudflare/cloudflared:\K[^ ]+' docker-compose.yml)
echo "   Tag: $CLOUDFLARED_TAG"

if docker manifest inspect "cloudflare/cloudflared:$CLOUDFLARED_TAG" > /dev/null 2>&1; then
  echo "✅ Image finnes på registry: cloudflare/cloudflared:$CLOUDFLARED_TAG"
else
  echo "❌ Image finnes ikke på registry: cloudflare/cloudflared:$CLOUDFLARED_TAG"
  exit 1
fi

echo "✅ Alle valideringer bestått"
