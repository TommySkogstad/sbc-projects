# Print-server

Gjør en gammel USB-printer tilgjengelig som **AirPrint** (iOS) og **Mopria** (Android) via WiFi. Ingen ekstra app, ingen sky, ingen abonnement. `printer.local` annonseres via mDNS og dukker opp automatisk i alle moderne OS.

## Stack

- **Rock 3C 1 GB** + microSD
- **Armbian Bookworm Minimal** (headless)
- **CUPS** — print-server-kjerne
- **Avahi** — mDNS-annonsering (AirPrint/Mopria)
- **ipp-usb** — moderne IPP-over-USB driver for nyere printere
- **printer-driver-all + hplip** — bred driverstøtte

## Hardware bestilt

- Radxa Rock 3C 1 GB (499 kr)
- USB A-til-B skriverkabel 2 m (~120 kr)
- SanDisk Ultra microSD 32 GB (har)
- USB-C strømforsyning 5V/3A (har)

## Build-plan

### Fase 1 — Forberedelse på laptop

1. Last ned Armbian Bookworm Minimal for Rock 3C fra https://www.armbian.com/rock-3c/
2. Last ned [balenaEtcher](https://www.balena.io/etcher/)
3. Forbered WiFi-config (SSID + passord) og SSH-key

### Fase 2 — Førstegangsoppsett (15 min)

1. Flash Armbian til microSD med Etcher
2. Mount SD på laptop, legg til WiFi-config og SSH-key i `armbian_first_run.txt`
3. Sett SD i Rock 3C, koble strøm
4. Finn IP via router eller `arp -a`, SSH inn som `root`

### Fase 3 — System-baseline (10 min)

```bash
apt update && apt upgrade -y
apt install -y avahi-daemon cups cups-filters cups-bsd \
  printer-driver-all hplip ipp-usb ghostscript \
  python3 python3-pip
hostnamectl set-hostname printer
systemctl enable --now avahi-daemon ipp-usb cups
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

### Fase 6 — AirPrint/Mopria (5 min)

Opprett `/etc/avahi/services/airprint.service`:

```xml
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">AirPrint %h</name>
  <service>
    <type>_ipp._tcp</type>
    <subtype>_universal._sub._ipp._tcp</subtype>
    <port>631</port>
    <txt-record>txtvers=1</txt-record>
    <txt-record>qtotal=1</txt-record>
    <txt-record>rp=printers/PRINTER_NAME</txt-record>
    <txt-record>ty=PRINTER_DESCRIPTION</txt-record>
    <txt-record>adminurl=http://printer.local:631/printers/PRINTER_NAME</txt-record>
    <txt-record>note=Living Room</txt-record>
    <txt-record>priority=0</txt-record>
    <txt-record>product=(GPL Ghostscript)</txt-record>
    <txt-record>pdl=application/pdf,image/jpeg,image/urf</txt-record>
    <txt-record>URF=W8,SRGB24,CP1,RS600</txt-record>
  </service>
</service-group>
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
