# Print-server

Gjør en gammel USB-printer tilgjengelig som **AirPrint** (iOS) og **Mopria** (Android) via WiFi. Ingen ekstra app, ingen sky, ingen abonnement. `printer.local` annonseres via mDNS og dukker opp automatisk i alle moderne OS.

## Stack

- **Rock 3C 1 GB** + microSD
- **Armbian Bookworm Minimal** (headless)
- **CUPS** — print-server-kjerne
- **Avahi** — mDNS-annonsering (AirPrint/Mopria)
- **ipp-usb** — moderne IPP-over-USB driver for nyere printere
- **printer-driver-all + hplip** — bred driverstøtte
- **flash.sh** — laptop-side provisioning av WiFi, SSH, og services

## Hardware bestilt

- Radxa Rock 3C 1 GB (499 kr)
- USB A-til-B skriverkabel 2 m (~120 kr)
- SanDisk Ultra microSD 32 GB (har)
- USB-C strømforsyning 5V/3A (har)

## Build-plan

### Fase 1 — Forberedelse på laptop

1. Last ned Armbian Bookworm Minimal for Rock 3C fra https://www.armbian.com/rock-3c/
2. Last ned [balenaEtcher](https://www.balena.io/etcher/)
3. Forbered SSH-nøkkel: `ssh-keygen -t ed25519` hvis du ikke har en

### Fase 2 — Flash og laptop-side provisioning (10 min)

1. Flash Armbian til microSD med Etcher
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
- Setter hostname til `printer`
- Konfigurerer WiFi fra `armbian_first_run.txt`
- Installerer CUPS, Avahi, ipp-usb, printer-drivers
- Starter services og setter opp Avahi-annonsering

Finn IP når den er oppe:
```bash
arp -a | grep -i rock
ssh root@<IP>
# eller direkte: ssh root@printer.local
```

### Fase 4 — CUPS-konfigurasjon (5 min)

```bash
cupsctl --remote-admin --remote-any --share-printers
usermod -aG lpadmin <bruker>
systemctl restart cups
```

CUPS web-UI: `http://printer.local:631`

### Fase 5 — Koble til printeren (10 min)

1. Koble printer med USB A-til-B-kabelen
2. Verifiser: `lsusb` og `lpinfo -v`
3. Legg til printer via CUPS web-UI, autodriver
4. Test: `echo "hei" | lp -d <printer-name>`

### Fase 6 — AirPrint/Mopria-konfigurasjon (5 min)

Filen `/etc/avahi/services/airprint.service` er allerede provisjonert av flash.sh, men må tilpasses:

```bash
ssh root@printer.local
nano /etc/avahi/services/airprint.service
```

Rediger `PRINTER_NAME`, `PRINTER_DESCRIPTION`, og `note=` basert på CUPS-setup fra fase 5:

```xml
<txt-record>rp=printers/PRINTER_NAME</txt-record>
<txt-record>ty=HP LaserJet Pro M404n</txt-record>
<txt-record>adminurl=http://printer.local:631/printers/PRINTER_NAME</txt-record>
<txt-record>note=Stuen</txt-record>
```

Restart Avahi:
```bash
systemctl restart avahi-daemon
```

Test fra iOS/Android — printeren skal dukke opp automatisk i utskriftsdialogen.

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

## Hva vi IKKE bygger nå

- Cloud-print backend
- Captive portal-onboarding
- Markedsanalyse / produktversjon (Rock 3C 85×56 mm er for stor — produkt ville krevd Orange Pi Zero 2W eller Radxa Zero 3W)
- Branding, support, GDPR-vurdering

## Låste beslutninger (ikke gjenåpne)

- microSD, ikke NVMe — sparer 700–1500 kr
- 1 GB RAM — holder fint for CUPS + Avahi + tynn web-UI
- Skip kabinett, heatsink, OTG-adapter
- Headless oppsett
