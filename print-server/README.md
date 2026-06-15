# Print-server

Gjør en USB-printer tilgjengelig som **AirPrint** (iOS), **Mopria** (Android) og **web-UI** (PDF-upload fra hvilken som helst nettleser) via WiFi. Ingen ekstra app, ingen sky, ingen abonnement. `printer-<navn>.local` annonseres via mDNS og dukker opp automatisk i alle moderne OS.

Primær use-case: plassere en USB-printer et annet sted enn arbeidsmaskinen — annet rom, eksternt kontor, hyttekontor — uten å investere i ny WiFi-printer eller løse det med en stasjonær PC.

## Stack

- **Rock 3C 1 GB** + microSD (Armbian Bookworm Minimal, headless)
- **CUPS** — print-server-kjerne
- **Avahi** — mDNS-annonsering (AirPrint/Mopria)
- **ipp-usb** — IPP-over-USB for moderne printere
- **Bred driver-bundle** — HPLIP, brlaser, escpr, splix, foo2zjs, Foomatic, Canon UFRII
- **cups-browsed** — AirPrint-bro for printere som ikke snakker PWG Raster nativt
- **hostapd + dnsmasq + captive portal** — WiFi-fallback ved tilkoblingsfeil
- **FastAPI web-UI** — PDF-upload (port av `tommytv-infra/printer-service`)
- **flash.sh** — laptop-side provisioning av WiFi, SSH og services

## Hardware

Bestilt fra Kjell:

- Radxa Rock 3C 1 GB (artikkelnr 88129) — 499 kr
- USB A-til-B skriverkabel 2 m — ~120 kr
- microSD 32 GB (Endurance anbefales hvis printeren skal stå i produksjon — apt-install + driver-bundle gir sustained writes første boot)
- USB-C strømforsyning 5V/3A

## Kompatibilitet

### Støttet (driver inkludert i bundle)

| Familie | Driver | Eksempler |
|---|---|---|
| HP LaserJet / DeskJet / OfficeJet | HPLIP | LaserJet 1010/1018/1020 (firmware-upload), 1100, 2055, 4250, Pro M-serien, alle DeskJet ≥ 2000 |
| Brother laser (open source) | brlaser | HL-2030, HL-L2300, HL-L2350, DCP-serien |
| Brother etikettprinter (USB) | ptouch | QL-700, QL-800, P-touch-serien |
| Canon moderne (IPP Everywhere) | driverless | LBP6230, LBP7100, MAXIFY/PIXMA fra 2017+ |
| Canon UFRII LT (eldre laser) | cnrdrvcups-ufr2-uk | LBP113, LBP161, LBP162, LBP223, MF230-serien |
| Canon BubbleJet / PIXMA klassisk | Gutenprint | iP1000–iP4000, MX-serien eldre |
| Epson ESC/P-R | escpr / escpr2 | XP-serien, WorkForce, EcoTank, eldre Stylus |
| Samsung laser | splix | ML-1610–2510, CLP-serien, M-serien eldre |
| Xerox eldre laser | splix | Phaser 3140, 3160, 6000-serien |
| OKI laser | oki | B-serien, C-serien |
| Dymo etikettprintere | dymo | LabelWriter 400, 450, 550 |
| Generisk PostScript | Foomatic | Alle PS-utstyrte enterprise-printere |

> **Test-status**: Tabellen baseres på driver-tilgjengelighet i arm64-pakker, **ikke verifisert testing på Rock 3C**. Etter første reelle utrulling oppdateres tabellen med en "Verifisert"-kolonne. Rapporter funn via printer-test-issue-mal i `.github/ISSUE_TEMPLATE/`.

### Støttes IKKE

| Familie | Hvorfor | Mulig workaround |
|---|---|---|
| **Lexmark MS/MX/CS-serien** | Lexmark Linux-driver er **x86-only**, ikke arm64 | Eldre Lexmark uten egen driver kan funke via Foomatic generic — modell-spesifikt, manuell PPD-opplasting i web-UI |
| **Kyocera KX-driver-only modeller** | Kyocera KX-driveren er x86-only | Hvis modellen er PostScript-utstyrt (vanlig i ECOSYS-serien) — funker via Foomatic generic PS. Sjekk modellens datablad. |
| **Dell B2360 / B3460 / 5230 / 5350** | Lexmark-OEM, samme blokker | Dell 1130/1133/1135/2335dn er Samsung-OEM og fungerer via splix |
| **HP LaserJet 1000 (original, 1998)** | Krever firmware-blob som ikke er kompilert for arm64 | LaserJet 1010 og senere fungerer |
| **Bluetooth-only printere** | Ingen BT-bridging | Bruk maskin med BT direkte |
| **Multifunksjon scanner (SANE)** | Print fungerer hvis modellen er listet over — scan er utenfor scope | Egen SANE-tjeneste eller direkte tilkobling til laptop |
| **Fax send/mottak** | Utenfor scope | — |

