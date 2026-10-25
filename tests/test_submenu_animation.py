"""Submenu transitions preserve the synchronous menu contract."""
import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MYSCREENDRAW_NO_KEYBOARD", "1")
os.environ.setdefault("PYNPUT_BACKEND", "dummy")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def panel():
    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QApplication
    import main

    app = QApplication.instance() or QApplication([])
    before = set(QApplication.topLevelWidgets())
    control = main.ControlPanel()
    canvas = main.DrawingCanvas(control)
    control.canvas = canvas
    control.set_ui_mode("icon", persist=False)
    control.show()
    try:
        yield control
    finally:
        control.pause_callbacks()
        for window in set(QApplication.topLevelWidgets()) - before:
            window.hide()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def wait_until(predicate, timeout=1000):
    from PyQt6.QtCore import QElapsedTimer
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < timeout:
        QApplication.processEvents()
        QTest.qWait(10)
    assert predicate()


def test_submenu_animation_setting_is_live_and_persisted(panel, monkeypatch):
    assert panel.submenu_animations_enabled is True
    assert panel.collect_settings()["submenu_animations_enabled"] is True

    panel.set_submenu_animations_enabled(False, persist=False)

    assert panel.submenu_animations_enabled is False
    assert panel.collect_settings()["submenu_animations_enabled"] is False

    saved = []
    monkeypatch.setattr(panel, "save_settings", lambda: saved.append(True))
    panel.build_settings_panel()
    panel.submenu_animation_checkbox.setChecked(True)
    assert panel.submenu_animations_enabled is True
    assert saved == [True]


def test_portrait_submenu_opens_from_toolbar_side_and_finishes_at_anchor(panel, monkeypatch):
    from PyQt6.QtCore import QPoint
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_orientation("portrait")
    panel.toolbar_window.move(20, 80)

    panel.set_submenu_animations_enabled(False, persist=False)
    panel.show_only_sub(panel.shape_sub)
    expected = QPoint(panel.menu_panel.pos())
    panel.show_only_sub(None)

    panel.set_submenu_animations_enabled(True, persist=False)
    panel.show_only_sub(panel.shape_sub)

    assert panel.menu_panel.isVisible()
    assert panel.menu_panel.pos() == expected + QPoint(-panel.SUBMENU_ANIMATION_OFFSET, 0)
    wait_until(lambda: panel._menu_open_animation is None)
    assert panel.menu_panel.pos() == expected
    assert panel.menu_panel.graphicsEffect() is None


def test_close_hides_real_menu_synchronously_and_uses_input_transparent_afterimage(panel, monkeypatch):
    from PyQt6.QtCore import Qt
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_submenu_animations_enabled(True, persist=False)
    panel.show_only_sub(panel.shape_sub)
    wait_until(lambda: panel._menu_open_animation is None)
    assert not panel.menu_panel.grab().isNull()

    panel.show_only_sub(None)

    assert not panel.menu_panel.isVisible()
    assert panel._menu_close_overlay.isVisible()
    assert panel.menu_panel.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert panel._menu_close_overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert panel._menu_close_overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert panel._menu_close_overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    wait_until(lambda: not panel._menu_close_overlay.isVisible())


def test_animation_parameters_and_window_opacity(panel, monkeypatch):
    from PyQt6.QtCore import QEasingCurve
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_ui_opacity(73, persist=False)
    panel.set_submenu_animations_enabled(True, persist=False)
    panel.show_only_sub(panel.shape_sub)

    group = panel._menu_open_animation
    assert group is not None
    assert group.animationCount() == 2
    for index in range(group.animationCount()):
        animation = group.animationAt(index)
        assert animation.duration() == 140
        assert animation.easingCurve().type() == QEasingCurve.Type.OutCubic
    assert panel.menu_panel.windowOpacity() == pytest.approx(0.73, abs=0.01)
    wait_until(lambda: panel._menu_open_animation is None)
    assert panel.menu_panel.graphicsEffect() is None
    assert panel.menu_panel.windowOpacity() == pytest.approx(0.73, abs=0.01)

    panel.show_only_sub(None)
    group = panel._menu_close_animation
    assert group is not None
    for index in range(group.animationCount()):
        animation = group.animationAt(index)
        assert animation.duration() == 100
        assert animation.easingCurve().type() == QEasingCurve.Type.InCubic
    assert panel._menu_close_overlay.windowOpacity() == pytest.approx(0.73, abs=0.01)


@pytest.mark.parametrize(
    ("orientation", "side", "expected"),
    [
        ("landscape", "below", (0, -10)),
        ("landscape", "above", (0, 10)),
        ("portrait", "right", (-10, 0)),
        ("portrait", "left", (10, 0)),
    ],
)
def test_animation_delta_points_toward_toolbar(panel, orientation, side, expected):
    from PyQt6.QtCore import QPoint

    panel.set_orientation(orientation)
    frame = panel.toolbar_window.frameGeometry()
    size = panel.menu_panel.size()
    if side == "below":
        final_pos = QPoint(frame.left(), frame.bottom() + 20)
    elif side == "above":
        final_pos = QPoint(frame.left(), frame.top() - size.height() - 20)
    elif side == "right":
        final_pos = QPoint(frame.right() + 20, frame.top())
    else:
        final_pos = QPoint(frame.left() - size.width() - 20, frame.top())

    assert panel._submenu_animation_delta(final_pos) == QPoint(*expected)


