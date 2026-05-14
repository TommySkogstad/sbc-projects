# GeoLoop — Systemspesifikasjon

Alle avklaringer er fullført. Dette dokumentet er den verifiserbare sannheten om anlegget.

---

## 1. Varmepumpe

| Parameter | Verdi |
|-----------|-------|
| Modell | Panasonic WH-MXC12G6E5 |
| Type | Aquarea G-generasjon, luft-vann monobloc |
| Styring | Innebygd termostat |
| Ekstern kontroll | Klemme 17/18 — potensialfri ON/OFF (fabrikkjumper) |
| Romtermostat | Klemme 9 (L), 10 (N), 12 (Heat). Klemme 11 = kjøling (ikke brukt) |
| Tankføler | Klemme 15/16 |
| CZ-TAW1 | Ikke kompatibel (krever H-gen+) |
| HeishaMon | Ikke kompatibel (G-gen bruker annen protokoll) |

## 2. Systemtopologi

Buffertanken (200 L, udelt) er sentral node. To separate kretser:

```
     VP-krets                                  Bakkesløyfe-krets

┌─────────────────┐                     ┌─────────────────────────┐
│   Varmepumpe    │                     │   Bakkeløyfe            │
│  WH-MXC12G6E5  │                     │   8 sløyfer, 900 m      │
└──┬──────────▲───┘                     └──┬──────────────▲───────┘
   │          │                            │              │
 T4(ut)       │                        T1(inn)         T2(ut)
   │     ┌────┴────────┐                  │              │
   │     │ Kolbetank   │                  │              │
   │     │ 10 L        │                  │              │
   │     │ 10 kW kolber│                  │              │
   │     └────▲────────┘                  │              │
   │          │                            │              │
   │       T3(inn)                         │              │
   │          │                            │              │
   ▼          │                            ▼              │
┌─────────────┴────────────────────────────┴──────────────┴───────┐
│                    Buffertank 200 L (T5)                         │
│                    (udelt felles volum, føler kl. 15/16)         │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Bakkeløyfe

| Parameter | Verdi |
|-----------|-------|
| Antall sløyfer | 8 |
| Total rørlengde | 900 m (~112 m per sløyfe) |
| Rør | 20 mm ytre, 2 mm vegg → 16 mm indre diameter |
| Legging | I sand, 5 cm under overflaten, asfalt over |
| Dekket areal | ~90 m² |
| Rørtetthet | ~10 m/m² |

## 4. Vannvolum

| Komponent | Volum |
|-----------|-------|
| Bakkeløyfe | 181 L |
| Buffertank | 200 L |
| Kolbetank | 10 L |
| Internrør | ~30 L |
| **Totalt** | **~421 L** |

Formel bakkeløyfe: V = π × r² × L = π × 0.008² × 900 = 0.181 m³

## 5. Maskinvare — styring

| Komponent | Modell |
|-----------|--------|
| Styringsenhet | Raspberry Pi 3B+ |
| Relékort | RPi Relay Board — 3 kanaler (HAT) |
| GPIO-utvidelse | Open-Smart GPIO Expansion Board |
| Plassering | Innendørs |
| Nettverk | Ethernet + WiFi |

### Relékanaler

| Kanal | Funksjon | Tilkobling |
|-------|----------|------------|
| 1 | Varmepumpe ON/OFF | VP klemme 17/18 (erstatter fabrikkjumper) |
| 2 | Ekstern sirkulasjonspumpe | Uavhengig styring |
| 3 | Ledig | Reservert (kolber i fremtiden) |

## 6. Temperatursensorer

Alle DS18B20 (1-Wire digital), hardkoblet, på GPIO4.

| # | Plassering | Krets | Formål |
|---|------------|-------|--------|
| T1 | Tank → bakkeløyfe | Bakkesløyfe | Turtemperatur til bakken |
| T2 | Bakkeløyfe → tank | Bakkesløyfe | Returtemperatur (delta-T → effekt) |
| T3 | Tank → VP (via kolbetank) | VP | Returvann til VP |
| T4 | VP → tank | VP | Turvann fra VP |
| T5 | Buffertank | Felles | Buffertemperatur (VP klemme 15/16) |

## 7. Prediktiv logikk

| Parameter | Verdi |
|-----------|-------|
| Treghet | ~24 timer fra oppstart til full effekt |
| Prediksjonsbehov | Minimum 24 timer frem (api.met.no gir 48t) |
| Faresone | -5 °C til +5 °C (rundt 0 °C er kritisk) |
| Prioritet | **Sikkerhet mot is** — hellere kjøre for mye |

## 8. Funksjonelle krav

| Funksjon | Beskrivelse |
|----------|-------------|
| Fjernstyring | Tilgang utenfra lokalt nett |
| Varsling | Alarm ved feil, sensorbortfall, VP-stopp |
| Logging | Historikk for etteranalyse |
| Grafer | Temperatur over tid — visuelt dashboard |
| Statistikk | Driftstid, forbruksoversikt |
| Integrasjon | Plejd (om mulig) |

## 9. Tilleggskomponenter (ikke styrt)

| Komponent | Status |
|-----------|--------|
| Kolber 10 kW (på VP inngang, 10 L tank) | Ingen styring i dag, mulig via relé K3 senere |
| Intern sirkulasjonspumpe | Følger VP automatisk |

## Referansedokumentasjon

- [docs/SM-WHMXC09G3E5_WH-MXC12G6E5.pdf](docs/SM-WHMXC09G3E5_WH-MXC12G6E5.pdf) — Servicemanual for varmepumpen
- [docs/CZ-TAW1-OI-1.pdf](docs/CZ-TAW1-OI-1.pdf) — CZ-TAW1 nettverksadapter (ikke kompatibel)
