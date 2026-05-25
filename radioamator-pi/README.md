# Radioamatør-pi

Companion-Pi til eksisterende radioamatørrigg. Kjører digitalmodes (FT8/FT4/JS8Call), software-TNC (Direwolf for APRS/packet), CAT-kontroll (Hamlib/rigctld), Winlink (Pat) og logging (CQRLOG) parallelt med transceiveren. Henger på USB-en til riggen og frigjør arbeidsmaskinen — kan stå 24/7 som WSPR/FT8-mottaker, APRS i-gate eller Winlink-RMS-relay uten å blokkere shacken.

Primær use-case: koble Pi-en til en moderne HF-rigg via én USB-kabel (CAT + audio i samme), så slipper du å dedikere PC-en. Sekundært: stand-alone APRS-igate på 2 m med en billig håndholdt + USB-lyd.

## Stack

- **Raspberry Pi 4 4 GB** (Pi 5 fungerer også, men trekker mer) + microSD Endurance 32 GB
- **Raspberry Pi OS Bookworm 64-bit Lite** (headless, X11/VNC ved behov)
- **Hamlib + rigctld** — CAT-kontroll mot rigg, delt sokkel for alle apper
- **WSJT-X** — FT8/FT4/JT65/MSK144/WSPR
- **JS8Call** — keyboard-to-keyboard HF-QSO (lavpunkts-DX, message-store-and-forward)
- **Fldigi + Flrig + Flmsg + Flarq** — PSK31/RTTY/Olivia/MFSK + emcomm-skjemaer
- **Direwolf** — software-TNC for APRS, AX.25-packet, KISS-server
- **Pat (Winlink)** — radio-email over VARA HF / ARDOP / packet
- **CQRLOG** — logger med LotW/eQSL/QRZ.com/Clublog-sync
- **GridTracker** — FT8/FT4-grid-kart, awards-tracking
- **chrony** — millisekund-tidssync (FT8 krever < 1 s slot-presisjon)
- **gpsd** (valgfritt) — GPS som chrony-refclock når internett ikke er tilgjengelig
- **Avahi** — `ham-pi.local` på nett
- **NoMachine / TigerVNC / x11vnc** — grafisk fjernpålogging (WSJT-X + Fldigi har GUI)
- **flash.sh** — laptop-side provisioning (WiFi, SSH, hostname, callsign)

## Hardware

### Pi-side
- Raspberry Pi 4 4 GB (Pi 5 hvis du har)
- microSD 32 GB Endurance (Sandisk High Endurance / Samsung PRO Endurance — 24/7-bruk)
- USB-C PSU 5 V / 3 A (Pi 4) eller 5 V / 5 A (Pi 5)
- Passivt kabinett med heatsink — WSJT-X-dekoding gir jevn CPU-belastning
- Ferrittklemmer på USB- og strømkabel (RFI-suppresjon — Pi støyer på HF)

### Rigg-side (avhengig av rigg)

| Riggtype | Tilkobling | Ekstra hardware |
|---|---|---|
| Moderne HF med USB (IC-7300, IC-705, FT-991A/AX, FTDX10, TS-590SG, IC-7610) | Én USB-kabel — CAT + audio + PTT alt på samme | Ingen (innebygd USB-CODEC) |
| Xiegu G90/X6100, Yaesu FT-818 | USB-CAT + ekstern audio | Digirig Mini eller SignaLink USB |
| Eldre HF (IC-7000, FT-857/897, TS-2000) | Separat CAT + audio | SignaLink USB **eller** Digirig Mobile (anbefalt — slipper VOX) |
| 2 m/70 cm håndholdt (FT-65, UV-5R, ID-31) for APRS | TRRS-audio + VOX, eller Mobilinkd | Mobilinkd TNC3 (BT) eller Digirig Mobile |
| Allmode med DATA-port (FT-991A, IC-7100) | DATA-jack + USB-CAT | Eventuelt isolasjons-trafo for hum |

> **Anbefaling for nyanskaffelse**: Digirig Mini (~85 USD) — galvanisk isolasjon, CM108-CODEC + CP2102-CAT i samme dongle, bedre RFI-egenskaper enn SignaLink. SignaLink USB fungerer fint og er "the classic", men har VOX-PTT som er mindre presist enn ekte CAT-PTT.

