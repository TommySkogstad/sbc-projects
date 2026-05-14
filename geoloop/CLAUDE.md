# GeoLoop

## Prosjekt
- **URL**: https://geoloop.tommytv.no (via Cloudflare Tunnel)
- **Stack**: Python 3.11, FastAPI, SQLite, Docker Compose, Cloudflare Tunnel
- **Målplattform**: Raspberry Pi 3B+ med DS18B20-sensorer og relékort
- **Formål**: Styring av vannbåren varme i utendørs bakke (snøsmelting/is-forebygging)

## Kjøring
- **Produksjon (RPi)**: `sudo systemctl start geoloop` eller `docker compose up -d --build`
- **Oppsett ny RPi**: `sudo bash scripts/setup-rpi.sh`
- **Tester**: `pytest tests/ -v` (krever `pip install -e ".[dev]"`)

## Arkitektur
- `geoloop/main.py` — Oppstart, APScheduler for periodisk værhenting
- `geoloop/web/app.py` — FastAPI web-app med auth, CSRF, rate limiting
- `geoloop/web/static/` — Vanilla JS frontend (ingen bundler, ingen CDN)
- `geoloop/weather/met_client.py` — api.met.no klient
- `geoloop/sensors/base.py` — DS18B20 via 1-Wire
- `geoloop/controller/base.py` — GPIO reléstyring
- `geoloop/db/store.py` — SQLite logging
- `geoloop/notify.py` — ntfy push-varsler

## Sikkerhet
- `.env` og `config.yaml` er kryptert med git-crypt (GPG-nøkkel `CA1E...8B`)
- Auth: SHA-256 passord-hash, HttpOnly cookie, SameSite=strict
- Rate limiting: 5 login-forsøk per IP per 5 min
- CSRF: Cookie + `x-csrf-token` header på alle POST-endepunkter
- Docker: Non-root bruker (`geoloop`), minnegrenser (256 MB)
- Frontend: Ingen innerHTML — all dynamisk rendering via DOM API (XSS-safe)
- Cloudflare Tunnel: Ingen åpne porter

## Konvensjoner
- Kommunikasjon og dokumentasjon på norsk (bokmål)
- Commit-meldinger på engelsk
- Vanilla JavaScript (ES5-kompatibel, ingen bundler)
- Ingen eksterne frontend-avhengigheter (CDN-fri)

## Docker
- `docker-compose.yml` kjører tre tjenester: `geoloop`, `cloudflared`, `watchdog`
- SQLite-database lagres i Docker volume `geoloop_data` montert på `/app/data`
- config.yaml monteres read-only på `/app/config.yaml`

## CI/CD
- GitHub Actions: `.github/workflows/ci.yml`
- Jobber: pytest + Docker build
- Kjører på push til main og PR
