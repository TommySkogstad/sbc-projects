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

## Brukerflyt (automatisert SD-bundle)

Forutsetter Ubuntu/Debian-laptop. Bytt ut steg 0 hvis du har Etcher og DietPi-imagen allerede.

### Steg 0 — Installer prereqs (~2 min, første gang)

```bash
./spotify-spiller/flash.sh --install-deps
```

Installerer `balena-etcher` (via Cloudsmith apt-repo) + `xz-utils` + `curl`. Idempotent — hopper over pakker som allerede er på plass. Bruk `--yes` for å skippe bekreftelse på Cloudsmith-repoen.

### Steg 1 — Last ned og flash DietPi (~10 min)

```bash
./spotify-spiller/flash.sh --download
```

Skriver ut lenke + filnavn for Rock 3C-imagen. Pakk ut med `xz -d`, åpne Etcher og flash til microSD. La SD-kortet bli stående montert i laptopen etterpå (auto-mountes typisk som `/media/<bruker>/boot`).

### Steg 2 — Injiser config (~1 min)

Fra repo-root:

```bash
./spotify-spiller/flash.sh
```

Scriptet auto-detekterer det monterte SD-kortet. Alternativer:

```bash
# Oppgi mount-path eksplisitt
./spotify-spiller/flash.sh /media/bruker/boot

# Multirom: gi enheten et unikt navn
./spotify-spiller/flash.sh --name "Kjøkken"

# Forhåndsvisning uten å skrive noe
./spotify-spiller/flash.sh --dry-run
```

### Steg 3 — Boot (~5–10 min)

1. Eject SD-kortet trygt
2. Sett SD i Rock 3C
3. Koble til: strøm (USB-C 5V/3A) + ethernet + 3.5mm AUX
4. Vent 5–10 min — DietPi henter pakker og installerer raspotify automatisk

**"Rock" dukker opp i Spotify-appen.** Trykk på enhetsikon og velg enheten. Lyden kommer ut av AUX.

### Standardoppsett

| Parameter | Verdi |
|---|---|
| Hostname | `spotify-rock` |
| Spotify Connect-navn | `Rock` (overstyr med `--name <navn>`) |
| Nett | DHCP, kablet ethernet |
| Audio | ALSA, RK3566 onboard AUX |
| SSH-passord | `dietpi` — **bytt ved første innlogging!** |

### Etter boot — verifisering

```bash
# SSH inn
ssh root@spotify-rock.local

# Test lyd
speaker-test -c 2 -t wav

# Sjekk raspotify-status
systemctl status raspotify
```

### Feilsøking

**"Rock" dukker ikke opp i Spotify-appen:**
- Sjekk at enheten har fått DHCP-adresse i ruterens klientliste
- Verifiser raspotify er oppe: `ssh root@spotify-rock.local` → `systemctl status raspotify`
- Sjekk `/var/log/raspotify/current` for feilmeldinger

**Ingen lyd fra AUX:**
- Kjør `aplay -l` og verifiser at RK3566 onboard-kort er listet
- Test ALSA direkte: `speaker-test -c 2 -t wav -D default`
- Sjekk volum: `alsamixer`

**DAC-kvalitet:**
```bash
# Verifiser 24-bit/96 KHz
aplay -l
cat /proc/asound/card*/pcm*/sub*/hw_params
```

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

- 2026-05-14: SD-bundle implementert (`flash.sh` + DietPi-automasjon). Klar for hardware-test når Rock 3C ankommer.

<details>
<summary>Alternativ: manuelt oppsett (uten flash.sh)</summary>

### Fase 1 — Flash DietPi

1. Flash vanilla DietPi Bookworm for Rock 3C med Etcher
2. Mount SD, sett `dietpi.txt` manuelt (se `setup/dietpi.txt` for eksempel)

### Fase 2 — Førstegangsoppsett

```bash
ssh root@dietpi.local   # default passord: dietpi
```

1. Sett hostname: `dietpi-config` → Security → Hostname → `spotify-rock`
2. Velg lyd-driver: `dietpi-config` → Audio Options → ALSA + Onboard sound
3. Verifiser lyd: `speaker-test -c 2 -t wav`

### Fase 3 — Raspotify

```bash
dietpi-software install 39
```

### Fase 4 — Konfigurasjon

Rediger `/etc/raspotify/conf`:

```
LIBRESPOT_NAME="Rock"
LIBRESPOT_BITRATE="320"
LIBRESPOT_INITIAL_VOLUME="60"
LIBRESPOT_DEVICE_TYPE="speaker"
LIBRESPOT_BACKEND="alsa"
LIBRESPOT_DEVICE="default"
```

```bash
systemctl restart raspotify
```

</details>
