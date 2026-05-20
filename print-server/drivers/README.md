# Drivers

Forhåndsbundlede printer-drivere som ikke er tilgjengelige i Debian/Armbian apt-repo.

## cnrdrvcups-ufr2-uk_6.20-1.20_arm64.deb

Canon UFRII LT-driver for eldre Canon-laser (LBP113, LBP161, LBP162, LBP223, MF230-serien m.fl.).

- **Versjon**: 6.20-1.20
- **Arkitektur**: arm64
- **Størrelse**: 7.7 MB
- **Kilde**: `http://gdlp01.c-wss.com/gds/8/0100007658/47/linux-UFRII-drv-v620-m17n-20.tar.gz`
- **Avhengigheter**: cups, libcups2, libjpeg62, libjbig0, lsb-release (alle i Bookworm arm64)

Hvorfor pre-bundlet og ikke lastet ned i `first-boot.sh`:

1. Canon-sidens download er bak reCAPTCHA — direkte URL kan flyttes uten varsel
2. Eliminerer internett-avhengighet for å fullføre first-boot
3. Driveren er liten nok (7.7 MB) til at lagring i repo ikke er et problem

Driveren installeres betinget av `add-printer.sh` når Canon USB VID (`0x04a9`) + UFRII LT-modellstring (`LBP`, `MF`) detekteres. Se [feedback om Canon LBP113 i `printer.tommytv.no`-pipelinen](https://github.com/TommySkogstad/sbc-projects/blob/main/print-server/README.md#canon-ufrii-lt--print-job-canceled-at-printer) for kontekst.

## Lisens

Canon UFRII-driveren distribueres av Canon under egen lisens (ikke open source). Driveren er fritt distribuerbart for bruk med Canon-printere — videredistribusjon som del av en print-server-løsning er ifølge Canons egne FAQ-er tillatt. Se `LICENSE-canon.txt` for utdrag.
