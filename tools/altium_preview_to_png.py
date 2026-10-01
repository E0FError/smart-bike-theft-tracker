#!/usr/bin/env python3
"""
altium_preview_to_png.py
========================
Convert an Altium ``*.SchDocPreview`` file into a PNG image.

Altium caches a raster preview of schematic sheets in the project's
``__Previews`` folder.  Each preview file is a small INI-like text file whose
``LargeImage`` / ``MediumImage`` / ``SmallImage`` values are hex-encoded,
zlib-compressed **32-bit BGRx** bitmaps stored **bottom-up** (Windows DIB
order).  This script decodes one of them and writes a normal top-down PNG.

It only uses the Python standard library, so no Pillow/numpy is required.

Usage
-----
    python3 tools/altium_preview_to_png.py IN.SchDocPreview OUT.png
    python3 tools/altium_preview_to_png.py IN.SchDocPreview OUT.png --scale 2
    python3 tools/altium_preview_to_png.py IN.SchDocPreview OUT.png \
        --crop 600,0,950,370 --size large
"""

from __future__ import annotations

import argparse
import binascii
import os
import re
import struct
import sys
import zlib

SIZE_ORDER = ("LargeImage", "MediumImage", "SmallImage")


def parse_preview(path: str) -> dict:
    """Return a dict of the preview metadata (including decoded bitmaps)."""
    with open(path, "r", errors="replace") as fh:
        text = fh.read()

    meta: dict = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"(Large|Medium|Small)Image", key):
            meta[key] = value.strip()
        elif re.fullmatch(r"(Large|Medium|Small)Image(Width|Height|OriginalSize)", key):
            meta[key] = int(value)
    if not meta:
        raise ValueError(f"no preview data found in {path!r}")
    return meta


def decode(meta: dict, which: str) -> tuple[int, int, bytes]:
    """Decode one image variant to a top-down RGBA byte buffer."""
    hexdata = meta[which]
    width = meta[f"{which}Width"]
    height = meta[f"{which}Height"]
    raw = zlib.decompress(binascii.unhexlify(hexdata))
    expected = width * height * 4
    if len(raw) != expected:
        raise ValueError(
            f"{which}: expected {expected} bytes, got {len(raw)}"
        )

    # BGRx, bottom-up -> RGBA, top-down
    out = bytearray(width * height * 4)
    stride = width * 4
    for y in range(height):
        src = (height - 1 - y) * stride
        dst = y * stride
        row = raw[src:src + stride]
        for x in range(width):
            b, g, r, _ = row[x * 4:x * 4 + 4]
            out[dst + x * 4:dst + x * 4 + 4] = bytes((r, g, b, 255))
    return width, height, bytes(out)


def crop_rgba(rgba: bytes, width: int, height: int,
              box: tuple[int, int, int, int]) -> tuple[int, int, bytes]:
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width, x1), min(height, y1)
    new_w, new_h = x1 - x0, y1 - y0
    out = bytearray(new_w * new_h * 4)
    for y in range(new_h):
        src = ((y0 + y) * width + x0) * 4
        out[y * new_w * 4:(y + 1) * new_w * 4] = rgba[src:src + new_w * 4]
    return new_w, new_h, bytes(out)


def scale_rgba(rgba: bytes, width: int, height: int,
               factor: int) -> tuple[int, int, bytes]:
    if factor == 1:
        return width, height, rgba
    new_w, new_h = width * factor, height * factor
    out = bytearray(new_w * new_h * 4)
    for y in range(new_h):
        sy = y // factor
        for x in range(new_w):
            sx = x // factor
            src = (sy * width + sx) * 4
            out[(y * new_w + x) * 4:(y * new_w + x) * 4 + 4] = rgba[src:src + 4]
    return new_w, new_h, bytes(out)


def write_png(path: str, width: int, height: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    body = bytearray()
    stride = width * 4
    for y in range(height):
        body.append(0)                      # filter type: none
        body += rgba[y * stride:(y + 1) * stride]

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(body), 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preview", help="input *.SchDocPreview file")
    ap.add_argument("output", help="output *.png file")
    ap.add_argument("--size", choices=["large", "medium", "small", "best"],
                    default="best", help="which cached resolution to use")
    ap.add_argument("--crop", default=None,
                    help="crop box as x0,y0,x1,y1 in pixels")
    ap.add_argument("--scale", type=int, default=1,
                    help="integer upscale factor (nearest neighbour)")
    args = ap.parse_args(argv)

    meta = parse_preview(args.preview)
    if args.size == "best":
        which = next((k for k in SIZE_ORDER if k in meta), SIZE_ORDER[0])
    else:
        which = args.size.capitalize() + "Image"

    width, height, rgba = decode(meta, which)
    print(f"decoded {which}: {width}x{height}")

    if args.crop:
        box = tuple(int(v) for v in args.crop.split(","))
        if len(box) != 4:
            ap.error("--crop needs four integers: x0,y0,x1,y1")
        width, height, rgba = crop_rgba(rgba, width, height, box)

    width, height, rgba = scale_rgba(rgba, width, height, args.scale)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    write_png(args.output, width, height, rgba)
    print(f"wrote {args.output} ({width}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
