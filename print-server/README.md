# Print-server

Gjør en gammel USB-printer tilgjengelig som **AirPrint** (iOS) og **Mopria** (Android) via WiFi. Ingen ekstra app, ingen sky, ingen abonnement. `printer-rock.local` annonseres via mDNS og dukker opp automatisk i alle moderne OS.

## Stack

- **Rock 3C 1 GB** + microSD
- **Armbian Bookworm Minimal** (headless)
- **CUPS** — print-server-kjerne
- **Avahi** — mDNS-annonsering (AirPrint/Mopria)
- **ipp-usb** — moderne IPP-over-USB driver for nyere printere
- **printer-driver-all + hplip** — bred driverstøtte
- **hostapd + dnsmasq** — WiFi AP-fallback ved tilkoblingsfeil
- **Captive portal** (Flask) — WiFi-onboarding med SSID-scanning og nettskjema
- **flash.sh** — laptop-side provisioning av WiFi, SSH, og services

## Hardware bestilt

- Radxa Rock 3C 1 GB (499 kr)
- USB A-til-B skriverkabel 2 m (~120 kr)
- SanDisk Ultra microSD 32 GB (har)
- USB-C strømforsyning 5V/3A (har)

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
3. Rediger `setup/armbian_first_run.txt`: sett WiFi-SSID, passord, og lim inn SSH-nøkkelen fra `cat ~/.ssh/id_ed25519.pub`
4. Mount SD på laptop. Skript auto-detekterer eller spør om partisjon:
   ```bash
   sudo ./flash.sh
   ```
   Med `--dry-run` for test. Copierer setup-filer og aktiverer first-boot.service.
5. Sett SD i Rock 3C, koble til USB-C strøm (5V/3A)

### Fase 3 — Første boot og system-baseline (auto, ~2-3 min)

first-boot.service kjører automatisk ved boot som root:
- Setter hostname til `printer-rock`
- Konfigurerer WiFi fra `armbian_first_run.txt`
- Installerer CUPS, Avahi, ipp-usb, printer-drivers
- Starter services og setter opp Avahi-annonsering

Finn IP når den er oppe:
```bash
arp -a | grep -i rock
ssh root@<IP>
# eller direkte: ssh root@printer-rock.local
```

### Fase 4 — CUPS-konfigurasjon (5 min)

```bash
cupsctl --remote-admin --remote-any --share-printers
usermod -aG lpadmin <bruker>
systemctl restart cups
```

CUPS web-UI: `http://printer-rock.local:631`

### Fase 5 — Auto-USB-printer-detect

1. Koble printer med USB A-til-B-kabelen
2. Systemet detekterer USB-printer automatisk via udev-regel `99-usb-printer.rules`
3. `add-printer.sh` kjøres automatisk:
   - Venter til CUPS er klar
   - Registrerer printer med navn `auto-USB-Printer` med IPP Everywhere driver (driverløs)
   - Oppdaterer Avahi AirPrint-tjeneste via `render-airprint.sh`
   - Logger til `/var/log/add-printer.log`

Verifiser:
```bash
lpstat -p -d
# eller web-UI: http://printer-rock.local:631/admin/
```

Debug: Hvis printer ikke detekteres, sjekk loggen og at CUPS kjører:
```bash
ssh root@printer-rock.local
tail -f /var/log/add-printer.log
systemctl status cups
```

### Fase 6 — Verifisering av AirPrint (2 min)

Filen `/etc/avahi/services/airprint.service` ble automatisk generert og oppdatert av `render-airprint.sh` i Fase 5 basert på detektert printer-navn.

Test fra iOS/Android — printeren skal nå dukke opp automatisk i utskriftsdialogen.

**Valgfritt — tilpass descripton/note:**

Hvis du vil endre printer-beskrivelse (f.eks. lokasjon), rediger `/etc/avahi/services/airprint.service` og restart Avahi:

```bash
ssh root@printer-rock.local
nano /etc/avahi/services/airprint.service
# Endre: <txt-record>note=Home</txt-record> osv.
systemctl restart avahi-daemon
```

### Fase 7 — Web-UI (valgfritt)

Tynn Ktor- eller Node-app foran CUPS' IPP-API:
- Drag-and-drop opplasting
- Kø-status
- Print-historikk

Skip hvis Fase 6 funker — AirPrint/Mopria dekker hele behovet for mobil-utskrift uansett.

## Utvidelser (etter at basis funker)

- Integrasjon mot `status.html`-dashboard (printer som komponent)
- ntfy-notiser ved utskrift-fullføring eller blekk-tomt
- Cloudflare Tunnel for utskrift hjemmefra
- CLI-snarvei: `print rapport.pdf` fra terminal

## WiFi-onboarding

Hvis enheten mister WiFi-tilkoblingen, startes en AP-fallback automatisk:

1. `wifi-check.service` kjører hvert 2. minutt og verifiserer forbindelse
2. Hvis tilkoblingen feiler: `hostapd` starter AP `printer-rock-setup` (192.168.4.1)
3. Brukeren kobler til AP og får opp **captive portal** i nettleseren
4. Web-skjemaet tillater SSID-scanning og PWA2-passord-oppgave
5. Etter lagring: enhet prøver å koble til igjen, AP stoppes automatisk

## Hva vi IKKE bygger nå

- Cloud-print backend
- Markedsanalyse / produktversjon (Rock 3C 85×56 mm er for stor — produkt ville krevd Orange Pi Zero 2W eller Radxa Zero 3W)
- Branding, support, GDPR-vurdering

## Låste beslutninger (ikke gjenåpne)

- microSD, ikke NVMe — sparer 700–1500 kr
- 1 GB RAM — holder fint for CUPS + Avahi + tynn web-UI
- Skip kabinett, heatsink, OTG-adapter
- Headless oppsett