### Antenne
Bruker eksisterende antenne via riggen — Pi har ingen RF-eksponering selv. RFI fra Pi inn i antennen avhjelpes med ferritter på USB-kabelen og kabinett-skjerming.

### Valgfritt
- **GPS-modul** (u-blox NEO-7M/NEO-M8 USB) — chrony-refclock når internett er ute. Kun nødvendig for portabel drift eller emcomm.
- **HiFiBerry DAC+ ADC** — kun hvis du vil bruke Pi-en som rendyrket SDR-mottaker uten å gå via riggen. Vanlig digital-mode-bruk trenger ikke dette.
- **Lite passivt LCD** for status — geoloop-style. Lavprio.

## Bruksområder

| Modus | Apper | Bruksmønster |
|---|---|---|
| FT8 / FT4 daglig | WSJT-X + GridTracker + CQRLOG | Pi står på, du kobler til via VNC når du vil kjøre QSO |
| WSPR-bake / -mottaker 24/7 | WSJT-X i WSPR-modus | Helautomatisk — Pi sender korte WSPR-pakker og/eller dekoder mottak til pskreporter.info |
| APRS i-gate | Direwolf + en RX-only håndholdt | Pi rapporterer mottatte APRS-pakker til APRS-IS over internett |
| APRS digipeater | Direwolf + TX-kapabel rigg | RF-til-RF-relay (krever lisens-vurdering) |
| JS8Call lav-effekt HF-chat | JS8Call + JS8Spotter | Keyboard-QSO med store distanser på lav effekt |
| Winlink emcomm-email | Pat + VARA HF (Wine) eller ARDOP | Radio-email mot CMS-server, fungerer uten internett |
| Fldigi PSK31/RTTY | Fldigi + Flrig | Klassiske digital-modes, lavpunkts |
| Remote rig fra mobil | rigctld + lett web-UI | Stem og dekode fra telefonen via VNC eller egen web-frontend |
| Logging-hub | CQRLOG eller Cloudlog | Sentral logg som alle apper skriver til via UDP/ADIF |

## Domene-strategi

- **Default**: kun mDNS på lokalt nett (`ham-pi.local`). Ingen ekstern eksponering.
- **Per-instans opt-in**: hvis du vil nå Pi-en utenfra (f.eks. fra hytta), opprett Cloudflare-tunnel under `tommytv.no`-zone og legg Cloudflare Access foran (`ham.tommytv.no`).
- **Aldri** eksponer rigctld eller VNC direkte på internett — alltid bak Access eller WireGuard.

## Build-plan

### Fase 1 — Forberedelse (5 min)

1. Last ned Raspberry Pi OS Bookworm 64-bit Lite fra https://www.raspberrypi.com/software/operating-systems/
2. Bestem callsign + grid-locator (Maidenhead 6-tegns, f.eks. `JO59ix`)
3. Forbered SSH-nøkkel hvis du ikke har en: `ssh-keygen -t ed25519`

### Fase 2 — Flash og laptop-side provisioning (10 min)

1. Flash med `rpi-imager` (anbefalt) eller `dd`:
   ```bash
   xz -d 2026-*-raspios-bookworm-arm64-lite.img.xz
   sudo dd if=2026-*-raspios-bookworm-arm64-lite.img bs=4M status=progress oflag=sync of=/dev/sdX
   ```
2. I `rpi-imager` "advanced options": sett hostname `ham-pi`, SSH-nøkkel, WiFi-SSID/passord, lokalitet
3. Kopier `setup/ham_first_run.txt.example` til `setup/ham_first_run.txt`, fyll ut callsign + grid
4. Mount SD-en, kjør:
   ```bash
   sudo ./flash.sh --callsign LA1XYZ --grid JO59ix --name "shack"
   ```
   Med `--dry-run` for forhåndsvisning. Setter hostname `ham-pi-<navn>`, kopierer first-boot-skript og enabler `first-boot.service`.
5. Sett SD i Pi-en, koble til strøm + nett

### Fase 3 — Første boot og pakke-install (auto, 15–25 min)

