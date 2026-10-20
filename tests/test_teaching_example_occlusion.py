# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-selection examples stay visible without following in-flight practice ink."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MYSCREENDRAW_NO_KEYBOARD', '1')
os.environ.setdefault('PYNPUT_BACKEND', 'dummy')

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QScreen
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from board_view import BoardView
from teaching.widgets import controller_geometry
from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import writing_host, next_info, assert_step


@pytest.fixture(autouse=True)
def only_offscreen(monkeypatch):
    assert QApplication.instance().platformName() == 'offscreen'

    def forbidden(*args, **kwargs):
        pytest.fail('No native desktop capture in teaching example tests')

    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)


def sample_step(host):
    panel = host.panel
    chapter = host.request.chapter_id
    if chapter == 'c01.ink':
        color = next(button for button in panel.color_buttons
                     if button.property('color_val') and
                     QColor(button.property('color_val')) != panel.canvas.pen_color)
        color.click()
        assert_step(host, 'width')
        panel.pen_slider.setValue(12 if panel.canvas.pen_width != 12 else 13)
        assert_step(host, 'stroke')
    elif chapter == 'c02.styles':
        next_info(host)
        panel.pen_style_buttons['pen'].click()
        assert_step(host, 'try_pen')
        assert not panel.canvas.all_segments
        mouse(panel.canvas, 'press', (160, 120))
        mouse(panel.canvas, 'move', (280, 180))
        mouse(panel.canvas, 'move', (390, 120))
        mouse(panel.canvas, 'release', (390, 120))
        assert_step(host, 'choose_fountain')
        panel.pen_style_buttons['fountain'].click()
        assert_step(host, 'try_fountain')
    elif chapter == 'c03.erase':
        next_info(host)
        panel.handle_eraser_click()
        panel.btn_circ.click()
        panel.e_slider.setValue(60)
        assert_step(host, 'circle_erase')
    else:
        raise AssertionError(chapter)
    assert host.presenter.engine.current_step.input_policy == 'canvas'
    assert panel.canvas.draw_state != 'SELECT'
    return QRectF(panel.canvas.page_content_bounds(panel.canvas.live_page()))


def layout_scene(host, monkeypatch, area=None):
    area = QRect(0, 0, 1600, 1000) if area is None else area
    panel = host.panel
    monkeypatch.setattr(host.presenter, '_available_geometry', lambda target: QRect(area))
    panel.canvas.setWindowState(Qt.WindowState.WindowNoState)
    panel.canvas.setGeometry(area)
    panel.show_only_sub(None)
    panel.toolbar_window.setFixedSize(128, area.height())
    panel.toolbar_window.move(area.topLeft())
    panel.logo_window.move(area.topLeft())
    host.presenter.controller.resize(736, 525)
    for _ in range(6):
        QApplication.processEvents()
    # QScreen itself remains offscreen's small native size. Keep the real page
    # rail at our supplied virtual work area's edge, not in its old center.
    panel.page_rail.move(area.right() + 1 - panel.page_rail.width(), area.top() + 400)
    host.presenter.refresh_layout()
    return area


def expected_example(canvas, document_bounds):
    # Independent oracle from actual document content (not _interaction_region,
    # object selection bounds, or the production to_view helper).
    zoom = canvas.board_view.zoom if canvas.board_view_active else 1.0
    x = canvas.board_view.x if canvas.board_view_active else 0.0
    y = canvas.board_view.y if canvas.board_view_active else 0.0
    rect = QRectF(document_bounds.x() * zoom + x, document_bounds.y() * zoom + y,
                  document_bounds.width() * zoom, document_bounds.height() * zoom)
    rect = rect.adjusted(-20, -20, 20, 20).intersected(QRectF(canvas.rect()))
    if rect.isEmpty():
        return QRect()
    return rect.toAlignedRect().translated(canvas.mapToGlobal(QPoint()))


def assert_example_clear(host, area, bounds):
    expected = expected_example(host.panel.canvas, bounds)
    card = host.presenter.controller.geometry()
    assert not expected.isEmpty()
    assert area.contains(card)
    assert not card.intersects(expected), (card, expected)
    assert not any(card.intersects(rect) for rect in host._layout_obstacles())
    return expected


