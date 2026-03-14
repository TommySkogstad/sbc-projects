# GeoLoop — Oppsettguide

Steg-for-steg-guide for å sette opp Raspberry Pi 3B+ med DS18B20-sensorer, RPi Relay Board og GeoLoop-programvaren via Docker.

> **Hurtigoppsett:** Foretrekker du automatisk installasjon? Kjør `sudo bash scripts/setup-rpi.sh` — det gjør steg 1.3, 1.4, del 4 og del 5 automatisk. Du trenger fortsatt å gjøre maskinvarekoblingen (del 2–3) og sensor-ID-konfigurasjonen manuelt.

Se [koblingsskjema.md](koblingsskjema.md) for detaljerte koblingsdiagrammer.

---

## Maskinvareoversikt

| # | Komponent | Modell | Merknad |
|---|-----------|--------|---------|
| 1 | Raspberry Pi 3B+ | BCM2837B0, 1 GB RAM | Styringsenhet |
| 2 | RPi Relay Board | 3 kanaler (HAT-format) | Sitter direkte på GPIO-header |
| 3 | Open-Smart GPIO Expansion Board | — | Gir tilgang til GPIO4 under relay board-HAT |
| 4 | Micro-SD-kort (32 GB+) | SanDisk Extreme anbefalt | OS og programvare |
| 5 | USB Micro-B strømforsyning (5V/2.5A) | Offisiell RPi 3B+ PSU | Strøm til RPi |
| 6 | DS18B20 temperatursensorer (vanntett) | Rørfølere, 5 stk | T1–T5 |
| 7 | 4,7 kΩ motstand | For 1-Wire pull-up | 1 stk |
| 8 | Ethernet-kabel | Cat5e/Cat6 | Anbefalt fremfor WiFi |

---

## Del 1: Raspberry Pi — grunnoppsett

### 1.1 Installer operativsystem

