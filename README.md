# Rock 3C

Samling av hobby-prosjekter bygget på **Radxa Rock 3C** ettkortsdatamaskin. Hver underkatalog inneholder build-plan og kode for et separat prosjekt — alle deler samme grunnhardware og kan kjøres på dedikerte enheter eller side-om-side på samme node.

## Hardware

**Radxa Rock 3C 1 GB** (artikkelnr 88129 hos Kjell, 499 kr) er valgt som standard. Specs:

- Rockchip RK3566 quad-core Cortex-A55 @ 1.6 GHz
- 1 GB LPDDR4 RAM
- WiFi 5 + Bluetooth 5.0
- 3× USB 2.0, 1× USB 3.0, Gigabit Ethernet
- HDMI 2.0 (4K/60 Hz)
- **3.5mm AUX (24-bit/96 KHz)**
- 40-pin GPIO header (Pi-kompatibel)
- M.2 M-key 2230 (PCIe 2.1 x1) — ikke 2280
- USB-C strøm: 5V/3A (5V/4A med M.2 SSD)
- Form-faktor: 85×56 mm

## Prosjekter

| Prosjekt | Status | Mappe |
|---|---|---|
| Print-server (AirPrint/Mopria via CUPS) | Build-plan klar, venter på hardware | [`print-server/`](print-server/) |
| Spotify-spiller (Spotify Connect via raspotify) | Planlagt | [`spotify-spiller/`](spotify-spiller/) |

## Felles OS-anbefaling

**DietPi** eller **Armbian Bookworm Minimal** for Rock 3C. Begge gir minimal Debian-base med god støtte for RK3566 og softwarekatalog som dekker både CUPS, raspotify, Snapcast, og resten av økosystemet.

Flash til microSD med Etcher eller `dd`. NVMe er valgfritt men ikke nødvendig for noen av prosjektene per nå.

## Hvorfor Rock 3C?

- 499 kr for full Linux-PC er røverkjøp
- Innebygd AUX gjør Spotify-spiller plug-and-play
- Pi-kompatibel GPIO og form-faktor (~Pi 4)
- Mer USB-porter enn Pi Zero, mindre fikkel enn Pi 5

## Lisens

MIT. Hobby-kode, ingen garanti.
