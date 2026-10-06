# SPDX-License-Identifier: GPL-3.0-or-later
"""Pixel-exact stroke cache verification, active appends, mutation/undo invalidation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch
from PyQt6.QtCore import QLine, QRectF, QPointF, Qt
from PyQt6.QtGui import QImage, QPainter, QPen, QColor
import pytest
import main
from test_document_safety_610 import document


def segments(style, marker=False):
    pen = QPen(QColor(50, 110, 220, 100 if marker else 255), 10,
               Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    result = []
    # Interleave two contacts and include an erased gap; first-seen order matters.
    for index in range(15):
        for stroke in range(2):
            x = 15 + index * 8 + (12 if index > 7 else 0)
            item = {"line": QLine(x, 40+stroke*45, x+8, 44+stroke*45),
                    "pen": QPen(pen), "id": str(stroke), "marker": marker}
            if style != "pen": item.update(style=style, options={}, nib=30)
            result.append(item)
    return result


def render(canvas, cached=True, clip=None):
    image = QImage(210, 150, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if clip is not None: painter.setClipRect(clip)
    try:
        method = canvas.draw_segments if cached else canvas._draw_segments_uncached
        method(painter, canvas.all_segments, clip=clip)
    finally: painter.end()
    return image


@pytest.mark.parametrize("style", list(main.PEN_STYLES) + ["marker"])
@pytest.mark.parametrize("clip", [None, QRectF(40, 15, 45, 80)])
def test_cached_pixels_match_original_renderer(document, style, clip):
    _, canvas = document
    canvas.all_segments = segments("pen" if style == "marker" else style, style == "marker")
    expected = render(canvas, False, clip)
    assert render(canvas, True, clip) == expected
    assert render(canvas, True, clip) == expected


def test_warm_grouped_paths_reused_and_active_path_extends_only_new_parts(document):
    _, canvas = document
    canvas.all_segments = segments("pen", True)
    render(canvas)
    cache = canvas._stroke_geometry_cache
    built = cache.parts_processed
    commands = list(cache.commands)
    render(canvas)
    assert cache.parts_processed == built
    previous_path = commands[0].path
    line = QLine(160, 40, 170, 44)
    canvas.all_segments.append(dict(canvas.all_segments[0], line=line))
    render(canvas)
    assert cache.parts_processed == built + 1
    assert cache.commands[0].path is previous_path
    assert render(canvas) == render(canvas, False)


def test_bounds_match_legacy_and_cache_is_reused(document):
    _, canvas = document
    canvas.all_segments = segments("neon")
    first = canvas.object_bounds("0")
    cache = canvas._stroke_geometry_cache
    built = cache.parts_processed
    assert canvas.object_bounds("0") == first
    assert cache.parts_processed == built
    assert first == canvas._uncached_stroke_bounds("0")


def test_transform_erase_undo_and_page_switch_invalidate(document):
    _, canvas = document
    canvas.enter_whiteboard()
    canvas.all_segments = segments("dashed")
    canvas.mark_content_changed()
    original = render(canvas)
    canvas.push_undo()
    canvas.selected_ids = {"0"}
    canvas.move_selection(QPointF(17, 5))
    assert render(canvas) != original
    assert render(canvas) == render(canvas, False)
    assert canvas.undo()
    assert render(canvas) == original
    # A same-length replacement must not collide with cached identity.
    snapshot = canvas.capture_page()
    snapshot["segments"][0]["line"] = QLine(5, 5, 70, 10)
    canvas.load_page(snapshot)
    assert render(canvas) == render(canvas, False)
    canvas.all_segments = canvas.all_segments[3:]
    assert render(canvas) == render(canvas, False)


def test_same_length_in_place_mutation_with_revision_invalidates(document):
    _, canvas = document
    canvas.all_segments = segments("neon")
    render(canvas)
    canvas.all_segments[4]["line"] = QLine(40, 120, 190, 125)
    canvas.mark_content_changed()
    assert render(canvas) == render(canvas, False)