### Krav for tilkobling

- **USB nødvendig** — printere med kun WiFi eller Bluetooth som tilkoblingsvei kan ikke brukes som klient
- For ukjente modeller: søk på `openprinting.org/printers/<modell>` — "Perfectly Supported" eller "Mostly Supported" = forventet OK
- Multifunksjon-enheter: kun print rutes; scanner og fax forblir tilgjengelig direkte fra printeren selv

### Hvis printeren din ikke er listet

`add-printer.sh` følger denne strategien:

1. Forsøk **IPP Everywhere** (driverless) først
2. Ved feil: forsøk **Foomatic-modell-match** på modell-string fra USB-descriptor
3. Hvis fortsatt ingen match: registrer som "Ukjent printer (manuell driver-valg)" og varsle via web-UI

Web-UI gir da brukeren mulighet til å laste opp egen PPD-fil. Pga sikkerhetsrisiko er dette opt-in og logges.

## Domene-strategi

- **Default**: kun mDNS på lokalt nett (`printer-<navn>.local`). Ingen ekstern eksponering, ingen Cloudflare-tunnel, ingen auth-bekymring.
- **Per-instans opt-in**: hvis en spesifikk Rock 3C trenger ekstern tilgang, opprett tunnel og DNS under eksisterende zone (f.eks. `kontor-print.tommytv.no`). Se Fase 8 nedenfor.
- **`printer.tommytv.no` er reservert** for den private NUC-tilkoblede Canon LBP113.

## Build-plan

### Fase 1 — Forberedelse på laptop

1. Last ned Armbian Bookworm Minimal for Rock 3C fra https://www.armbian.com/rock-3c/
2. Forbered SSH-nøkkel: `ssh-keygen -t ed25519` hvis du ikke har en

> **Ubuntu 24.04+:** `balena-etcher` støttes ikke (mangler `gconf`). Bruk `dd` i stedet.

### Fase 2 — Flash og laptop-side provisioning (10 min)

1. Flash Armbian til microSD med `dd`:
   ```bash
   xz -d Armbian_*_Rock-3c_bookworm_*.img.xz
   sudo dd if=Armbian_*_Rock-3c_bookworm_*.img bs=4M status=progress oflag=sync of=/dev/sdX
   ```
2. Kopier `setup/armbian_first_run.txt.example` til `setup/armbian_first_run.txt`
3. Rediger: sett WiFi-SSID, passord, og lim inn SSH-nøkkel fra `cat ~/.ssh/id_ed25519.pub`
4. Mount SD på laptop, kjør:
   ```bash
   sudo ./flash.sh --name "kontor"
   ```
   Med `--dry-run` for forhåndsvisning. Scriptet auto-detekterer SD-partisjon, kopierer setup-filer og aktiverer `first-boot.service`. `--name`-flagget setter hostname til `printer-kontor`.
5. Sett SD i Rock 3C, koble til USB-C strøm

### Fase 3 — Første boot og driver-install (auto, 8–10 min)

`first-boot.service` kjører automatisk som root ved første boot:

- Setter hostname (`printer-<navn>`)
- Konfigurerer WiFi fra `armbian_first_run.txt`
- Installerer driver-bundle (~580 MB via apt):
  - `cups`, `cups-filters`, `cups-bsd`, `cups-browsed`
  - `avahi-daemon`, `ipp-usb`, `ghostscript`, `libjpeg62`
  - `printer-driver-all`, `hplip`, `hplip-data`
  - `printer-driver-brlaser`, `printer-driver-escpr`, `printer-driver-escpr2`
  - `printer-driver-foo2zjs`, `printer-driver-splix`
  - `printer-driver-foomatic-db`, `foomatic-db-engine`