`first-boot.service` kjører som root og:

- Setter hostname og tidssone (Europe/Oslo)
- Aktiverer SSH og UFW (kun 22, 5900-VNC, 6010-Pat fra lokalt nett)
- Installerer pakker fra apt:
  - `hamlib-utils`, `libhamlib-utils`, `libhamlib4` — CAT-stack
  - `wsjtx`, `js8call`, `fldigi`, `flrig`, `flmsg`, `flarq`
  - `direwolf`, `ax25-tools`, `ax25-apps`
  - `chrony`, `gpsd`, `gpsd-clients`
  - `cqrlog` (eller Cloudlog via egen PHP/MariaDB-stack)
  - `tigervnc-standalone-server`, `xfce4` (lett desktop til VNC-bruk)
  - `python3-pip`, `git`, `screen`, `tmux`
- Installerer Pat Winlink fra siste GitHub-release (.deb, arm64)
- Installerer GridTracker AppImage (eller eldre .deb-bygg hvis arm64 ikke har AppImage)
- Skriver standardkonfig:
  - `/etc/chrony/chrony.conf` — Pool NTP + valgfri GPS-refclock
  - `~/.wsjtx/WSJT-X.ini` — callsign, grid, rigctld-link
  - `~/.fldigi/fldigi_def.xml` — callsign, grid, flrig-link
  - `/etc/direwolf.conf` — callsign, APRS-IS-passcode hvis i-gate
  - `~/.config/Hamlib/rigctld.conf` — riggmodell og device
- Setter udev-regler for stabilt audio-/serial-navn:
  - `/dev/ham-rig-cat` → CAT-USB
  - `/dev/ham-rig-audio` → USB-CODEC (sjekkes via `cat /proc/asound/cards`)
- Starter og enabler systemd-units (rigctld, direwolf-kiss, pat-listen, chrony, ssh, vncserver@1)

Sjekk fremdrift:
```bash
ssh pi@ham-pi-<navn>.local
tail -f /var/log/first-boot.log
```

### Fase 4 — Rigg-deteksjon og CAT-test (5 min)

1. Koble riggen via USB. udev-regelen bør gi `/dev/ham-rig-cat` (sjekk med `ls -l /dev/ham-rig-*`)
2. Identifiser Hamlib-rig-ID: `rigctl --list | grep -i <rigg-navn>`
3. Sett rig-ID i `/etc/default/rigctld` (f.eks. `MODEL=3073` for IC-7300)
4. Start rigctld: `systemctl restart rigctld`
5. Test fra Pi:
   ```bash
   rigctl -m 2 -r localhost:4532 f       # les frekvens
   rigctl -m 2 -r localhost:4532 m       # les modus
   ```
6. Test PTT (kort, dummy-load eller dempet antenne anbefales):
   ```bash
   rigctl -m 2 -r localhost:4532 T 1     # PTT on
   sleep 1
   rigctl -m 2 -r localhost:4532 T 0     # PTT off
   ```

### Fase 5 — Audio-konfigurasjon (5 min)

1. List soundcards: `cat /proc/asound/cards`
2. Riggens CODEC er typisk `USB Audio CODEC` — noter card-nummer
3. Sett som default i `~/.asoundrc`:
   ```
   defaults.pcm.card N
   defaults.ctl.card N
   ```
4. Verifiser opptak: `arecord -D plughw:N,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav`
5. Sett input-nivå med `alsamixer` (F6 → velg rigg-CODEC) — sikt på –6 til –12 dBFS i WSJT-X waterfall

### Fase 6 — WSJT-X / Fldigi / JS8Call (10 min)

1. Start `tigervncserver -localhost no :1` (eller koble via NoMachine)
2. Koble fra Mac/PC: `ssh -L 5901:localhost:5901 pi@ham-pi-<navn>.local`, åpne VNC mot `localhost:5901`
3. Åpne WSJT-X:
   - **Settings → General**: callsign + grid (settes av first-boot, verifiser)
   - **Settings → Radio**: Rig = "Hamlib NET rigctl", Network Server = `localhost:4532`, PTT = "CAT"
   - **Settings → Audio**: Input/Output = rigg-USB-CODEC
   - Klikk **Test CAT** og **Test PTT**
