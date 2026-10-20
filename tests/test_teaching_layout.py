# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure geometry and synthetic Qt-window tests; no desktop capture or native input."""
from __future__ import annotations

from itertools import permutations
import os
import random
import sys
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MYSCREENDRAW_NO_KEYBOARD', '1')
os.environ.setdefault('PYNPUT_BACKEND', 'dummy')

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from teaching.models import (END_CHAPTER, TutorialCatalog, TutorialChapter, TutorialCourse,
                             TutorialStep, WaitClause, WaitSpec)
from teaching.presentation import TeachingPresenter
from teaching.targets import TargetRegistry
from teaching.widgets import TutorialController, controller_geometry


def assert_clear(rect, available, obstacles):
    assert available.contains(rect)
    assert not any(rect.intersects(obstacle) for obstacle in obstacles)


def test_left_panels_push_window_right_of_the_entire_panel():
    area = QRect(0, 0, 1440, 900)
    toolbar, panel = QRect(8, 80, 96, 650), QRect(116, 80, 360, 650)
    anchor = QRect(128, 220, 50, 35)
    geometry = controller_geometry(anchor, QSize(420, 300), area, obstacles=(toolbar, panel))
    assert_clear(geometry, area, (toolbar, panel))
    assert geometry.left() >= panel.right() + 1 + 12
    assert geometry.size() == QSize(420, 300)


@pytest.mark.parametrize('panel,side', [
    (QRect(0, 0, 1000, 350), 'below'),
    (QRect(0, 350, 1000, 350), 'above'),
])
def test_full_width_panel_uses_open_vertical_space(panel, side):
    area = QRect(0, 0, 1000, 700)
    anchor = QRect(30, panel.top() + 120, 50, 40)
    geometry = controller_geometry(anchor, QSize(420, 300), area, obstacles=(panel,))
    assert_clear(geometry, area, (panel, anchor))
    if side == 'below':
        assert geometry.top() >= panel.bottom() + 1 + 12
    else:
        assert geometry.bottom() + 1 + 12 <= panel.top()


def test_right_panel_can_fall_back_left():
    area, panel = QRect(0, 0, 1200, 800), QRect(700, 0, 500, 800)
    geometry = controller_geometry(QRect(1130, 100, 50, 40), QSize(420, 300), area,
                                   obstacles=(panel,))
    assert_clear(geometry, area, (panel,))
    assert geometry.right() + 1 + 12 <= panel.left()


def test_free_slot_can_require_edges_from_two_different_obstacles():
    area = QRect(0, 0, 1200, 850)
    obstacles = (QRect(0, 0, 330, 850), QRect(330, 0, 870, 260),
                 QRect(950, 260, 250, 590), QRect(330, 640, 620, 210))
    result = controller_geometry(QRect(15, 95, 50, 40), QSize(420, 300), area,
                                 obstacles=obstacles)
    assert_clear(result, area, obstacles)
    assert result.left() >= 330 and result.top() >= 260


def test_gap_yields_to_an_exact_fitting_slot_without_resizing():
    area, size = QRect(0, 0, 660, 400), QSize(420, 300)
    obstacles = (QRect(0, 0, 120, 400), QRect(540, 0, 120, 400))
    geometry = controller_geometry(QRect(5, 120, 70, 40), size, area, obstacles=obstacles)
    assert_clear(geometry, area, obstacles)
    assert geometry.left() == 120 and geometry.size() == size


@pytest.mark.parametrize('anchor', [QRect(), QRect(-10000, -10000, 50, 40),
                                     QRect(5000, 5000, 50, 40)])
@pytest.mark.parametrize('area,size', [
    (QRect(-1600, -900, 1000, 800), QSize(420, 300)),
    (QRect(120, 80, 320, 220), QSize(420, 300)),
    (QRect(-50, -70, 1, 1), QSize(420, 300)),
])
def test_clamps_offscreen_anchors_and_small_work_areas(anchor, area, size):
    obstacles = (QRect(area.left(), area.top(), 90, area.height()),)
    geometry = controller_geometry(anchor, size, area, obstacles=obstacles)
    assert area.contains(geometry)
    assert geometry.size() == QSize(min(size.width(), area.width()),
                                    min(size.height(), area.height()))


