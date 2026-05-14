# GeoLoop — Koblingsskjema

Komplett koblingsguide for Raspberry Pi 3B+, RPi Relay Board og DS18B20-temperatursensorer.

---

## Komponentoversikt og plassering

```
┌─────────────────────────────────────────────────────────────┐
│              Elektrikkskap / Teknisk rom                     │
│                                                             │
│  ┌──────────────┐    ┌─────────────────────────────────┐   │
│  │ Open-Smart   │    │       RPi Relay Board (HAT)      │   │
│  │ GPIO         │    │  ┌──────┐ ┌──────┐ ┌──────┐    │   │
│  │ Expansion    │    │  │ K1   │ │ K2   │ │ K3   │    │   │
│  └──────┬───────┘    │  │ VP   │ │Pumpe │ │Ledig │    │   │
│         │            │  └──┬───┘ └──┬───┘ └──────┘    │   │
│  ┌──────┴───────────────────────────────────────────┐  │   │
│  │            Raspberry Pi 3B+                      │  │   │
│  │               (under relay board-et)             │  │   │
│  └─────────────────────────────────────┬────────────┘  │   │
│                                        │               │   │
│                               USB 5V/2.5A PSU          │   │
└────────────────────────────────────────────────────────┘   │
                 │K1              │K2
                 ▼                ▼
         VP klemme 17/18   Sirkulasjonspumpe (230V)
```

---

## Del 1 — DS18B20 Temperatursensorer (1-Wire, GPIO4)

Alle 5 sensorer kobles **parallelt** på samme tre ledere. Bruker Open-Smart GPIO Expansion Board for tilgang til GPIO4 siden relay board-HAT dekker over hoved-GPIO-headeren.

```
Open-Smart GPIO Expansion Board
         │
         ├─── 3.3V (pin 1 på RPi header)
         │         │
         │         ├── VDD ── DS18B20 T1 (Sløyfe inn)   ─── rød ledning
         │         ├── VDD ── DS18B20 T2 (Sløyfe ut)    ─── rød ledning
         │         ├── VDD ── DS18B20 T3 (VP inn)        ─── rød ledning
         │         ├── VDD ── DS18B20 T4 (VP ut)         ─── rød ledning
         │         └── VDD ── DS18B20 T5 (Tank)          ─── rød ledning
         │
         ├─── GND  (pin 6 på RPi header)
         │         │
         │         ├── GND ── DS18B20 T1  ─── svart ledning
         │         ├── GND ── DS18B20 T2  ─── svart ledning
         │         ├── GND ── DS18B20 T3  ─── svart ledning
         │         ├── GND ── DS18B20 T4  ─── svart ledning
         │         └── GND ── DS18B20 T5  ─── svart ledning
         │
         └─── GPIO4 (pin 7 på RPi header)
                   │
                   ├─ [4,7 kΩ] ─── 3.3V   ← pull-up-motstand (1 stk)
                   │
                   ├── DATA ── DS18B20 T1  ─── gul ledning
                   ├── DATA ── DS18B20 T2  ─── gul ledning
                   ├── DATA ── DS18B20 T3  ─── gul ledning
                   ├── DATA ── DS18B20 T4  ─── gul ledning
                   └── DATA ── DS18B20 T5  ─── gul ledning
```

### DS18B20 ledningsfarge (standard vanntett rørføler)

| Ledning | Farge  | Kobles til          |
|---------|--------|---------------------|
| VDD     | Rød    | 3.3V                |
| GND     | Svart  | GND                 |
| DATA    | Gul    | GPIO4 (+ pull-up)   |

> **Pull-up:** Monter 4,7 kΩ motstanden mellom GPIO4 og 3.3V, én gang, uavhengig av antall sensorer. Bruk gjerne et lite breadboard eller lodd den direkte i kabelskjøten.

---

## Del 2 — RPi Relay Board (HAT) og GPIO-pinner

RPi Relay Board sitter direkte på Raspberry Pi 3B+ sin 40-pins GPIO-header (HAT-format). GeoLoop bruker disse pinnene:

| Kanal | Funksjon           | BCM GPIO | Fysisk pin | Active High |
|-------|--------------------|----------|------------|-------------|
| K1    | Varmepumpe ON/OFF  | GPIO 26  | Pin 37     | Ja (HIGH=PÅ)|
| K2    | Sirkulasjonspumpe  | GPIO 20  | Pin 38     | Ja (HIGH=PÅ)|
| K3    | Ledig (reserve)    | GPIO 21  | Pin 40     | Ja (HIGH=PÅ)|

> **Viktig:** Dobbeltsjekk mot databladet for ditt spesifikke relay board at K1=GPIO26, K2=GPIO20, K3=GPIO21 stemmer. GPIO-tilordningen varierer mellom produsenter.

### RPi 40-pins GPIO-header (utvalgte pinner)

```
                    RPi 40-pin GPIO-header
                    ┌─────────────────────┐
              3.3V  │  1 │  2 │  5V       │
              SDA   │  3 │  4 │  5V       │
              SCL   │  5 │  6 │  GND  ◄── sensor GND
  sensor DATA ──── GPIO4│  7 │  8 │  TX       │
              GND   │  9 │ 10 │  RX       │
                    │ 11 │ 12 │  GPIO18   │
                    │ 13 │ 14 │  GND      │
                    │ 15 │ 16 │  GPIO23   │
  sensor 3.3V ──── 3.3V │ 17 │ 18 │  GPIO24   │
                    │ 19 │ 20 │  GND      │
                    │ 21 │ 22 │  GPIO25   │
                    │ 23 │ 24 │  GPIO8    │
                    │ 25 │ 26 │  GPIO7    │
                    │ 27 │ 28 │           │
                    │ 29 │ 30 │  GND      │
                    │ 31 │ 32 │           │
                    │ 33 │ 34 │  GND      │
                    │ 35 │ 36 │           │
  K1 (VP) ──── GPIO26│ 37 │ 38 │  GPIO20 ──── K2 (Pumpe)
              GND   │ 39 │ 40 │  GPIO21 ──── K3 (Ledig)
                    └─────────────────────┘
```

