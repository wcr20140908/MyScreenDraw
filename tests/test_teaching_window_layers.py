# SPDX-License-Identifier: GPL-3.0-or-later
"""Teaching windows join the existing native ordering contract; offscreen + mocked APIs."""
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QWidget

from app_lifecycle import LifecycleState
from teaching.widgets import TutorialController
from test_teaching_application_isolation import drain
from test_teaching_application_lifecycle import rig
from test_teaching_core_course import core_host


@pytest.mark.parametrize('core_host', ['c01.ink'], indirect=True)
def test_controller_is_ordered_above_canvas_and_open_pen_menu(core_host):
    host, _ = core_host
    panel, controller = host.panel, host.presenter.controller
    panel.show_only_sub(panel.draw_sub)
    assert panel.canvas.is_drawing_mode and panel.menu_panel.isVisible()
    stack = panel.floating_stack()
    assert controller in stack, 'Teaching control bar is excluded from the canvas ordering chain'
    assert stack.index(controller) < stack.index(panel.menu_panel)
    assert host.presenter.highlight in stack


@pytest.mark.parametrize('core_host', ['c01.ink'], indirect=True)
def test_native_owner_and_audit_include_controller_after_mode_and_menu_changes(core_host, monkeypatch):
    host, _ = core_host
    panel, controller = host.panel, host.presenter.controller
    owner = Mock()
    audit = Mock(return_value=(False, None, set()))
    monkeypatch.setattr(host.module, 'set_window_owner', owner)
    monkeypatch.setattr(host.module, 'enforce_topmost_order', audit)
    monkeypatch.setattr(host.module, 'mark_tool_window', Mock())
    monkeypatch.setattr(host.module, 'disable_touch_gestures', Mock())
    for drawing in (False, True):
        panel.set_drawing_mode(drawing)
        panel._bound_key = None
        panel.bind_topmost_stack()
        chain = audit.call_args.args[0]
        assert int(controller.winId()) in chain
        assert chain.index(int(controller.winId())) < chain.index(int(panel.canvas.winId()))
        assert any(call.args == (int(controller.winId()), int(panel.canvas.winId())) for call in owner.call_args_list)


@pytest.mark.parametrize('core_host', ['c01.ink'], indirect=True)
def test_pen_mode_keeps_controller_mouse_input_and_highlight_transparent(core_host):
    host, _ = core_host
    controller, canvas = host.presenter.controller, host.panel.canvas
    assert canvas.is_drawing_mode and not canvas.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not controller.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not controller.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert host.presenter.highlight.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert host.presenter.highlight.windowFlags() & Qt.WindowType.WindowTransparentForInput
    requests = QSignalSpy(host.pause_requested)
    before = canvas.document_signature()
    assert controller.isVisible()
    QTest.mouseClick(controller.pause_button, Qt.MouseButton.LeftButton)
    assert len(requests) == 1 and canvas.document_signature() == before


def test_show_rebinds_teaching_window_without_activating_or_showing_another_window(rig, monkeypatch):
    manager = rig.manager
    raise_window = Mock()
    monkeypatch.setattr(rig.panel, 'raise_floating', raise_window, raising=False)
    controller = TutorialController(lambda key: key)
    try:
        manager.register_teaching_window(controller)
        controller.show()
        drain(rig.app)
        assert raise_window.call_args.args == (controller,)
        assert controller.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert manager.teaching_windows() == (controller,)
        manager.unregister_tool_window(controller)
        assert manager.teaching_windows() == ()
    finally:
        manager.unregister_tool_window(controller)
        controller.hide()
        controller.deleteLater()
        drain(rig.app)


@pytest.mark.parametrize('retire', ['hide', 'unregister', 'delete', 'suspend', 'background'])
def test_delayed_raise_never_resurrects_a_retired_or_hidden_teaching_window(rig, monkeypatch, retire):
    manager = rig.manager
    raise_window = Mock()
    monkeypatch.setattr(rig.panel, 'raise_floating', raise_window, raising=False)
    controller = TutorialController(lambda key: key)
    try:
        manager.register_teaching_window(controller)
        controller.show()
        if retire == 'hide':
            controller.hide()
        elif retire == 'unregister':
            manager.unregister_tool_window(controller)
        elif retire == 'delete':
            sip.delete(controller)
        elif retire == 'suspend':
            rig.panel._teaching_suspended = True
            controller.hide()
        else:
            manager.state = LifecycleState.HIDDEN
            controller.hide()
        drain(rig.app)
        assert not raise_window.called
        if not sip.isdeleted(controller):
            assert manager._raise_teaching_window(controller) is False
    finally:
        rig.panel._teaching_suspended = False
        manager.state = LifecycleState.SHOWING
        manager.unregister_tool_window(controller)
        if not sip.isdeleted(controller):
            controller.hide()
            controller.deleteLater()
        drain(rig.app)


def test_layer_registration_does_not_grant_suspension_exemption(rig):
    controller = TutorialController(lambda key: key)
    try:
        rig.manager.register_teaching_window(controller)
        rig.panel._teaching_suspended = True
        controller.show()
        drain(rig.app)
        assert not controller.isVisible()
        assert controller not in rig.manager._practice_teaching_windows
        assert controller not in rig.manager._teaching_recovery_windows
    finally:
        rig.panel._teaching_suspended = False
        rig.manager.unregister_tool_window(controller)
        controller.hide()
        controller.deleteLater()
        drain(rig.app)


@pytest.mark.parametrize('core_host', ['c01.ink'], indirect=True)
def test_actual_host_controller_avoids_moving_panels_without_changing_input_epoch(core_host, monkeypatch):
    from PyQt6.QtCore import QRect
    host, _ = core_host
    panel, presenter = host.panel, host.presenter
    monkeypatch.setattr(presenter, '_available_geometry', lambda target: QRect(0, 0, 1400, 900))
    panel.toolbar_window.setGeometry(0, 80, 90, 650)
    panel.logo_window.setGeometry(0, 0, 90, 60)
    panel.show_only_sub(panel.draw_sub)
    panel.menu_panel.setFixedSize(360, 600)
    panel.menu_panel.move(110, 80)
    epoch, target = presenter.engine.step_epoch, presenter.active_target_id
    presenter.refresh_layout()
    geometry = presenter.controller.geometry()
    assert not geometry.intersects(panel.menu_panel.frameGeometry())
    assert not geometry.intersects(panel.toolbar_window.frameGeometry())
    assert geometry.left() > panel.menu_panel.frameGeometry().right()
    panel.menu_panel.setFixedSize(550, 600)
    panel.menu_panel.move(720, 80)
    presenter.refresh_layout()
    assert not presenter.controller.geometry().intersects(panel.menu_panel.frameGeometry())
    assert presenter.controller.geometry().right() < panel.menu_panel.frameGeometry().left()
    assert presenter.engine.step_epoch == epoch and presenter.active_target_id == target
    assert presenter.barrier.active and presenter.controller.isVisible()
