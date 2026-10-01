# Altium exports (drop-in)

This project has **no Altium preview cache**, and the PCB is stored in Altium's
binary primitive format, so the schematic/layout imagery cannot be recovered
from the source files alone. Authentic exports go in this folder.

## What to export from Altium Designer

With `Smart Bike Theft Tracker (...).PrjPcb` open:

| Export | How | Save here as |
|---|---|---|
| Top hierarchy sheet | `File → Smart PDF` (or right-click sheet → *Export → Image*) | `schematic-top.png` |
| MCU sheet | same | `schematic-mcu.png` |
| GyroSense sheet | same | `schematic-gyrosense.png` |
| GPS sheet | same | `schematic-gps.png` |
| BatteryCharger sheet | same | `schematic-power.png` |
| PCB top layer | `File → Export → Image` / *Smart PDF*, Top Layer only | `pcb-layout-top.png` |
| PCB bottom layer | same, Bottom Layer only | `pcb-layout-bottom.png` |
| PCB 3D render | `View → 3D Layout Mode`, then `File → Export → Image` (PNG, ≥2000 px) | `pcb-3d.png` |

Optional extras (nice to have):
- `pcb-layout-all.png` — all layers / composite view
- `pcb-3d-iso.png` — the isometric 3D view
- `Group11_BOM_altium.csv` — `Reports → Bill of Materials`

## Notes

- PNG at ~2000 px wide is ideal so text stays legible on GitHub.
- The final project is a **4-layer** board; a layer-stack screenshot
  (`pcb-stackup.png`) is a welcome bonus for the RF section.
- Once these files are in place, `README.md` will reference them directly.
