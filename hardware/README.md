# Hardware sources (Altium Designer)

Altium Designer project for the **Smart Bike Theft Tracker**
(GPS + LoRaWAN, ultra-low power), Group 11.

| File | Contents |
|---|---|
| `Smart Bike Theft Tracker (GPS + LoRaWAN, Ultra-Low Power).PrjPcb` | Altium project — **open this file** |
| `Top.SchDoc` | Top-level hierarchy |
| `BatteryCharger.SchDoc` | USB-C, MCP73831 charger, TPS63001 buck-boost |
| `MCU.SchDoc` | STM32WL5MOCH6TR + LoRa antenna |
| `GyroSense.SchDoc` | ADXL345 accelerometer |
| `GPS.SchDoc` | NEO-6M GPS + antenna + power gating |
| `*.Harness` | Harness definitions for the sheet ports |
| `Smart Bike Theft Tracker.PcbDoc` | 4-layer PCB layout |
| `Schlib1.SchLib` / `PcbLib1.PcbLib` | Symbols and footprints |
| `Smart_Bike_Theft_Tracker_Schematics.pdf` | All schematic sheets, exported from Altium |
| `Smart_Bike_Theft_Tracker.step` | 3D STEP model of the assembled board |
| `Group11_BOM.csv` | BOM exported by `../analysis/extract_bom.py` |

## Opening the project

1. Open **Altium Designer**.
2. `File → Open` and select the `.PrjPcb` file above.
3. The four hierarchical sheets and the PCB load automatically.

## Notes

- The board is a **4-layer** stack; the RF feeds are 50 Ω controlled-impedance
  coplanar waveguides with ground (see the design notes).
- Altium artefacts (`__Previews/`, `History/`, `Project Logs*/`,
  `Project Outputs*/`) are excluded by `.gitignore` and regenerate on open.
- High-resolution schematic and PCB images exported from Altium live in
  [`../images/altium/`](../images/altium/).
