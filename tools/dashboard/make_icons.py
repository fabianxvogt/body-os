#!/usr/bin/env python3
"""Generate the home-screen icons (stdlib only, deterministic): the dashboard's gradient tile with the
white pulse mark (index.html .mark). Output: icons/apple-touch-icon.png (180), icon-192.png, icon-512.png.

Run: python3 tools/dashboard/make_icons.py [OUT_DIR]   (default: tools/dashboard/icons)
Full-bleed and opaque, with the mark inside the central 60 % so iOS and Android masks never cut it."""

import math
import os
import struct
import sys
import zlib

C1 = (0x2A, 0x78, 0xD6)  # --c1 (light theme)
C3 = (0x1B, 0xAF, 0x7A)  # --c3
ANGLE = 140              # CSS linear-gradient(140deg, var(--c1), var(--c3))
PULSE = [(3, 12), (7, 12), (9.5, 6), (14.5, 18), (17, 12), (21, 12)]  # "M3 12h4l2.5-6 5 12 2.5-6h4", 24-unit box
STROKE = 2.2
MARK = 0.58              # share of the icon width covered by the 24-unit box
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}


def png(width, height, rows):
    """rows: list of bytes objects, each width*3 RGB bytes."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def icon(size):
    a = math.radians(ANGLE)
    gx, gy = math.sin(a), -math.cos(a)
    glen = abs(size * gx) + abs(size * gy)
    scale = size * MARK / 24.0
    off = (size - 24 * scale) / 2.0
    pts = [(off + x * scale, off + y * scale) for x, y in PULSE]
    segs = list(zip(pts, pts[1:]))
    hw = STROKE / 2.0 * scale
    lo, hi = off + 2 * scale, off + 22 * scale  # bounding box of the mark (with stroke)
    rows = []
    for y in range(size):
        cy = y + 0.5
        row = bytearray()
        for x in range(size):
            cx = x + 0.5
            t = ((cx - size / 2.0) * gx + (cy - size / 2.0) * gy) / glen + 0.5
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            bg = [C1[i] + (C3[i] - C1[i]) * t for i in range(3)]
            cov = 0.0
            if lo - 1 <= cx <= hi + 1 and off + 5 * scale - 1 <= cy <= off + 19 * scale + 1:
                d = min(_seg_dist(cx, cy, s[0][0], s[0][1], s[1][0], s[1][1]) for s in segs)
                cov = max(0.0, min(1.0, hw - d + 0.5))
            row += bytes(int(round(c + (255 - c) * cov)) for c in bg)
        rows.append(bytes(row))
    return png(size, size, rows)


def main(argv):
    out = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    os.makedirs(out, exist_ok=True)
    for name, size in SIZES.items():
        with open(os.path.join(out, name), "wb") as f:
            f.write(icon(size))
        print("wrote %s (%dx%d)" % (os.path.join(out, name), size, size))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
