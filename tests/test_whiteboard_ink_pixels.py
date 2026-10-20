# SPDX-License-Identifier: GPL-3.0-or-later
"""Incremental whiteboard paints must match a clean frame, including fractional DPI."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPointF, QRect, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QRegion
from PyQt6.QtWidgets import QApplication, QMainWindow

import main
from board_view import BoardView
from runtime_paths import RuntimeContext, RuntimePaths


@pytest.fixture
def ink_canvas(tmp_path, monkeypatch):
    assert QApplication.platformName() == "offscreen", "Never run these tests on a real screen"
    runtime = RuntimeContext(RuntimePaths(Path(main.APP_DIR), Path(main.RESOURCE_DIR), tmp_path))
    runtime.ui_active = False
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", runtime)
    for name, value in runtime.paths.module_aliases().items():
        monkeypatch.setattr(main, name, value)
    canvas = main.DrawingCanvas(runtime=runtime)
    canvas.setWindowState(Qt.WindowState.WindowNoState)
    canvas.resize(480, 520)
    canvas.whiteboard_mode = True
    canvas.board_style = "BLACK"
    canvas.smart_shapes_enabled = False
    canvas.speed_width_enabled = False
    yield canvas
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(QApplication.instance(), [canvas])


def mouse(canvas, kind, point):
    event = QMouseEvent(kind, QPointF(*point), QPointF(*point),
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier)
    {QEvent.Type.MouseButtonPress: canvas.mousePressEvent,
     QEvent.Type.MouseMove: canvas.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: canvas.mouseReleaseEvent}[kind](event)


def surface(canvas, dpr):
    image = QImage(round(canvas.width() * dpr), round(canvas.height() * dpr),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.GlobalColor.transparent)
    return image


def paint_region(canvas, image, rect):
    # QWidget's translucent backing store clears each dirty region before paintEvent.
    painter = QPainter(image)
    try:
        painter.setClipRegion(QRegion(rect))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(canvas.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        canvas.render(painter, rect.topLeft(), QRegion(rect))
    finally:
        painter.end()


def assert_same_pixels(actual, expected, stage):
    a = actual.constBits().asstring(actual.sizeInBytes())
    b = expected.constBits().asstring(expected.sizeInBytes())
    # This is an opaque board even when the pen is translucent. Checking alpha
    # catches the exact desktop bleed-through, including a one-pixel dirty edge.
    alpha = a[3::4]
    assert min(alpha) == 255, (stage, "opaque board leaked alpha", min(alpha))
    if actual == expected:
        return
    # Integer clip rounding may change stroke antialiasing very slightly, not
    # leave stale/missing ink. Compare the entire frame, not just a chosen edge.
    differences = [(i, abs(x - y)) for i, (x, y) in enumerate(zip(a, b)) if abs(x - y) > 8]
    assert not differences, (stage, "bad channels", len(differences), "worst",
                             max(d for _, d in differences), "first", differences[:8])


@pytest.mark.parametrize("phase", ["live", "committed"])
@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 1.75, 2.0])
@pytest.mark.parametrize("view", [BoardView(), BoardView(37.25, -23.5, 1.7),
                                  BoardView(-28.75, 61.25, 0.65)])
@pytest.mark.parametrize("style", ["pen", "calligraphy", "neon", "marker", "fountain"])
def test_live_and_committed_dirty_paints_match_full_frame(ink_canvas, monkeypatch, dpr, view, style, phase):
    canvas = ink_canvas
    canvas.board_view = view
    canvas.draw_state = "MARKER" if style == "marker" else "PEN"
    canvas.pen_style = "pen" if style == "marker" else style
    canvas.pen_width = 6
    canvas.speed_width_enabled = False
    actual = surface(canvas, dpr)
    paint_region(canvas, actual, canvas.rect())
    updates = []

    def record_update(widget, *args):
        assert widget is canvas
        updates.append(QRect(args[0]) if args else canvas.rect())

    # Observe the real DrawingCanvas.update document -> view conversion, not a
    # test-side reimplementation of it; no native window or input injection.
    monkeypatch.setattr(QMainWindow, "update", record_update)
    points = [(53.2, 58.6), (71.4, 106.3), (109.5, 174.1), (176.2, 249.7),
              (212.4, 314.8), (283.6, 383.3), (347.8, 438.2)]
    actions = [(QEvent.Type.MouseButtonPress, points[0])]
    actions.extend((QEvent.Type.MouseMove, point) for point in points[1:])
    actions.append((QEvent.Type.MouseButtonRelease, points[-1]))
    for index, (kind, point) in enumerate(actions):
        updates.clear()
        mouse(canvas, kind, point)
        for rect in updates:
            clipped = rect.intersected(canvas.rect())
            if not clipped.isEmpty():
                paint_region(canvas, actual, clipped)
        # Committed cases deliberately do not assert live frames: reverting the
        # fix must independently fail AFTER mouse release, not only while moving.
        check = kind != QEvent.Type.MouseButtonRelease if phase == "live" else kind == QEvent.Type.MouseButtonRelease
        if check:
            expected = surface(canvas, dpr)
            paint_region(canvas, expected, canvas.rect())
            stage = f"{style} dpr={dpr} view={view} event={kind.name} frame={index} dirty={updates}"
            assert_same_pixels(actual, expected, stage)
    assert canvas.all_segments and canvas.undo_stack