def test_empty_anchor_centers_in_an_empty_work_area():
    area = QRect(-1000, -700, 1000, 800)
    geometry = controller_geometry(QRect(), QSize(420, 300), area)
    assert geometry == QRect(-710, -450, 420, 300)


def test_empty_anchor_still_avoids_visible_windows():
    area, obstacle = QRect(0, 0, 1200, 800), QRect(440, 280, 320, 240)
    geometry = controller_geometry(QRect(), QSize(420, 300), area, obstacles=(obstacle,))
    assert_clear(geometry, area, (obstacle,))


def test_rectangle_order_duplicates_and_offscreen_obstacles_do_not_change_placement():
    area, anchor, size = QRect(0, 0, 1000, 750), QRect(50, 100, 60, 40), QSize(420, 300)
    obstacles = (QRect(0, 0, 220, 750), QRect(220, 0, 780, 180), QRect(900, 180, 100, 570))
    before = tuple(rect.getRect() for rect in (area, anchor, *obstacles))
    expected = controller_geometry(anchor, size, area, obstacles=obstacles)
    for order in permutations(obstacles):
        assert controller_geometry(anchor, size, area, obstacles=iter(order)) == expected
    assert controller_geometry(anchor, size, area,
                               obstacles=(*obstacles, *obstacles, QRect(), QRect(4000, 4000, 50, 50))) == expected
    assert before == tuple(rect.getRect() for rect in (area, anchor, *obstacles))


def test_translation_between_negative_and_positive_monitors_is_invariant():
    area, anchor = QRect(0, 0, 1000, 750), QRect(50, 100, 60, 40)
    obstacles = (QRect(0, 0, 220, 750), QRect(220, 0, 780, 180))
    original = controller_geometry(anchor, QSize(420, 300), area, obstacles=obstacles)
    offset = QPoint(-2200, 850)
    shifted = controller_geometry(anchor.translated(offset), QSize(420, 300), area.translated(offset),
                                 obstacles=(rect.translated(offset) for rect in obstacles))
    assert shifted == original.translated(offset)


def test_minimum_obscured_area_matches_a_small_independent_pixel_oracle():
    rng = random.Random(617)
    area, size = QRect(-3, -2, 11, 9), QSize(4, 3)
    for _ in range(60):
        obstacles = tuple(QRect(rng.randrange(-5, 8), rng.randrange(-4, 7),
                                rng.randrange(1, 10), rng.randrange(1, 8)) for _ in range(4))
        blocked = {(x, y) for x in range(area.left(), area.right() + 1)
                   for y in range(area.top(), area.bottom() + 1)
                   if any(rect.contains(x, y) for rect in obstacles)}

        def blocked_pixels(rect):
            return sum((x, y) in blocked for x in range(rect.left(), rect.right() + 1)
                       for y in range(rect.top(), rect.bottom() + 1))

        best = min(blocked_pixels(QRect(x, y, size.width(), size.height()))
                   for x in range(area.left(), area.right() + 2 - size.width())
                   for y in range(area.top(), area.bottom() + 2 - size.height()))
        result = controller_geometry(QRect(-2, -1, 1, 1), size, area, obstacles=obstacles, gap=1)
        assert area.contains(result) and result.size() == size
        assert blocked_pixels(result) == best


@pytest.mark.parametrize('area,size,gap', [(QRect(), QSize(10, 10), 12),
                                         (QRect(0, 0, 100, 100), QSize(), 12),
                                         (QRect(0, 0, 100, 100), QSize(10, 10), -1)])
def test_rejects_invalid_layout_dimensions(area, size, gap):
    with pytest.raises(ValueError):
        controller_geometry(QRect(), size, area, gap=gap)


def test_rejects_non_rectangle_obstacles_even_when_they_are_from_a_generator():
    with pytest.raises(TypeError, match='QRect'):
        controller_geometry(QRect(), QSize(40, 30), QRect(0, 0, 100, 100),
                            obstacles=(rect for rect in (QRect(), 'toolbar')))