---

## Del 3 — Relé K1: Varmepumpe (Panasonic WH-MXC12G6E5)

Klemme 17/18 er en **lavspenning potensialfri kontakt** — ingen 230V, trygt å koble selv.

```
Panasonic WH-MXC12G6E5             RPi Relay Board
Innvendig klemmerekke               Kanal 1 (K1)
┌────────────────────┐              ┌──────────────────┐
│                    │              │                  │
│  Klemme 17 ────────┼──────────────┤ NO  (Normally    │
│                    │              │      Open)       │
│  Klemme 18 ────────┼──────────────┤ COM (Common)     │
│                    │              │                  │
│  [Fabrikkjumper]   │              │  GPIO26 styrer   │
│   fjernes!         │              └──────────────────┘
└────────────────────┘

Relé LUKKET (GPIO26=HIGH) → 17 og 18 kortsluttet → VP starter
Relé ÅPENT  (GPIO26=LOW)  → 17 og 18 brutt       → VP stopper
```

**Steg:**
1. Slå av varmepumpen på strømbryteren
2. Åpne VP-ens deksel (servicemanual side 14)
3. Finn klemmerekken — klemme 17 og 18 er merket
4. **Fjern fabrikkjumperen** mellom klemme 17 og 18
5. Koble to ledere (0,5–1,5 mm²) fra klemme 17 → NO og klemme 18 → COM på relay board K1
6. Lukk dekselet og slå på strøm igjen

---

## Del 4 — Relé K2: Sirkulasjonspumpe (230V)

> ⚠️ **230V — utføres av fagperson eller person med nødvendig kompetanse.**

Sirkulasjonspumpen styres ved å bryte/slutte faseleder (L). Nøytral (N) og jord (PE) kobles direkte.

```
230V-kilde (sikringsskap)           RPi Relay Board
                                    Kanal 2 (K2)
L (fase) ───────────────────────── COM
                                    NO ──────────── Pumpe L-inn
N (nøytral) ─────────────────────────────────────── Pumpe N-inn
PE (jord) ───────────────────────────────────────── Pumpe PE

Relé LUKKET (GPIO20=HIGH) → L koblet til pumpe → Pumpe PÅ
Relé ÅPENT  (GPIO20=LOW)  → L brutt             → Pumpe AV
```

**Krav til relay board:**
- Må tåle minst 250V AC, 10A (typisk 16A anbefalt)
- Bruk kabel av rett tverrsnitt for pumpeeffekten (minimum 1,5 mm²)

---

## Del 5 — Sensorplassering i anlegget

```
        VP-krets                              Bakkesløyfe-krets

 ┌──────────────────┐                  ┌──────────────────────────┐
 │   Varmepumpe     │                  │   Bakkeløyfe             │
 │  WH-MXC12G6E5   │                  │   8 sløyfer × 112 m      │
 └──┬────────────▲──┘                  └──┬──────────────────▲────┘
    │            │                        │                  │
   T4            │                       T1                 T2
 (VP ut)         │                  (Sløyfe inn)      (Sløyfe ut)
    │       ┌────┴──────┐                │                  │
    │       │ Kolbetank │                │                  │
    │       │ 10 L      │                │                  │
    │       │ 10 kW     │                │                  │
    │       └────▲──────┘                │                  │
    │            │                       │                  │
    │           T3                       │                  │
    │       (VP inn)                     │                  │
    │            │                       │                  │
    ▼            │                       ▼                  │
 ┌──────────────────────────────────────────────────────────┴────┐
 │                     Buffertank 200 L                          │
 │                     T5 — tankføler (VP klemme 15/16)         │
 └───────────────────────────────────────────────────────────────┘
```

| Sensor | Navn i config   | Plassering (monter her)                          |
|--------|-----------------|--------------------------------------------------|
| T1     | `loop_inlet`    | Rørfølger på røret fra tank **inn** til bakke    |
| T2     | `loop_outlet`   | Rørfølger på røret fra bakke **tilbake** til tank|
| T3     | `hp_inlet`      | Rørfølger på returrøret **inn** til varmepumpen  |
| T4     | `hp_outlet`     | Rørfølger på turrøret **ut** av varmepumpen      |
| T5     | `tank`          | Følger festet ved VP klemme 15/16 (tanktemperatur)|

> **Montering:** Bruk rørklips eller isoleringsbånd for å feste sensoren mot røret. Legg varmeisolasjon over for riktig avlesning.

---

## Del 6 — Fullstendig GPIO-oppsummering

| Signal         | BCM GPIO | Fysisk pin | Tilkobling                        |
|----------------|----------|------------|-----------------------------------|
| 1-Wire data    | GPIO 4   | Pin 7      | DS18B20 DATA + 4,7 kΩ pull-up    |
| Relé K1 (VP)   | GPIO 26  | Pin 37     | VP klemme 17/18                   |
| Relé K2 (pumpe)| GPIO 20  | Pin 38     | Sirkulasjonspumpe (230V via relé) |
| Relé K3 (ledig)| GPIO 21  | Pin 40     | Ikke i bruk                       |
| 3.3V           | —        | Pin 1, 17  | DS18B20 VDD + pull-up motstand   |
| GND            | —        | Pin 6, 9…  | DS18B20 GND                       |