1. Last ned [Raspberry Pi Imager](https://www.raspberrypi.com/software/) på din PC/Mac
2. Sett inn micro-SD-kortet
3. I Imager:
   - Enhet: **Raspberry Pi 3**
   - OS: **Raspberry Pi OS Lite (64-bit)** — ingen desktop nødvendig
   - Klikk tannhjulet → konfigurer:
     - Brukernavn og passord (noter disse!)
     - WiFi hvis du ikke bruker Ethernet
     - Aktiver SSH
     - Tidssone: `Europe/Oslo`
4. Skriv til SD-kortet

### 1.2 Første oppstart

1. Sett SD-kortet i RPi
2. Koble til Ethernet og strøm
3. Vent ca. 60 sekunder til RPi starter opp
4. Finn IP-adressen:
   ```bash
   ping raspberrypi.local
   # Eller sjekk ruterens DHCP-liste
   ```
5. SSH inn:
   ```bash
   ssh brukernavn@raspberrypi.local
   ```

### 1.3 Oppdater systemet

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl
```

### 1.4 Aktiver 1-Wire for DS18B20-sensorer

```bash
sudo nano /boot/firmware/config.txt
```

Legg til nederst:
```
dtoverlay=w1-gpio,gpiopin=4
```

Start på nytt:
```bash
sudo reboot
```

---

## Del 2: Koble til DS18B20-sensorer

> Se [koblingsskjema.md](koblingsskjema.md) for detaljert diagram.

Alle 5 sensorer kobles **parallelt** på GPIO4 via Open-Smart GPIO Expansion Board:

- **Rød** → 3.3V
- **Svart** → GND
- **Gul** → GPIO4 (+ én 4,7 kΩ pull-up motstand til 3.3V)

### 2.1 Verifiser at sensorene er oppdaget

```bash
# Last 1-Wire-moduler (gjøres automatisk etter reboot med dtoverlay)
sudo modprobe w1-gpio
sudo modprobe w1-therm

# Skal vise én mappe per sensor, f.eks. 28-01234567890a
ls /sys/bus/w1/devices/
```

Forventet output:
```
28-01234567890a  28-01234567890b  28-01234567890c  28-01234567890d  28-01234567890e  w1_bus_master1
```

Ikke 5 sensorer? Sjekk:
- Kabling (spesielt pull-up motstanden)
- At `dtoverlay=w1-gpio,gpiopin=4` er i `/boot/firmware/config.txt`
- At RPi er rebooted etter endringen

### 2.2 Les temperatur og noter sensor-IDer

```bash
for f in /sys/bus/w1/devices/28-*/w1_slave; do
    id=$(echo $f | grep -oP '28-[a-f0-9]+')
    temp=$(grep -oP 't=\K[0-9]+' $f)
    echo "$id  →  $(echo "scale=3; $temp/1000" | bc) °C"
done
```

**Skriv ned hvilken sensor-ID som tilhører hvilken plassering** (T1–T5). Gjør dette ved å holde en sensor i hånden (varmere) og se hvilken ID som skiller seg ut.

---

## Del 3: Koble til RPi Relay Board

> Se [koblingsskjema.md](koblingsskjema.md) for detaljert diagram.

Relay board-et sitter som HAT direkte på RPi GPIO-headeren. GeoLoop bruker:

| Kanal | BCM GPIO | Funksjon              |
|-------|----------|-----------------------|
| K1    | GPIO 26  | Varmepumpe (klemme 17/18) |
| K2    | GPIO 20  | Sirkulasjonspumpe     |
| K3    | GPIO 21  | Ledig (reserve)       |

### 3.1 Koble relé K1 til varmepumpe

1. Slå av VP på strømbryteren
2. Åpne VP-dekselet (se servicemanual)
3. Finn klemme 17 og 18 — **fjern fabrikkjumperen** mellom dem
4. Koble to ledere: klemme 17 → NO, klemme 18 → COM på K1
5. Lukk dekselet og slå på igjen

### 3.2 Test reléene manuelt

```bash
# Installer GPIO-verktøy
sudo apt install -y python3-gpiozero

python3 - <<'EOF'
from gpiozero import OutputDevice
import time

k1 = OutputDevice(26)   # Varmepumpe
k2 = OutputDevice(20)   # Sirkulasjonspumpe

print("K1 PÅ (VP) — hør et klikk")
k1.on(); time.sleep(2)
print("K1 AV")
k1.off(); time.sleep(1)

print("K2 PÅ (Pumpe)")
k2.on(); time.sleep(2)
print("K2 AV")
k2.off()
EOF
```

Du skal høre et klikk fra hvert relé. VP skal starte når K1 er PÅ (forutsatt at fabrikkjumperen er fjernet).

---

## Del 4: Installer Docker

```bash
# Installer Docker
curl -fsSL https://get.docker.com | sh

# Legg til brukeren i docker-gruppen
sudo usermod -aG docker $USER

# Logg ut og inn igjen for at gruppeendringen skal gjelde
exit
```

SSH inn igjen, og verifiser:
```bash
docker --version
docker compose version
```

---

## Del 5: Sett opp GeoLoop

### 5.1 Klon prosjektet og lås opp hemmeligheter

```bash
cd ~
git clone https://github.com/TommySkogstad/GeoLoop
cd GeoLoop

# Lås opp krypterte filer (krever GPG-nøkkel)
# Kopier nøkkelen fra en maskin som har den:
#   gpg --export-secret-keys CA1E41D13067550891949E067F35459C441CBC8B > /tmp/geoloop.gpg
#   scp /tmp/geoloop.gpg pi@<rpi-ip>:/tmp/
gpg --import /tmp/geoloop.gpg
sudo apt install -y git-crypt
git-crypt unlock

# Verifiser at .env og config.yaml er dekryptert (lesbar tekst)
cat .env
```

### 5.2 Cloudflare Tunnel (for ekstern tilgang)

1. Gå til [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → **Networks → Tunnels → Create a tunnel**
2. Navn: `geoloop`, type: Docker
3. Under **Public Hostnames**: legg til `geoloop.tommytv.no` → `http://geoloop:8000`
4. Kopier tunnel-tokenet

```bash
cp .env.example .env
nano .env
```

Rediger `.env` med ditt Cloudflare Tunnel-token. Filen er allerede dekryptert fra git-crypt i steg 5.1.

```bash
# .env inneholder:
# CLOUDFLARE_TUNNEL_TOKEN=...   (Cloudflare Tunnel-token)
# GEOLOOP_PASSWORD=...          (passord for web-grensesnittet)
# NTFY_URL=...                  (ntfy-server for push-varsler)
# NTFY_TOPIC=...                (ntfy-topic)
```

> **GEOLOOP_PASSWORD** er valgfritt. Hvis det er satt, kreves passord for å åpne dashboardet. Innlogging er rate-begrenset (5 forsøk per 5 min) og beskyttet med CSRF-token.

### 5.3 Konfigurer GeoLoop

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Fyll inn:

```yaml
location:
  lat: 59.2732    # Din breddegrad (hent fra norgeskart.no)
  lon: 10.4810    # Din lengdegrad

database:
  path: "/app/data/geoloop.db"   # Bruk denne stien i Docker

sensors:
  loop_inlet:
    id: "28-SENSOR_ID_HER"       # T1 — sensor-ID fra steg 2.2
  loop_outlet:
    id: "28-SENSOR_ID_HER"       # T2
  hp_inlet:
    id: "28-SENSOR_ID_HER"       # T3
  hp_outlet:
    id: "28-SENSOR_ID_HER"       # T4
  tank:
    id: "28-SENSOR_ID_HER"       # T5

relays:
  heat_pump:
    gpio_pin: 26
    active_high: true
  circulation_pump:
    gpio_pin: 20
    active_high: true
  spare:
    gpio_pin: 21
    active_high: true
```

> **Finn koordinater:** Gå til [norgeskart.no](https://norgeskart.no), høyreklikk på din lokasjon → kopier koordinater.

### 5.4 Start GeoLoop

```bash
docker compose up -d --build
```

Sjekk at begge containere er oppe:
```bash
docker compose ps
```

Forventet:
```
NAME                    STATUS
geoloop-geoloop-1       Up (healthy)
geoloop-cloudflared-1   Up
```

---

## Del 6: Verifiser at alt fungerer

```bash
# Sjekk logger
docker compose logs geoloop --tail 30

# Test API lokalt
curl http://localhost:8000/api/status

# Test via Cloudflare Tunnel (fra PC eller mobil)
curl https://geoloop.tommytv.no/api/status
```

Forventet output fra `/api/status`:
```json
{
  "heating": { "on": false },
  "weather": { "air_temperature": 3.2, ... },
  "sensors": {
    "loop_inlet": 0.5,
    "loop_outlet": 4.2,
    ...
  }
}
```

Hvis sensor-verdier viser `null`, sjekk at sensor-ID-ene i `config.yaml` stemmer med det som ligger i `/sys/bus/w1/devices/`.

---

## Del 7: Automatisk oppstart

### Alternativ A: systemd-tjeneste (anbefalt)

Hvis du brukte `setup-rpi.sh`, er systemd-tjenesten allerede installert:

```bash
sudo systemctl start geoloop      # Start
sudo systemctl stop geoloop       # Stopp
sudo systemctl restart geoloop    # Restart (bygger image på nytt)
sudo systemctl status geoloop     # Status
journalctl -u geoloop -f          # Logger
```

### Alternativ B: Docker restart-policy

Docker starter containere automatisk ved oppstart av RPi så lenge `restart: unless-stopped` er satt i `docker-compose.yml` (allerede konfigurert).

```bash
sudo systemctl enable docker
sudo systemctl status docker
```

### Oppdatering

```bash
cd /opt/geoloop   # eller ~/GeoLoop
git pull
sudo systemctl restart geoloop
# Eller: docker compose up -d --build
```

---

## Feilsøking

| Problem | Løsning |
|---------|---------|
| Sensor vises ikke i `/sys/bus/w1/devices/` | Sjekk kabling og pull-up motstand. Sjekk at `dtoverlay=w1-gpio,gpiopin=4` er i `config.txt`. Reboot. |
| Sensor-verdi er `null` i API | Sensor-ID i `config.yaml` stemmer ikke — kjør `ls /sys/bus/w1/devices/` og oppdater config. |
| Relé klikker ikke | Sjekk GPIO-pinne mot databladet for ditt relay board. Kjør manuell test fra steg 3.2. |
| VP starter ikke når relé lukker | Sjekk at fabrikkjumperen mellom klemme 17/18 er fjernet. |
| Cloudflare Tunnel kobler ikke til | Sjekk token i `.env`. Logg inn på Cloudflare Zero Trust og verifiser at tunnelen er aktiv. |
| `docker compose up` feiler | Kjør `docker compose logs` for feilmelding. Sjekk at `config.yaml` er gyldig YAML. |
| Dashboardet viser ikke graf | Tøm nettleser-cache (Ctrl+Shift+R). Historikk bygges opp gradvis fra første syklus (10 min). |

---

## Systemdiagram

```
     VP-krets                                  Bakkesløyfe-krets

┌─────────────────┐                     ┌─────────────────────────┐
│   Varmepumpe    │                     │   Bakkeløyfe            │
│  WH-MXC12G6E5  │                     │   8 sløyfer, 900 m      │
└──┬──────────▲───┘                     └──┬──────────────▲───────┘
   │          │                            │              │
  T4(ut)      │                        T1(inn)         T2(ut)
   │     ┌────┴────────┐                  │              │
   │     │ Kolbetank   │                  │              │
   │     │ 10 L        │                  │              │
   │     │ 10 kW kolber│                  │              │
   │     └────▲────────┘                  │              │
   │          │                           │              │
   │       T3(inn)                        │              │
   │          │                           │              │
   ▼          │                           ▼              │
┌─────────────┴───────────────────────────┴──────────────┴──────┐
│                    Buffertank 200 L (T5)                        │
└────────────────────────────────────────────────────────────────┘

Relé K1 (GPIO26) ──── VP klemme 17/18 (ON/OFF)
Relé K2 (GPIO20) ──── Ekstern sirkulasjonspumpe
Relé K3 (GPIO21) ──── Ledig (kolber i fremtiden)
```

**Totalt vannvolum: ~421 liter** (181 L sløyfe + 200 L buffer + 10 L kolbetank + ~30 L internrør)

---

## Referansedokumentasjon

- [koblingsskjema.md](koblingsskjema.md) — Detaljerte koblingsdiagrammer
- [docs/SM-WHMXC09G3E5_WH-MXC12G6E5.pdf](SM-WHMXC09G3E5_WH-MXC12G6E5.pdf) — Servicemanual for Panasonic WH-MXC12G6E5
- [docs/CZ-TAW1-OI-1.pdf](CZ-TAW1-OI-1.pdf) — Panasonic CZ-TAW1 nettverksadapter (ikke kompatibel med G-gen)
