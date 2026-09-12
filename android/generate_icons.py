#!/usr/bin/env python3
"""Generate placeholder launcher icons for the ULTRON AI Android app.

Run this script to create basic PNG icons in all required sizes.
Requires: Pillow (pip install Pillow)

Usage:
    python generate_icons.py
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

# Icon sizes for Android mipmap directories
ICON_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

# ULTRON brand colors
BG_COLOR = (5, 9, 10)       # #05090A
GREEN = (61, 255, 176)      # #3DFB0
DIM_GREEN = (28, 107, 83)   # #1C6B53


def create_png(width: int, height: int, pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Create a minimal PNG file from pixel data."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    raw_data = b""
    for row in pixels:
        raw_data += b"\x00"  # filter byte
        for r, g, b, a in row:
            raw_data += struct.pack("BBBB", r, g, b, a)

    compressed = zlib.compress(raw_data, 9)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")

    return header + ihdr + idat + iend


def generate_icon(size: int) -> bytes:
    """Generate a ULTRON icon with 'U' letter on dark background."""
    pixels = []
    center_x, center_y = size // 2, size // 2
    radius = size // 2 - 2

    for y in range(size):
        row = []
        for x in range(size):
            dx = x - center_x
            dy = y - center_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < radius:
                # Inside circle - dark background
                bg = BG_COLOR

                # Draw 'U' shape
                u_left = center_x - size // 5
                u_right = center_x + size // 5
                u_top = center_y - size // 5
                u_bottom = center_y + size // 5
                u_thickness = max(2, size // 12)

                is_u = False
                # Left vertical bar
                if (u_left - u_thickness <= x <= u_left + u_thickness and
                        u_top <= y <= u_bottom):
                    is_u = True
                # Right vertical bar
                if (u_right - u_thickness <= x <= u_right + u_thickness and
                        u_top <= y <= u_bottom):
                    is_u = True
                # Bottom curve
                if (u_left <= x <= u_right and
                        u_bottom - u_thickness <= y <= u_bottom + u_thickness):
                    is_u = True
                # Bottom curve rounding
                curve_y = u_bottom + (u_thickness // 2)
                if (u_left <= x <= u_right and
                        abs(y - curve_y) <= u_thickness):
                    is_u = True

                if is_u:
                    row.append(GREEN + (255,))
                else:
                    row.append(bg + (255,))
            else:
                # Outside circle - transparent
                row.append((0, 0, 0, 0))

        pixels.append(row)

    return create_png(size, size, pixels)


def main():
    base_dir = Path(__file__).parent / "app" / "src" / "main" / "res"

    for folder, size in ICON_SIZES.items():
        out_dir = base_dir / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "ic_launcher.png"

        png_data = generate_icon(size)
        out_file.write_bytes(png_data)
        print(f"  Created {out_file} ({size}x{size})")

    print("Icons generated successfully!")


if __name__ == "__main__":
    main()