- Installerer Canon UFRII-driver fra forhåndsbundlet `.deb` (`drivers/cnrdrvcups-ufr2-uk_6.20-1.20_arm64.deb`)
- Starter og enabler tjenester (avahi-daemon, ipp-usb, cups, printer-web)

Førsteboot-tid forventes 8–10 min. Sjekk fremdrift:

```bash
ssh root@printer-<navn>.local
tail -f /var/log/first-boot.log
```

### Fase 4 — CUPS-konfigurasjon (auto, del av first-boot)

```bash
cupsctl --remote-admin --remote-any --share-printers
```

CUPS web-UI: `http://printer-<navn>.local:631`

### Fase 5 — Auto-USB-printer-detect

1. Koble printer med USB A-B-kabelen
2. udev-regel `99-usb-printer.rules` fyrer `add-printer.sh`
3. Skriptet leser USB VID/PID og ruter til riktig driver:

| VID | Vendor | Strategi |
|---|---|---|
| `0x03f0` | HP | HPLIP-discovery (`hp:/usb/<model>?serial=<sn>`) |
| `0x04a9` | Canon | IPP Everywhere først; ved kansellering → ipp-usb + UFRII-PPD |
| `0x04f9` | Brother | brlaser via Foomatic-match |
| `0x04b8` | Epson | escpr / escpr2 etter modell-string |
| `0x04e8` | Samsung | splix |
| `0x06bc` | OKI | oki |
| `0x0922` | Dymo | dymo |
| `0x043d` | Lexmark | **Avvis** med tydelig melding (ikke støttet, se kompatibilitetsmatrise) |
| `0x0482` | Kyocera | Forsøk Foomatic generic PS; logg advarsel |
| (andre) | — | IPP Everywhere → Foomatic-fallback → manuell PPD via web-UI |

4. Alle avgjørelser logges til `/var/log/add-printer.log` med VID + matchet regel — kritisk for feilsøking
5. Etter vellykket lpadmin: `render-airprint.sh` oppdaterer Avahi-tjenesten

Verifiser:

```bash
ssh root@printer-<navn>.local
lpstat -p -d
tail -f /var/log/add-printer.log
```

### Fase 6 — AirPrint / Mopria (best-effort)

For printere med ekte IPP Everywhere-firmware: dukker opp direkte i iOS- og Android-utskriftsdialog.

For eldre printere (de fleste UFRII LT-modeller, mange Brother-modeller): `cups-browsed` fungerer som AirPrint-bro og oversetter PWG Raster → printerens native format via CUPS-filterstakken. Fungerer i de fleste tilfeller, men noen modeller kreves manuelt feilsøkt.

Hvis AirPrint ikke fungerer for en spesifikk modell: bruk web-UI (Fase 7) som primær mobilflyt.

### Fase 7 — Web-UI (primær mobilflyt)

FastAPI-tjeneste på `http://printer-<navn>.local:8080`:

- Drag-and-drop PDF-upload
- Validering: PDF-magic, maks 20 MB / 50 sider (via `pdfinfo`)
- Print-options: kopier (1–10), enkeltsidig / tosidig-langside / tosidig-kortside
- Kø-status (via CUPS IPP-API)
- Logger til `/var/log/printer-web.log`

Tjenesten kjører native som systemd-unit, ikke Docker — sparer ~150 MB RAM på 1 GB SBC.

Kode portert fra `tommytv-infra/printer-service/app/`.

### Fase 8 — Ekstern tilgang via Cloudflare Tunnel (valgfritt)

Hvis Rock 3C-instansen skal nås utenfor lokalt nett:

1. Opprett tunnel i Cloudflare dashboard
2. Sett opp DNS-record under egnet zone (f.eks. `kontor-print.tommytv.no` → tunnel-CNAME)
3. Kopier `setup/cloudflared.service.example` til `/etc/systemd/system/cloudflared.service`, legg inn tunnel-token
4. **Sett opp Cloudflare Access** med email-allowlist før første aktivering — ellers er printeren åpen for hele internett
5. `systemctl enable --now cloudflared`

cloudflared kjører native som systemd-tjeneste, ikke Docker — sparer RAM.

## WiFi-onboarding

Hvis enheten mister WiFi-tilkoblingen, startes AP-fallback automatisk:

1. `wifi-check.service` kjører hvert 2. minutt og verifiserer forbindelse
2. Hvis tilkoblingen feiler: `hostapd` starter AP `printer-<navn>-setup` (192.168.4.1)
3. Bruker kobler til AP og får opp **captive portal** i nettleseren
4. Web-skjemaet tillater SSID-scanning og WPA2-passord-oppgave
5. Etter lagring: enhet kobler til igjen, AP stoppes automatisk

Kritisk for utplassering hos kunde/kontor uten SSH-tilgang.

## Feilsøking

### Printeren dukker ikke opp

```bash
ssh root@printer-<navn>.local
tail -50 /var/log/add-printer.log     # USB-deteksjon
lpstat -p -d                            # CUPS-registrering
systemctl status cups ipp-usb avahi-daemon
```

### Canon UFRII LT — "Print job canceled at printer"

Symptom: IPP Everywhere godtar jobben men printeren avlyser umiddelbart. Skyldes at firmwaren ikke faktisk implementerer PWG Raster.

`add-printer.sh` skal detektere dette automatisk og switche til ipp-usb-pipelinen. Hvis ikke, manuell fix:

```bash
lpadmin -x <navn>
lpadmin -p <navn> -E \
  -v ipp://localhost:60000/ipp/print \
  -m CNRCUPSLBP161ZK.ppd
```

`ipp-usb`-tjenesten MÅ kjøre — sjekk med `systemctl status ipp-usb`. Direkte `usb://Canon/...`-backend fungerer IKKE — ipp-usb må stå mellom.

### AirPrint dukker ikke opp på iOS, men funker via web-UI

Printer-firmware støtter ikke IPP Everywhere ekte, og `cups-browsed`-broen er ikke aktivert. Sjekk:

```bash
systemctl status cups-browsed
cat /etc/cups/cups-browsed.conf | grep -i browse
```

Hvis web-UI fungerer er print-pipelinen i orden — AirPrint er kun et discovery/format-problem.

### First-boot henger på apt-install

Verifiser internett-tilkobling via `ping 1.1.1.1`. apt-install krever fungerende WiFi for å hente ~580 MB drivere. Hvis WiFi feiler: AP-fallback bør slå til etter 2 min — koble til og reonboarde.

## Hva vi IKKE bygger

- Cloud-print backend (krever infrastruktur)
- Markedsanalyse / produktversjon (Rock 3C 85×56 mm er for stor — produktform-faktor ville krevd Orange Pi Zero 2W eller Radxa Zero 3W)
- Branding, support-system, GDPR-vurdering
- Scanner-funksjonalitet (SANE — utenfor scope)
- Fax send/mottak
- Bluetooth-bridging

## Låste beslutninger (ikke gjenåpne)

- microSD, ikke NVMe — sparer 700–1500 kr, M.2 2230 er niche/dyr
- 1 GB RAM — holder fint for CUPS + Avahi + FastAPI web-UI
- Skip kabinett, heatsink, OTG-adapter
- Headless oppsett — ingen HDMI/skjerm/tastatur
- Bred driver-bundle i first-boot (8–10 min ekstra apt-tid, ~580 MB SD-bruk) — verdt det for plug-and-play-UX
- LAN-only (mDNS) som default — tunnel er opt-in per instans

## Status

- 2026-04-27: Hardware-valg gjort, build-plan klar
- 2026-05-15: Rock 3C ankommet, klar for hardware-test. README oppdatert med dd-flyt for Ubuntu 24.04+.
- 2026-05-20: README utvidet med kompatibilitetsmatrise, bred driver-bundle, web-UI som primær mobilflyt, VID/PID-routing, domene-strategi. Implementasjon (first-boot.sh, add-printer.sh, web-UI-port) pending.
- 2026-06-11: CI-testing implementert (`.github/workflows/print-server-ci.yml`) — tester shell-scripts med bats/shellcheck og Python-kode med pytest.
- 2026-06-15: Sikkerhet — oppgradert python-multipart til 0.0.21 og pinnet h11==0.16.0, starlette==0.46.0 for å fikse HTTP request smuggling og injection-sårbarhet (issue #46). Videre oppgradert fastapi==0.121.0 og starlette==0.49.1 for å fikse GHSA-7f5h-v6xp-fcq8 og GHSA-2c2j-9gv5-cj73 (issue #48).
