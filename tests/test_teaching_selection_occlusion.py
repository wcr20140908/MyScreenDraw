# SPDX-License-Identifier: GPL-3.0-or-later
"""Selection placement against real private fixtures, never native screen/input."""
from dataclasses import replace
import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MYSCREENDRAW_NO_KEYBOARD', '1')
os.environ.setdefault('PYNPUT_BACKEND', 'dummy')

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt
from PyQt6.QtGui import QColor, QPixmap, QScreen
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from board_view import BoardView
from teaching.application import ApplicationTeachingHost
from teaching.widgets import controller_geometry, interaction_controller_geometry
from test_teaching_writing_courses import writing_host, next_info, assert_step
from test_teaching_business_adapters import mouse


@pytest.fixture(autouse=True)
def no_desktop(monkeypatch):
    assert QApplication.instance().platformName() == 'offscreen'

    def forbidden(*args, **kwargs):
        pytest.fail('Selection placement tests cannot capture the desktop')

    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)


def selection_step(host):
    if host.request.chapter_id == 'c01.select':
        host.panel.canvas.undo()
        host.panel.canvas.redo()
    else:
        next_info(host)
    host.panel.handle_select_click()
    step = host.presenter.engine.current_step
    assert any(clause.event == 'selection.changed' for clause in step.wait.clauses)
    assert host.presenter.active_target_id == 'canvas.ink'
    assert host.presenter.engine.phase == 'running'


def layout_scene(host, monkeypatch, area=QRect(0, 0, 1600, 1000)):
    panel, presenter = host.panel, host.presenter
    monkeypatch.setattr(presenter, '_available_geometry', lambda target: QRect(area))
    panel.canvas.setWindowState(Qt.WindowState.WindowNoState)
    panel.canvas.setGeometry(area)
    panel.toolbar_window.setFixedSize(128, area.height())
    panel.toolbar_window.move(area.topLeft())
    panel.logo_window.setGeometry(area.x(), area.y(), 128, 60)
    presenter.controller.resize(736, 525)
    presenter.refresh_layout()
    return area


def global_box(canvas, rect, margin=20):
    # Independent oracle: explicitly apply the camera, *not* the production
    # selection-region helper or canvas.to_view. Qt widget positions are already
    # logical pixels and must not be multiplied by devicePixelRatioF().
    zoom = canvas.board_view.zoom if canvas.board_view_active else 1
    x = canvas.board_view.x if canvas.board_view_active else 0
    y = canvas.board_view.y if canvas.board_view_active else 0
    mapped = QRectF(rect.x() * zoom + x, rect.y() * zoom + y,
                   rect.width() * zoom, rect.height() * zoom)
    mapped = mapped.adjusted(-margin, -margin, margin, margin).intersected(QRectF(canvas.rect()))
    return mapped.toAlignedRect().translated(canvas.mapToGlobal(QPoint()))


def assert_workspace_clear(host, area):
    canvas, controller = host.panel.canvas, host.presenter.controller
    bounds = canvas.page_content_bounds(canvas.live_page())
    expected = global_box(canvas, bounds)
    assert not expected.isEmpty()
    assert area.contains(controller.geometry())
    assert not controller.geometry().intersects(expected), (controller.geometry(), expected)
    assert not any(controller.geometry().intersects(rect) for rect in host._layout_obstacles())
    return expected


