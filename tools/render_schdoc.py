#!/usr/bin/env python3
"""
render_schdoc.py
================
Render an Altium ``*.SchDoc`` schematic sheet to a standalone SVG.

Altium normally draws schematics itself, but a SchDoc is just a serialised list
of records (components, pins, wires, labels, ...).  This script parses those
records and re-draws the sheet with the Python standard library, which makes it
possible to publish readable schematic images from a project *without* Altium.

Rendering rules
---------------
* ``RECORD=27``  wires            -> blue polylines
* ``RECORD=6``   symbol graphics  -> dark-red lines
* ``RECORD=14``  symbol rectangle -> pale-yellow body with dark-red border
* ``RECORD=2``   pins             -> dark-red stubs with pin number / name
* ``RECORD=25``  net labels       -> purple text
* ``RECORD=17``  power ports      -> green text + bar
* ``RECORD=18``  harness ports    -> green rounded boxes
* ``RECORD=34/41`` designators / comments -> black / grey text

Usage
-----
    python3 tools/render_schdoc.py SHEET.SchDoc out.svg [--title "..."]

Then convert with, e.g.::

    inkscape out.svg --export-type=png --export-filename=out.png
"""

from __future__ import annotations

import argparse
import html
import re
import sys

# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def split_records(data: str) -> list[dict]:
    """Split a SchDoc into a list of field dictionaries."""
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
            # strip trailing binary junk and NULs
            value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f].*$", "", value, flags=re.S)
            rec[key] = value
        if "RECORD" in rec:
            # OwnerIndex references a record's position in the sheet stream,
            # so remember it to link pins / symbols / designators back.
            rec["_pos"] = str(position)
            records.append(rec)
    return records


