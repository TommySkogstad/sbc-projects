#!/bin/sh
# Sjekk at /app/data er skrivbar for geoloop-brukeren
if [ ! -w /app/data ]; then
    echo "WARN: /app/data er ikke skrivbar — fiks med:"
    echo "  docker run --rm -v geoloop_geoloop_data:/data alpine chown -R $(id -u):$(id -g) /data"
    exit 1
fi

exec "$@"