@pytest.mark.parametrize('writing_host', [
    'c01.select', 'c04.select_move', 'c04.transform', 'c04.copy_delete', 'c07.format',
], indirect=True)
def test_every_selection_course_keeps_the_real_sample_clear(writing_host, monkeypatch):
    host, progress = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch)
    snapshot, records = host.presenter._snapshot(), list(progress)
    signature = host.panel.canvas.document_signature()
    # The reported oversized left card really WOULD cover this live fixture
    # using the old, toolbar-only placement. Keep this negative control here.
    canvas = host.panel.canvas
    anchor = QRect(canvas.mapToGlobal(QPoint()), canvas.size())
    old = controller_geometry(anchor, QSize(736, 525), area, obstacles=host._layout_obstacles())
    sample = assert_workspace_clear(host, area)
    assert old.intersects(sample), (old, sample)
    host.presenter.controller.next_button.click()
    host.presenter.refresh_layout()
    assert host.presenter._snapshot() == snapshot and progress == records
    assert canvas.document_signature() == signature and not canvas.selected_ids
    assert host.presenter.barrier.installed


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_rectangle_corridor_is_clear_and_still_requires_two_objects(writing_host, monkeypatch):
    host, progress = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch)
    canvas = host.panel.canvas
    ids = {item['id'] for item in canvas.shape_items}
    assert len(ids) == 2
    # Move the private objects away from the toolbar; do not change the rule.
    for item in canvas.shape_items:
        item['points'] = [point + QPointF(140, 40) for point in item['points']]
    host.presenter.refresh_layout()
    expected = assert_workspace_clear(host, area)
    # Clicking one object must NOT satisfy this mandatory box-selection step.
    point = canvas.object_bounds(next(iter(ids))).center().toPoint()
    mouse(canvas, 'press', (point.x(), point.y()))
    mouse(canvas, 'release', (point.x(), point.y()))
    assert_step(host, 'box')
    assert not any(record[1] == 'completed' for record in progress)
    local = expected.translated(-canvas.mapToGlobal(QPoint())).adjusted(2, 2, -2, -2)
    start, end = local.topLeft(), local.bottomRight()
    mouse(canvas, 'press', (start.x(), start.y()))
    mouse(canvas, 'move', (end.x(), end.y()))
    host.presenter.refresh_layout()
    assert not host.presenter.controller.geometry().intersects(expected)
    assert_step(host, 'box')
    mouse(canvas, 'release', (end.x(), end.y()))
    assert canvas.selected_ids == ids
    assert_step(host, 'copy')
    host.presenter.refresh_layout()
    assert not host.presenter.controller.geometry().intersects(host.registry.global_rect('selection.duplicate'))


@pytest.mark.parametrize('writing_host', ['c04.transform'], indirect=True)
def test_handle_info_step_and_transforms_keep_handles_clear_after_step_resize(writing_host, monkeypatch):
    host, _ = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch)
    canvas = host.panel.canvas
    mouse(canvas, 'press', (170, 150))
    mouse(canvas, 'release', (170, 150))
    assert_step(host, 'handles')
    for expected_step in ('handles', 'scale'):
        if expected_step == 'scale':
            next_info(host)
        host.presenter.controller.resize(920, 680)
        host.presenter.refresh_layout()
        assert area.contains(host.presenter.controller.geometry())
        for rect in (canvas.selection_bounds(), *canvas.selection_handles().values()):
            assert not host.presenter.controller.geometry().intersects(global_box(canvas, rect))
        expected_region = global_box(canvas, canvas.selection_bounds())
        for rect in canvas.selection_handles().values():
            expected_region = expected_region.united(global_box(canvas, rect))
        assert host._selection_region() == expected_region
        assert_step(host, expected_step)


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
@pytest.mark.parametrize('infinite,zoom,offset', [
    (True, 0.65, QPoint(-1700, -400)), (True, 1.5, QPoint(180, 70)),
    (False, 2.0, QPoint(-1700, 70)),
])
def test_camera_and_dpi_use_logical_global_rectangles(writing_host, monkeypatch, infinite, zoom, offset):
    host, _ = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch, QRect(offset, QSize(1800, 1100)))
    canvas = host.panel.canvas
    host.panel.infinite_whiteboard = infinite
    canvas.board_view = BoardView(320.5, 105.25, zoom)
    monkeypatch.setattr(canvas, 'devicePixelRatioF', lambda: 2.0)
    document = canvas.document_signature()
    host.presenter.refresh_layout()
    expected = assert_workspace_clear(host, area)
    assert host._selection_region() == expected
    assert canvas.document_signature() == document


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_timer_rechecks_camera_marquee_and_moving_objects_without_advancing(writing_host, monkeypatch):
    host, progress = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch, QRect(0, 0, 2000, 1200))
    canvas, presenter = host.panel.canvas, host.presenter
    for _ in range(6):
        QApplication.processEvents()  # Settle initial target watches before changing the camera.
    snapshot, records = presenter._snapshot(), list(progress)
    old = QRect(presenter.controller.geometry())
    # Put actual sample content at the old controller position using the camera.
    bounds = canvas.page_content_bounds(canvas.live_page())
    canvas.board_view = BoardView(old.x() - bounds.x() + 40, old.y() - bounds.y() + 40, 1)
    canvas.view_changed()
    assert old.intersects(global_box(canvas, bounds))
    QTest.qWait(230)
    assert_workspace_clear(host, area)
    assert presenter.controller.geometry() != old
    # Live marquee can extend well beyond the objects; protect it on refresh.
    old = QRect(presenter.controller.geometry())
    view = old.adjusted(30, 30, -30, -30).translated(-canvas.mapToGlobal(QPoint()))
    canvas.selection_rect = QRectF(canvas.to_document(QPointF(view.topLeft())),
                                   canvas.to_document(QPointF(view.bottomRight())))
    presenter.refresh_layout()
    assert host._selection_region().contains(global_box(canvas, canvas.selection_rect))
    assert presenter._snapshot() == snapshot and progress == records
    canvas.selection_rect = None


