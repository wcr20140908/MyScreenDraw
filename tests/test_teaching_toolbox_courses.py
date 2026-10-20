# SPDX-License-Identifier: GPL-3.0-or-later
"""C12 lens use: real private Qt drawing, never desktop capture or OS input."""
import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPixmap, QScreen
from PyQt6.QtWidgets import QApplication

from teaching.toolbox_fixtures import render_private_magnifier_frame
from test_teaching_application_isolation import drain
from test_teaching_toolbox_interface import qt_slot_failures
from test_teaching_writing_courses import writing_host, next_info, assert_step

pytestmark = pytest.mark.parametrize('writing_host', ['c12.magnifier'], indirect=True)


@pytest.fixture
def lens_host(writing_host, monkeypatch):
    host, progress = writing_host
    assert QApplication.instance().platformName() == 'offscreen'

    def forbidden(*args, **kwargs):
        raise AssertionError('magnifier practice must not capture the desktop')

    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)
    monkeypatch.setattr(host.panel, 'grab_screen', forbidden)
    drain(QApplication.instance())
    yield host, progress


def move(canvas, x, y):
    point = QPointF(x, y)
    event = QMouseEvent(QEvent.Type.MouseMove, point, QPointF(canvas.mapToGlobal(point.toPoint())),
                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas, event)


def use_step(host):
    panel = host.panel
    next_info(host)
    panel.tool_menu_buttons['handle_magnifier_click'].click()
    assert_step(host, 'zoom')
    panel.btn_mag_zoom_in.click()
    panel.mag_size_slider.setValue(320)
    panel.btn_mag_refresh.click()
    assert_step(host, 'move')
    assert not panel.magnifier_sub.isVisible()
    assert host.presenter.registry.resolve('magnifier.practice') is panel.canvas


def sweep(canvas):
    move(canvas, 220, 210)
    move(canvas, 260, 225)


def test_settings_repaint_and_tiny_motion_do_not_replace_visible_lens_use(lens_host):
    host, progress = lens_host
    panel, canvas = host.panel, host.panel.canvas
    use_step(host)
    before = canvas.document_signature()
    panel.refresh_magnifier()
    canvas.repaint()
    assert_step(host, 'move')
    assert not host.presenter.engine.next()
    move(canvas, 220, 210)
    move(canvas, 221, 210)
    assert_step(host, 'move')
    # Slow movement must work: no individual event moves as much as 32 pixels.
    for x in range(222, 253):
        move(canvas, x, 210)
    assert_step(host, 'done')
    assert canvas.document_signature() == before
    assert not host.presenter.engine._issued
    next_info(host)
    assert progress[-1] == ('c12.magnifier', 'completed', 1)


@pytest.mark.parametrize('broken', ['no_paint', 'no_lens', 'no_motion', 'hidden',
                                     'missing_frame', 'foreign_frame', 'blank_frame', 'suppressed'])
def test_missing_business_results_fail_then_real_lens_movement_passes(lens_host, monkeypatch, broken):
    host, _ = lens_host
    panel, canvas = host.panel, host.panel.canvas
    use_step(host)
    original = canvas.magnifier_pixmap
    with monkeypatch.context() as patch:
        if broken == 'no_paint':
            patch.setattr(canvas, 'repaint', lambda: None)
        elif broken == 'no_lens':
            patch.setattr(canvas, 'draw_magnifier', lambda painter: None)
        elif broken == 'no_motion':
            patch.setattr(canvas, '_touch_synthesized', lambda event: True)
        elif broken == 'hidden':
            canvas.hide()
        elif broken == 'missing_frame':
            patch.setattr(canvas, 'magnifier_pixmap', None)
        elif broken == 'foreign_frame':
            patch.setattr(canvas, 'magnifier_pixmap', original.copy())
        elif broken == 'blank_frame':
            frame = QPixmap(original.size())
            frame.fill(canvas.board_background())
            patch.setattr(canvas, 'magnifier_pixmap', frame)
            patch.setattr(panel, '_teaching_magnifier_frame_key', frame.cacheKey())
        if broken == 'suppressed':
            with panel.teaching_events.suppress():
                sweep(canvas)
        else:
            sweep(canvas)
        assert_step(host, 'move')
        assert not host.presenter.engine._issued
    canvas.show()
    drain(QApplication.instance())
    sweep(canvas)
    assert_step(host, 'done')
    assert not host.presenter.engine._issued


def test_blank_board_outside_lens_and_previous_epoch_cannot_count(lens_host):
    host, _ = lens_host
    canvas = host.panel.canvas
    use_step(host)
    for point in ((10, 10), (80, 80), (580, 520), (620, 520)):
        move(canvas, *point)
    assert_step(host, 'move')
    sweep(canvas)
    assert_step(host, 'done')
    host.presenter.controller.previous_button.click()
    assert_step(host, 'move')
    move(canvas, 230, 210)
    assert_step(host, 'move')
    move(canvas, 270, 225)
    assert_step(host, 'done')


