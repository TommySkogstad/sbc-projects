---
name: Printer-test-rapport
about: Rapporter resultat fra test av en spesifikk printer-modell på Rock 3C
title: "Test: <printer-modell>"
labels: print-server, test-report
assignees: ''
---

## Printer-info

- **Modell** (full string fra USB-descriptor):
- **Vendor (VID)**: `0x____`
- **Product (PID)**: `0x____`
- **Tilkoblingstype**: USB
- **Firmware-versjon** (hvis kjent):

> Hent VID/PID med `lsusb` på Rock 3C etter at printeren er koblet til.

## Driver-valg

- **Driver valgt av `add-printer.sh`**:
- **PPD-fil brukt**:
- **Konfigurert URI** (output fra `lpstat -v`):

> Sjekk `/var/log/add-printer.log` for hvilken regel som matchet.

## Testresultat

### Print-test (lp via SSH)

```bash
echo "test fra Rock 3C" | lp -d <printer-navn>
```

- [ ] Print kom ut fysisk
- [ ] Korrekt formatert (ikke gibberish/feil tegnsett)

### Web-UI-test (PDF-upload)

- [ ] PDF-opplasting fungerte
- [ ] Print kom ut fysisk
- [ ] Tosidig fungerte (hvis testet)
- [ ] Flere kopier fungerte (hvis testet)

### AirPrint-test (iOS/iPadOS)

- [ ] Printeren dukket opp i utskriftsdialog
- [ ] Print kom ut fysisk
- [ ] Format korrekt

### Mopria-test (Android)

- [ ] Printeren dukket opp i Mopria-app
- [ ] Print kom ut fysisk
- [ ] Format korrekt

## Konklusjon

- [ ] **Fungerer fullt ut** — flytt til "Verifisert"-kolonne i kompatibilitetstabellen
- [ ] **Fungerer med begrensninger** (spesifiser) — flytt til "Verifisert med advarsel"
- [ ] **Fungerer ikke** — flytt til "Bekreftet IKKE funker"

## Andre observasjoner

(Logg-utdrag, atferdsbeskrivelse, debug-funn, lenker til CUPS-issues etc.)
