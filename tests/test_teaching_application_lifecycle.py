# SPDX-License-Identifier: GPL-3.0-or-later
"""Teaching suspension contracts, using real Qt only on the offscreen platform."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MYSCREENDRAW_NO_KEYBOARD", "1")
os.environ.setdefault("PYNPUT_BACKEND", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QRect, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon, QWidget

from app_lifecycle import AppLifecycleManager, LifecycleState


class TeachingPanel(QWidget):
    """A real QObject tree, without native stacking, input, capture, or persistence."""

    def __init__(self):
        super().__init__()
        self.runtime_context = SimpleNamespace(ui_active=True, tray=False, ordinary_recovery=True)
        self.document = SimpleNamespace(pages=[{"ink": [1, 2]}], undo=["stroke"], redo=["erase"])
        self.pages = self.document.pages
        self.undo = self.document.undo
        self.redo = self.document.redo
        self.tool = "pen"
        self.project_dirty = True
        self.project_path = "unchanged.msd"
        self.selection = ["selected-stroke"]
        self.listener = SimpleNamespace(stop=self.forbidden)
        self._bound_key = ("old-native-binding",)
        self.bind_calls = 0

    def forbidden(self, *args, **kwargs):
        raise AssertionError("Teaching lifecycle must not edit, persist, stop listeners, or use background mode")

    pause_callbacks = forbidden
    resume_callbacks = forbidden
    set_drawing_mode = forbidden
    close_thumbnail_panel = forbidden
    show_only_sub = forbidden
    _close_name_projection = forbidden
    save_project = forbidden

    def bind_topmost_stack(self):
        self.bind_calls += 1


def timer(parent, interval, active=True, single_shot=False):
    value = QTimer(parent)
    value.setTimerType(Qt.TimerType.PreciseTimer)
    value.setSingleShot(single_shot)
    value.setInterval(interval)
    if active:
        value.start()
    return value


def document_snapshot(panel):
    names = ("document", "pages", "undo", "redo", "tool", "project_dirty", "project_path", "selection")
    return {name: (getattr(panel, name), deepcopy(getattr(panel, name))) for name in names}


def assert_document_unchanged(panel, before):
    for name, (identity, value) in before.items():
        assert getattr(panel, name) is identity, name
        assert getattr(panel, name) == value, name
    assert panel.canvas.document is panel.document
    assert panel.canvas.draw_state == "DRAWING"
    assert panel.canvas.current_tool == "pen"
    assert panel.canvas.is_drawing_mode is True


@pytest.fixture
def rig():
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "offscreen", "These tests must never use a visible native platform"
    app.setQuitOnLastWindowClosed(False)
    panel = TeachingPanel()
    panel.setGeometry(40, 50, 220, 160)
    panel.canvas = QWidget()
    panel.canvas.setGeometry(20, 30, 330, 240)
    panel.canvas.document = panel.document
    panel.canvas.draw_state = "DRAWING"
    panel.canvas.current_tool = "pen"
    panel.canvas.is_drawing_mode = True
    panel.settings_panel = QWidget(None, Qt.WindowType.Tool)
    panel.settings_panel.setGeometry(70, 90, 180, 140)
    registered = QWidget(None, Qt.WindowType.Tool)
    registered.setGeometry(110, 130, 170, 120)
    nested = QDialog(panel.canvas)
    nested.setGeometry(140, 150, 120, 100)
    foreign = QWidget()
    foreign.setGeometry(160, 180, 210, 150)
    manager = AppLifecycleManager(panel)
    panel.lifecycle = manager
    manager.register_tool_window(registered)
    manager.tray_menu = QMenu(panel)
    panel.timer = timer(panel, 60_000)
    panel.detached_timer = timer(None, 61_000)
    panel.idle_timer = timer(panel, 62_000, active=False)
    panel.single_timer = timer(panel, 63_000, single_shot=True)
    nested_owner = QObject(panel.canvas)
    nested_timer = timer(nested_owner, 64_000)
    registered_timer = timer(registered, 65_000)
    foreign_timer = timer(foreign, 66_000)
    owned = (panel, panel.canvas, panel.settings_panel, registered, nested)
    timers = (panel.timer, panel.detached_timer, panel.idle_timer,
              panel.single_timer, nested_timer, registered_timer)
    for window in (panel, panel.canvas, registered, nested, foreign):
        window.show()
    result = SimpleNamespace(app=app, panel=panel, manager=manager, owned=owned, timers=timers,
                             registered=registered, nested=nested, foreign=foreign,
                             foreign_timer=foreign_timer)
    try:
        yield result
    finally:
        app.removeEventFilter(manager._window_guard)
        for value in timers + (foreign_timer,):
            if not sip.isdeleted(value):
                value.stop()
                if value.parent() is None:
                    value.deleteLater()
        for window in set(owned + (foreign, manager.tray_menu)) | set(manager._tool_windows):
            if window is not None and not sip.isdeleted(window):
                for value in window.findChildren(QTimer):
                    value.stop()
                window.hide()
                window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("state", [LifecycleState.SHOWING, "drawing", LifecycleState.COLLAPSED, LifecycleState.HIDDEN])
def test_suspension_does_not_change_document_or_lifecycle_state(rig, state, monkeypatch):
    panel, manager = rig.panel, rig.manager
    manager.state = state
    manager._state_before_hidden = "drawing"
    manager._background_allowed_windows.add(rig.registered)
    saved_background_windows = [lambda: rig.registered]
    manager._restore_windows = saved_background_windows
    monkeypatch.setattr(manager, "hide_to_background", panel.forbidden)
    before = document_snapshot(panel)
    token = manager.suspend_for_teaching()
    assert token is not None
    assert panel._teaching_suspended is True
    assert manager.state == state and manager._state_before_hidden == "drawing"
    assert manager._restore_windows is saved_background_windows
    assert rig.registered in manager._background_allowed_windows
    assert all(not window.isVisible() for window in rig.owned)
    assert all(not value.isActive() for value in rig.timers)
    assert rig.foreign.isVisible() and rig.foreign_timer.isActive()
    assert_document_unchanged(panel, before)


def test_restore_exact_visibility_geometry_timers_and_document(rig):
    panel, manager = rig.panel, rig.manager
    before = document_snapshot(panel)
    geometry = {window: QRect(window.geometry()) for window in rig.owned}
    visibility = {window: window.isVisible() for window in rig.owned}
    intervals = [value.interval() for value in rig.timers]
    activity = [value.isActive() for value in rig.timers]
    token = manager.suspend_for_teaching()
    for window in rig.owned:
        window.setGeometry(260, 270, 100, 80)
    for value in rig.timers:
        value.setInterval(70_000)
        value.setSingleShot(False)
        value.setTimerType(Qt.TimerType.CoarseTimer)
    panel.idle_timer.start()
    assert manager.restore_after_teaching(token) is None
    assert panel._teaching_suspended is False
    for window in rig.owned:
        assert window.isVisible() == visibility[window]
        assert window.geometry() == geometry[window]
    assert [value.interval() for value in rig.timers] == intervals
    assert [value.isActive() for value in rig.timers] == activity
    assert all(value.timerType() == Qt.TimerType.PreciseTimer for value in rig.timers)
    assert panel.single_timer.isSingleShot()
    assert not panel.settings_panel.isVisible()
    assert panel.bind_calls == 1
    assert rig.foreign.isVisible() and rig.foreign_timer.isActive()
    assert_document_unchanged(panel, before)


@pytest.mark.parametrize("state", [Qt.WindowState.WindowNoState, Qt.WindowState.WindowMinimized,
                                   Qt.WindowState.WindowMaximized, Qt.WindowState.WindowFullScreen])
def test_restore_window_state_and_normal_geometry(rig, state):
    window = rig.registered
    window.setWindowState(state)
    geometry, normal = QRect(window.geometry()), QRect(window.normalGeometry())
    token = rig.manager.suspend_for_teaching()
    window.setWindowState(Qt.WindowState.WindowNoState)
    window.setGeometry(280, 290, 100, 80)
    rig.manager.restore_after_teaching(token)
    assert window.windowState() == state
    assert window.geometry() == geometry
    assert window.normalGeometry() == normal


@pytest.mark.parametrize("state", [LifecycleState.HIDDEN, LifecycleState.COLLAPSED, "drawing"])
def test_controlled_restore_is_not_blocked_by_background_or_inactive_ui(rig, state):
    manager = rig.manager
    manager.state = state
    token = manager.suspend_for_teaching()
    rig.panel.runtime_context.ui_active = False
    manager.restore_after_teaching(token)
    assert rig.panel.isVisible() and rig.registered.isVisible()
    assert not rig.panel.settings_panel.isVisible()
    assert manager.state == state


def test_repeated_suspend_is_rejected_without_losing_original_token(rig):
    token = rig.manager.suspend_for_teaching()
    with pytest.raises(RuntimeError):
        rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    assert rig.panel.isVisible() and rig.panel.timer.isActive()


def test_foreign_and_invalid_tokens_are_rejected_without_affecting_other_panel(rig):
    other_panel = TeachingPanel()
    other = AppLifecycleManager(other_panel)
    token = rig.manager.suspend_for_teaching()
    try:
        for invalid in (None, object(), token):
            with pytest.raises(ValueError):
                other.restore_after_teaching(invalid)
        assert not getattr(other_panel, "_teaching_suspended", False)
        assert rig.panel._teaching_suspended
        rig.manager.restore_after_teaching(token)
        with pytest.raises(ValueError):
            other.restore_after_teaching(token)
    finally:
        rig.app.removeEventFilter(other._window_guard)
        other_panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_successful_restore_is_idempotent_even_during_new_suspension(rig):
    first = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(first)
    first_timer_id = rig.panel.timer.timerId()
    rig.manager.restore_after_teaching(first)
    assert rig.panel.timer.timerId() == first_timer_id
    assert rig.panel.bind_calls == 1
    second = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(first)
    assert rig.panel._teaching_suspended and not rig.panel.timer.isActive()
    rig.manager.restore_after_teaching(second)
    assert rig.panel.isVisible()


@pytest.mark.parametrize("failure", ["bind_raises", "bind_false", "bind_error_flag", "geometry",
                                     "saved_geometry", "state", "show", "timer"])
def test_failed_restore_is_fail_closed_and_same_token_can_be_retried(rig, monkeypatch, failure):
    panel, manager = rig.panel, rig.manager
    before = document_snapshot(panel)
    token = manager.suspend_for_teaching()
    original_bind = panel.bind_topmost_stack

    def fail(*args, **kwargs):
        raise RuntimeError("injected restoration failure")

    with monkeypatch.context() as patch:
        if failure == "bind_raises":
            patch.setattr(panel, "bind_topmost_stack", fail)
        elif failure == "bind_false":
            patch.setattr(panel, "bind_topmost_stack", lambda: False)
        elif failure == "bind_error_flag":
            def caught_failure():
                panel._topmost_error = True
            patch.setattr(panel, "bind_topmost_stack", caught_failure)
        elif failure == "geometry":
            patch.setattr(rig.registered, "setGeometry", fail)
        elif failure == "saved_geometry":
            patch.setattr(rig.registered, "restoreGeometry", lambda *args: False)
        elif failure == "state":
            patch.setattr(rig.registered, "setWindowState", fail)
        elif failure == "show":
            patch.setattr(rig.registered, "show", lambda: None)
        else:
            patch.setattr(panel.single_timer, "start", fail)
        with pytest.raises(RuntimeError):
            manager.restore_after_teaching(token)
        assert panel._teaching_suspended is True
        assert all(not window.isVisible() for window in rig.owned)
        assert all(not value.isActive() for value in rig.timers)
        assert rig.foreign.isVisible() and rig.foreign_timer.isActive()
        assert_document_unchanged(panel, before)
    panel._topmost_error = None
    panel.bind_topmost_stack = original_bind
    manager.restore_after_teaching(token)
    assert panel.isVisible() and rig.registered.isVisible()
    assert not panel.settings_panel.isVisible()
    assert panel.timer.isActive() and not panel.idle_timer.isActive()
    assert_document_unchanged(panel, before)


def test_reentrant_restore_is_rejected_and_remains_retryable(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    with monkeypatch.context() as patch:
        patch.setattr(rig.panel, "bind_topmost_stack", lambda: rig.manager.restore_after_teaching(token))
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
    assert rig.panel._teaching_suspended
    assert all(not value.isActive() for value in rig.timers)
    rig.manager.restore_after_teaching(token)
    assert rig.panel.isVisible()


def test_rebind_cannot_show_originally_hidden_or_new_owned_windows(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    new_tool = QWidget(None, Qt.WindowType.Tool)
    rig.manager.register_tool_window(new_tool)
    attempted_visibility = []

    def rebind():
        for window in (rig.panel.settings_panel, new_tool):
            window.show()
            attempted_visibility.append(window.isVisible())
        rig.foreign.show()
        assert rig.panel._teaching_suspended

    monkeypatch.setattr(rig.panel, "bind_topmost_stack", rebind)
    rig.manager.restore_after_teaching(token)
    assert attempted_visibility == [False, False]
    assert not new_tool.isVisible() and not rig.panel.settings_panel.isVisible()
    assert rig.foreign.isVisible()


def test_failed_rebind_hides_new_owned_windows_and_stops_new_owned_timers(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    new_tool = QWidget(None, Qt.WindowType.Tool)
    rig.manager.register_tool_window(new_tool)
    new_timer = timer(new_tool, 60_000, active=False)

    def rebind():
        new_tool.show()
        new_timer.start()
        raise RuntimeError("failed after partial work")

    with monkeypatch.context() as patch:
        patch.setattr(rig.panel, "bind_topmost_stack", rebind)
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
    assert not new_tool.isVisible() and not new_timer.isActive()
    assert all(not value.isActive() for value in rig.timers)
    rig.manager.restore_after_teaching(token)


@pytest.mark.parametrize("single_shot", [False, True])
def test_timer_remaining_deadline_is_paused_without_changing_nominal_interval(rig, single_shot):
    value = rig.panel.timer
    value.setSingleShot(single_shot)
    value.start(1_500)
    time.sleep(0.18)
    remaining = value.remainingTime()
    assert 0 < remaining < 1_400
    token = rig.manager.suspend_for_teaching()
    time.sleep(0.08)
    rig.manager.restore_after_teaching(token)
    assert value.isActive() and value.interval() == 1_500
    assert abs(value.remainingTime() - remaining) <= 45


def wait_until(app, condition, seconds=1.0):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.002)
    assert condition(), "Qt timeout was not delivered within the offscreen test deadline"


@pytest.mark.parametrize("single_shot", [False, True])
def test_resumed_timeout_keeps_single_shot_or_original_repeating_period(rig, single_shot):
    value = rig.panel.timer
    value.setSingleShot(single_shot)
    fired = []
    value.timeout.connect(lambda: fired.append(time.monotonic()))
    value.start(180)
    time.sleep(0.10)
    token = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    wait_until(rig.app, lambda: len(fired) >= (1 if single_shot else 2))
    assert value.interval() == 180
    if single_shot:
        assert not value.isActive()
        time.sleep(0.20)
        rig.app.processEvents()
        assert len(fired) == 1
    else:
        assert fired[1] - fired[0] >= 0.145
        assert value.isActive()


def test_zero_interval_and_already_stopped_timers_keep_their_activity(rig):
    rig.panel.timer.start(0)
    rig.panel.single_timer.stop()
    token = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    assert rig.panel.timer.isActive() and rig.panel.timer.interval() == 0
    assert not rig.panel.single_timer.isActive() and rig.panel.single_timer.interval() == 63_000


@pytest.mark.parametrize("state", [LifecycleState.SHOWING, LifecycleState.HIDDEN])
@pytest.mark.parametrize("reason", ["teaching", "inactive_practice"])
def test_show_guard_blocks_owned_not_foreign_or_tray_windows(rig, state, reason):
    manager, panel = rig.manager, rig.panel
    manager.state = state
    manager._background_allowed_windows.add(panel.settings_panel)
    manager._quit_dialog_showing = True
    if reason == "teaching":
        panel._teaching_suspended = True
    else:
        panel.runtime_context.ui_active = False
    late = QDialog(panel.canvas)
    manager.register_tool_window(late)
    for window in rig.owned + (late,):
        window.hide()
        window.show()
        assert not window.isVisible()
    rig.foreign.hide()
    rig.foreign.show()
    manager.tray_menu.show()
    assert rig.foreign.isVisible() and manager.tray_menu.isVisible()
    assert rig.foreign_timer.isActive()


def test_normal_background_allowed_windows_keep_existing_semantics(rig):
    manager, panel = rig.manager, rig.panel
    manager.state = LifecycleState.HIDDEN
    panel.settings_panel.hide()
    manager._background_allowed_windows.add(panel.settings_panel)
    panel.settings_panel.show()
    assert panel.settings_panel.isVisible()
    panel.hide()
    panel.show()
    assert not panel.isVisible()
    assert rig.foreign.isVisible()


def test_practice_restart_returns_before_tempfile_save_spawn_or_quit(rig, monkeypatch):
    rig.panel.runtime_context.ordinary_recovery = False

    def forbidden(*args, **kwargs):
        raise AssertionError("Practice restart must not create recovery files, start processes, or quit")

    monkeypatch.setattr(tempfile, "gettempdir", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(rig.manager, "_do_quit", forbidden)
    assert rig.manager._restart_app() is None
    assert rig.panel.project_path == "unchanged.msd" and rig.panel.project_dirty


def test_existing_tray_capability_guard_runs_before_native_tray_checks(monkeypatch):
    panel = TeachingPanel()
    app = QApplication.instance()

    def forbidden():
        raise AssertionError("Disabled tray capability must not query native tray availability")

    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", forbidden)
    manager = AppLifecycleManager(panel)
    try:
        assert manager.tray_icon is None and manager.tray_menu is None
    finally:
        app.removeEventFilter(manager._window_guard)
        panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def focus_editor(rig, parent=None):
    from PyQt6.QtWidgets import QTextEdit
    editor = QTextEdit(rig.panel if parent is None else parent)
    editor.setPlainText("uncommitted live text")
    editor.show()
    editor.window().activateWindow()
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    rig.app.processEvents()
    assert rig.app.focusWidget() is editor
    return editor


def test_owned_focus_and_live_text_are_restored_without_committing(rig):
    editor = focus_editor(rig)
    changes = []
    editor.textChanged.connect(lambda: changes.append(editor.toPlainText()))
    rig.panel.canvas.end_text_edit = rig.panel.forbidden
    cursor = editor.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(11, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    token = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    rig.app.processEvents()
    assert rig.app.focusWidget() is editor
    assert editor.toPlainText() == "uncommitted live text" and changes == []
    assert editor.textCursor().position() == 11 and editor.textCursor().anchor() == 3


@pytest.mark.parametrize("unsafe", ["deleted", "disabled", "hidden", "foreign_parent"])
def test_focus_restore_skips_deleted_disabled_hidden_or_no_longer_owned_widget(rig, unsafe, monkeypatch):
    editor = focus_editor(rig)
    token = rig.manager.suspend_for_teaching()
    if unsafe == "deleted":
        editor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    elif unsafe == "disabled":
        editor.setEnabled(False)
    elif unsafe == "hidden":
        editor.hide()
    else:
        editor.setParent(rig.foreign)
        editor.show()
    if unsafe != "deleted":
        monkeypatch.setattr(editor, "setFocus", rig.panel.forbidden)
    rig.manager.restore_after_teaching(token)
    assert not rig.panel._teaching_suspended


def test_focus_snapshot_does_not_hold_editor_alive(rig):
    import gc
    import weakref
    editor = focus_editor(rig)
    ref = weakref.ref(editor)
    token = rig.manager.suspend_for_teaching()
    editor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del editor
    gc.collect()
    assert ref() is None
    rig.manager.restore_after_teaching(token)


def test_original_foreign_focus_is_never_explicitly_restored(rig, monkeypatch):
    editor = focus_editor(rig, rig.foreign)
    token = rig.manager.suspend_for_teaching()
    monkeypatch.setattr(editor, "setFocus", rig.panel.forbidden)
    rig.manager.restore_after_teaching(token)
    assert rig.foreign.isVisible()


def test_current_foreign_focus_is_not_stolen_when_restoring_owned_focus(rig, monkeypatch):
    original = focus_editor(rig)
    token = rig.manager.suspend_for_teaching()
    foreign = focus_editor(rig, rig.foreign)
    monkeypatch.setattr(original, "setFocus", rig.panel.forbidden)
    rig.manager.restore_after_teaching(token)
    assert rig.foreign.isVisible()
    assert foreign.toPlainText() == "uncommitted live text"


def test_successful_restore_resets_timer_last_without_counting_practice_time(rig):
    panel = rig.panel
    panel._timer_last = time.monotonic()
    panel.timer_left = 30.0
    ticks = []

    def tick():
        now = time.monotonic()
        panel.timer_left -= max(0.0, now - panel._timer_last)
        panel._timer_last = now
        ticks.append(now)

    panel.timer.timeout.connect(tick)
    panel.timer.start(60)
    token = rig.manager.suspend_for_teaching()
    start = panel._timer_last
    time.sleep(0.16)
    rig.app.processEvents()
    assert ticks == [] and panel.timer_left == 30.0
    assert panel._timer_last == start
    before_restore = time.monotonic()
    rig.manager.restore_after_teaching(token)
    assert before_restore <= panel._timer_last <= time.monotonic()
    wait_until(rig.app, lambda: bool(ticks))
    assert 29.85 < panel.timer_left <= 30.0


def test_unregister_independent_window_removes_ownership_and_only_its_background_allowance(rig):
    manager, window = rig.manager, rig.registered
    child = QDialog(window)
    child.hide()
    manager._background_allowed_windows.update((window, child, rig.panel.settings_panel))
    assert manager._owns_window(window) and manager._owns_window(child)
    manager.unregister_tool_window(window)
    assert not manager._owns_window(window) and not manager._owns_window(child)
    assert window not in manager._background_allowed_windows
    assert child in manager._background_allowed_windows
    assert rig.panel.settings_panel in manager._background_allowed_windows
    rig.panel._teaching_suspended = True
    window.hide()
    window.show()
    assert window.isVisible(), "An unregistered independent window is no longer guarded"
    manager.unregister_tool_window(window)  # Balanced teardown may be repeated.


def test_unregister_parent_owned_window_preserves_parent_chain_ownership(rig):
    manager, window = rig.manager, rig.nested
    manager.register_tool_window(window)
    manager._background_allowed_windows.add(window)
    manager.unregister_tool_window(window)
    assert manager._owns_window(window)
    assert window not in manager._background_allowed_windows
    assert manager._owns_window(rig.registered)


def test_restore_reasserts_input_barrier_until_all_steps_succeed(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    rig.panel._teaching_suspended = False  # An external controller must not lift our barrier early.

    def bind():
        assert rig.panel._teaching_suspended
        rig.panel.settings_panel.show()
        assert not rig.panel.settings_panel.isVisible()

    monkeypatch.setattr(rig.panel, "bind_topmost_stack", bind)
    rig.manager.restore_after_teaching(token)
    assert rig.panel._teaching_suspended is False


def test_failed_restore_stops_timer_created_by_rollback_hide_handler(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    created = []
    original_hide = rig.registered.hide

    def hide_with_timer():
        original_hide()
        created.append(timer(rig.registered, 60_000))

    def fail():
        raise RuntimeError("rebind failed")

    with monkeypatch.context() as patch:
        patch.setattr(rig.registered, "hide", hide_with_timer)
        patch.setattr(rig.panel, "bind_topmost_stack", fail)
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
        assert created and all(not value.isActive() for value in created)
    rig.manager.restore_after_teaching(token)


def test_restore_does_not_claim_success_if_show_handler_changes_geometry(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    original_show = rig.registered.show

    def moved_show():
        original_show()
        rig.registered.move(310, 320)

    with monkeypatch.context() as patch:
        patch.setattr(rig.registered, "show", moved_show)
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
    assert rig.panel._teaching_suspended and not rig.registered.isVisible()
    rig.manager.restore_after_teaching(token)
    assert rig.registered.geometry() == QRect(110, 130, 170, 120)


def test_restore_does_not_claim_success_if_timer_configuration_was_not_restored(rig, monkeypatch):
    token = rig.manager.suspend_for_teaching()
    rig.panel.timer.setInterval(71_000)
    with monkeypatch.context() as patch:
        patch.setattr(rig.panel.timer, "setInterval", lambda *args: None)
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
    assert rig.panel._teaching_suspended and not rig.panel.timer.isActive()
    rig.manager.restore_after_teaching(token)
    assert rig.panel.timer.interval() == 60_000


@pytest.mark.parametrize("callback", ["stop", "restart"])
def test_resumed_real_timeout_can_stop_or_restart_its_timer(rig, callback):
    value = rig.panel.timer
    fired = []

    def timeout():
        fired.append(time.monotonic())
        if callback == "stop":
            value.stop()
        elif len(fired) == 1:
            value.start(230)

    value.timeout.connect(timeout)
    value.start(100)
    time.sleep(0.05)
    token = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    wait_until(rig.app, lambda: len(fired) >= (1 if callback == "stop" else 2))
    if callback == "stop":
        assert not value.isActive() and value.interval() == 100
    else:
        assert value.interval() == 230 and fired[1] - fired[0] >= 0.19


def test_second_suspension_preserves_a_still_pending_first_timer_phase(rig):
    value = rig.panel.timer
    value.start(1_500)
    time.sleep(0.10)
    first = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(first)
    time.sleep(0.05)
    remaining = value.remainingTime()
    second = rig.manager.suspend_for_teaching()
    time.sleep(0.05)
    rig.manager.restore_after_teaching(second)
    assert value.interval() == 1_500
    assert abs(value.remainingTime() - remaining) <= 45


def test_only_trusted_explicit_recovery_window_can_show_after_failed_restore(rig, monkeypatch):
    manager, panel = rig.manager, rig.panel
    token = manager.suspend_for_teaching()
    with monkeypatch.context() as patch:
        patch.setattr(panel, "bind_topmost_stack", lambda: False)
        with pytest.raises(RuntimeError):
            manager.restore_after_teaching(token)
    recovery = QDialog(panel)
    child_dialog = QDialog(recovery)
    manager.allow_teaching_recovery_window(recovery)
    assert recovery in manager._tool_windows
    recovery.show()
    child_dialog.show()
    assert recovery.isVisible() and not child_dialog.isVisible()
    for original in rig.owned:
        original.show()
        assert not original.isVisible()
    assert all(not value.isActive() for value in rig.timers)
    assert panel._teaching_suspended and rig.foreign.isVisible()
    panel.runtime_context.ui_active = False
    recovery.hide()
    recovery.show()
    assert not recovery.isVisible(), "Practice before activation cannot use the recovery bypass"
    panel.runtime_context.ui_active = True
    recovery.show()
    assert recovery.isVisible()
    manager.disallow_teaching_recovery_window(recovery)
    assert not recovery.isVisible()
    recovery.show()
    assert not recovery.isVisible(), "Revoking the bypass must not revoke ownership and evade the guard"
    assert manager._owns_window(recovery)
    manager.restore_after_teaching(token)
    assert panel.isVisible() and not panel._teaching_suspended


def test_unregister_also_revokes_recovery_permission_before_reregistration(rig):
    window = QWidget(None, Qt.WindowType.Tool)
    token = rig.manager.suspend_for_teaching()
    rig.manager.allow_teaching_recovery_window(window)
    rig.manager.unregister_tool_window(window)
    assert not rig.manager._owns_window(window)
    rig.manager.register_tool_window(window)
    window.show()
    assert not window.isVisible()
    rig.manager.restore_after_teaching(token)


def test_recovery_window_authorization_is_weak_and_rejects_non_top_level_widgets(rig):
    import gc
    import weakref
    child = QWidget(rig.panel)
    with pytest.raises(ValueError):
        rig.manager.allow_teaching_recovery_window(child)
    with pytest.raises(ValueError):
        rig.manager.allow_teaching_recovery_window(QObject())
    window = QWidget(None, Qt.WindowType.Tool)
    rig.manager.allow_teaching_recovery_window(window)
    ref = weakref.ref(window)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del window
    gc.collect()
    assert ref() is None, "Neither ownership nor recovery authorization may keep a prompt alive"


def test_original_timer_callbacks_stay_paused_through_focus_restoration(rig, monkeypatch):
    editor = focus_editor(rig)
    fired = []
    rig.panel.timer.timeout.connect(lambda: fired.append("original callback"))
    rig.panel.timer.start(0)
    token = rig.manager.suspend_for_teaching()
    original_focus = editor.setFocus

    def focus_with_nested_events(*args):
        assert rig.panel._teaching_suspended
        rig.app.processEvents()
        assert fired == [], "Original timers must not run in a nested focus/event loop before restore commits"
        original_focus(*args)

    monkeypatch.setattr(editor, "setFocus", focus_with_nested_events)
    rig.manager.restore_after_teaching(token)
    assert not rig.panel._teaching_suspended and rig.panel.timer.isActive()
    assert fired == []


@pytest.mark.parametrize("active", [False, True])
def test_destroyed_original_business_timer_still_fails_closed(rig, active):
    value = rig.panel.single_timer if active else rig.panel.idle_timer
    token = rig.manager.suspend_for_teaching()
    value.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    with pytest.raises(RuntimeError):
        rig.manager.restore_after_teaching(token)
    assert rig.panel._teaching_suspended
    assert all(not window.isVisible() for window in rig.owned)
    with pytest.raises(RuntimeError):
        rig.manager.restore_after_teaching(token)


@pytest.mark.parametrize("explicitly_trusted", [False, True])
def test_only_explicit_coordinator_subtree_is_excluded_from_business_timer_control(rig, explicitly_trusted):
    coordinator = QObject(rig.panel)
    coordinator.setObjectName("TeachingCoordinator")
    transport = QObject(coordinator)
    watchdog = timer(coordinator, 60_000)
    communication = timer(transport, 0)
    delivered = []
    communication.timeout.connect(lambda: delivered.append("transport still running"))
    if explicitly_trusted:
        rig.panel.teaching_coordinator = coordinator
    else:
        rig.panel.other_worker = coordinator  # Class/name alone must not confer trust.
    token = rig.manager.suspend_for_teaching()
    assert watchdog.isActive() is explicitly_trusted
    assert communication.isActive() is explicitly_trusted
    assert all(not value.isActive() for value in rig.timers)
    rig.app.processEvents()
    assert bool(delivered) is explicitly_trusted
    coordinator.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert sip.isdeleted(watchdog) and sip.isdeleted(communication)
    if explicitly_trusted:
        rig.manager.restore_after_teaching(token)
        assert rig.panel.isVisible() and rig.registered.isVisible()
        assert rig.panel.timer.isActive() and not rig.panel.idle_timer.isActive()
        assert not rig.panel._teaching_suspended
    else:
        with pytest.raises(RuntimeError):
            rig.manager.restore_after_teaching(token)
        assert rig.panel._teaching_suspended and not rig.panel.timer.isActive()


def test_fullscreen_no_focus_window_keeps_state_when_show_finishes_pending_geometry(rig):
    window = QWidget(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                     | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowStaysOnTopHint)
    window.setGeometry(0, 0, 200, 100)
    window.setWindowState(Qt.WindowState.WindowFullScreen)
    window.show()
    rig.app.processEvents()
    rig.manager.register_tool_window(window)
    geometry, normal = QRect(window.geometry()), QRect(window.normalGeometry())
    assert window.windowState() == Qt.WindowState.WindowFullScreen
    token = rig.manager.suspend_for_teaching()
    rig.manager.restore_after_teaching(token)
    assert window.windowState() == Qt.WindowState.WindowFullScreen
    assert window.geometry() == geometry and window.normalGeometry() == normal
