# SPDX-License-Identifier: GPL-3.0-or-later
"""Document/view integration using actual canvas input and isolated project files."""
import math
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPoint, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QEventPoint, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtSvg import QSvgRenderer

import main
from board_view import BoardView
from persistence import read_json_maybe_gz, validate_page_data
from test_document_safety_610 import document


def mouse(canvas, kind, x, y):
    event = QMouseEvent(kind, QPointF(x, y), QPointF(x, y),
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier)
    {QEvent.Type.MouseButtonPress: canvas.mousePressEvent,
     QEvent.Type.MouseMove: canvas.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: canvas.mouseReleaseEvent}[kind](event)


def touch(canvas, kind, coordinates):
    points = [SimpleNamespace(id=lambda id=id: id, position=lambda p=p: QPointF(*p),
        state=lambda state=state: state) for id, p, state in coordinates]
    assert canvas._dispatch_touch(SimpleNamespace(type=lambda: kind, points=lambda: points))


def test_transformed_input_render_erase_selection_and_navigation(document):
    panel, canvas = document
    canvas.resize(800, 600)
    canvas.enter_whiteboard()
    panel.set_drawing_mode(True)
    canvas.smart_shapes_enabled = False
    canvas.speed_width_enabled = False
    canvas.board_view = BoardView(600, 250, 2.5)
    canvas.draw_state = 'PEN'
    canvas.pen_color = QColor('#e04040')
    for kind, pos in ((QEvent.Type.MouseButtonPress, (100.5, 120.25)),
                      (QEvent.Type.MouseMove, (160.5, 150.25)),
                      (QEvent.Type.MouseButtonRelease, (160.5, 150.25))):
        mouse(canvas, kind, *pos)
    assert canvas.all_segments
    last = canvas.all_segments[-1]['line'].p2()
    assert last.x() == pytest.approx(-175.8)
    assert last.y() == pytest.approx(-39.9)
    image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.render(image)
    assert image.pixelColor(150, 145) != canvas.board_background()
    canvas.shape_type = 'RECT'
    canvas.shape_items.append(canvas.make_shape_item(QRectF(-120, -60, 25, 25)))
    canvas.draw_state = 'SELECT'
    mouse(canvas, QEvent.Type.MouseButtonPress, 290, 90)
    mouse(canvas, QEvent.Type.MouseMove, 380, 180)
    mouse(canvas, QEvent.Type.MouseButtonRelease, 380, 180)
    assert canvas.selected_ids
    canvas.selected_ids.clear()
    canvas.draw_state = 'ERASER'
    canvas.eraser_type = 'STROKE'
    mouse(canvas, QEvent.Type.MouseButtonPress, 150, 145)
    mouse(canvas, QEvent.Type.MouseButtonRelease, 150, 145)
    assert not canvas.all_segments
    canvas.board_view.x += 30
    canvas.undo()
    assert canvas.all_segments and canvas.board_view.x == 630
    history = len(canvas.undo_stack)
    panel.set_drawing_mode(False)
    assert canvas.is_roaming and not canvas._mouse_passthrough
    mouse(canvas, QEvent.Type.MouseButtonPress, 100, 100)
    mouse(canvas, QEvent.Type.MouseMove, 160, 130)
    mouse(canvas, QEvent.Type.MouseButtonRelease, 160, 130)
    assert (canvas.board_view.x, canvas.board_view.y) == (690, 280)
    assert len(canvas.undo_stack) == history
    anchor = canvas.to_document(QPointF(300, 250))
    canvas.wheelEvent(QWheelEvent(QPointF(300, 250), QPointF(300, 250), QPoint(), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    assert canvas.board_view.zoom == pytest.approx(3.0)
    assert canvas.to_document(QPointF(300, 250)) == anchor
    panel.set_infinite_whiteboard(False)
    assert not canvas.board_view_active and canvas._mouse_passthrough
    assert canvas.to_document(QPointF(150, 145)) == QPointF(150, 145)
    panel.set_infinite_whiteboard(True)
    assert canvas.is_roaming and not canvas._mouse_passthrough


def test_touch_view_pages_save_reopen_and_old_projects(document, tmp_path):
    panel, canvas = document
    canvas.enter_whiteboard()
    panel.set_drawing_mode(False)
    P, U, R = QEventPoint.State.Pressed, QEventPoint.State.Updated, QEventPoint.State.Released
    touch(canvas, QEvent.Type.TouchBegin, [(1, (100, 100), P)])
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (140, 120), U)])
    assert canvas.board_view.to_data() == {'x': 40, 'y': 20, 'zoom': 1}
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (140, 120), U), (2, (240, 120), P)])
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (100, 140), U), (2, (300, 140), U)])
    assert canvas.board_view.zoom == 2
    touch(canvas, QEvent.Type.TouchEnd, [(1, (100, 140), R), (2, (300, 140), R)])
    first_view = canvas.board_view.to_data()
    assert not canvas.undo_stack and not canvas.all_segments
    canvas.new_page()
    assert canvas.board_view == BoardView()
    canvas.board_view = BoardView(-50, 80, 0.75)
    canvas.view_changed()
    second_view = canvas.board_view.to_data()
    canvas.switch_page(-1)
    assert canvas.board_view.to_data() == first_view
    canvas.duplicate_page()
    assert canvas.board_view.to_data() == first_view
    path = str(tmp_path / 'navigation.msd')
    assert panel.save_project(path)
    data = read_json_maybe_gz(path)
    assert [p['view'] for p in data['pages']] == [first_view, first_view, second_view]
    canvas.board_view.x += 100
    canvas.view_changed()
    assert panel.has_unsaved_changes()
    assert canvas.serialized_document_pages()[1]['view']['x'] == first_view['x'] + 100
    assert panel.save_project(path)
    assert panel.open_project_from_path(path)
    assert canvas.board_view.x == first_view['x'] + 100
    legacy = main.deserialize_page({'segments': [], 'texts': [], 'shapes': [], 'images': []})
    canvas.load_page(legacy)
    assert canvas.board_view == BoardView()
    assert validate_page_data({'view': {'x': 0, 'y': 0, 'zoom': 2}})[0]
    assert not validate_page_data({'view': {'x': 0, 'y': 0, 'zoom': 0}})[0]


