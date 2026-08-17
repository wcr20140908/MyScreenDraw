# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Display geometry helpers independent of the main window."""
from __future__ import annotations

import math


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value)) and not isinstance(value, bool)
    except (TypeError, ValueError):
        return False


def clamp_rect(x: int, y: int, width: int, height: int, screen: tuple[int, int, int, int], margin: int = 0) -> tuple[int, int]:
    left, top, screen_width, screen_height = screen
    max_x = left + max(0, screen_width - width - margin)
    max_y = top + max(0, screen_height - height - margin)
    return max(left + margin, min(max_x, x)), max(top + margin, min(max_y, y))


def choose_screen(saved_x: int, saved_y: int, screens: list[dict], saved_name: str | None = None) -> dict | None:
    if not screens:
        return None
    if saved_name:
        for screen in screens:
            if screen.get("name") == saved_name:
                return screen
    for screen in screens:
        left, top, width, height = screen["geometry"]
        if left <= saved_x < left + width and top <= saved_y < top + height:
            return screen
    return screens[0]


def sane_dpi(value: object, fallback: float = 96.0) -> float:
    """Return a usable DPI value; Qt can report zero or unreliable negatives."""
    try:
        dpi = float(value)
    except (TypeError, ValueError):
        return fallback
    return dpi if 40.0 <= dpi <= 1000.0 else fallback


def pixels_per_mm_from_dpi(dpi: object, fallback_dpi: float = 96.0) -> float:
    return sane_dpi(dpi, fallback_dpi) / 25.4


def valid_pixels_per_mm(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return 1.0 <= number <= 40.0


def screen_key(name: object, geometry: object, dpr: object, logical_dpi: object) -> str:
    """Build a stable-enough key for a physical display calibration."""
    label = str(name or "screen").strip() or "screen"
    try:
        left, top, width, height = (int(v) for v in geometry)
    except (TypeError, ValueError):
        left, top, width, height = 0, 0, 0, 0
    try:
        dpr_value = round(float(dpr), 3)
    except (TypeError, ValueError):
        dpr_value = 1.0
    try:
        dpi_value = round(sane_dpi(logical_dpi), 2)
    except (TypeError, ValueError):
        dpi_value = 96.0
    return f"{label}|{left},{top},{width},{height}|dpr={dpr_value:g}|dpi={dpi_value:g}"


def normalize_calibrations(value: object) -> dict[str, dict]:
    """Filter persisted per-screen calibration records without Qt dependencies."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        if not valid_pixels_per_mm(raw.get("px_per_mm")):
            continue
        try:
            px_per_mm = float(raw["px_per_mm"])
        except (TypeError, ValueError):
            continue
        if px_per_mm < 1.0 or px_per_mm > 40.0:
            continue
        known_length_mm = float(raw.get("known_length_mm", 100.0)) if _finite_number(raw.get("known_length_mm", 100.0)) else 100.0
        dpr = float(raw.get("dpr", 1.0)) if _finite_number(raw.get("dpr", 1.0)) else 1.0
        logical_dpi = float(raw.get("logical_dpi", 96.0)) if _finite_number(raw.get("logical_dpi", 96.0)) else 96.0
        geometry = raw.get("geometry", [])
        if not (isinstance(geometry, list) and len(geometry) == 4 and all(_finite_number(v) for v in geometry)):
            geometry = []
        result[key] = {
            "screen_key": key,
            "px_per_mm": px_per_mm,
            "known_length_mm": max(10.0, min(1000.0, known_length_mm)),
            "dpr": max(0.5, min(8.0, dpr)),
            "logical_dpi": sane_dpi(logical_dpi),
            "geometry": [int(v) for v in geometry],
        }
    return result


def protractor_angle_degrees(x: object, y: object, snap: bool = False) -> float | None:
    """Return the local angle from the left baseline (0..180) for a semicircle."""
    try:
        x_value, y_value = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if y_value > 1e-6 or x_value == 0 and y_value == 0:
        return None
    angle = math.degrees(math.atan2(-y_value, -x_value))
    if angle < 0.0:
        angle += 360.0
    # y 落在 (0, 1e-6] 的容差带里时 atan2 会绕到 180~360 那一侧：靠近 360 说明贴的是
    # 左端基线（0°），靠近 180 说明贴的是右端基线（180°）。直接 min(180, angle) 会把
    # 「几乎 0°」误钳成 180°，正好读成相反的一端。
    if angle > 180.0:
        angle = 0.0 if angle > 270.0 else 180.0
    angle = max(0.0, min(180.0, angle))
    return round(angle) if snap else angle


def clamp_ruler_width(value: object, minimum: float = 28.0, maximum: float = 120.0) -> float:
    """Return a usable visual ruler width without changing its physical scale."""
    try:
        width = float(value)
    except (TypeError, ValueError):
        width = 36.0
    if not math.isfinite(width):
        width = 36.0
    return max(minimum, min(maximum, width))


def ruler_geometry(length_mm: object, tick_mm: object, major_tick_mm: object, px_per_mm: object) -> dict[str, float]:
    """Normalize physical ruler dimensions and convert them to Qt logical pixels."""
    try:
        length = float(length_mm)
        tick = float(tick_mm)
        major_tick = float(major_tick_mm)
        ratio = float(px_per_mm)
    except (TypeError, ValueError):
        length, tick, major_tick, ratio = 150.0, 1.0, 10.0, pixels_per_mm_from_dpi(96.0)
    length = max(10.0, min(1000.0, length))
    tick = max(0.1, min(length, tick))
    major_tick = max(tick, min(length, major_tick))
    if not valid_pixels_per_mm(ratio):
        ratio = pixels_per_mm_from_dpi(96.0)
    return {
        "length_mm": length,
        "tick_mm": tick,
        "major_tick_mm": major_tick,
        "px_per_mm": ratio,
        "length": length * ratio,
        "spacing": tick * ratio,
        "major_spacing": major_tick * ratio,
    }


def ruler_mm_from_local_x(x: object, length_px: object, length_mm: object) -> float | None:
    """Convert a local ruler x coordinate to a clamped millimetre reading."""
    try:
        px, px_length, mm_length = float(x), float(length_px), float(length_mm)
    except (TypeError, ValueError):
        return None
    if px_length <= 0 or mm_length <= 0:
        return None
    return max(0.0, min(mm_length, (px + px_length / 2.0) * mm_length / px_length))