def test_geometry_never_queries_the_screen_or_constructs_windows(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Pure geometry cannot query a screen or construct a widget')

    with monkeypatch.context() as patch:
        patch.setattr(QGuiApplication, 'primaryScreen', forbidden)
        patch.setattr(QWidget, '__init__', forbidden)
        assert_clear(controller_geometry(QRect(20, 90, 60, 40), QSize(420, 300),
                                         QRect(0, 0, 1200, 800), obstacles=(QRect(0, 0, 220, 800),)),
                     QRect(0, 0, 1200, 800), (QRect(0, 0, 220, 800),))


def drain(app):
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def scene(monkeypatch):
    import main

    def forbidden(*args, **kwargs):
        pytest.fail('Layout tests cannot construct the production UI or an input listener')

    monkeypatch.setattr(main.ControlPanel, '__init__', forbidden)
    monkeypatch.setattr(main.keyboard, 'Listener', forbidden)
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == 'offscreen'
    previous = set(app.topLevelWidgets())
    host = QWidget()
    host.setGeometry(-980, -240, 120, 600)
    button = QPushButton('target', host)
    button.setGeometry(10, 100, 90, 40)
    menu = QWidget()
    menu.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    menu.setGeometry(-848, -240, 300, 600)
    host.show()
    menu.show()
    drain(app)
    registry = TargetRegistry()
    registry.register('toolbar.mode', lambda: button)
    catalog = TutorialCatalog((TutorialCourse('c01', 1, 1, 'course', (
        TutorialChapter('c01.layout', 'chapter', 'private_sample', (
            TutorialStep('write', 'title', 'body', 'operation', 'toolbar.mode', 'target_only', (), (),
                         WaitSpec((WaitClause('ink.committed', 'success', min_count={'segments': 1}),)),
                         END_CHAPTER),)),)),))
    presenters, records = [], []
    value = SimpleNamespace(app=app, host=host, button=button, menu=menu, registry=registry,
                            area=QRect(-1000, -300, 1600, 1000), records=records)

    def obstacles():
        return (QRect(widget.mapToGlobal(QPoint()), widget.size()) for widget in (host, menu)
                if not sip.isdeleted(widget) and widget.isVisible())

    def build(**kwargs):
        presenter = TeachingPresenter(catalog, session_id='layout', registry=registry,
                                      owns=lambda window: window is host,
                                      canvas=lambda: host,
                                      translate=lambda key: '{current}/{total}' if key == 'teaching_progress' else key,
                                      prepare_fixture=lambda fixture: None, on_progress=lambda *args: records.append(args),
                                      available_geometry=lambda target: QRect(value.area), **kwargs)
        presenters.append(presenter)
        return presenter

    value.build, value.obstacles = build, obstacles
    yield value
    for presenter in presenters:
        presenter.close()
        presenter.deleteLater()
    registry.close()
    registry.deleteLater()
    for window in app.topLevelWidgets():
        if window not in previous and not sip.isdeleted(window):
            window.hide()
            window.deleteLater()
    drain(app)
    assert not errors, errors


def test_controller_place_preserves_size_opacity_style_and_host_geometry(scene):
    control = TutorialController(lambda key: key)
    before = (control.size(), control.windowOpacity(), control.styleSheet(),
              scene.host.geometry(), scene.menu.geometry())
    result = control.place(QRect(-970, -140, 90, 40), scene.area, obstacles=scene.obstacles())
    assert_clear(result, scene.area, tuple(scene.obstacles()))
    assert control.geometry() == result
    assert before == (control.size(), control.windowOpacity(), control.styleSheet(),
                      scene.host.geometry(), scene.menu.geometry())


def test_presenter_default_callbacks_remain_optional(scene):
    presenter = scene.build()
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    assert presenter.controller.isVisible()
    assert not presenter._layout_timer.isActive()
    assert presenter.barrier.installed


def test_presenter_avoids_left_panels_without_requesting_activation_or_changing_windows(scene, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Showing teaching windows must not request activation or focus')

    monkeypatch.setattr(QWidget, 'activateWindow', forbidden)
    monkeypatch.setattr(QWidget, 'setFocus', forbidden)
    host_before = (scene.host.geometry(), scene.host.windowOpacity(), scene.host.styleSheet(),
                   scene.menu.geometry(), scene.menu.windowOpacity(), scene.menu.styleSheet())
    presenter = scene.build(layout_obstacles=scene.obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))
    assert presenter.controller.x() >= scene.menu.geometry().right() + 1 + 12
    assert presenter.controller.size() == QSize(420, 300)
    assert host_before == (scene.host.geometry(), scene.host.windowOpacity(), scene.host.styleSheet(),
                           scene.menu.geometry(), scene.menu.windowOpacity(), scene.menu.styleSheet())
    for window in (presenter.controller, presenter.highlight):
        assert window.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert window.windowModality() == Qt.WindowModality.NonModal
    assert presenter.highlight.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert presenter.highlight.geometry() == scene.registry.global_rect('toolbar.mode')


def test_timer_avoids_an_independently_opened_panel_without_touching_input_or_step(scene, monkeypatch):
    scene.menu.hide()
    presenter = scene.build(layout_obstacles=scene.obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    geometry = QRect(presenter.controller.geometry())
    snapshot, records = presenter._snapshot(), list(scene.records)
    scene.menu.setGeometry(geometry)
    scene.menu.show()
    drain(scene.app)
    # offscreen auto-activates Tool windows on show despite their no-focus flags.
    # Test movement separately, with the host holding Qt's synthetic focus.
    QApplication.setActiveWindow(scene.host)
    scene.button.setFocus()
    focus, active = scene.app.focusWidget(), scene.app.activeWindow()

    def forbidden(*args, **kwargs):
        pytest.fail('Placement refresh must not reconfigure the input barrier')

    with monkeypatch.context() as patch:
        patch.setattr(presenter.barrier, 'activate', forbidden)
        patch.setattr(presenter.barrier, 'deactivate', forbidden)
        QTest.qWait(240)
        assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))
        assert presenter.controller.geometry() != geometry
        assert presenter._snapshot() == snapshot and scene.records == records
        assert presenter.barrier.installed
        assert scene.app.focusWidget() is focus and scene.app.activeWindow() is active