def test_export_all_content_outside_view_png_pdf_svg_eps(document, tmp_path):
    panel, canvas = document
    canvas.enter_whiteboard()
    canvas.board_view = BoardView(50000, -50000, 8)
    canvas.all_segments = [
        {'id': name, 'line': QLineF(x, y, x + 150, y), 'pen': QPen(QColor(color), 18)}
        for name, x, y, color in [('left', -2200, -1100, '#ee2020'),
                                  ('right', 2600, 1900, '#2040ee')]]
    canvas.mark_content_changed()
    page, size = canvas.capture_page(), QSize(800, 600)
    scale, x, y = canvas.page_export_transform(page, 800, 600)
    def assert_ink(image):
        for segment in page['segments']:
            center = segment['line'].center()
            pixel = image.pixelColor(round(center.x() * scale + x), round(center.y() * scale + y))
            assert pixel != QColor('#f7f7f1')
    assert_ink(canvas.render_page_pixmap(page, size).toImage())
    for fmt in ('PNG', 'PDF'):
        destination = str(tmp_path / ('board.' + fmt.lower()))
        result = main.export_document(fmt, destination, [page],
            lambda p, i, total: canvas.render_page_pixmap(p, size))
        assert result.success
        if fmt == 'PNG':
            assert_ink(QImage(destination))
        else:
            pdf = QPdfDocument(None)
            assert pdf.load(destination) == QPdfDocument.Error.None_
            assert_ink(pdf.render(0, size))
            pdf.close()
    for fmt in ('SVG', 'EPS'):
        destination = str(tmp_path / ('board.' + fmt.lower()))
        result = panel._export_vector_pages(fmt, destination, [page], size,
                                           lambda *args: None, lambda: False)
        assert result.success
        if fmt == 'SVG':
            image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            QSvgRenderer(destination).render(painter)
            painter.end()
            assert_ink(image)
        else:
            text = (tmp_path / 'board.eps').read_text('latin-1')
            assert f'{main.eps_export._fmt(scale)} {main.eps_export._fmt(scale)} scale' in text
            assert '-2200' in text and '2600' in text
