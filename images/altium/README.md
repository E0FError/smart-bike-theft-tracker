# Altium exports

High-resolution images exported from Altium Designer for the **Smart Bike Theft
Tracker** (DTU 34374 final project, Group 11).

| File | Contents |
|---|---|
| `schematic-top.png` | Top-level hierarchy (4 sheet symbols + harness ports) |
| `schematic-power.png` | `BatteryCharger.SchDoc` — USB-C, MCP73831, TPS63001 |
| `schematic-mcu.png` | `MCU.SchDoc` — STM32WL5MOCH6TR + LoRa SMA |
| `schematic-gyrosense.png` | `GyroSense.SchDoc` — ADXL345 |
| `schematic-gps.png` | `GPS.SchDoc` — NEO-6M + U.FL + backup cell |
| `pcb-layout-top.png` | PCB top-copper layer |
| `pcb-3d.png` | Isometric 3D render of the assembled board |

These were derived as follows:

- The five schematic images were rendered from
  `hardware/Smart_Bike_Theft_Tracker_Schematics.pdf` (one page per sheet) with
  `pdftoppm -r 200`.
- `pcb-3d.png` was produced from the STEP model
  (`hardware/Smart_Bike_Theft_Tracker.step`) by
  [`../../tools/render_step_3d.py`](../../tools/render_step_3d.py) — Open CASCADE
  tessellation via **gmsh**, then a shaded orthographic render with matplotlib.
  No screenshot was needed.
- `pcb-layout-top.png` is an Altium layer export.

The native sources (`.SchDoc`, `.PcbDoc`, `.step`, schematic PDF) live in
[`../../hardware/`](../../hardware/).
