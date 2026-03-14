# GeoLoop

Styring av vannbåren varme i utendørs bakke (snøsmelting/is-forebygging) via Raspberry Pi, med prediktiv oppstart basert på værdata.

[![CI](https://github.com/TommySkogstad/GeoLoop/actions/workflows/ci.yml/badge.svg)](https://github.com/TommySkogstad/GeoLoop/actions/workflows/ci.yml)

## Systemarkitektur

```
┌─────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│  Værtjeneste │────▶│  Raspberry Pi 3B+      │     │  RPi Relay Board │
│  (api.met.no)│     │                        │────▶│  (3 kanaler)     │
└─────────────┘     │  + Open-Smart GPIO     │     │                  │
                     │    Expansion           │     │  K1: VP ON/OFF   │
┌─────────────┐     │                        │     │  K2: Sirk.pumpe  │
│  Temp-       │────▶│  - Styringslogikk      │     │  K3: Ledig       │
│  sensorer    │     │  - Web UI / API        │     └────────┬─────────┘
│  (5 stk)     │     └────────────────────────┘              │
└─────────────┘                                     ┌────────▼─────────┐
                                                    │  Panasonic       │
                                                    │  WH-MXC12G6E5   │
                                                    │  (klemme 17/18)  │
                                                    └──────────────────┘
```

## Maskinvare

| Komponent | Modell | Rolle |
|-----------|--------|-------|
| Styringsenhet | Raspberry Pi 3B+ | Kjører GeoLoop-programvaren |
| Relékort | RPi Relay Board (3 kanaler, HAT) | Styrer VP og sirkulasjonspumpe |
| GPIO-utvidelse | Open-Smart GPIO Expansion Board | Ekstra pinner til sensorer |
| Varmepumpe | Panasonic WH-MXC12G6E5 (Aquarea G-gen) | Luft-vann, hovedvarmekilden |
| Kolber | 10 kW elektriske, 10 L tank | Tilleggsvarme på VP inngang (ingen styring ennå) |
| Sirkulasjonspumpe | Ekstern + intern (følger VP) | Sirkulerer varme i bakkeløyfen |
| Bakkeløyfe | 8 sløyfer, 900 m totalt (20/16 mm) | ~181 liter vannvolum |
| Buffertank | 200 liter | Tankføler på VP klemme 15/16 |

### Temperatursensorer (5 målepunkter)

| # | Plassering | Formål |
|---|------------|--------|
| T1 | Inn til varmesløyfe (bakke) | Turtemperatur til bakken |
| T2 | Ut av varmesløyfe (bakke) | Returtemperatur fra bakken (delta-T) |
| T3 | Inn til varmepumpe | Returvann til VP |
| T4 | Ut av varmepumpe | Turvann fra VP |
| T5 | Vanntank (200 L) | Buffertemperatur (VP klemme 15/16) |

### Relétilkoblinger

| Kanal | Funksjon | Tilkobling |
|-------|----------|------------|
| 1 | Varmepumpe ON/OFF | VP klemme 17/18 (potensialfri, erstatter fabrikkjumper) |
| 2 | Ekstern sirkulasjonspumpe | Uavhengig av VP |
| 3 | Ledig | Reservert for fremtidig bruk (kolber) |

## Hurtigstart

### Automatisk oppsett (anbefalt for RPi)

```bash
# På en fersk Raspberry Pi (Raspberry Pi OS Lite 64-bit):
curl -fsSL https://raw.githubusercontent.com/TommySkogstad/GeoLoop/main/scripts/setup-rpi.sh | sudo bash
```

Skriptet installerer Docker, aktiverer 1-Wire, kloner repo, setter opp git-crypt og systemd-tjeneste. Se [scripts/setup-rpi.sh](scripts/setup-rpi.sh) for detaljer.

### Manuelt oppsett

Kjøres via Docker på Raspberry Pi med Cloudflare Tunnel — ingen åpne porter.

```bash
git clone https://github.com/TommySkogstad/GeoLoop
cd GeoLoop

# 1. Lås opp krypterte filer (krever GPG-nøkkel)
gpg --import /tmp/geoloop.gpg   # importer GPG-nøkkel
git-crypt unlock

# 2. Rediger .env med Cloudflare Tunnel-token og passord
nano .env

# 3. Konfigurer posisjon, sensor-IDer og database-sti
nano config.yaml

# 4. Start
docker compose up -d --build

# Sjekk status
curl https://geoloop.tommytv.no/api/status
```

### Cloudflare-oppsett

1. Gå til [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → **Networks → Tunnels → Create a tunnel**
2. Navn: `geoloop`, velg Docker som connector-type
3. Under **Public Hostnames**: `geoloop.tommytv.no` → `http://geoloop:8000`
4. Kopier tunnel-token til `.env`

> **Mistet tokenet?** Logg inn på [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → Networks → Tunnels → `geoloop` → Configure → kopier token på nytt.

## Prosjektstruktur

```
GeoLoop/
├── Dockerfile                # Docker-image (Python 3.11-slim, non-root)
├── docker-compose.yml        # Cloudflare Tunnel + GeoLoop + Watchdog
├── .env                      # Miljøvariabler (git-crypt-kryptert)
├── config.yaml               # Konfigurasjon (git-crypt-kryptert)
├── .gitattributes            # git-crypt-regler
├── pyproject.toml            # Avhengigheter og prosjektmetadata
├── geoloop/
│   ├── main.py               # Oppstart, scheduler, livsløp
│   ├── config.py             # Konfig-lasting fra YAML
│   ├── notify.py             # ntfy push-varsler
│   ├── weather/
│   │   └── met_client.py     # api.met.no-klient
│   ├── sensors/
│   │   └── base.py           # Abstrakt sensorgrensesnitt
│   ├── controller/
│   │   └── base.py           # Abstrakt styringsgrensesnitt
│   ├── db/
│   │   └── store.py          # SQLite-logging
│   └── web/
│       ├── app.py            # FastAPI med JSON-API + auth + CSRF
│       └── static/           # Frontend (vanilla JS, CSS)
├── scripts/
│   ├── setup-rpi.sh          # Fullstendig RPi-oppsett (Docker, 1-Wire, git-crypt)
│   └── install.sh            # Alternativ: direkte Python-installasjon (uten Docker)
├── tests/
│   ├── test_met_client.py
│   └── test_store.py
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions: pytest + Docker build
└── docs/
    ├── oppsett-guide.md      # Maskinvare- og installasjonsguide
    ├── koblingsskjema.md      # Detaljerte koblingsdiagrammer
    ├── CZ-TAW1-OI-1.pdf      # CZ-TAW1 dok (ikke kompatibel)
    └── SM-WHMXC09G3E5_WH-MXC12G6E5.pdf  # VP servicemanual
```

## API-endepunkter

| Endepunkt | Beskrivelse |
|-----------|-------------|
| `POST /api/login` | Logg inn med passord (rate-begrenset: 5 forsøk / 5 min) |
| `GET /api/status` | Gjeldende tilstand (vær, sensorer, releer) — åpen |
| `GET /api/weather` | Siste værdata + 24-timers prognose |
| `GET /api/sensors` | Les alle temperatursensorer |
| `GET /api/system` | Systeminformasjon og konfigurasjon |
| `GET /api/history?hours=24` | Sensorhistorikk og VP-perioder |
| `GET /api/log?limit=50` | Historikk fra databasen |
| `GET /api/thresholds` | Gjeldende temperaturgrenser |
| `POST /api/thresholds` | Oppdater temperaturgrenser (CSRF-beskyttet) |
| `POST /api/heating/on` | Manuell overstyring: varme PÅ (CSRF-beskyttet) |
| `POST /api/heating/off` | Manuell overstyring: varme AV (CSRF-beskyttet) |
| `POST /api/heating/auto` | Tilbake til automatisk styring (CSRF-beskyttet) |

Alle POST-endepunkter (unntatt login) krever CSRF-token via `x-csrf-token`-header.

## Varsler (ntfy)

GeoLoop sender push-varsler via [ntfy](https://ntfy.tommytv.no) ved viktige hendelser:

| Hendelse | Prioritet | Tag |
|----------|-----------|-----|
| Isfare — varme PÅ | Høy | `warning` |
| Modus endret: PÅ | Normal | `fire` |
| Modus endret: AV | Normal | `snowflake` |
| Modus endret: AUTO | Normal | `robot_face` |
| Temperaturgrenser endret | Normal | `thermometer` |

### Abonnere på varsler

1. **Installer ntfy-appen** på telefonen:
   - [Android (Google Play)](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - [iOS (App Store)](https://apps.apple.com/app/ntfy/id1625396347)

2. **Legg til din egen server:**
   - Åpne appen → Innstillinger → **Administrer kontoer** → **Legg til konto**
   - Server-URL: `https://ntfy.tommytv.no`
   - Brukernavn: `tommy`
   - Passord: `tommy`

3. **Abonner på topic:**
   - Trykk **+** → Skriv inn topic: `geoloop-21a`
   - Velg serveren `ntfy.tommytv.no` (ikke ntfy.sh)

Du vil nå motta push-varsler i sanntid når systemet slår seg av/på eller oppdager isfare.

### Serveroppsett (for admin)

GeoLoop kobler seg til ntfy med følgende miljøvariabler i `.env`:

```bash
NTFY_URL=https://ntfy.tommytv.no    # Egen ntfy-server
NTFY_TOPIC=geoloop-21a              # Topic for varsler
NTFY_USER=geoloop                   # Brukernavn for publisering
NTFY_PASS=ditt-passord-her          # Passord for publisering
```

Opprett brukeren på ntfy-serveren:

```bash
# På tommytv-serveren (der ntfy kjører)
docker exec -it ntfy ntfy user add geoloop
docker exec ntfy ntfy access geoloop 'geoloop-*' rw
```

## Sikkerhet

| Lag | Tiltak |
|-----|--------|
| Nettverk | Cloudflare Tunnel — ingen åpne porter, all trafikk via Cloudflare |
| Autentisering | Passord med SHA-256 hash, HttpOnly cookie, SameSite=strict |
| Rate limiting | Maks 5 innloggingsforsøk per IP per 5 minutter (429-respons) |
| CSRF | Cookie + header-token på alle muterende endepunkter |
| XSS | Ingen innerHTML — all dynamisk rendering via DOM API |
| Hemmeligheter | `.env` og `config.yaml` kryptert med git-crypt (GPG) |
| Container | Non-root bruker i Docker, minnegrenser (256 MB) |
| Varsling | ntfy push-varsler ved alle tilstandsendringer |
| CI/CD | GitHub Actions: pytest + Docker build på push/PR |

### git-crypt

Sensitive filer (`.env`, `config.yaml`) er kryptert i git med git-crypt.

```bash
# Låse opp (krever GPG-nøkkel):
gpg --import nøkkel.gpg
git-crypt unlock

# Sjekk status:
git-crypt status -e
```

## Komponenter

### Styringslogikk (kjernen)
- **Beslutningsmotor**: Når skal varmen på/av?
- **Prediktiv modell**: Start oppvarming *før* det blir glatt, basert på treghet i systemet
- **Moduser**: Auto (værbasert), manuell på/av, tidsplan

### Maskinvareintegrasjon (RPi)
- GPIO-styring av 3 relékanaler via RPi Relay Board (HAT)
- 5 temperatursensorer (tur/retur bakke, tur/retur VP, vanntank)
- Ekstern kontrollkabel til VP klemme 17/18 (potensialfri ON/OFF)

### Værdataintegrasjon
- **api.met.no** (Yr) — gratis, norsk, god dekning
- Henter: temperatur, nedbør, nedbørstype, vindforhold
- Predikerer isfare basert på kombinasjon av faktorer

## Teknisk stack

| Komponent | Valg | Begrunnelse |
|-----------|------|-------------|
| Språk | Python >=3.11 | Naturlig for RPi, GPIO, rask prototyping |
| Web-rammeverk | FastAPI + uvicorn | Asynkront, lett å kjøre på RPi |
| Værtjeneste | api.met.no | Gratis, norsk, godt dokumentert |
| HTTP-klient | httpx | Asynkron, moderne |
| Tempsensorer | DS18B20 (1-Wire) | Billig, vanntett variant finnes, enkel på RPi |
| Relé | RPi Relay Board (3-kanals HAT) | Sitter direkte på RPi, 3 uavhengige kanaler |
| Database | SQLite | Lokal logging uten ekstra infra |
| Scheduler | APScheduler | Periodisk værhenting |
| Prosesskjøring | Docker + Cloudflare Tunnel | Ingen åpne porter, tilgjengelig via geoloop.tommytv.no |
| CI/CD | GitHub Actions | pytest + Docker build ved push/PR |
| Hemmeligheter | git-crypt (GPG) | .env og config.yaml kryptert i repo |

## Utvikling (lokalt uten Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## Produksjonsdeploy

### Automatisk (anbefalt)

Se [Hurtigstart](#hurtigstart) — `setup-rpi.sh` gjør alt automatisk.

### Systemd-kommandoer

```bash
sudo systemctl start geoloop      # Start
sudo systemctl stop geoloop       # Stopp
sudo systemctl restart geoloop    # Restart (bygger image på nytt)
sudo systemctl status geoloop     # Status
journalctl -u geoloop -f          # Logger
```

### Oppdatering

```bash
cd /opt/geoloop
git pull
sudo systemctl restart geoloop
```

## Dokumentasjon

- [docs/oppsett-guide.md](docs/oppsett-guide.md) — Steg-for-steg maskinvareguide
- [docs/koblingsskjema.md](docs/koblingsskjema.md) — Detaljerte koblingsdiagrammer
- [TODO-avklaringer.md](TODO-avklaringer.md) — Systemspesifikasjon