def test_panel_movement_and_closure_refresh_from_fresh_rectangles(scene):
    presenter = scene.build(layout_obstacles=scene.obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    original = QRect(presenter.controller.geometry())
    scene.menu.setGeometry(original)
    presenter.refresh_layout()
    assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))
    assert presenter.controller.geometry() != original
    scene.menu.hide()
    presenter.refresh_layout()
    assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))
    assert presenter.controller.x() < original.x()


def test_mutating_a_reused_qrect_is_observed_and_unchanged_layout_is_cached(scene, monkeypatch):
    obstacles = [QRect(-1000, -300, 220, 1000)]
    presenter = scene.build(layout_obstacles=lambda: obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    old = QRect(presenter.controller.geometry())
    obstacles[0].setRect(*old.getRect())
    presenter.refresh_layout()
    assert_clear(presenter.controller.geometry(), scene.area, obstacles)
    assert presenter.controller.geometry() != old

    def forbidden(*args, **kwargs):
        pytest.fail('An unchanged placement must not solve or set geometry again')

    with monkeypatch.context() as patch:
        patch.setattr(presenter.controller, 'place', forbidden)
        presenter.refresh_layout()
        presenter.refresh_layout()
    assert presenter.engine.phase == 'running'


def test_paused_controller_keeps_dynamic_avoidance_without_resuming(scene, monkeypatch):
    presenter = scene.build(layout_obstacles=scene.obstacles)
    presenter.start('c01', 'c01.layout')
    presenter.pause()
    drain(scene.app)
    old = QRect(presenter.controller.geometry())
    scene.menu.setGeometry(old)
    snapshot = presenter._snapshot()

    def forbidden(*args, **kwargs):
        pytest.fail('Paused placement must not resume or reconfigure input')

    with monkeypatch.context() as patch:
        patch.setattr(presenter.barrier, 'activate', forbidden)
        patch.setattr(presenter.barrier, 'deactivate', forbidden)
        presenter.refresh_layout()
    assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))
    assert presenter._snapshot() == snapshot and presenter.engine.phase == 'paused'
    assert not presenter.barrier.installed


