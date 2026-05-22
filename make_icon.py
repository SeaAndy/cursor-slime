#!/usr/bin/env python3
"""Render the slime sprite as a macOS .icns icon.

Generates a multi-resolution iconset using the same pixel-art data as the
desktop pet, then packs it via `iconutil -c icns`.

Usage:  python3 make_icon.py
Output: ~/.cursor/pet/CursorSlime.app/Contents/Resources/CursorSlime.icns
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

import slime  # reuse SPRITES / COLORS / STATE_PALETTES

PALETTE = slime.STATE_PALETTES["idle"]
SPRITE = slime.SPRITES["idle"]
SW, SH = slime.SPRITE_W, slime.SPRITE_H

APP_RES = Path.home() / ".cursor" / "pet" / "CursorSlime.app" / "Contents" / "Resources"
APP_RES.mkdir(parents=True, exist_ok=True)


def render_slime(size_px: int) -> QImage:
    """Render the slime sprite centered in a size_px square, transparent bg."""
    img = QImage(size_px, size_px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    # Use the largest integer pixel size that fits with a little padding.
    pad = max(2, size_px // 14)
    px = max(1, min((size_px - pad * 2) // SW, (size_px - pad * 2) // SH))
    sw_px = SW * px
    sh_px = SH * px
    ox = (size_px - sw_px) // 2
    oy = (size_px - sh_px) // 2

    p = QPainter(img)
    p.setPen(Qt.PenStyle.NoPen)
    for r, row in enumerate(SPRITE):
        for c, ch in enumerate(row):
            color = PALETTE.get(ch) or slime.COLORS.get(ch)
            if not color:
                continue
            p.fillRect(ox + c * px, oy + r * px, px, px, QColor(color))

    # Slight shadow under the slime, in the bottom padding area.
    shadow_y = oy + sh_px + max(1, px // 2)
    if shadow_y + 2 < size_px:
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawEllipse(ox + sw_px // 4, shadow_y, sw_px // 2, max(2, px))
    p.end()
    return img


def main():
    QApplication(sys.argv)  # need a Q* instance for QImage/QPainter on macOS

    pairs = [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    with tempfile.TemporaryDirectory() as td:
        iconset = Path(td) / "CursorSlime.iconset"
        iconset.mkdir()
        for size, name in pairs:
            img = render_slime(size)
            img.save(str(iconset / name), "PNG")

        out_icns = APP_RES / "CursorSlime.icns"
        # `iconutil -c icns SRC -o DST`
        subprocess.check_call([
            "/usr/bin/iconutil", "-c", "icns", str(iconset),
            "-o", str(out_icns),
        ])
        print(f"wrote {out_icns}  ({out_icns.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
