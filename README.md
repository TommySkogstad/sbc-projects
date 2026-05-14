# SBC Projects

Samling av hobby-prosjekter på single-board computers (SBC) — Radxa Rock-serien og Raspberry Pi. Hver underkatalog er et selvstendig prosjekt med egen build-plan, kode og dokumentasjon. Felles repo for å holde antall GitHub-prosjekter nede og dele oppsett-skript på tvers.

## Prosjekter

| Prosjekt | Hardware | Status | Mappe |
|---|---|---|---|
| **GeoLoop** | Raspberry Pi 3B+ | Produksjon — styrer vannbåren bakkevarme | [`geoloop/`](geoloop/) |
| **Print-server** | Rock 3C 1 GB | Provisioning implementert (flash.sh), venter hardware | [`print-server/`](print-server/) |
| **Spotify-spiller** | Rock 3C 1 GB | Planlagt | [`spotify-spiller/`](spotify-spiller/) |

## Hardware

### Radxa Rock 3C 1 GB (~499 kr Kjell, art.nr 88129)

Lavterskel SBC for enkeltformål-prosjekter. Innebygd 24-bit/96 KHz AUX gjør den ideell for Spotify-spiller.

- Rockchip RK3566 (4× Cortex-A55 @ 1.6 GHz)
- 1 GB LPDDR4
- WiFi 5 + BT 5.0, Gigabit Ethernet
- 3× USB 2.0, 1× USB 3.0, HDMI 2.0 (4K/60)
- 3.5mm AUX, 40-pin GPIO

### Radxa Rock 4C+ 4 GB (~799 kr Kjell, art.nr 88142) — vurdert

Kraftigere SBC for prosjekter som krever Docker, multi-service eller GPU-akselerasjon.

- Rockchip RK3399-T (big.LITTLE: 2× A72 @ 1.5 GHz + 4× A53 @ 1 GHz)
- 4 GB LPDDR4, Mali T860MP4 GPU
- Dual Micro-HDMI (4K + 2K), 2× USB 2.0 + 2× USB 3.0
- Innebygd strømbryter, ekstern antenne-tilkobling
- Kandidat for: SHS-host (self-hosted Homey), Frigate NVR, info-skjerm, retro-spillkonsoll

### Raspberry Pi 3B+

I bruk i GeoLoop med Open-Smart GPIO Expansion + RPi Relay Board for VP-styring og sirkulasjonspumpe.

## Felles OS-anbefaling

| Bruksområde | OS |
|---|---|
| Lett enkeltformål (print-server) | Armbian Bookworm Minimal |
| Audio-stack (Spotify, Snapcast, AirPlay) | DietPi Bookworm |
| Industrial/IoT (GeoLoop) | Raspberry Pi OS Lite |
| Docker-hub (SHS, Frigate) | Armbian Bookworm + Docker |

## Hemmeligheter

`geoloop/.env` og `geoloop/config.yaml` er git-crypt-kryptert med samme GPG-nøkkel som de andre prosjektene (`CA1E41D13067550891949E067F35459C441CBC8B`). På nye maskiner: `git-crypt unlock` etter clone.

## Lisens

MIT. Hobby-kode, ingen garanti.