def test_adaptive_card_finds_a_readable_slot_and_impossible_layout_minimizes_overlap():
    area = QRect(0, 0, 1000, 700)
    sample = QRect(130, 0, 510, 700)
    toolbar = QRect(0, 0, 128, 700)
    size, minimum = QSize(736, 525), QSize(250, 260)
    result = interaction_controller_geometry(area, size, minimum, area, sample, (toolbar,))
    assert area.contains(result)
    assert not result.intersects(sample) and not result.intersects(toolbar)
    assert result.width() >= minimum.width() and result.height() >= minimum.height()
    assert result.width() < size.width() and result.height() == size.height()
    impossible = interaction_controller_geometry(area, size, minimum, area, area, (toolbar,))
    assert area.contains(impossible) and impossible.size() == minimum
    assert not impossible.intersects(toolbar)


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_adaptive_card_preserves_controls_scrolls_copy_and_restores_requested_size(writing_host, monkeypatch):
    host, _ = writing_host
    selection_step(host)
    area = layout_scene(host, monkeypatch, QRect(0, 0, 1120, 800))
    canvas, presenter = host.panel.canvas, host.presenter
    controller = presenter.controller
    controller.body_label.setText(controller.body_label.text() * 20)
    canvas.board_view = BoardView(180, 0, 1.1)
    presenter.refresh_layout()
    assert_workspace_clear(host, area)
    assert controller.size() != QSize(736, 525)
    QApplication.processEvents()
    for name in ('previous', 'next', 'pause', 'skip', 'retry', 'exit'):
        button = getattr(controller, name + '_button')
        assert button.isVisible() and controller.rect().contains(button.geometry())
    assert controller.body_scroll.viewport().height() > 0
    assert controller.body_scroll.verticalScrollBar().maximum() > 0
    assert controller.body_label.text()
    assert not controller.next_button.isEnabled()
    # Expanding the synthetic screen must restore the pre-fit size.
    area.setWidth(2100)
    canvas.setGeometry(area)
    presenter.refresh_layout()
    assert_workspace_clear(host, area)
    assert controller.size() == QSize(736, 525)


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_all_catalog_selection_steps_use_live_bounds_for_every_object_kind(writing_host):
    host, _ = writing_host
    canvas = host.panel.canvas
    canvas.setGeometry(0, 0, 1800, 1100)
    canvas.board_view = BoardView()
    # Real object measurement APIs, including rotated images and text.
    canvas.all_segments = []
    canvas.shape_items = []
    canvas.text_items = [{'id': 991, 'pos': QPointF(260, 120), 'text': 'x + y',
                          'color': QColor('black'), 'width': 2, 'size': 28,
                          'scale': 1.2, 'rotation': 15}]
    pixmap = QPixmap(40, 30)
    pixmap.fill(QColor('blue'))
    canvas.image_items = [{'id': 992, 'pos': QPointF(580, 220), 'size': QSizeF(180, 110),
                           'rotation': 30, 'pixmap': pixmap}]
    canvas.selected_ids.clear()
    canvas.draw_state = 'PEN'  # Detection cannot depend only on the active tool.
    steps = [step for step in host.catalog.all_steps() if step.wait and
             any(clause.event.startswith('selection.') for clause in step.wait.clauses)]
    assert len(steps) >= 15
    for step in steps:
        source = SimpleNamespace(panel=host.panel, presenter=SimpleNamespace(
            engine=SimpleNamespace(current_step=step)))
        expected = global_box(canvas, canvas.page_content_bounds(canvas.live_page()))
        assert ApplicationTeachingHost._selection_region(source) == expected, step.id
    # Non-selection operations do not reserve arbitrary canvas content.
    source.presenter.engine.current_step = replace(steps[0], wait=None)
    assert ApplicationTeachingHost._selection_region(source).isEmpty()
    # Far-away objects must not turn the infinite viewport into one obstacle.
    source.presenter.engine.current_step = steps[0]
    expected = ApplicationTeachingHost._selection_region(source)
    canvas.image_items.append(dict(canvas.image_items[0], id=993, pos=QPointF(100000, 20000)))
    assert ApplicationTeachingHost._selection_region(source) == expected