def test_all_shared_submenus_take_the_open_animation_path(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_submenu_animations_enabled(True, persist=False)
    assert len(panel.all_subs()) == 11
    for target in panel.all_subs():
        panel.show_only_sub(target)
        assert panel.menu_panel.isVisible()
        assert panel._menu_open_animation is not None
        assert [sub.isVisible() for sub in panel.all_subs()].count(True) == 1
        assert target.isVisible()
        wait_until(lambda: panel._menu_open_animation is None)
        panel.show_only_sub(None)
        panel._stop_menu_close_animation(hide_overlay=True)


def test_latest_request_wins_across_open_close_and_switch(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_submenu_animations_enabled(True, persist=False)

    panel.show_only_sub(panel.shape_sub)
    assert panel._menu_open_animation is not None
    panel.show_only_sub(None)
    assert not panel.menu_panel.isVisible()
    assert not panel._menu_close_overlay.isVisible()

    panel.show_only_sub(panel.shape_sub)
    wait_until(lambda: panel._menu_open_animation is None)
    panel.show_only_sub(None)
    assert panel._menu_close_overlay.isVisible()
    panel.show_only_sub(panel.tools_sub)
    assert not panel._menu_close_overlay.isVisible()
    assert panel.menu_panel.isVisible()
    assert panel.tools_sub.isVisible()
    assert panel._menu_open_animation is not None

    panel.show_only_sub(panel.file_sub)
    assert panel.menu_panel.isVisible()
    assert panel.file_sub.isVisible()
    assert not panel.tools_sub.isVisible()
    assert panel._menu_open_animation is None


@pytest.mark.parametrize("application_enabled,system_enabled", [(False, True), (True, False)])
def test_disabled_animation_paths_are_immediate(panel, monkeypatch, application_enabled, system_enabled):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: system_enabled, raising=False)
    panel.set_submenu_animations_enabled(application_enabled, persist=False)
    panel.show_only_sub(panel.shape_sub)
    assert panel.menu_panel.isVisible()
    assert panel._menu_open_animation is None
    panel.show_only_sub(None)
    assert not panel.menu_panel.isVisible()
    assert not panel._menu_close_overlay.isVisible()


def test_thumbnail_open_clears_close_afterimage(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.canvas.enter_whiteboard()
    panel.set_submenu_animations_enabled(True, persist=False)
    panel.show_only_sub(panel.shape_sub)
    wait_until(lambda: panel._menu_open_animation is None)
    panel.show_only_sub(None)
    assert panel._menu_close_overlay.isVisible()

    panel.toggle_thumbnail_panel()

    assert panel.thumbnail_panel.isVisible()
    assert not panel.menu_panel.isVisible()
    assert not panel._menu_close_overlay.isVisible()


def test_animation_frames_do_not_restack_windows(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    raised = []
    monkeypatch.setattr(panel, "raise_floating", lambda window: raised.append(window))
    panel.set_submenu_animations_enabled(True, persist=False)

    panel.show_only_sub(panel.shape_sub)
    assert raised == [panel.menu_panel]
    wait_until(lambda: panel._menu_open_animation is None)
    assert raised == [panel.menu_panel]

    panel.show_only_sub(None)
    assert raised == [panel.menu_panel, panel._menu_close_overlay]
    wait_until(lambda: panel._menu_close_animation is None)
    assert raised == [panel.menu_panel, panel._menu_close_overlay]


def test_animation_construction_failure_falls_back_to_immediate_state(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    panel.set_submenu_animations_enabled(True, persist=False)
    monkeypatch.setattr(panel, "_start_menu_open_animation",
                        lambda _final_pos: (_ for _ in ()).throw(RuntimeError("unavailable")))
    panel.show_only_sub(panel.shape_sub)
    assert panel.menu_panel.isVisible()
    assert panel._menu_open_animation is None

    monkeypatch.setattr(panel, "_start_menu_close_animation",
                        lambda *_args: (_ for _ in ()).throw(RuntimeError("unavailable")))
    panel.show_only_sub(None)
    assert not panel.menu_panel.isVisible()
    assert not panel._menu_close_overlay.isVisible()


def test_two_control_panels_keep_animation_state_isolated(panel, monkeypatch):
    import main

    monkeypatch.setattr(main, "client_area_animations_enabled", lambda: True, raising=False)
    other = main.ControlPanel()
    other_canvas = main.DrawingCanvas(other)
    other.canvas = other_canvas
    other.set_ui_mode("icon", persist=False)
    other.show()
    try:
        panel.set_submenu_animations_enabled(True, persist=False)
        other.set_submenu_animations_enabled(True, persist=False)
        panel.show_only_sub(panel.shape_sub)
        other.show_only_sub(other.tools_sub)
        assert panel._menu_open_animation is not None
        assert other._menu_open_animation is not None
        assert panel._menu_open_animation is not other._menu_open_animation

        panel.show_only_sub(None)
        assert panel._menu_open_animation is None
        assert other._menu_open_animation is not None
        assert other.menu_panel.isVisible()
    finally:
        other.pause_callbacks()
