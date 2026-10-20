# SPDX-License-Identifier: GPL-3.0-or-later
"""Local erasing keeps unrelated ink cached, paint order exact, and undo intact."""
from PyQt6.QtCore import QEvent, QLine, QLineF, QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen

from benchmark_strokes_610 import build_segments
from test_document_safety_610 import document


def frame(canvas, cached=True, previous=None, clip=None):
    image = QImage(previous) if previous is not None else QImage(
        1280, 900, QImage.Format.Format_ARGB32_Premultiplied)
    if previous is None:
        image.fill(QColor('white'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if clip is not None:
        painter.setClipRect(clip)
        painter.fillRect(clip, QColor('white'))
    try:
        draw = canvas.draw_segments if cached else canvas._draw_segments_uncached
        draw(painter, canvas.all_segments, clip=clip)
    finally:
        painter.end()
    return image


def test_local_eraser_drag_preserves_cache_pixels_order_and_undo(document, monkeypatch):
    _, canvas = document
    canvas.draw_state = 'ERASER'
    updates = []
    monkeypatch.setattr(canvas, 'update', lambda *args: updates.append(args))
    workload = build_segments(parts=60)
    for index, part in enumerate(workload):
        kind = (index // 60) % 3
        part['marker'] = kind == 1
        if kind == 2:
            part['style'] = 'dashed'
    red = QPen(QColor(220, 30, 30, 100), 8)
    blue = QPen(QColor(30, 30, 220, 100), 8)
    # Removing A's first part must move the remaining A path after B in paint order.
    lead = {'id': 'A', 'line': QLine(1100, 780, 1120, 780), 'pen': red, 'marker': True}
    under = {'id': 'B', 'line': QLine(1100, 840, 1140, 840), 'pen': blue, 'marker': True}
    tail = dict(lead, line=QLine(1100, 840, 1140, 840))
    distance = canvas.point_to_segment_distance_sq
    calls = []
    def measured_distance(point, line):
        calls.append(line)
        return distance(point, line)
    monkeypatch.setattr(canvas, 'point_to_segment_distance_sq', measured_distance)
    for eraser_type in ('CIRCLE', 'STROKE'):
        canvas.eraser_type = eraser_type
        canvas.all_segments = [lead, under, tail] + workload
        canvas.push_undo()
        original = frame(canvas)
        cache = canvas._stroke_geometry_cache
        built = cache.parts_processed
        source = canvas.all_segments
        calls.clear()
        canvas.last_erase_point = QPoint(1200, 780)
        canvas.execute_erase_path(QPoint(1240, 780))
        assert canvas.all_segments is source, 'Blank erasing must not invalidate the whole page'
        assert frame(canvas) == original
        assert cache.parts_processed == built
        assert len(calls) < 20, 'Blank erasing must not scan all page segments'
        calls.clear()
        updates.clear()
        canvas.last_erase_point = canvas.mouse_pos = QPoint(1070, 780)
        canvas.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(1110, 780),
            QPointF(1110, 780), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier))
        assert updates and all(len(args) == 1 for args in updates), 'Erasing must request local paints'
        dirty = QRectF()
        for args in updates:
            dirty = dirty.united(QRectF(args[0]))
        assert dirty.contains(QPointF(1070, 780)) and dirty.contains(QPointF(1110, 780))
        remaining_a = [part for part in canvas.all_segments if part['id'] == 'A']
        assert remaining_a == ([tail] if eraser_type == 'CIRCLE' else [])
        assert any(part is under for part in canvas.all_segments)
        assert len(calls) < 20, 'Local erasing must inspect only nearby ink'
        erased = frame(canvas)
        assert erased == frame(canvas, cached=False)
        assert frame(canvas, previous=original, clip=dirty) == erased
        assert cache.parts_processed - built < 20, 'Unrelated strokes must remain cached'
        assert erased != original
        assert canvas.undo() and frame(canvas) == original
        assert canvas.redo() and frame(canvas) == erased
        # Appended ink still paints last after deletion/rebuild changed command order.
        canvas.all_segments.append(dict(lead, id='last', line=under['line']))
        assert frame(canvas) == frame(canvas, cached=False)
    # The hit path accepts floating point geometry; do not quantize future board coordinates.
    canvas.eraser_type = 'CIRCLE'
    canvas.all_segments = [dict(lead, line=QLineF(1100.25, 780.5, 1120.25, 780.5))]
    canvas.execute_erase(QPointF(1110.25, 780.5))
    assert not canvas.all_segments
