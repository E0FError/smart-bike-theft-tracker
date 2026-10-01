#!/usr/bin/env python3
"""
extract_bom.py
==============
Parse every ``*.SchDoc`` sheet of the Smart Bike Theft Tracker and emit a
bill of materials (CSV) plus a summary to stdout.

Altium links a component's pins, graphics, designator and comment through the
``OwnerIndex`` field, which is the **record position** of the component in the
sheet stream.  This script resolves that mapping and collects one row per
component per sheet.

Usage
-----
    python3 analysis/extract_bom.py hardware/Group11_BOM.csv
"""

from __future__ import annotations

import csv
import glob
import os
import re
import sys


def split_records(data: str) -> list[dict]:
    records = []
    position = -1
    for chunk in re.split(r"(?=\|RECORD=)", data):
        if not chunk.startswith("|RECORD="):
            continue
        position += 1
        rec: dict = {}
        for token in chunk.split("|"):
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f].*$", "", value, flags=re.S)
            rec[key] = value
        if "RECORD" in rec:
            rec["_pos"] = str(position)
            records.append(rec)
    return records


def sheet_components(path: str) -> list[dict]:
    records = split_records(open(path, "rb").read().decode("latin1"))
    sheet = os.path.splitext(os.path.basename(path))[0]

    comps: dict[str, dict] = {}
    for r in records:
        if r.get("RECORD") == "1":
            comps[r["_pos"]] = {
                "sheet": sheet,
                "ref": "",
                "value": "",
                "libref": r.get("LibReference", ""),
                "description": r.get("ComponentDescription", ""),
                "footprint": "",
            }
    for r in records:
        owner = r.get("OwnerIndex", "")
        if owner not in comps:
            continue
        if r.get("RECORD") == "34" and r.get("Name") == "Designator":
            comps[owner]["ref"] = r.get("Text", "")
        elif r.get("RECORD") == "41" and r.get("Name") == "Comment":
            comps[owner]["value"] = r.get("Text", "")
        elif r.get("RECORD") == "45" or r.get("RECORD") == "44":
            if r.get("ModelType") == "PCBLIB":
                comps[owner]["footprint"] = r.get("ModelName", "")
    return [c for c in comps.values() if c["ref"]]


# Preferred display values where the schematic comment is generic.
VALUE_FIX = {
    "CAP_0603": "Capacitor",
    "RES_0603": "Resistor",
    "Inductor": "0 \u03a9 (DNP inductor)",
}


def main(out_csv: str) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    files = sorted(glob.glob(os.path.join(root, "hardware", "*.SchDoc")))

    rows = []
    seen = set()
    for f in files:
        for c in sheet_components(f):
            key = (c["sheet"], c["ref"])
            if key in seen:
                continue
            seen.add(key)
            value = c["value"] or VALUE_FIX.get(c["libref"], c["libref"])
            rows.append({
                "Sheet": c["sheet"],
                "Reference": c["ref"],
                "Value": value,
                "Library Reference": c["libref"],
                "Footprint": c["footprint"],
                "Description": c["description"],
            })
    rows.sort(key=lambda r: (r["Sheet"], r["Reference"]))

    for r in rows:
        print(f"{r['Sheet']:16} {r['Reference']:10} {r['Value']:28} "
              f"{r['Library Reference'][:34]:35} {r['Description'][:50]}")

    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} components -> {out_csv}")
    return 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "hardware/Group11_BOM.csv"
    sys.exit(main(out))
