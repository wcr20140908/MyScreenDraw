# SPDX-License-Identifier: GPL-3.0-or-later
"""ControlPanel compatibility bridge for the upgraded calculator."""
import json
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from test_teaching_application import application_host, practice_request


def test_control_panel_exposes_new_panel_through_legacy_calculator_contract(application_host):
    host, _ = application_host
    host.context.activate()
    panel = host.panel

    panel.open_calculator()

    assert panel.calculator_widget.mode == "basic"
    assert panel.calc_buttons is panel.calculator_widget.basic_buttons
    assert panel._calc_display is panel.calculator_widget.expression_edit
    for code in ("C", "2", "+", "3", "="):
        panel._calc_input(code)
    assert panel._calc_expr == panel._calc_display.text() == "5"


def test_calculator_mode_angle_retention_and_position_are_in_settings(application_host):
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    panel.open_calculator()
    panel.calculator_widget.set_mode("scientific")
    panel.calculator_widget.toggle_angle()
    panel.calc_panel.move(321, 234)

    settings = panel.collect_settings()

    assert settings["calculator_last_mode"] == "scientific"
    assert settings["calculator_angle_mode"] == "rad"
    assert settings["calculator_history_retention"] == "session"
    assert settings["calculator_x"] == 321 and settings["calculator_y"] == 234


def test_teaching_calculator_keeps_session_history_despite_saved_retention_and_emits_no_content(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    events = []
    monkeypatch.setattr("main.track_event", lambda name, **payload: events.append((name, payload)))
    panel.open_calculator()

    panel.set_calculator_history_retention("7d")
    for code in ("C", "2", "+", "3", "="):
        panel._calc_input(code)
    panel.calculator_widget.copy_result()

    assert panel.calculator_history_retention == "7d"
    assert panel.calculator_widget.history.retention == "session"
    assert all("expression" not in payload and "result" not in payload and "value" not in payload
               for _name, payload in events)


def test_calculator_window_shrinks_after_mode_switch_and_history_collapse(application_host):
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    panel.open_calculator()
    widget = panel.calculator_widget
    widget.set_mode('statistics')
    QTest.qWait(20)
    statistics_height = panel.calc_panel.height()
    widget.set_mode('base')
    QTest.qWait(20)
    assert panel.calc_panel.height() < statistics_height - 100
    widget.set_mode('basic')
    QTest.qWait(20)
    compact_height = panel.calc_panel.height()
    widget.history_toggle.setChecked(True)
    QTest.qWait(20)
    assert widget.history_frame.geometry().right() <= widget.width()
    assert not widget.history_frame.geometry().intersects(widget.stack.geometry())
    widget.history_toggle.setChecked(False)
    QTest.qWait(20)
    assert panel.calc_panel.height() <= compact_height + 8
    assert widget.stack.height() <= widget.stack.sizeHint().height() + 4
    assert QApplication.primaryScreen().availableGeometry().contains(panel.calc_panel.frameGeometry())



def test_repeated_open_uses_one_window_and_enter_escape_preserve_session(application_host):
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    panel.open_calculator()
    window, widget, history = panel.calc_panel, panel.calculator_widget, panel.calculator_widget.history
    for _ in range(5):
        panel.open_calculator()
        assert panel.calc_panel is window and panel.calculator_widget is widget
        assert widget.history is history
    edit = widget.expression_edit
    QTest.mouseClick(edit, Qt.MouseButton.LeftButton)
    edit.selectAll()
    QTest.keyClicks(edit, '2+3')
    QTest.keyClick(edit, Qt.Key.Key_Return)
    assert edit.text() == '5' and len(history.entries) == 1
    QTest.keyClick(edit, Qt.Key.Key_Escape)
    assert not window.isVisible()
    panel.open_calculator()
    assert panel.calc_panel is window and widget.expression_edit.text() == '5'
    settings = panel.collect_settings()
    assert not any(key.startswith('calculator_') and any(word in key for word in ('draft', 'expression', 'memory'))
                   for key in settings)
