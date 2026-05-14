# Spotify-spiller

Lavterskel **Spotify Connect-mottaker** på Rock 3C. Plug-and-play via Spotify-appen — ingen ekstra app eller fjernkontroll. Innebygd 3.5mm AUX (24-bit/96 KHz) kobles direkte til høyttaler eller forsterker.

Senere: utvides til **synkronisert multirom** via Snapcast hvis flere noder er aktuelt.

## Stack

- **Rock 3C 1 GB** + microSD
- **DietPi Bookworm** (minimal Debian + software-katalog)
- **raspotify** (librespot) — Spotify Connect-endepunkt
- **ALSA** + innebygd RK3566 AUX

## Hvorfor DietPi over Armbian for denne?

DietPi har raspotify, Snapcast, Squeezelite, Shairport-sync m.fl. som ferdige software-valg i `dietpi-software` TUI. Installasjon = velg fra meny, ferdig. Armbian fungerer også, men krever litt mer manuell oppsett.

## Hardware

- Radxa Rock 3C 1 GB (499 kr)
- 3.5mm minijack-kabel (har, eller billig fra Kjell/Clas)
- microSD (har eller fra print-server-prototypen hvis dedikert)
- USB-C strømforsyning 5V/3A

**Totalt: ~499 kr per node**

## Build-plan

### Fase 1 — Flash DietPi (10 min)

1. Last ned [DietPi for Rock 3C](https://dietpi.com/downloads/images/) (eller bruk Armbian + manuell raspotify hvis foretrukket)
2. Flash til microSD med Etcher
3. Mount SD, rediger `dietpi-wifi.txt` og `dietpi.txt` (WiFi-config + automatisk førstegangsoppsett)
4. Sett SD i Rock 3C, koble strøm + AUX-kabel

### Fase 2 — Førstegangsoppsett (15 min)

1. SSH inn: `ssh root@dietpi.local` (default passord: `dietpi`, byttes ved første boot)
2. Sett hostname: `dietpi-config` → Security → Hostname → `spotify-stua` (eller annet)
3. Velg lyd-driver: `dietpi-config` → Audio Options → ALSA + `Onboard sound`
4. Verifiser lyd: `speaker-test -c 2 -t wav`

### Fase 3 — Raspotify (5 min)

```bash
dietpi-software install 39   # Raspotify
```

Eller manuelt:
```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

### Fase 4 — Konfigurasjon

Rediger `/etc/raspotify/conf`:

```
LIBRESPOT_NAME="Stua"
LIBRESPOT_BITRATE="320"
LIBRESPOT_INITIAL_VOLUME="60"
LIBRESPOT_DEVICE_TYPE="speaker"
LIBRESPOT_BACKEND="alsa"
LIBRESPOT_DEVICE="default"
```

Restart: `systemctl restart raspotify`

### Fase 5 — Test

Åpne Spotify-app på telefon → trykk på enhetsikon → velg "Stua". Lyden skal komme ut av AUX-porten.

## Multirom-utvidelse (Snapcast)

Hvis du senere kjøper flere Rock 3C-er for flere rom:

```
[Rock 3C #1: Stua]   ──> librespot ──> Snapcast server ──┐
                                                          │
                                            ┌─────────────┤
                                            ↓             ↓
                                  [Rock 3C #2: Kjøkken]  [Rock 3C #3: Bad]
                                  Snapcast client        Snapcast client
```

**Server-node:**
```bash
dietpi-software install 124   # Snapcast Server
dietpi-software install 39    # Raspotify (konfigurert til å pipe til Snapcast FIFO)
```

I `/etc/raspotify/conf`:
```
LIBRESPOT_BACKEND="pipe"
LIBRESPOT_DEVICE="/tmp/snapfifo"
```

**Klient-noder:**
```bash
dietpi-software install 125   # Snapcast Client
```

Klient peker mot server-IP. ±1 ms drift mellom rom, kontrollerbar fra Snapweb eller Home Assistant Snapcast-integrasjon.

## Alternative streamere (samme oppskrift)

DietPi-katalogen har også:

- **Shairport-sync** — AirPlay 2-mottaker (parallelt med raspotify, samme node)
- **Squeezelite** — Logitech Media Server-klient
- **Mopidy** — multi-source streamer (Spotify, Tidal, lokal MP3, YouTube)
- **MPD** — klassisk Music Player Daemon
- **Roon Bridge** — hvis du har Roon Core

Alle kan kjøre side-om-side på samme Rock 3C så lenge volum og prioritet håndteres.

## Hva vi IKKE bygger først

- Touch-skjerm-frontend
- Stemmestyring
- Egen mobilapp (Spotify Connect dekker dette)
- Multirom (gjøres når flere noder er aktuelt)

## Status

- 2026-05-14: Planlagt. Venter på Rock 3C-bestilling fra Kjell sammen med print-server-hardware.