def num(rec: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(rec.get(key, default))
    except (TypeError, ValueError):
        return default


def has(rec: dict, key: str) -> bool:
    return key in rec and rec[key] != ""


# --------------------------------------------------------------------------
# Geometry extraction
# --------------------------------------------------------------------------


def collect(records: list[dict]) -> dict:
    comps: dict[str, dict] = {}
    for r in records:
        if r.get("RECORD") == "1":
            comps[r["_pos"]] = {
                "x": num(r, "Location.X"),
                "y": num(r, "Location.Y"),
                "lib": r.get("LibReference", ""),
                "rects": [],
                "lines": [],
                "pins": [],
                "des": "",
                "comment": "",
            }

    for r in records:
        t = r.get("RECORD")
        owner = r.get("OwnerIndex", "")
        if t == "14" and owner in comps:
            comps[owner]["rects"].append(
                (num(r, "Location.X"), num(r, "Location.Y"),
                 num(r, "Corner.X"), num(r, "Corner.Y")))
        elif t == "6" and owner in comps:
            comps[owner]["lines"].append(
                (num(r, "X1"), num(r, "Y1"), num(r, "X2"), num(r, "Y2")))
        elif t == "2" and owner in comps:
            comps[owner]["pins"].append({
                "x": num(r, "Location.X"), "y": num(r, "Location.Y"),
                "len": num(r, "PinLength", 10),
                "number": r.get("Designator", ""),
                "name": r.get("Name", "").replace("\\", ""),
            })
        elif t == "34" and r.get("Name") == "Designator" and owner in comps:
            comps[owner]["des"] = r.get("Text", "")
        elif t == "41" and r.get("Name") == "Comment" and owner in comps:
            comps[owner]["comment"] = r.get("Text", "")

    # attach designator/comment locations
    des_loc = {}
    com_loc = {}
    for r in records:
        owner = r.get("OwnerIndex", "")
        if r.get("RECORD") == "34" and r.get("Name") == "Designator":
            des_loc[owner] = (num(r, "Location.X"), num(r, "Location.Y"))
        if r.get("RECORD") == "41" and r.get("Name") == "Comment":
            com_loc[owner] = (num(r, "Location.X"), num(r, "Location.Y"))
    for k, c in comps.items():
        c["des_loc"] = des_loc.get(k)
        c["com_loc"] = com_loc.get(k)

    wires = [(num(r, "X1"), num(r, "Y1"), num(r, "X2"), num(r, "Y2"))
             for r in records if r.get("RECORD") == "27"]
    labels = [{"x": num(r, "Location.X"), "y": num(r, "Location.Y"),
               "text": r.get("Text", "")}
              for r in records if r.get("RECORD") == "25"]
    power = [{"x": num(r, "Location.X"), "y": num(r, "Location.Y"),
              "text": r.get("Text", ""), "orient": num(r, "Orientation", 0)}
             for r in records if r.get("RECORD") == "17"]
    harness = [{"x": num(r, "Location.X"), "y": num(r, "Location.Y"),
                "text": r.get("Text", ""), "width": num(r, "Width", 60),
                "height": num(r, "Height", 20)}
               for r in records if r.get("RECORD") == "18"]

    notes = []
    for r in records:
        if r.get("RECORD") in ("28", "29") and has(r, "Text"):
            txt = r["Text"].replace("~1", "\n").replace("%UTF8%", "")
            txt = html.unescape(txt)
            notes.append({"x": num(r, "Location.X"), "y": num(r, "Location.Y"),
                          "text": txt})
        if r.get("RECORD") == "30":  # embedded bitmap placeholder
            notes.append({"x": num(r, "Location.X"), "y": num(r, "Location.Y"),
                          "text": "", "image": (
                              num(r, "Corner.X"), num(r, "Corner.Y"))})
    return {"comps": comps, "wires": wires, "labels": labels,
            "power": power, "harness": harness, "notes": notes}


def pin_direction(pin: dict, comp: dict) -> tuple[int, int]:
    """(dx, dy) the pin points, away from the symbol body."""
    if comp["rects"]:
        x0, y0, x1, y1 = comp["rects"][0]
        left, right = min(x0, x1), max(x0, x1)
        top, bottom = min(y0, y1), max(y0, y1)
        px, py = pin["x"], pin["y"]
        if abs(px - left) < 1 and not (abs(py - top) < 1 or abs(py - bottom) < 1):
            return (-1, 0)
        if abs(px - right) < 1 and not (abs(py - top) < 1 or abs(py - bottom) < 1):
            return (1, 0)
        if abs(py - top) < 1:
            return (0, -1)
        if abs(py - bottom) < 1:
            return (0, 1)
    # two-terminal discretes: point away from the component origin
    if pin["y"] < comp["y"]:
        return (0, -1)
    if pin["y"] > comp["y"]:
        return (0, 1)
    if pin["x"] < comp["x"]:
        return (-1, 0)
    return (1, 0)


def pin_end(pin: dict, comp: dict) -> tuple[float, float]:
    dx, dy = pin_direction(pin, comp)
    return pin["x"] + dx * pin["len"], pin["y"] + dy * pin["len"]


# --------------------------------------------------------------------------
# SVG rendering
# --------------------------------------------------------------------------


def render(records: list[dict], out_path: str, title: str = "") -> None:
    g = collect(records)

    xs, ys = [], []

    def add(x, y):
        xs.append(x)
        ys.append(y)

    for x1, y1, x2, y2 in g["wires"]:
        add(x1, y1)
        add(x2, y2)
    for c in g["comps"].values():
        for x0, y0, x1, y1 in c["rects"]:
            add(x0, y0)
            add(x1, y1)
        for x1, y1, x2, y2 in c["lines"]:
            add(x1, y1)
            add(x2, y2)
        for p in c["pins"]:
            add(*pin_end(p, c))
            add(p["x"], p["y"])
        if c.get("des_loc"):
            add(*c["des_loc"])
        if c.get("com_loc"):
            add(*c["com_loc"])
    for item in g["labels"] + g["power"] + g["harness"]:
        add(item["x"], item["y"])
    for nt in g["notes"]:
        add(nt["x"], nt["y"])
        if "image" in nt:
            add(*nt["image"])

    minx, maxx = min(xs) - 40, max(xs) + 40
    miny, maxy = min(ys) - 40, max(ys) + 40
    width = maxx - minx
    height = maxy - miny

    target_w = 2000
    scale = target_w / width
    # keep text legible for small sheets
    scale = min(scale, 3.2)
    pad = 30
    W = width * scale + 2 * pad
    H = height * scale + 2 * pad + (40 if title else 0)
    top = pad + (40 if title else 0)

    def X(x): return pad + (x - minx) * scale
    def Y(y): return top + (maxy - y) * scale          # Altium is bottom-up

    fs = max(11, min(26, 15 * scale))                   # label font size
    fs_small = fs * 0.78

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}">')
    out.append(f'<rect width="{W:.0f}" height="{H:.0f}" fill="#ffffff"/>')
    if title:
        out.append(f'<text x="{W/2:.0f}" y="28" font-family="Helvetica,Arial,sans-serif" '
                   f'font-size="24" font-weight="bold" text-anchor="middle" '
                   f'fill="#111">{html.escape(title)}</text>')

    def line(x1, y1, x2, y2, color, w, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" '
                   f'y2="{Y(y2):.1f}" stroke="{color}" stroke-width="{w}"{d}/>')

    def text(x, y, s, size, color, anchor="middle", weight="normal"):
        out.append(f'<text x="{X(x):.1f}" y="{Y(y):.1f}" '
                   f'font-family="Helvetica,Arial,sans-serif" font-size="{size:.1f}" '
                   f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}">'
                   f'{html.escape(s)}</text>')

    # embedded image placeholders
    for nt in g["notes"]:
        if "image" in nt:
            x1, y1 = nt["x"], nt["y"]
            x0, y0 = nt["image"]
            xa, xb = min(x0, x1), max(x0, x1)
            ya, yb = min(y0, y1), max(y0, y1)
            out.append(
                f'<rect x="{X(xa):.1f}" y="{Y(yb):.1f}" width="{(xb-xa)*scale:.1f}" '
                f'height="{(yb-ya)*scale:.1f}" fill="none" stroke="#cccccc" '
                f'stroke-dasharray="6,4"/>')

    # symbol bodies
    for c in g["comps"].values():
        for x0, y0, x1, y1 in c["rects"]:
            xa, xb = min(x0, x1), max(x0, x1)
            ya, yb = min(y0, y1), max(y0, y1)
            out.append(
                f'<rect x="{X(xa):.1f}" y="{Y(yb):.1f}" width="{(xb-xa)*scale:.1f}" '
                f'height="{(yb-ya)*scale:.1f}" fill="#fff8dc" stroke="#8b1a1a" '
                f'stroke-width="2"/>')
        for x1, y1, x2, y2 in c["lines"]:
            line(x1, y1, x2, y2, "#8b1a1a", 1.8)

    # wires
    for x1, y1, x2, y2 in g["wires"]:
        line(x1, y1, x2, y2, "#1f5fbf", 2.0)

    # pins
    for c in g["comps"].values():
        for p in c["pins"]:
            ex, ey = pin_end(p, c)
            line(p["x"], p["y"], ex, ey, "#8b1a1a", 1.6)
            out.append(f'<circle cx="{X(ex):.1f}" cy="{Y(ey):.1f}" r="2.6" '
                       f'fill="#1f5fbf"/>')
            if p["number"]:
                mx, my = (p["x"] + ex) / 2, (p["y"] + ey) / 2
                dx, dy = pin_direction(p, c)
                ox, oy = (-dy * 6, dx * 6)
                out.append(
                    f'<text x="{X(mx+ox):.1f}" y="{Y(my+oy):.1f}" '
                    f'font-family="Helvetica,Arial,sans-serif" font-size="{fs_small*0.8:.1f}" '
                    f'fill="#8b1a1a" text-anchor="middle">{html.escape(p["number"])}</text>')
            if p["name"] and c["rects"] and not p["name"].isdigit():
                # nudge the pin name just inside the body
                dx, dy = pin_direction(p, c)
                out.append(
                    f'<text x="{X(p["x"]+dx*4):.1f}" y="{Y(p["y"]+dy*4):.1f}" '
                    f'font-family="Helvetica,Arial,sans-serif" font-size="{fs_small*0.85:.1f}" '
                    f'fill="#333" text-anchor="{"start" if dx>0 else "end" if dx<0 else "middle"}">'
                    f'{html.escape(p["name"])}</text>')

    # net labels
    for item in g["labels"]:
        if item["text"]:
            text(item["x"], item["y"], item["text"], fs, "#7b2d8e", "start",
                 "bold")

    # power ports
    for item in g["power"]:
        if item["text"]:
            text(item["x"], item["y"] - 8, item["text"], fs, "#2e8b57", "middle",
                 "bold")

    # harness ports
    for item in g["harness"]:
        w = max(60, len(item["text"]) * 9)
        out.append(
            f'<rect x="{X(item["x"]):.1f}" y="{Y(item["y"]):.1f}" width="{w*scale:.1f}" '
            f'height="{22*scale:.1f}" rx="8" fill="#e6f5e6" stroke="#2e8b57" '
            f'stroke-width="1.5"/>')
        text(item["x"] + w / 2, item["y"] + 7, item["text"], fs_small,
             "#2e8b57", "middle", "bold")

    # designators and comments
    for c in g["comps"].values():
        if c.get("des_loc"):
            text(*c["des_loc"], c["des"], fs, "#111", "middle", "bold")
        elif c["des"]:
            text(c["x"], c["y"] - 14, c["des"], fs, "#111", "middle", "bold")
        if c.get("com_loc") and c["comment"]:
            text(*c["com_loc"], c["comment"], fs_small, "#555", "middle")

    # text notes
    for nt in g["notes"]:
        if not nt.get("text"):
            continue
        for i, ln in enumerate(nt["text"].split("\n")):
            out.append(
                f'<text x="{X(nt["x"]):.1f}" y="{Y(nt["y"])+i*fs*1.25:.1f}" '
                f'font-family="Helvetica,Arial,sans-serif" font-size="{fs_small:.1f}" '
                f'fill="#333">{html.escape(ln)}</text>')

    out.append("</svg>\n")
    with open(out_path, "w") as fh:
        fh.write("\n".join(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("schdoc")
    ap.add_argument("output")
    ap.add_argument("--title", default="")
    args = ap.parse_args(argv)

    data = open(args.schdoc, "rb").read().decode("latin1")
    records = split_records(data)
    render(records, args.output, args.title)
    print(f"rendered {args.schdoc} -> {args.output} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