@pytest.mark.parametrize('dpr', [1.0, 1.5, 2.0])
def test_private_source_tracks_board_transform_and_pixel_ratio(lens_host, monkeypatch, dpr):
    host, _ = lens_host
    panel, canvas = host.panel, host.panel.canvas
    panel.infinite_whiteboard = True
    canvas.board_view.zoom = 1.4
    canvas.board_view.x, canvas.board_view.y = 55, 20
    monkeypatch.setattr(canvas, 'devicePixelRatioF', lambda: dpr)
    segment = canvas.all_segments[0]['line']
    sample = canvas.to_view(segment.pointAt(0.5))

    def assert_source_ink(frame):
        image = frame.toImage()
        color = image.pixelColor(round(sample.x() * dpr), round(sample.y() * dpr))
        assert color == QColor('#235789'), color.name()
        assert frame.devicePixelRatio() == dpr
        assert frame.width() >= canvas.width() * dpr
        assert frame.height() >= canvas.height() * dpr

    # Calibrate the pixel assertion: a missing content paint must actually fail.
    with monkeypatch.context() as patch:
        patch.setattr(canvas, 'draw_content', lambda painter: None)
        with pytest.raises(AssertionError):
            assert_source_ink(render_private_magnifier_frame(panel))
    assert_source_ink(render_private_magnifier_frame(panel))


def test_real_lens_enlarges_source_but_pixmap_render_does_not_complete(lens_host, monkeypatch):
    host, _ = lens_host
    panel, canvas = host.panel, host.panel.canvas
    use_step(host)
    canvas.mouse_pos = QPointF(240, 210)

    def assert_enlarged_ink():
        frame = QPixmap(canvas.size())
        frame.fill(canvas.board_background())
        painter = QPainter(frame)
        try:
            canvas.draw_magnifier(painter)
        finally:
            painter.end()
        # At x=240 the source line is y=199.4; 2.5x maps it to y=183.5.
        assert frame.toImage().pixelColor(240, 184) == QColor('#235789')
        assert canvas.magnifier_pixmap.toImage().pixelColor(240, 184) == canvas.board_background()

    with monkeypatch.context() as patch:
        patch.setattr(canvas, 'draw_magnifier', lambda painter: None)
        with pytest.raises(AssertionError):
            assert_enlarged_ink()
    assert_enlarged_ink()
    assert_step(host, 'move')
    sweep(canvas)
    assert_step(host, 'done')


def test_no_bus_keeps_ordinary_mouse_path_without_forced_paints(lens_host, monkeypatch):
    host, _ = lens_host
    canvas, panel = host.panel.canvas, host.panel
    use_step(host)

    def unexpected():
        raise AssertionError('ordinary pointer motion must not force synchronous painting')

    # The control detects the lesson-only repaint, then verifies no-bus behavior.
    monkeypatch.setattr(canvas, 'repaint', unexpected)
    with pytest.raises(AssertionError, match='ordinary pointer'):
        canvas.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(220, 210), QPointF(220, 210),
            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    panel.teaching_events = None
    move(canvas, 260, 225)
    assert canvas.mouse_pos == QPointF(260, 225)
    assert_step(host, 'move')


@pytest.mark.parametrize('origin,dpr', [((0, 0), 1.0), ((-1700, -180), 1.5)])
def test_controller_dodges_actual_lens_sweep_without_following_pointer(lens_host, monkeypatch, origin, dpr):
    from test_teaching_text_occlusion import layout_scene
    host, _ = lens_host
    area = layout_scene(host, monkeypatch, origin, dpr)
    use_step(host)
    canvas, presenter = host.panel.canvas, host.presenter
    drain(QApplication.instance())
    # Independently construct the visible lens+badge sweep over the actual two
    # pointer positions used by this exercise, not the protection helper result.
    sweep_rect = QRect(58, 48, 364, 369).translated(canvas.mapToGlobal(QPoint()))

    def assert_clear():
        card = presenter.controller.frameGeometry()
        assert area.contains(card), (area, card)
        assert not card.intersects(sweep_rect), (card, sweep_rect)

    assert_clear()
    # Move the real card over the lens while leaving source ink unobstructed.
    # This is exactly the gap in the old source-only interaction region.
    presenter.controller.move(sweep_rect.topLeft())
    with pytest.raises(AssertionError):
        assert_clear()
    presenter.refresh_layout()
    assert_clear()
    stable = QRect(presenter.controller.frameGeometry())
    move(canvas, 220, 210)
    presenter.refresh_layout()
    assert presenter.controller.frameGeometry() == stable
    move(canvas, 240, 215)
    presenter.refresh_layout()
    assert presenter.controller.frameGeometry() == stable
    assert_step(host, 'move')
    move(canvas, 260, 225)
    assert_step(host, 'done')