4. Samme oppskrift for JS8Call og Fldigi (peker mot samme rigctld)
5. Verifiser dekoding med åpen båndaktivitet (20 m FT8 er alltid liv)

### Fase 7 — Direwolf APRS (10 min, valgfritt)

1. Rediger `/etc/direwolf.conf`:
   ```
   MYCALL LA1XYZ-10
   IGSERVER euro.aprs2.net
   IGLOGIN LA1XYZ 12345     # passcode fra http://apps.magicbug.co.uk/passcode/
   PBEACON sendto=IG delay=0:30 every=10 lat=59^00.00N long=10^00.00E symbol=igate comment="Pi i-gate"
   ```
2. Start: `systemctl restart direwolf`
3. Sjekk på https://aprs.fi at `LA1XYZ-10` dukker opp

### Fase 8 — Pat Winlink (10 min, valgfritt)

1. Konfigurer: `pat configure` (åpner editor på `~/.config/pat/config.json`)
2. Sett callsign, secure login password (fra Winlink-konto), locator
3. Test ARDOP eller VARA HF (VARA krever Wine + Windows-binær — egen guide)
4. Start web-UI: `pat http` — `http://ham-pi-<navn>.local:8080`

### Fase 9 — Tidssync-verifisering

FT8 krever ±1 s. Med standard NTP + chrony bør du ligge < 50 ms:
```bash
chronyc tracking
chronyc sources -v
```
Hvis offset > 200 ms: legg til GPS-refclock (se valgfri seksjon).

### Fase 10 — Logging (CQRLOG eller Cloudlog)

- **CQRLOG**: native arm64-pakke i Bookworm-repo, lokal MariaDB. Bra for single-op.
- **Cloudlog**: PHP/MariaDB web-app — kjør på NUC i stedet (egen Docker-compose), Pi sender ADIF over UDP.
- WSJT-X / JS8Call / Fldigi konfigureres til å sende ADIF til loggen ved hver QSO.

## Tidssync — GPS-refclock (valgfri)

For portabel eller off-grid bruk uten internett:

1. Koble u-blox NEO-M8 USB
2. Verifiser: `gpsd -N -D 3 /dev/ttyUSB0` viser fix
3. Aktiver i `/etc/chrony/chrony.conf`:
   ```
   refclock SHM 0 refid GPS precision 1e-1 offset 0.0 delay 0.2
   refclock SOCK /var/run/chrony.ttyUSB0.sock refid PPS precision 1e-7
   ```
4. `systemctl restart chrony gpsd`
5. `chronyc sources -v` — GPS bør stå som primær når Internet-NTP er borte

## RFI / støy-håndtering

Pi-er støyer bredbåndet på HF. Tiltak (i prioritert rekkefølge):

1. **Ferrittklemmer** (Würth 742 711 32 / FT240-43) rundt USB-kabel mellom Pi og rigg, strømkabel og ethernet — typisk –10 til –20 dB i støy
2. **Skjermet kabinett** (ikke det vanlige akrylkabinettet) — Argon NEO eller Flirc-style med aluminium
3. **Lineær PSU** i stedet for switching-PSU — dyrere, men kutter switching-spikes
4. **Fysisk avstand** ≥ 1 m mellom Pi og rigg / antennetuner / coax
5. **Felles jord** mellom Pi-PSU og rigg-PSU
6. Hvis 10 m / 6 m fortsatt er ødelagt: prøv Pi 4 i stedet for Pi 5 (Pi 5 er målt med mer RFI)

## Sikkerhet og lisens

- **Sendelisens kreves** for all transmisjon. Pi-en kan motta lovlig uten lisens (SDR / WSPR-RX / FT8-RX), men APRS-digipeater, Winlink-TX, FT8-TX, JS8-TX og enhver annen TX krever gyldig amatørradiolisens og oppsett av riktig callsign.
- For RX-only / i-gate-only deployment: sett `PTT=NONE` i WSJT-X og kommenter ut TX-config i Direwolf for å hindre utilsiktet transmisjon.
- VNC-passord MÅ settes (`vncpasswd`). Eksponer aldri VNC eller rigctld utenfor LAN uten Cloudflare Access eller WireGuard foran.
- `pat http` kjører uten auth som default — bruk SSH-tunnel eller bind til `127.0.0.1` ved ekstern bruk.

