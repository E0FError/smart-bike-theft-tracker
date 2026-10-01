# Smart Bike Theft Tracker — GPS + LoRaWAN, Ultra-Low Power

![Course](https://img.shields.io/badge/DTU-34374%20IoT%20Hardware%20%26%20PCB%20Design-blue)
![MCU](https://img.shields.io/badge/MCU-STM32WL5M%20%2B%20LoRaWAN-important)
![PCB](https://img.shields.io/badge/PCB-4--layer%2C%2050%20%CE%A9%20RF-orange)
![Battery](https://img.shields.io/badge/battery%20life-~5.4%20days%20worst%20case-green)
![Type](https://img.shields.io/badge/type-course%20project-lightgrey)

A complete, analysis-driven hardware design for an **anti-bike-theft tracker**:
an ultra-low-power device that sleeps until an accelerometer detects movement,
then acquires its position with GPS and transmits an alert with coordinates over
**LoRaWAN**. The design covers everything the brief demanded — a deep-sleep MCU,
a full battery/charger/regulator power tree, motion sensing, GPS, RF layout and
a quantified **power budget**.

![System block diagram](images/system-block-diagram.jpg)

> **Group 11 — co-designed.** This was the two-person final project for the DTU
> course *34374 IoT Hardware and PCB Design*, built with
> **Louis Sønderby Pelletier**. The report is included in
> [`docs/`](docs/Group11_Final_Project_Report.pdf).

---

## What I worked on

The project was a full two-person collaboration. From the report's group
contribution table, my (**Finn Oskar Grabbe**) primary ownership was:

| Area | My contribution |
|---|---|
| Accelerometer | Component choice + `GyroSense` schematic + layout |
| GPS | Component choice + `GPS` schematic + layout |
| PCB layout | Board layout (placement, routing, RF feeds) |

Louis led the introduction/architecture, the MCU and power-supply component
choices, the power design and the power budget, plus the power/MCU schematics
and layout. Everything was reviewed together.

---

## Design at a glance

| Parameter | Value |
|---|---|
| Application | Bike theft tracker: motion → GPS fix → LoRaWAN alert |
| MCU + radio | **STM32WL5MOCH6TR** (Cortex-M4 + M0+, integrated LoRaWAN, no external crystals/matching) |
| Motion sensor | **ADXL345BCCZ-RL7** 3-axis accelerometer, interrupt to MCU `WKUP1` |
| GPS | **u-blox NEO-6M-0-001** (UART NMEA) + U.FL antenna + backup cell |
| LoRa antenna | SMA edge launch (`SMA-J-P-H-ST-EM1`) for an `ANT-SS900` |
| Arming | 2-position slide switch (`500SSP1S1M2QEA`) on an MCU GPIO |
| Charger | **MCP73831T-2ACI/OT** from USB-C |
| Battery | **Jauch LP605060JU**, 1900 mAh LiPo with protection (PCM) |
| Regulator | **TPS63001** buck-boost → 3.3 V (chosen over an LDO) |
| Peak current | ≈ 74 mA (MCU 7 mA + accelerometer 0.14 mA + GPS 67 mA) |
| Battery life | **≈ 5.4 days** worst case; ≈ weekly charging in practice |
| PCB | 4-layer FR-4, ≈ 57 × 41 mm, 50 Ω controlled-impedance RF |

---

## 1. System architecture

Four functional blocks map directly onto the hierarchical schematic:

| Sheet | Block | Key parts |
|---|---|---|
| `Top.SchDoc` | Hierarchy | `U_GPS`, `U_GyroSense`, `U_MCU`, `U_BatteryCharger` |
| `BatteryCharger.SchDoc` | Power | MCP73831 charger, TPS63001 buck-boost, USB-C, JST, slide switch |
| `MCU.SchDoc` | Compute + radio | STM32WL5MOCH6TR, LoRa SMA, decoupling |
| `GyroSense.SchDoc` | Motion | ADXL345, I²C pull-up, decoupling |
| `GPS.SchDoc` | Positioning | NEO-6M, U.FL antenna, backup cell, load-switch gating |

### Operation

1. **Sleep** — ARMED, no movement. MCU standby ≈ 125 nA; GPS in power-save with
   the backup domain alive; accelerometer at a low ODR.
2. **Wake** — the ADXL345 pulls its interrupt to the MCU. The MCU checks the
   slide switch: DISARMED → back to standby, ARMED → continue.
3. **GPS fix** — the GPS rail is enabled and NMEA is read over UART. The backup
   cell makes this a **hot start**.
4. **LoRa TX** — coordinates are transmitted as a LoRaWAN alert; the system
   returns to sleep.

---

## 2. Component choices

### MCU + LoRaWAN — STM32WL5MOCH6TR
The decisive advantage is the **integrated LoRaWAN radio with in-package
matching network and oscillators** — no external RF matching, no crystals —
which shrinks the board and removes the most error-prone RF layout work. It
provides I²C/SPI/UART/ADC, interrupt wake pins and a very low standby current.
It costs more (≈ €12.43) than a €5–10 STM32, but the savings in board area,
design risk and complexity justify it, and STM's documentation is excellent.

### Motion — ADXL345BCCZ-RL7
A 3-axis, 3 × 5 mm accelerometer with built-in **activity/inactivity, tap and
free-fall** detection and a FIFO. Its interrupt output drives the MCU wake pin
(`WKUP1`/`PA0`), so the system never has to poll — this is what makes the
sub-milliamp sleep budget achievable.

### GPS — u-blox NEO-6M-0-001
A self-contained receiver with a **simple UART interface** (9600 bps NMEA),
16 × 12.2 × 2.4 mm and 2.7–3.6 V. It offloads all navigation processing from
the host. The trade-off, called out in the report, is that the NEO-6 family is
**End-of-Life** — acceptable for this design because a current u-blox module is a
drop-in pin-compatible upgrade. A **backup coin cell** (`STPS0540Z` + retainer)
enables a fast hot start at the moment of theft.

### Power — MCP73831 charger, Jauch protected LiPo, TPS63001 regulator
- **MCP73831T-2ACI/OT**: single-cell 4.2 V Li-Ion/LiPo charger with a status
  output, from a USB-C receptacle (`USB4125-GF-A-0190`) with 5.1 kΩ CC pulldowns.
- **Jauch LP605060JU**, 1900 mAh, with an integrated **protection circuit
  module** — the design's stated battery-protection assumption and a size match
  for the board.
- **TPS63001 buck-boost** for 3.3 V — see below.

Full parts list: [`docs/bom.md`](docs/bom.md) ·
[`hardware/Group11_BOM.csv`](hardware/Group11_BOM.csv).

---

## 3. Power design — why a buck-boost, not an LDO

The brief required an explicit LDO-vs-SMPS comparison. An **MCP1700 LDO** was
evaluated against the **TPS63001 buck-boost** at the 74 mA peak load:

| | MCP1700 (LDO) | TPS63001 (buck-boost) |
|---|---|---|
| Minimum input | 3.3 V·1.03 + 0.35 V = **3.749 V** | **1.8 V** |
| Loss at 74 mA | 33.2 mW | 27.1 mW (η ≈ 90 %) |
| Quiescent current | **4 µA** | 51.5 µA |
| Complexity | 2 capacitors | inductor + more passives |

The LDO has the better quiescent current and simplicity, **but its minimum input
of 3.75 V is higher than the usable voltage of a LiPo cell** (down to ~3.0 V),
so it cannot hold regulation across a full discharge. The buck-boost keeps
3.3 V from 1.8 V up, and is slightly more efficient. It was therefore selected:

$$
I_{in}=\frac{3.3\,\text{V}\times74\,\text{mA}}{0.8\times3.0\,\text{V}}=101.8\,\text{mA}
\quad\text{(well under the cell's 380 mA, 0.2 C rating)}
$$

![TPS63001 efficiency vs input voltage](images/tps63001-efficiency-vin.png)

---

## 4. Power budget & battery life

Three operating states were modelled, each component's draw taken from its
datasheet and referred to the battery through the SMPS efficiency:

| Component | Sleep | GPS fix | LoRa TX |
|---|---:|---:|---:|
| MCU | 125 nA | 1.1 mA | 1.1 mA |
| GPS | 11 mA | 47 mA | 11 mA |
| Backup battery | 879 µA | 0 mA | 0 mA |
| Accelerometer | 30 µA | 30 µA | 30 µA |
| SMPS output | 12 mA | 48 mA | 12 mA |
| **Battery discharge** | **14.7 mA** | **51.8 mA** | **14.7 mA** |

With one 1-minute hot-start fix per day:

$$
14.7\,\text{mA}\times24\,\text{h}+51.8\,\text{mA}\times\tfrac{1}{60}\,\text{h}
=353.7\ \tfrac{\text{mAh}}{\text{day}}
\;\Rightarrow\;
\text{Battery life}=\frac{1900}{353.7}=5.4\ \text{days}
$$

![Battery discharge current by state](images/power-budget.png)

This 5.4 days is the **worst case** (full-use); the tracker transmits only on an
actual alert, so it needs charging roughly **once a week**.

---

## 5. RF & PCB layout

The board is a **4-layer FR-4** design (≈ 57 × 41 mm). Both antenna feeds are
**50 Ω controlled-impedance coplanar waveguides with ground**, with via stitching
to confine the field and stabilise impedance.

![GPS antenna feed](images/rf-gps-antenna-feed.png)
![LoRa antenna feed](images/rf-lora-antenna-feed.png)

RF best practices applied:

- **LoRa** — straight feed to the edge-mounted SMA at 868/915 MHz.
- **GPS** — short **curved** feed to the U.FL connector at 1575.42 MHz; arcs
  avoid the impedance perturbation of 90° corners.
- **Continuous reference plane** beneath the RF traces (no splits).
- **Direct ground connections** on RF pads — thermal spokes add inductance.
- **No layer transitions** on the feeds — vias add parasitic inductance and
  reflections.

The 3.3 V rail is routed **star-style** from the regulator instead of
daisy-chaining loads, so transient currents do not create local supply dips:

![3.3 V power distribution](images/power-distribution.png)

---

## 6. Schematic & PCB

The complete Altium project (four hierarchical schematic sheets, harness
definitions, symbol/footprint libraries and the 4-layer PCB) is in
[`hardware/`](hardware/). High-resolution schematic and PCB images exported from
Altium are collected in [`images/altium/`](images/altium/); see that folder for
the export list. The tool [`tools/render_schdoc.py`](tools/render_schdoc.py)
can additionally render any sheet straight from a `.SchDoc` without Altium.

---

## 7. Repository contents

```
smart-bike-theft-tracker/
├── README.md
├── hardware/                              # Altium project (+ generated BOM)
│   ├── Smart Bike Theft Tracker (...).PrjPcb
│   ├── Top.SchDoc  BatteryCharger.SchDoc  MCU.SchDoc
│   ├── GyroSense.SchDoc  GPS.SchDoc  *.Harness
│   ├── Smart Bike Theft Tracker.PcbDoc    # 4-layer PCB
│   ├── Schlib1.SchLib  PcbLib1.PcbLib
│   └── Group11_BOM.csv
├── docs/
│   ├── Group11_Final_Project_Report.pdf   # the submitted report
│   ├── system-design.md                   # architecture + design rationale
│   └── bom.md
├── analysis/
│   ├── power_budget.py                    # states, LDO/SMPS, battery life
│   ├── extract_bom.py                     # SchDoc -> BOM CSV
│   └── power_budget.json
├── tools/
│   ├── render_schdoc.py                   # Altium SchDoc -> SVG renderer
│   └── altium_preview_to_png.py
└── images/
    ├── system-block-diagram.jpg  power-budget.png
    ├── rf-gps-antenna-feed.png   rf-lora-antenna-feed.png
    ├── power-distribution.png
    └── altium/                            # Altium exports (schematics, PCB)
```

## 8. Reproducing the analysis

No third-party packages are required:

```bash
python3 analysis/power_budget.py      # power budget, LDO/SMPS, battery life + figure
python3 analysis/extract_bom.py       # regenerate hardware/Group11_BOM.csv
python3 tools/render_schdoc.py hardware/MCU.SchDoc mcu.svg --title "MCU"
```

To inspect the hardware, open the `.PrjPcb` in **Altium Designer**.

## 9. References

- STMicroelectronics — STM32WL5M dual-core LoRaWAN module.
- Analog Devices — ADXL345 3-axis digital accelerometer.
- u-blox — NEO-6M GPS receiver.
- Microchip — MCP73831 charger; Texas Instruments — TPS63001 buck-boost.
- Course material: *34374 IoT Hardware and PCB Design*, Final Project brief, DTU.

---

### Attribution & academic use

DTU 34374 final project, Group 11 — Finn Oskar Grabbe & Louis Sønderby
Pelletier. Shared publicly for portfolio purposes. If you are taking the course,
please use it for reference only and produce your own work.