@pytest.mark.parametrize('writing_host', ['c01.ink', 'c02.styles', 'c03.erase'], indirect=True)
def test_nonselection_courses_preserve_existing_example_visibility(writing_host, monkeypatch):
    host, progress = writing_host
    bounds = sample_step(host)
    area = layout_scene(host, monkeypatch)
    sample = assert_example_clear(host, area, bounds)
    canvas, presenter = host.panel.canvas, host.presenter
    # The exact old selection-only behavior covers the example on this scene.
    old = controller_geometry(QRect(canvas.mapToGlobal(QPoint()), canvas.size()),
                              QSize(736, 525), area, obstacles=host._layout_obstacles())
    assert old.intersects(sample)
    snapshot, records, document = presenter._snapshot(), list(progress), canvas.document_signature()
    assert host._selection_region().isEmpty()  # Existing selection API unchanged.
    presenter.controller.next_button.click()
    presenter.refresh_layout()
    assert presenter._snapshot() == snapshot and progress == records
    assert canvas.document_signature() == document and presenter.barrier.installed


@pytest.mark.parametrize('writing_host', ['c01.ink'], indirect=True)
@pytest.mark.parametrize('zoom,offset', [(0.6, QPoint(-1700, -300)), (1.5, QPoint(140, 80))])
def test_example_snapshot_follows_camera_and_canvas_position_not_device_pixels(
        writing_host, monkeypatch, zoom, offset):
    host, _ = writing_host
    bounds = sample_step(host)
    area = layout_scene(host, monkeypatch, QRect(offset, QSize(1800, 1000)))
    canvas = host.panel.canvas
    monkeypatch.setattr(canvas, 'devicePixelRatioF', lambda: 2.0)
    original = QRect(host.presenter.controller.geometry())
    # Position the camera so the old card would now cover the example.
    local = original.topLeft() - canvas.mapToGlobal(QPoint())
    canvas.board_view = BoardView(local.x() + 45 - bounds.x() * zoom,
                                  local.y() + 55 - bounds.y() * zoom, zoom)
    canvas.view_changed()
    assert original.intersects(expected_example(canvas, bounds))
    QTest.qWait(230)
    assert_example_clear(host, area, bounds)
    assert host.presenter.controller.geometry() != original
    assert host._interaction_region().contains(expected_example(canvas, bounds))


@pytest.mark.parametrize('writing_host', ['c01.ink'], indirect=True)
def test_active_stroke_does_not_expand_protection_or_chase_the_pen(writing_host, monkeypatch):
    host, progress = writing_host
    bounds = sample_step(host)
    area = layout_scene(host, monkeypatch, QRect(0, 0, 1600, 1100))
    canvas, presenter = host.panel.canvas, host.presenter
    before, protected = QRect(presenter.controller.geometry()), host._interaction_region()
    snapshot, records = presenter._snapshot(), list(progress)
    ids = {segment['id'] for segment in canvas.all_segments}
    # Deliberately grow the synthetic stroke into the card's old rectangle.
    # Calling the owned canvas directly is not OS input and lets the test prove
    # the region does not incorporate that in-flight line and trigger a jump.
    destination = before.center() - canvas.mapToGlobal(QPoint())
    mouse(canvas, 'press', (520, 820))
    for point in ((700, 780), (800, 650), (destination.x(), destination.y())):
        mouse(canvas, 'move', point)
        QTest.qWait(170)
        assert {segment['id'] for segment in canvas.all_segments} - ids
        assert presenter.controller.geometry() == before
        assert host._interaction_region() == protected
        assert_example_clear(host, area, bounds)
        assert presenter._snapshot() == snapshot and progress == records
    mouse(canvas, 'release', (destination.x(), destination.y()))
    assert presenter.engine.current_step_id != 'stroke'
    assert not presenter.engine.last_error


