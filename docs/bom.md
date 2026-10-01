# Bill of materials & component rationale

Group 11 — **Smart Bike Theft Tracker** (GPS + LoRaWAN, ultra-low power).

An Altium-style BOM is generated automatically from the schematics:
[`../hardware/Group11_BOM.csv`](../hardware/Group11_BOM.csv)
(`python3 analysis/extract_bom.py`).

## Power / charger sheet — `BatteryCharger.SchDoc`

| Ref | Value | Part / description | Why |
|---|---|---|---|
| U1 | — | **MCP73831T-2ACI/OT** Li-Ion charger (SOT-23-5) | Single-cell 4.2 V charger with status output and programmable current |
| U2 | — | **TPS63001DRCR** buck-boost, 3.3 V | Regulates across the full LiPo range (1.8 V min input) at high efficiency |
| L1 | 2.2 µH | **TDK VLS4012ET-2R2M**, 2.2 A | Buck-boost inductor from the TPS63001 reference design |
| USB1 | — | **USB4125-GF-A-0190** USB Type-C receptacle, 6P | Primary 5 V input, USB-C for EU compliance |
| R1, R2 | 5.1 kΩ | 0603 | USB-C CC1/CC2 pull-downs (sink advertisement) |
| D3 | SMAJ5.0A | TVS diode | Input ESD / overvoltage protection |
| SW2 | — | **500SSP1S1M2QEA** slide switch (SPDT, On-On) | ARMED / DISARMED user control (polled by MCU GPIO) |
| D1 | 598-8110-107F | Red 0805 LED | Charge-status indicator |
| R3 | 140 Ω | 0603 | Status LED series resistor |
| R4, R5 | 1.05 kΩ / 100 Ω | 0603 | Slide-switch / feedback network |
| C1, C2 | 4.7 µF | 0603 MLCC | Charger input/output capacitors (datasheet values) |
| C3, C5, C6 | 10 µF | 0603 MLCC | Buck-boost input/output capacitors |
| C4 | 100 nF | 0603 MLCC | High-frequency decoupling |
| BAT1 | — | **JST `B2B-XH-A`** battery connector | Standard 2-pin LiPo connection |
| — | 1900 mAh | **Jauch LP605060JU** protected LiPo (with PCM) | Fits the board outline; integrated protection circuit module |

## MCU sheet — `MCU.SchDoc`

| Ref | Value | Part / description | Why |
|---|---|---|---|
| U3 | — | **STM32WL5MOCH6TR** (STM32WL5M) | Cortex-M4 + M0+ with **integrated LoRaWAN radio**, matching network and oscillators → no external RF matching or crystals |
| J1 | — | **SMA-J-P-H-ST-EM1** edge-mount SMA | LoRa antenna connector for the `ANT-SS900` antenna |
| SW1 | — | **TL3301AF160QG** tactile switch | User / reset button |
| L2 | 0 Ω | Inductor position, **DNP** | Populated as a 0 Ω link — "not necessary" per design note |
| R6, R7 | 4.7 kΩ | 0603 | I²C / boot pull-ups |
| C7 | 1 µF | X7R 0603 | Bulk decoupling |
| C8, C9 | — | 0603 MLCC | Decoupling |

## GyroSense sheet — `GyroSense.SchDoc`

| Ref | Value | Part / description | Why |
|---|---|---|---|
| U6 | — | **ADXL345BCCZ-RL7** | 3-axis accelerometer with **motion interrupt** that wakes the MCU from deep sleep; 3 × 5 mm, FIFO, tap/activity/inactivity/free-fall |
| R11 | 4.7 kΩ | 0603 | I²C pull-up |
| C_A1 | 0.1 µF | 0603 MLCC | Decoupling |
| C_A2 | 10 µF | 0603 MLCC | Bulk decoupling |

## GPS sheet — `GPS.SchDoc`

| Ref | Value | Part / description | Why |
|---|---|---|---|
| U5 | — | **NEO-6M-0-001** GPS module | UART NMEA output, compact (16 × 12.2 × 2.4 mm), 2.7–3.6 V |
| J2 | — | **A-1JB** U.FL / AMC connector | GPS antenna feed (50 Ω) |
| BAT2 | — | Coin-cell retainer (`2998`) | Backup cell keeps RTC/ephemeris for a **hot start** |
| D2 | STPS0540Z | Schottky rectifier | Backup-battery ORing / reverse protection |
| Q5 | CSD13381F4 | N-channel MOSFET (3-PicoStar) | **Power gating** of the GPS rail to save energy |
| D4 | LTST-C171KGKT | Green LED | GPS fix / status indication |
| L3 | 27 nH | LQG18HN27NJ00D chip inductor | RF bias/choke for the antenna path |
| R8, R9, R10 | 1 kΩ / 3.3 kΩ / 22 Ω | 0603 | LED, UART and RF series resistors |
| C10 | 1 µF | 0603 MLCC | Decoupling |

## Notes

- **U3** is a multi-part schematic symbol (three units: MCU core, radio and
  power/RF); it is one physical component, so the generated CSV collapses the
  units to a single line.
- The block diagram also shows a `24AA32A` EEPROM inside the GPS block as a
  possible configuration store; it is **not** populated in the schematic, so it
  is omitted from the BOM.
- All RF parts and the RF feeds were chosen together: 50 Ω controlled-impedance
  coplanar waveguide with ground on a 4-layer stack (see
  [`../docs/system-design.md`](../docs/system-design.md)).
