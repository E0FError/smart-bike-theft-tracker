#!/usr/bin/env python3
"""
power_budget.py
===============
Power-budget and battery-life analysis for the **Smart Bike Theft Tracker**
(GPS + LoRaWAN, ultra-low power).  Reproduces the numbers in section 6 of the
design report and the LDO-vs-SMPS comparison from section 4.

Three operating states are modelled:
    SLEEP    parked, armed, no movement  (MCU standby, GPS backup, accel LPM)
    GPS_FIX  theft detected, acquiring a fix (hot start)
    LORA_TX  transmitting the alert + coordinates

The script prints the tables and writes ``images/power-budget.png``.
Standard library only.
"""

from __future__ import annotations

import json
import os

# --------------------------------------------------------------------------
# Design inputs
# --------------------------------------------------------------------------
VBAT_NOM = 3.6          # [V]  nominal single-cell LiPo voltage
VBAT_MIN = 3.0          # [V]  minimum usable cell voltage
VRAIL = 3.3             # [V]  regulated system rail
BATTERY_MAH = 1900.0    # [mAh] Jauch LP605060JU (with PCM)
PEAK_CURRENT_MA = 74.0  # [mA] worst-case total (MCU + accel + GPS)

# Per-component current draw [mA] in each state (report table 6.1)
COMPONENTS = {
    #                  SLEEP     GPS_FIX   LORA_TX
    "MCU":           (0.000125,   1.1,      1.1),
    "GPS":           (11.0,      47.0,     11.0),
    "Backup battery": (0.879,     0.0,      0.0),
    "Accelerometer": (0.030,      0.030,    0.030),
}

# SMPS output current and efficiency per state (TPS63001)
SMPS = {
    "SLEEP":   {"iout_ma": 12.0, "eff": 0.75},
    "GPS_FIX": {"iout_ma": 48.0, "eff": 0.85},
    "LORA_TX": {"iout_ma": 12.0, "eff": 0.75},
}

# Time assumptions for a theft day
TIME_SLEEP_H = 24.0
TIME_GPS_FIX_MIN = 1.0


# --------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------


def battery_discharge(state: str) -> float:
    """Battery current [mA] needed to supply the SMPS in a given state."""
    s = SMPS[state]
    return VRAIL * s["iout_ma"] / (s["eff"] * VBAT_NOM)


def budget() -> dict:
    states = ["SLEEP", "GPS_FIX", "LORA_TX"]
    discharge = {s: battery_discharge(s) for s in states}

    sleep_ma = round(discharge["SLEEP"], 1)
    gps_ma = round(discharge["GPS_FIX"], 1)
    daily_mah = sleep_ma * TIME_SLEEP_H + gps_ma * (TIME_GPS_FIX_MIN / 60.0)
    life_days = BATTERY_MAH / daily_mah

    # component sum (excluding SMPS line, which is the aggregate)
    comp_sum = {s: sum(v[i] for v in COMPONENTS.values())
                for i, s in enumerate(states)}

    return {
        "states": states,
        "components_mA": {k: dict(zip(states, v)) for k, v in COMPONENTS.items()},
        "component_sum_mA": comp_sum,
        "smps": SMPS,
        "battery_discharge_mA": discharge,
        "daily_mAh": daily_mah,
        "battery_mAh": BATTERY_MAH,
        "battery_life_days": life_days,
    }


def ldo_vs_smps() -> dict:
    """Section 4 comparison of an MCP1700 LDO with the TPS63001 buck-boost."""
    ldo_dropout = 0.350
    ldo_vout_tol = 0.03
    ldo_vin_min = VRAIL * (1 + ldo_vout_tol) + ldo_dropout
    ldo_loss_mw = (ldo_vin_min - VRAIL) * PEAK_CURRENT_MA
    ldo_iq_ua = 4.0

    smps_eff = 0.90
    pout_mw = VRAIL * PEAK_CURRENT_MA
    smps_loss_mw = pout_mw * (1 / smps_eff - 1)
    smps_iq_ua = 51.5
    smps_vin_min = 1.8

    return {
        "ldo": {"part": "MCP1700", "vin_min_V": ldo_vin_min,
                "loss_mW": ldo_loss_mw, "iq_uA": ldo_iq_ua},
        "smps": {"part": "TPS63001", "vin_min_V": smps_vin_min,
                 "loss_mW": smps_loss_mw, "iq_uA": smps_iq_ua},
        "vbat_min_V": VBAT_MIN,
        "pout_mW": pout_mw,
    }


