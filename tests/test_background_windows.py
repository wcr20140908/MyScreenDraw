# SPDX-License-Identifier: GPL-3.0-or-later
"""Background mode owns all app windows, not just the main toolbar."""
import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PyQt6.QtWidgets import QColorDialog, QMenu, QWidget
from test_upgrade_settings import app, rig


def open_tools(rig):
    p, c = rig.fresh()
    p.show()
    c.show()
    p.open_calculator()
    p.open_settings_panel()
    p.roster_panel, _ = p._make_tool_window("roster test")
    p.roster_panel.show()
    p.mini_timer.show()
    return p, c


def test_all_persistent_tools_hide_and_restore_with_content(rig, app):
    p, c = open_tools(rig)
    p._calc_expr = "12+34"
    windows = [p.calc_panel, p.settings_panel, p.roster_panel, p.mini_timer]
    positions = [w.pos() for w in windows]
    p.lifecycle.hide_to_background()
    assert all(not w.isVisible() for w in windows)
    assert not c.isVisible()
    p.lifecycle.hide_to_background()  # must not overwrite the saved snapshot
    p.lifecycle.restore_from_background()
    assert all(w.isVisible() for w in windows)
    assert [w.pos() for w in windows] == positions
    assert p._calc_expr == "12+34"
    assert not c.is_drawing_mode
    assert p.settings_panel in p.floating_stack()


def test_closed_tools_do_not_reopen_and_collapsed_toolbar_stays_collapsed(rig):
    p, c = open_tools(rig)
    p.calc_panel.hide()
    p.lifecycle.state = "collapsed"
    p.toolbar_window.hide()
    p.lifecycle.hide_to_background()
    p.lifecycle.restore_from_background()
    assert not p.calc_panel.isVisible()
    assert p.roster_panel.isVisible()
    assert not p.toolbar_window.isVisible()
    assert p.logo_window.isVisible()


def test_background_suppresses_delayed_and_new_owned_windows_not_tray(rig, app):
    p, c = open_tools(rig)
    p.lifecycle.hide_to_background()
    p.timer_running = True
    p.update_timer_ui()
    QTimer.singleShot(0, p.calc_panel.show)
    p.future_panel, _ = p._make_tool_window("future independent tool")
    p.future_panel.show()
    picker = QColorDialog(p.settings_panel)
    picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
    picker.show()
    tray = QMenu()
    p.lifecycle.tray_menu = tray
    app.processEvents()  # drain delayed tool/focus events before the tray interaction
    tray.show()
    assert not any(w.isVisible() for w in [p.calc_panel, p.mini_timer, p.future_panel, picker])
    assert tray.isVisible()
    tray.hide()
    picker.close()
    p.lifecycle.restore_from_background()
    assert p.calc_panel.isVisible()
    assert not p.future_panel.isVisible()
    assert not picker.isVisible()


def test_open_dialog_restores_but_deleted_window_does_not(rig, app):
    p, c = open_tools(rig)
    picker = QColorDialog(p.settings_panel)
    picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
    picker.show()
    p.lifecycle.hide_to_background()
    assert not picker.isVisible()
    p.roster_panel.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    p.lifecycle.restore_from_background()
    assert picker.isVisible()
    assert sip.isdeleted(p.roster_panel)
    picker.close()


def test_closed_hidden_dialog_not_resurrected(rig):
    p, c = open_tools(rig)
    picker = QColorDialog(p.settings_panel)
    picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
    picker.show()
    p.lifecycle.hide_to_background()
    picker.close()
    p.lifecycle.restore_from_background()
    assert not picker.isVisible()


def test_one_manager_does_not_hide_another_panels_windows(rig):
    p, c = open_tools(rig)
    other, _ = rig.fresh()
    other.open_calculator()
    p.lifecycle.hide_to_background()
    assert other.calc_panel.isVisible()


def test_tray_settings_is_usable_without_restoring_other_windows(rig, app):
    p, c = open_tools(rig)
    p.lifecycle.hide_to_background()
    p.lifecycle._open_settings_from_tray()
    assert p.settings_panel.isVisible()
    assert not p.calc_panel.isVisible()
    assert not c.isVisible()
    picker = QColorDialog(p.settings_panel)
    picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
    picker.show()
    app.processEvents()
    assert picker.isVisible()
    picker.close()
    p.settings_panel.close()
    p.settings_panel.show()  # a later callback is not a fresh tray request
    assert not p.settings_panel.isVisible()


def test_background_quit_confirmation_can_be_seen_and_cancelled(rig, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    p, c = open_tools(rig)
    p.lifecycle.hide_to_background()
    seen = []
    def cancel(dialog):
        dialog.show()
        seen.append(dialog.isVisible())
        p.calc_panel.show()
        assert not p.calc_panel.isVisible()
        dialog.close()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", cancel)
    p.lifecycle._quit_app()
    assert seen == [True]
    assert p.lifecycle.is_background()
    assert not p.settings_panel.isVisible()
    assert not p.timer.isActive()


def test_tray_restores_collapsed_then_expands_on_next_request(rig):
    p, c = open_tools(rig)
    p.lifecycle.state = "collapsed"
    p.toolbar_window.hide()
    p.lifecycle.hide_to_background()
    p.lifecycle.restore_from_background()
    assert p.lifecycle.state == "collapsed"
    assert not p.toolbar_window.isVisible()
    p.lifecycle.restore_from_background()
    assert p.lifecycle.state == "showing"
    assert p.toolbar_window.isVisible()


def test_repeated_cycles_and_transient_menu_do_not_change_tool_snapshot(rig):
    p, c = open_tools(rig)
    menu = QMenu(p.settings_panel)
    for _ in range(3):
        menu.show()
        p.lifecycle.hide_to_background()
        assert not menu.isVisible()
        assert not p.calc_panel.isVisible()
        p.lifecycle.restore_from_background()
        assert p.calc_panel.isVisible()
        assert not menu.isVisible()
    menu.close()


def test_tray_settings_close_button_revokes_background_permission(rig):
    p, c = open_tools(rig)
    p.lifecycle.hide_to_background()
    p.lifecycle._open_settings_from_tray()
    p.settings_panel.hide()  # custom title-bar close button uses hide, not close
    p.settings_panel.show()
    assert not p.settings_panel.isVisible()
    p.lifecycle.restore_from_background()
    assert not p.settings_panel.isVisible()


def test_name_projection_is_transient_and_cannot_appear_in_background(rig):
    p, c = open_tools(rig)
    p._show_name_projection("Synthetic name")
    projection = p._name_projection
    assert projection.isVisible()
    p.lifecycle.hide_to_background()
    assert not projection.isVisible()
    p.lifecycle.restore_from_background()
    assert not projection.isVisible()
    p.lifecycle.hide_to_background()
    p._show_name_projection("Another synthetic name")
    assert not projection.isVisible()


def test_guard_tolerates_python_wrapper_teardown(rig):
    p, c = open_tools(rig)
    guard = p.lifecycle._window_guard
    ref = guard._manager_ref
    try:
        del guard._manager_ref
        assert guard.eventFilter(p.calc_panel, QEvent(QEvent.Type.Show)) is False
    finally:
        guard._manager_ref = ref


def test_new_parentless_tool_is_guarded_before_panel_attribute_assignment(rig):
    p, c = open_tools(rig)
    p.lifecycle.hide_to_background()
    future, _ = p._make_tool_window("future tool")
    assert future.parent() is None
    future.show()
    assert not future.isVisible()
    p.lifecycle.restore_from_background()
    assert not future.isVisible()
    future.deleteLater()