@pytest.mark.parametrize('writing_host', ['c01.ink'], indirect=True)
def test_small_work_area_shrinks_readably_and_restores_size(writing_host, monkeypatch):
    host, _ = writing_host
    bounds = sample_step(host)
    area = layout_scene(host, monkeypatch, QRect(0, 0, 1040, 710))
    canvas, controller = host.panel.canvas, host.presenter.controller
    # Move the actual example into a position that rules out a full-height or
    # full-width 736x525 card, but leaves a readable smaller rectangle.
    canvas.board_view = BoardView(130, 200, 1.25)
    host.presenter.refresh_layout()
    assert_example_clear(host, area, bounds)
    assert controller.size() != QSize(736, 525)
    for name in ('previous', 'next', 'pause', 'skip', 'retry', 'exit'):
        button = getattr(controller, name + '_button')
        assert button.isVisible() and controller.rect().contains(button.geometry())
    assert controller.body_scroll.viewport().height() >= 1
    assert not controller.next_button.isEnabled()
    area.setSize(QSize(1800, 1100))
    canvas.setGeometry(area)
    host.presenter.refresh_layout()
    assert_example_clear(host, area, bounds)
    assert controller.size() == QSize(736, 525)


@pytest.mark.parametrize('writing_host', ['c01.ink'], indirect=True)
@pytest.mark.parametrize('transition', ['previous', 'retry', 'page'])
def test_step_retry_and_page_changes_rebuild_example_snapshot(writing_host, monkeypatch, transition):
    host, _ = writing_host
    sample_step(host)
    area = layout_scene(host, monkeypatch, QRect(0, 0, 1800, 1100))
    canvas, presenter = host.panel.canvas, host.presenter
    old_key = host._example_snapshot
    old = QRect(presenter.controller.geometry())
    bounds = canvas.page_content_bounds(canvas.live_page())
    offset = old.topLeft() - canvas.mapToGlobal(QPoint()) - bounds.topLeft().toPoint() + QPoint(35, 45)
    # Mutate only this temp fixture's objects without a drawing completion event.
    for segment in canvas.all_segments:
        segment['line'].translate(QPointF(offset))
    canvas._stroke_geometry_cache.invalidate()
    expected_bounds = canvas.page_content_bounds(canvas.live_page())
    assert old.intersects(expected_example(canvas, expected_bounds))
    if transition == 'previous':
        presenter.controller.previous_button.click()
        assert_step(host, 'width')
        host.panel.pen_slider.setValue(13 if host.panel.canvas.pen_width != 13 else 14)
        assert_step(host, 'stroke')
    elif transition == 'retry':
        # Exercise real target-loss/retry flow without native windows or events.
        canvas.hide()
        presenter._targets_changed()
        assert presenter.engine.phase == 'paused' and presenter._missing
        canvas.show()
        presenter.retry()
        assert_step(host, 'stroke')
    else:
        # Keep the same step but load a different private page with different ID.
        page = canvas.capture_page()
        import uuid
        page['page_id'] = str(uuid.uuid4())
        canvas.load_page(page)
        presenter.refresh_layout()
    presenter.refresh_layout()
    assert_example_clear(host, area, expected_bounds)
    assert host._example_snapshot != old_key


@pytest.mark.parametrize('writing_host', ['c01.ink'], indirect=True)
def test_blank_next_chapter_has_no_stale_example_or_inflight_ink_region(writing_host, monkeypatch):
    host, _ = writing_host
    sample_step(host)
    area = layout_scene(host, monkeypatch)
    assert not host._interaction_region().isEmpty()
    host.presenter.engine.stop()
    host.presenter.start('c02', 'c02.styles')
    next_info(host)
    host.panel.pen_style_buttons['pen'].click()
    assert_step(host, 'try_pen')
    assert not host.panel.canvas.all_segments
    assert host._interaction_region().isEmpty()
    assert host.presenter.controller.size() == QSize(736, 525)
    before = QRect(host.presenter.controller.geometry())
    mouse(host.panel.canvas, 'press', (600, 780))
    mouse(host.panel.canvas, 'move', (700, 830))
    host.presenter.refresh_layout()
    assert host._interaction_region().isEmpty()
    assert host.presenter.controller.geometry() == before
    mouse(host.panel.canvas, 'release', (740, 790))
    assert_step(host, 'choose_fountain')
    host.panel.pen_style_buttons['fountain'].click()
    assert_step(host, 'try_fountain')
    bounds = host.panel.canvas.page_content_bounds(host.panel.canvas.live_page())
    assert_example_clear(host, area, bounds)