## Feilsøking

### WSJT-X dekoder ikke noe

```bash
# Sjekk audio-nivå (skal ligge på –6 til –12 dBFS i WSJT-X waterfall)
alsamixer

# Sjekk tidssync (må være < 1 s)
chronyc tracking

# Sjekk båndaktivitet — er det faktisk noen som sender på 14.074?
# 20 m FT8 er alltid liv på dagtid
```

### "Hamlib error: IO error" når WSJT-X starter

CAT-portsmidlet er feil. Sjekk:
```bash
ls -l /dev/ham-rig-cat              # udev-regel feilet hvis denne mangler
ls -l /dev/ttyUSB* /dev/ttyACM*     # finn ekte device-navn
rigctl -m <id> -r /dev/ttyUSB0 f    # test direkte
```
Hvis udev-regelen ikke matcher: rediger `/etc/udev/rules.d/99-ham-rig.rules` med riktig idVendor/idProduct fra `lsusb`.

### Riggen sender ikke når WSJT-X prøver TX

PTT-config-mismatch. Tre vanlige fail-modes:
1. PTT satt til "VOX" men VOX er av på riggen → sett PTT til "CAT" i WSJT-X
2. PTT satt til "CAT" men riggens USB-kabel-modus er konfigurert som "RTS/DTR" → enten endre i riggens meny (oftest "USB SEND") eller bytt til "RTS"/"DTR" i WSJT-X PTT-config
3. Riggens "USB SEND" peker mot feil port (vanlig på IC-7300: må stå på "USB" ikke "DATA OFF")

### APRS i-gate sender ingen pakker til APRS-IS

```bash
journalctl -u direwolf -f          # se direwolf-logs
```
Vanlige feil: feil passcode, manglende `IGLOGIN`-linje, eller `IGSERVER` blokkert av brannmur.

### Pat Winlink: "no connection" mot CMS

Sjekk at internett er oppe (`pat connect telnet:` skal funke) før du klandrer radio-pipelinen.

## Hva vi IKKE bygger (først)

- SDR-mottaker-stack (RTL-SDR, OpenWebRX) — egen Pi / egen mappe hvis det blir aktuelt
- Egen DMR/D-STAR/YSF-hotspot (Pi-Star/WPSD) — bruk Pi-Star sitt eget image, ikke gjenoppfinn det
- Allstarlink/Echolink-node — Apper kan installeres parallelt, men eget repo hvis det blir hovedformål
- Repeater-kontroll (SVXLink) — krever dedikert rigg + lisens-vurdering
- Egen mobilapp — VNC + Pat web-UI dekker fjernbruk

## Låste beslutninger (ikke gjenåpne)

- Pi 4 4 GB som baseline — Pi 5 ok men bråker mer på HF; Pi Zero 2W for svak til WSJT-X-dekoding
- Raspberry Pi OS, ikke DietPi — hamradio-pakkene er bedre testet på offisiell distro
- microSD Endurance — ikke vurder NVMe-HAT med mindre du har spesifikt I/O-problem (du har ikke)
- Bookworm 64-bit — 32-bit har eldre Hamlib-versjoner
- Headless + VNC for GUI-apper — sparer skjerm/tastatur, fungerer fint over LAN
- USB-tilkobling til rigg (ikke serielle nivåskiftere) — moderne riggene har dette innebygd; Digirig for de uten

## Avklaringer før implementasjon

- Hvilken rigg skal Pi-en koble til? (avgjør Hamlib rig-ID, USB-VID/PID for udev-regel)
- Callsign og 6-tegns grid?
- Skal vi kjøre i-gate / Winlink-RMS / WSPR-bake 24/7 — eller er det "manuell shack-assist"?
- Trengs GPS-refclock (portabel/emcomm) eller holder internett-NTP?
- Cloudflare Access foran for fjerntilgang, eller kun LAN/WireGuard?

## Status

- 2026-05-25: Byggeplan klar. Hardware ikke bestilt enda — avventer rigg-spec og avklaringer over.