def test_work_area_change_clamps_controller_without_resizing_host_windows(scene):
    presenter = scene.build(layout_obstacles=scene.obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    original = (scene.host.geometry(), scene.menu.geometry())
    scene.area = QRect(-1400, -800, 350, 240)
    presenter.refresh_layout()
    assert scene.area.contains(presenter.controller.geometry())
    assert presenter.controller.size() == scene.area.size()
    assert original == (scene.host.geometry(), scene.menu.geometry())


def test_native_dialog_scope_hides_windows_and_suspends_layout_callbacks(scene):
    reads = []

    def obstacles():
        reads.append(True)
        return scene.obstacles()

    presenter = scene.build(layout_obstacles=obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    with presenter.native_dialog():
        count = len(reads)
        assert not presenter.controller.isVisible() and not presenter.highlight.isVisible()
        assert not presenter._layout_timer.isActive()
        scene.menu.setGeometry(presenter.controller.geometry())
        presenter.refresh_layout()
        assert len(reads) == count
    assert presenter.controller.isVisible() and presenter._layout_timer.isActive()
    assert_clear(presenter.controller.geometry(), scene.area, tuple(scene.obstacles()))


def test_restacks_visible_windows_after_show_and_highlight_without_manage_hooks(scene):
    restacked = []

    def restack(window):
        assert window.isVisible()
        restacked.append((window, QRect(window.geometry())))

    presenter = scene.build(layout_obstacles=scene.obstacles, restack_window=restack)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    assert any(window is presenter.controller for window, _ in restacked)
    assert any(window is presenter.highlight and rect == scene.registry.global_rect('toolbar.mode')
               for window, rect in restacked)
    assert restacked[-1][0] is presenter.controller
    assert presenter.highlight.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    restacked.clear()
    scene.menu.setGeometry(presenter.controller.geometry())
    presenter.refresh_layout()
    assert restacked and all(window is presenter.controller for window, _ in restacked)


@pytest.mark.parametrize('hook', ['layout_obstacles', 'restack_window'])
def test_constructor_rejects_untrusted_hook_values_before_creating_windows(scene, hook):
    previous = set(scene.app.topLevelWidgets())
    with pytest.raises(ValueError, match='trusted callable'):
        scene.build(**{hook: 'host.function'})
    assert set(scene.app.topLevelWidgets()) == previous


@pytest.mark.parametrize('failure', ['raise', 'invalid'])
def test_obstacle_callback_failure_stops_presentation_and_releases_barrier(scene, failure):
    source = {'value': ()}

    def obstacles():
        if source['value'] == 'raise':
            raise RuntimeError('unavailable layout source')
        return source['value']

    presenter = scene.build(layout_obstacles=obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    failed = QSignalSpy(presenter.failed)
    source['value'] = 'raise' if failure == 'raise' else ['not a QRect']
    presenter.refresh_layout()
    assert len(failed) == 1 and failed[0] == ['presentation_failed']
    assert presenter.engine.phase == 'stopped'
    assert not presenter.controller.isVisible() and not presenter.highlight.isVisible()
    assert not presenter.barrier.installed and not presenter._layout_timer.isActive()


def test_obstacle_callback_can_close_presenter_without_resurrecting_windows(scene):
    source = {'close': False}

    def obstacles():
        if source['close']:
            presenter.close()
        return scene.obstacles()

    presenter = scene.build(layout_obstacles=obstacles)
    presenter.start('c01', 'c01.layout')
    drain(scene.app)
    source['close'] = True
    presenter.refresh_layout()
    assert presenter._closed and not presenter._layout_timer.isActive()
    assert not presenter.controller.isVisible() and not presenter.barrier.installed
    drain(scene.app)
    assert sip.isdeleted(presenter.controller)
    presenter.refresh_layout()


def test_restacking_callback_can_close_presenter_without_starting_timer(scene):
    def restack(window):
        if window is presenter.controller:
            presenter.close()

    presenter = scene.build(layout_obstacles=scene.obstacles, restack_window=restack)
    presenter.start('c01', 'c01.layout')
    assert presenter._closed and not presenter._layout_timer.isActive()
    assert not presenter.barrier.installed