def print_report(b: dict, c: dict) -> None:
    states = b["states"]
    print("=" * 72)
    print(" Smart Bike Theft Tracker - power budget")
    print("=" * 72)
    print(f" Battery: Jauch LP605060JU  {b['battery_mAh']:.0f} mAh (with PCM)"
          f"   Vnom={VBAT_NOM} V   Vmin={VBAT_MIN} V")
    print("-" * 72)
    hdr = f" {'Component':18}" + "".join(f"{s:>14}" for s in states)
    print(hdr)
    for name, vals in b["components_mA"].items():
        print(f" {name:18}" + "".join(f"{vals[s]:>11.3f} mA" for s in states))
    print("-" * 72)
    print(" SMPS output".ljust(19) +
          "".join(f"{b['smps'][s]['iout_ma']:>11.1f} mA" for s in states))
    print(" SMPS efficiency".ljust(19) +
          "".join(f"{b['smps'][s]['eff']*100:>11.0f} %" for s in states))
    print(" Battery discharge".ljust(19) +
          "".join(f"{b['battery_discharge_mA'][s]:>11.1f} mA" for s in states))
    print("-" * 72)
    print(f" Daily energy : {b['battery_discharge_mA']['SLEEP']:.1f} mA x "
          f"{TIME_SLEEP_H:.0f} h + {b['battery_discharge_mA']['GPS_FIX']:.1f} mA x "
          f"{TIME_GPS_FIX_MIN:.0f} min = {b['daily_mAh']:.1f} mAh/day")
    print(f" Battery life : {b['battery_mAh']:.0f} / {b['daily_mAh']:.1f} = "
          f"{b['battery_life_days']:.2f} days")
    print("-" * 72)
    print(" LDO vs SMPS (peak load {:.0f} mA):".format(PEAK_CURRENT_MA))
    l, s = c["ldo"], c["smps"]
    print(f"   {l['part']:10} LDO  : Vin,min={l['vin_min_V']:.3f} V  "
          f"loss={l['loss_mW']:.2f} mW  Iq={l['iq_uA']:.1f} uA")
    print(f"   {s['part']:10} SMPS : Vin,min={s['vin_min_V']:.1f} V  "
          f"loss={s['loss_mW']:.2f} mW  Iq={s['iq_uA']:.1f} uA")
    print(f"   -> LDO needs Vin >= {l['vin_min_V']:.2f} V, above a LiPo cell's "
          f"usable {VBAT_MIN:.1f} V -> choose the SMPS")
    print("=" * 72)


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


def plot_budget(b: dict, out_svg: str) -> None:
    W, H = 1280, 720
    pad = {"l": 110, "r": 60, "t": 110, "b": 90}
    pw, ph = W - pad["l"] - pad["r"], H - pad["t"] - pad["b"]
    states = b["states"]
    vals = [b["battery_discharge_mA"][s] for s in states]
    ymax = 60

    def sx(i): return pad["l"] + (i + 0.5) * pw / len(states)
    def sy(v): return pad["t"] + (ymax - v) / ymax * ph

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
             f'<text x="{W/2}" y="46" font-family="Helvetica,Arial,sans-serif" '
             f'font-size="24" font-weight="bold" text-anchor="middle">'
             f'Battery discharge current by operating state</text>',
             f'<text x="{W/2}" y="74" font-family="Helvetica,Arial,sans-serif" '
             f'font-size="15" text-anchor="middle" fill="#555">'
             f'3.3 V rail through the TPS63001 buck-boost, V_BAT = {VBAT_NOM} V</text>']

    for v in range(0, ymax + 1, 10):
        y = sy(v)
        parts.append(f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{W-pad["r"]}" '
                     f'y2="{y:.1f}" stroke="#e8e8e8"/>')
        parts.append(f'<text x="{pad["l"]-12}" y="{y+5:.1f}" '
                     f'font-family="Helvetica,Arial,sans-serif" font-size="13" '
                     f'text-anchor="end">{v}</text>')
    parts.append(f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" '
                 f'y2="{H-pad["b"]}" stroke="#555" stroke-width="1.6"/>')
    parts.append(f'<line x1="{pad["l"]}" y1="{H-pad["b"]}" x2="{W-pad["r"]}" '
                 f'y2="{H-pad["b"]}" stroke="#555" stroke-width="1.6"/>')
    parts.append(f'<text x="{W/2}" y="{H-16}" font-family="Helvetica,Arial,sans-serif" '
                 f'font-size="15" font-weight="bold" text-anchor="middle">'
                 f'Operating state</text>')
    parts.append(f'<text x="24" y="{H/2}" font-family="Helvetica,Arial,sans-serif" '
                 f'font-size="15" font-weight="bold" text-anchor="middle" '
                 f'transform="rotate(-90 24 {H/2})">Battery current  [mA]</text>')

    labels = {"SLEEP": "Sleep", "GPS_FIX": "GPS fix", "LORA_TX": "LoRa TX"}
    colors = {"SLEEP": "#2e8b57", "GPS_FIX": "#c0392b", "LORA_TX": "#1f5fbf"}
    bw = pw / len(states) * 0.45
    for i, s in enumerate(states):
        v = vals[i]
        x = sx(i) - bw / 2
        y = sy(v)
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" '
                     f'height="{H-pad["b"]-y:.1f}" fill="{colors[s]}" rx="4"/>')
        parts.append(f'<text x="{sx(i):.1f}" y="{y-12:.1f}" '
                     f'font-family="Helvetica,Arial,sans-serif" font-size="17" '
                     f'font-weight="bold" text-anchor="middle" fill="{colors[s]}">'
                     f'{v:.1f} mA</text>')
        parts.append(f'<text x="{sx(i):.1f}" y="{H-pad["b"]+26:.1f}" '
                     f'font-family="Helvetica,Arial,sans-serif" font-size="15" '
                     f'text-anchor="middle">{labels[s]}</text>')

    parts.append(
        f'<text x="{W-pad["r"]}" y="{pad["t"]+26}" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="15" text-anchor="end" fill="#333">'
        f'Daily energy = {b["daily_mAh"]:.1f} mAh/day    \u2022    '
        f'Battery life = {b["battery_life_days"]:.1f} days</text>')
    parts.append("</svg>\n")
    open(out_svg, "w").write("\n".join(parts))


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    b = budget()
    c = ldo_vs_smps()
    print_report(b, c)
    data = {"power_budget": b, "ldo_vs_smps": c}
    with open(os.path.join(here, "power_budget.json"), "w") as fh:
        json.dump(data, fh, indent=2)
    img = os.path.join(root, "images")
    os.makedirs(img, exist_ok=True)
    plot_budget(b, os.path.join(img, "power-budget.svg"))
    print(f"\nWrote images/power-budget.svg")


if __name__ == "__main__":
    main()
