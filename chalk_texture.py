# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic chalk powder for QImage texture brushes; no QApplication needed.

``make_chalk_texture(color, density=58, opacity=94)`` takes percentages, matching
main's chalk pen options. The caller can cache returned images as usual. Internal
caches contain only immutable, color-independent bytes, never shared QImages.
"""
from functools import lru_cache
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QRadialGradient


TEXTURE_SIZE = 192  # Four times the old repeat period, still only 144 KiB in ARGB32.


def _percent(value, default):
    # Match normalize_pen_options without importing main (and starting GUI hooks).
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 10 <= value <= 100:
        return int(value)
    return default


@lru_cache(maxsize=1)
def _powder_field():
    """Return (ranked deposit field, grain strength) on a seamless torus.

    Randomly positioned radial deposits avoid a cell/dot lattice. Two radius
    ranges model larger powder clumps and their broken crumbs. Wrapped deposits
    make the brush repeat without straight seams; independent fine grit breaks
    up the soft radial boundaries. The private PRNG never touches global state.
    """
    size = TEXTURE_SIZE
    rng = random.Random(0x4348414C4B)
    field = QImage(size, size, QImage.Format.Format_RGB32)
    field.fill(QColor(127, 127, 127))
    gradients = []
    for value in (0, 255):
        gradient = QRadialGradient(QPointF(0, 0), 1.0)
        gradient.setColorAt(0.0, QColor(value, value, value, 235))
        gradient.setColorAt(0.48, QColor(value, value, value, 155))
        gradient.setColorAt(1.0, QColor(value, value, value, 0))
        gradients.append(gradient)
    unit_ellipse = QRectF(-1, -1, 2, 2)
    painter = QPainter(field)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for count, low, high in ((200, 5.0, 12.0), (1400, 0.7, 3.6)):
            for _ in range(count):
                x, y = rng.random() * size, rng.random() * size
                rx = rng.uniform(low, high)
                ry = rx * rng.uniform(0.55, 1.45)
                gradient = gradients[1 if rng.random() < 0.5 else 0]
                xs = [x] + ([x + size] if x < rx else []) + ([x - size] if x + rx > size else [])
                ys = [y] + ([y + size] if y < ry else []) + ([y - size] if y + ry > size else [])
                for cy in ys:
                    for cx in xs:
                        painter.save()
                        painter.translate(cx, cy)
                        painter.scale(rx, ry)
                        painter.setBrush(gradient)
                        painter.drawEllipse(unit_ellipse)
                        painter.restore()
    finally:
        painter.end()

    gray = field.convertToFormat(QImage.Format.Format_Grayscale8)
    # 192 is divisible by four, so Grayscale8 has no row padding.
    smooth = gray.constBits().asstring(gray.sizeInBytes())
    scores, grain = bytearray(size * size), bytearray(size * size)
    histogram = [0] * 256
    fine_grain = rng.randbytes(size * size)
    for i, (value, grit) in enumerate(zip(smooth, fine_grain)):
        score = (value * 7 + grit) // 8
        scores[i] = score
        histogram[score] += 1
        # True pinholes stay empty even at density 100; no pale/white pigment.
        grain[i] = 0 if grit < 16 else 140 + (grit * 115 // 255)

    # Ranking decouples the density slider from the particular noise histogram:
    # more density adds material in place, rather than reshuffling every grain.
    rank = bytearray(256)
    total = 0
    for value, count in enumerate(histogram):
        rank[value] = round((total + count / 2) * 255 / len(scores))
        total += count
    return bytes(scores).translate(bytes(rank)), bytes(grain)


@lru_cache(maxsize=8)
def _density_mask(density):
    ranks, grain = _powder_field()
    cutoff = (100 - density) * 255 / 100
    ramp = [max(0, min(255, round((value - cutoff) * 255 / 24))) for value in range(256)]
    return bytes(ramp[value] * strength // 255 for value, strength in zip(ranks, grain))


def make_chalk_texture(color: QColor, density=58, opacity=94) -> QImage:
    """Make an owned 192x192 straight-alpha ARGB32 chalk brush image.

    ``density`` and ``opacity`` use main's 10..100 percent range and defaults;
    finite in-range floats truncate as in normalize_pen_options. Invalid values
    fall back to 58/94. Density monotonically adds clustered coverage; opacity
    scales the existing mask linearly, multiplied by QColor.alpha(). RGB is
    exactly the supplied color, including faint particles (never mixed with
    white). Geometry is independent of RGB, opacity and process hash seed.

    No GUI application, global random state, filesystem or main import is used.
    Return values are independently mutable; only immutable masks are cached.
    A finite texture necessarily repeats every 192 logical pixels. SVG fallback
    and the existing style_texture image cache remain the caller's concern.
    """
    density, opacity = _percent(density, 58), _percent(opacity, 94)
    mask = _density_mask(density)
    indexed = QImage(mask, TEXTURE_SIZE, TEXTURE_SIZE, TEXTURE_SIZE,
                     QImage.Format.Format_Indexed8)
    red, green, blue, alpha = color.getRgb()
    scale = opacity * alpha / (100 * 255)
    rgb = (red << 16) | (green << 8) | blue
    indexed.setColorTable([(round(value * scale) << 24) | rgb for value in range(256)])
    # Qt expands the palette in C++; avoid Python pixelColor/setPixelColor loops.
    # Non-premultiplied RGB preserves hue exactly even at very low alpha. Qt's
    # raster painter premultiplies as needed when consuming this brush.
    return indexed.convertToFormat(QImage.Format.Format_ARGB32)
