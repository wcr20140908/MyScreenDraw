# SPDX-License-Identifier: GPL-3.0-or-later
"""Instrument layout through owned offscreen controls, without desktop input."""
import math

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

from test_teaching_application_isolation import drain
from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import writing_host, next_info, assert_step


@pytest.fixture(autouse=True)
def no_desktop(monkeypatch):
    assert QApplication.instance().platformName() == 'offscreen'

    def forbidden(*args, **kwargs):
        pytest.fail('Instrument layout tests must not capture the desktop')

    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)


def visible_bounds(canvas, aid):
    # Independent oracle for painted bodies plus the full handle hit areas.
    kind = aid['kind']
    if kind == 'ruler':
        geometry = canvas.ruler_geometry(aid)
        local = QRectF(-geometry['length'] / 2 - 8, geometry['top'] - 22,
                       geometry['length'] + 16, geometry['width'] + 26)
    elif kind.startswith('set_square'):
        size = aid['size']
        height = size if kind == 'set_square_45' else size / math.sqrt(3)
        local = QRectF(-8, -8, size + 16, height + 16)
    else:
        radius = aid['radius']
        local = QRectF(-radius - 12, -radius - 12, 2 * radius + 24, radius + 50)
    for getter in (canvas._aid_rotate_handle_local, canvas._aid_close_handle_local,
                   canvas._aid_scale_handle_local, canvas._aid_width_handle_local):
        point = getter(aid)
        if point is not None:
            radius = 14 / aid['scale']
            local = local.united(QRectF(point.x() - radius, point.y() - radius,
                                       radius * 2, radius * 2))
    rect = canvas.aid_transform(aid).mapRect(local)
    zoom = canvas.board_view.zoom if canvas.board_view_active else 1
    x = canvas.board_view.x if canvas.board_view_active else 0
    y = canvas.board_view.y if canvas.board_view_active else 0
    return QRectF(rect.x() * zoom + x, rect.y() * zoom + y,
                  rect.width() * zoom, rect.height() * zoom).toAlignedRect().translated(
                      canvas.mapToGlobal(QPoint()))


def layout_scene(host, monkeypatch, area, dpr):
    import toolbar_windows
    panel, presenter = host.panel, host.presenter
    monkeypatch.setattr(toolbar_windows, '_available_rect', lambda widget: QRect(area))
    monkeypatch.setattr(panel, 'screen_geometry', lambda *widgets: QRect(area))
    monkeypatch.setattr(presenter, '_available_geometry', lambda target: QRect(area))
    monkeypatch.setattr(panel.canvas, 'devicePixelRatioF', lambda: dpr)
    panel.canvas.setWindowState(Qt.WindowState.WindowNoState)
    panel.canvas.setGeometry(area)
    panel.toolbar_window.move(area.topLeft())
    panel.logo_window.move(area.topLeft())
    panel.show_only_sub(panel.aid_sub)
    presenter.controller.resize(600, 420)
    drain(QApplication.instance())
    presenter.refresh_layout()


def drag(canvas, aid, mode):
    if mode == 'move':
        start = QPointF(aid['pos'])
        end = start + QPointF(20, 20)
    else:
        getter = {'width': canvas._aid_width_handle_local,
                  'rotate': canvas._aid_rotate_handle_local,
                  'scale': canvas._aid_scale_handle_local}[mode]
        start = canvas.aid_transform(aid).map(getter(aid))
        delta = start - aid['pos']
        end = start + QPointF(0, 12) if mode == 'width' else aid['pos'] + (
            QPointF(-delta.y(), delta.x()) if mode == 'rotate' else delta * .85)
    assert canvas.aid_hit(start) == (aid, mode)
    point = lambda p: (round(canvas.to_view(p).x()), round(canvas.to_view(p).y()))
    mouse(canvas, 'press', point(start))
    assert canvas.aid_drag['mode'] == mode
    mouse(canvas, 'move', point(end))
    mouse(canvas, 'release', point(end))


@pytest.mark.parametrize('writing_host', ['c11.instruments'], indirect=True)
@pytest.mark.parametrize('area,dpr', [
    (QRect(0, 0, 1463, 820), 1.75),
    (QRect(-1600, -180, 1280, 720), 2.0),
])
def test_lesson_spreads_new_aids_without_repositioning_previous_ones(writing_host, monkeypatch, area, dpr):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    layout_scene(host, monkeypatch, area, dpr)
    next_info(host)
    for kind, modes in [('ruler', ('move', 'width')), ('protractor', ('rotate',)),
                        ('set_square_45', ('scale',)), ('set_square_30', ('scale',))]:
        prior = [dict(aid, pos=QPointF(aid['pos'])) for aid in canvas.aids]
        panel.aid_buttons[kind].click()
        host.presenter.refresh_layout()
        aid = canvas.aids[-1]
        bounds = visible_bounds(canvas, aid)
        assert area.contains(bounds), (kind, bounds, area)
        assert canvas.aids[:-1] == prior, 'Adding a tool must not rearrange user-adjusted tools'
        for other in canvas.aids[:-1]:
            assert not bounds.intersects(visible_bounds(canvas, other)), (kind, other['kind'])
        assert not bounds.intersects(host.presenter.controller.frameGeometry()), (kind, 'controller')
        for obstacle in host._layout_obstacles():
            assert not bounds.intersects(obstacle), (kind, obstacle, bounds)
        for mode in modes:
            drag(canvas, aid, mode)
    assert_step(host, 'clear')
    snapshot, records = host.presenter._snapshot(), list(progress)
    positions = [QPointF(aid['pos']) for aid in canvas.aids]
    host.presenter.controller.resize(700, 500)
    host.presenter.refresh_layout()
    assert [aid['pos'] for aid in canvas.aids] == positions
    assert host.presenter._snapshot() == snapshot and progress == records
    for aid in canvas.aids:
        assert not visible_bounds(canvas, aid).intersects(host.presenter.controller.frameGeometry())
        for getter, mode in ((canvas._aid_close_handle_local, 'close'),
                             (canvas._aid_scale_handle_local, 'scale'),
                             (canvas._aid_rotate_handle_local, 'rotate')):
            point = canvas.aid_transform(aid).map(getter(aid))
            assert canvas.aid_hit(point) == (aid, mode)
    panel.btn_aid_clear.click()
    assert not canvas.aids
    assert_step(host, 'done')
