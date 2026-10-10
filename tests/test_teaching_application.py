# SPDX-License-Identifier: GPL-3.0-or-later
"""Authenticated application bridge; test-only course resources, no desktop input."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject, QTimer, QPoint, pyqtSignal
from PyQt6.QtWidgets import QApplication

from persistence import make_project_data, atomic_write_project
from runtime_paths import RuntimePaths, RuntimeContext
from teaching.bootstrap import PracticeRequest
from test_teaching_application_isolation import drain


class Peer(QObject):
    received = pyqtSignal(dict)
    closed = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.messages = []
        self.is_closed = False

    def send(self, kind, payload):
        message = uuid.uuid4().hex
        self.messages.append((kind, payload, message))
        return message

    def close(self):
        if not self.is_closed:
            self.is_closed = True
            self.closed.emit()

    def control(self, action, **details):
        self.received.emit({'type': 'control', 'payload': {'action': action, **details}})


class Host(QObject):
    exit_requested = pyqtSignal()
    failed = pyqtSignal(str)
    pause_requested = pyqtSignal()

    def __init__(self, progress):
        super().__init__()
        self.calls = []
        self.progress = progress
        self.progress_ack = Mock()

    def activate(self):
        self.calls.append('activate')
        self.progress('c01.foundation', 'in_progress', 1)

    def pause(self, *, hidden=False):
        self.calls.append(('pause', hidden))

    def resume(self):
        self.calls.append('resume')

    def close(self):
        self.calls.append('close')


@pytest.fixture
def practice_request(tmp_path):
    root = Path(__file__).resolve().parents[1]
    resources = tmp_path / 'resources'
    tutorial = resources / 'assets' / 'tutorials'
    (tutorial / 'fixtures').mkdir(parents=True)
    page = {'id': uuid.uuid4().hex, 'name': 'Practice', 'segments': [],
            'texts': [], 'shapes': [], 'images': []}
    atomic_write_project(str(tutorial / 'fixtures' / 'blank.msd'), make_project_data(
        pages=[page], current_page=0, whiteboard_mode=True, board_style='WHITE', app_version='6.1.0'))
    course = {'schema_version': 1, 'id': 'c01', 'revision': 1, 'compat_revision': 1,
              'title_key': 'teaching_center_title', 'chapters': [{
                  'id': 'c01.foundation', 'title_key': 'teaching_center_title', 'fixture': 'blank', 'steps': [
                      {'id': 'ink', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
                       'target': 'canvas.ink', 'input_policy': 'canvas',
                       'wait': {'event': 'ink.committed', 'outcome': 'success'}, 'next': 'save'},
                      {'id': 'save', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
                       'target': 'file.save', 'input_policy': 'target_only', 'reveal': ['open_file_panel'],
                       'wait': {'event': 'project.saved', 'outcome': 'success'}, 'next': 'end_chapter'}]}]}
    (tutorial / 'course.json').write_text(json.dumps(course), encoding='utf-8')
    index = {'schema_version': 1, 'fixtures': {'blank': 'fixtures/blank.msd'}, 'courses': ['course.json'],
             'groups': [{'id': 'core', 'title_key': 'teaching_center_title', 'courses': ['c01']}]}
    (tutorial / 'catalog.json').write_text(json.dumps(index), encoding='utf-8')
    paths = RuntimePaths.create_practice(root, resources, temp_root=tmp_path / 'owned-temp')
    return PracticeRequest(paths, 'myscreendraw-teaching-' + uuid.uuid4().hex, 'c01', 'c01.foundation')


@pytest.fixture
def child(practice_request):
    from teaching.application import PracticeChild
    peer = Peer()
    context = RuntimeContext(practice_request.paths)
    hosts = []
    def factory(progress):
        assert context.ui_active is False
        host = Host(progress)
        hosts.append(host)
        return host
    runtime = PracticeChild(practice_request, peer, context=context, host_factory=factory)
    yield runtime, peer, context, hosts
    runtime.stop()


def test_child_constructs_hidden_host_then_waits_for_authenticated_activate(child):
    runtime, peer, context, hosts = child
    assert not hosts and not peer.messages
    runtime.start()
    assert not context.ui_active and hosts[0].calls == []
    assert [message[0] for message in peer.messages] == ['hello', 'ready']
    peer.control('activate')
    assert runtime.phase == 'running' and context.ui_active
    assert hosts[0].calls == ['activate']
    assert [message[0] for message in peer.messages][-2:] == ['activated', 'chapter_state']


def test_duplicate_activate_cannot_show_another_ui(child):
    runtime, peer, context, hosts = child
    runtime.start()
    peer.control('activate')
    peer.control('activate')
    assert runtime.phase == 'stopped' and not context.ui_active
    assert hosts[0].calls.count('activate') == 1 and hosts[0].calls[-1] == 'close'


def test_child_disconnect_closes_host_without_marking_completed(child):
    runtime, peer, context, hosts = child
    runtime.start()
    peer.control('activate')
    peer.close()
    assert runtime.phase == 'stopped' and not context.ui_active
    assert hosts[0].calls[-1] == 'close'
    assert not any(kind == 'chapter_state' and payload['status'] == 'completed'
                   for kind, payload, _ in peer.messages)


def test_pause_and_hidden_pause_resume_are_explicit(child):
    runtime, peer, context, hosts = child
    runtime.start(); peer.control('activate')
    peer.control('pause', hidden=True)
    assert runtime.phase == 'paused' and hosts[0].calls[-1] == ('pause', True)
    peer.control('resume')
    assert runtime.phase == 'running' and hosts[0].calls[-1] == 'resume'


def test_progress_ack_is_correlated_and_false_is_not_success(child):
    runtime, peer, context, hosts = child
    runtime.start(); peer.control('activate')
    message_id = peer.messages[-1][2]
    peer.received.emit({'type': 'state_ack', 'payload': {
        'message_id': message_id, 'chapter_id': 'c01.foundation', 'persisted': False}})
    hosts[0].progress_ack.assert_called_once_with('c01.foundation', 'in_progress', False)
    assert runtime.phase == 'running'


def test_unknown_progress_ack_fails_closed(child):
    runtime, peer, context, hosts = child
    runtime.start(); peer.control('activate')
    peer.received.emit({'type': 'state_ack', 'payload': {
        'message_id': 'unknown', 'chapter_id': 'c01.foundation', 'persisted': True}})
    assert runtime.phase == 'stopped'
    assert hosts[0].progress_ack.call_count == 0


def test_failed_host_initialization_never_claims_ready(practice_request):
    from teaching.application import PracticeChild
    peer = Peer(); context = RuntimeContext(practice_request.paths)
    def broken(progress):
        raise ValueError('invalid offline course')
    runtime = PracticeChild(practice_request, peer, context=context, host_factory=broken)
    runtime.start()
    assert not context.ui_active and runtime.phase == 'stopped'
    assert 'ready' not in [message[0] for message in peer.messages]


@pytest.fixture
def application_host(practice_request, monkeypatch):
    import main
    from teaching.application import ApplicationTeachingHost
    context = RuntimeContext(practice_request.paths)
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', context)
    for name, value in practice_request.paths.module_aliases().items():
        monkeypatch.setattr(main, name, value)
    main.ensure_directories()
    monkeypatch.setattr(main, 'notify_user', Mock())
    app = QApplication.instance()
    prior = set(app.topLevelWidgets())
    progress = []
    host = ApplicationTeachingHost(main, practice_request, on_progress=lambda *value: progress.append(value))
    yield host, progress
    host.close()
    for widget in set(app.topLevelWidgets()) - prior:
        if not sip.isdeleted(widget):
            for timer in widget.findChildren(QTimer): timer.stop()
            widget.hide(); widget.deleteLater()
    drain(app)


def test_actual_host_stays_hidden_before_activation(application_host):
    host, progress = application_host
    assert not host.panel.canvas.isVisible()
    assert not host.panel.toolbar_window.isVisible()
    assert host.panel.listener is None and host.panel.lifecycle.tray_icon is None
    assert progress == [] and not host.panel.timer.isActive()


def test_actual_ink_and_save_terminal_results_complete_real_chapter(application_host, practice_request):
    host, progress = application_host
    host.context.activate(); host.activate()
    assert host.presenter.engine.current_step.id == 'ink'
    assert host.presenter.engine.phase == 'running'
    canvas = host.panel.canvas
    canvas._pointer_press(1, QPoint(20, 20), 1.0)
    canvas._pointer_move(1, QPoint(80, 50), 1.0)
    assert host.presenter.engine.current_step.id == 'ink'
    canvas._pointer_release(1, QPoint(100, 60))
    assert host.presenter.engine.current_step.id == 'save'
    destination = practice_request.paths.data_dir / 'lesson.msd'
    assert host.panel.save_project(str(destination))
    assert host.presenter.engine.phase == 'completed'
    assert progress[-1] == ('c01.foundation', 'completed', 1)
    assert destination.is_file()


def test_failed_or_cancelled_real_save_does_not_complete_step(application_host, practice_request, monkeypatch):
    host, progress = application_host
    host.context.activate(); host.activate()
    host.presenter.engine.next()  # not allowed to bypass the actual ink wait
    assert host.presenter.engine.current_step.id == 'ink'
    canvas = host.panel.canvas
    canvas._pointer_press(1, QPoint(20, 20), 1.0)
    canvas._pointer_move(1, QPoint(40, 30), 1.0)
    canvas._pointer_release(1, QPoint(50, 35))
    assert host.presenter.engine.current_step.id == 'save'
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    assert not host.panel.save_project()
    assert host.presenter.engine.phase == 'running'
    assert not host.panel.save_project(str(practice_request.paths.temp_root / 'outside.msd'))
    assert host.presenter.engine.current_step.id == 'save'
    assert not any(value[1] == 'completed' for value in progress)


_BRIDGE = r"""
import os, runpy, sys
from pathlib import Path
app_dir=Path(sys.argv[1]); resources=Path(sys.argv[2]); role=sys.argv[3]
sys.path.insert(0,str(app_dir))
sys._MEIPASS=str(resources)
from PyQt6.QtCore import QTimer, QPoint
from teaching.application import ApplicationTeachingHost
original=ApplicationTeachingHost.activate
def activate(self):
    original(self)
    def actions():
        if role=='skip':
            self.presenter.engine.skip_chapter()
        elif role=='complete':
            canvas=self.panel.canvas
            canvas._pointer_press(1,QPoint(20,20),1.0)
            canvas._pointer_move(1,QPoint(80,60),1.0)
            canvas._pointer_release(1,QPoint(100,80))
            self.panel.save_project(str(self.request.paths.data_dir/'completed.msd'))
        QTimer.singleShot(100,self.exit_requested.emit)
    QTimer.singleShot(40,actions)
ApplicationTeachingHost.activate=activate
sys.argv=[str(app_dir/'main.py'),*sys.argv[4:]]
runpy.run_path(str(app_dir/'main.py'),run_name='__main__')
"""


def until(predicate, timeout=12000, diagnostic=None):
    import time
    from PyQt6.QtTest import QTest
    app = QApplication.instance()
    deadline = time.monotonic() + timeout / 1000
    while not predicate() and time.monotonic() < deadline:
        app.processEvents(); QTest.qWait(5)
    assert predicate(), 'Application integration did not reach expected state: ' + repr(diagnostic() if diagnostic else None)


@pytest.fixture
def parent_coordinator(practice_request, tmp_path, monkeypatch):
    import main
    import sys
    from teaching.application import TeachingCoordinator
    from teaching.state import TutorialStateStore
    context = RuntimeContext(RuntimePaths.for_normal(practice_request.paths.app_dir,
                                                     practice_request.paths.resource_dir))
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', context)
    monkeypatch.setattr(main, 'notify_user', Mock())
    app = QApplication.instance(); prior = set(app.topLevelWidgets())
    panel = main.ControlPanel(runtime=context)
    panel.canvas = main.DrawingCanvas(panel, runtime=context)
    panel.apply_theme(); panel.load_settings()
    panel._teaching_restore_finished = True
    def command(request):
        from teaching.bootstrap import practice_arguments
        return sys.executable, ['-B', '-c', _BRIDGE, str(request.paths.app_dir),
                                str(request.paths.resource_dir), 'complete',
                                *practice_arguments(request.paths, request.channel, request.course_id, request.chapter_id)]
    coordinator = TeachingCoordinator(main, panel,
        state_store=TutorialStateStore(tmp_path / 'parent-progress.json'),
        command_factory=command, temp_root=tmp_path / 'owned-temp', foreground=lambda: True)
    panel.teaching_coordinator = coordinator
    coordinator.restore_errors = []
    restore = coordinator.session.restore
    def tracked_restore(token):
        try:
            return restore(token)
        except Exception:
            import traceback
            coordinator.restore_errors.append(traceback.format_exc())
            raise
    coordinator.session.restore = tracked_restore
    yield panel, coordinator
    coordinator.close()
    if coordinator.session.process is not None:
        until(lambda: coordinator.session.phase in ('idle', 'stopped'))
    panel.shutdown_autosave(); panel.stop_update_worker()
    for widget in set(app.topLevelWidgets()) - prior:
        if not sip.isdeleted(widget):
            for timer in widget.findChildren(QTimer): timer.stop()
            widget.hide(); widget.deleteLater()
    drain(app)


def test_tools_entry_opens_actual_teaching_center(parent_coordinator):
    panel, coordinator = parent_coordinator
    assert coordinator.open_center()
    panel.btn_teaching.click()
    assert coordinator.center is not None and coordinator.center.isVisible()
    assert coordinator.center.select_chapter('c01', 'c01.foundation')
    assert coordinator.session.phase == 'idle'


def test_first_welcome_waits_for_normal_recovery_to_finish(parent_coordinator):
    panel, coordinator = parent_coordinator
    panel._teaching_restore_finished = False
    assert not coordinator.maybe_show_welcome()
    assert coordinator.welcome.dialog is None
    panel._teaching_restore_finished = True
    assert coordinator.maybe_show_welcome()
    assert coordinator.welcome.dialog is not None and coordinator.welcome.dialog.isVisible()
    assert coordinator.session.phase == 'idle'


def test_active_original_gesture_never_gets_cancelled_to_start_teaching(parent_coordinator):
    panel, coordinator = parent_coordinator
    panel.canvas._pointer_press(1, QPoint(10, 10), 1.0)
    before = dict(panel.canvas._pointer_slots)
    assert not coordinator.start('c01', 'c01.foundation')
    assert panel.canvas._pointer_slots == before
    assert coordinator.session.phase == 'idle' and not panel._teaching_suspended
    panel.canvas._pointer_release(1, QPoint(15, 15))


def test_real_separate_application_completes_and_restores_original(parent_coordinator):
    from test_document_safety_610 import ink
    panel, coordinator = parent_coordinator
    ink(panel.canvas, 'original-unsaved-ink')
    signature = panel.canvas.document_signature()
    history = panel.canvas.undo_stack
    before = (panel.project_path, panel.project_dirty, panel.canvas.draw_state, panel.canvas.pages,
              panel.canvas.selected_ids, panel.lifecycle.state)
    phases = []; coordinator.session.phase_changed.connect(phases.append)
    assert coordinator.start('c01', 'c01.foundation')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=lambda: (coordinator.session.phase, coordinator.session.last_error, coordinator.session.restore_pending, coordinator.restore_errors, phases if 'phases' in locals() else None))
    assert coordinator.session.last_error is None
    assert 'running' in phases and 'restoring' in phases
    assert coordinator.state_store.chapter_status('c01.foundation') == 'completed'
    assert panel.canvas.document_signature() == signature and panel.canvas.undo_stack is history
    assert (panel.project_path, panel.project_dirty, panel.canvas.draw_state, panel.canvas.pages,
            panel.canvas.selected_ids, panel.lifecycle.state) == before
    assert not panel._teaching_suspended
    assert panel.toolbar_window.isVisible() and panel.canvas.isVisible()
    assert not coordinator.session.paths.runtime_root.exists()


def test_real_separate_application_skip_is_not_completion(parent_coordinator):
    import sys
    from teaching.bootstrap import practice_arguments
    panel, coordinator = parent_coordinator
    def command(request):
        return sys.executable, ['-B', '-c', _BRIDGE, str(request.paths.app_dir),
                                str(request.paths.resource_dir), 'skip',
                                *practice_arguments(request.paths, request.channel, request.course_id, request.chapter_id)]
    coordinator.session.command_factory = command
    assert coordinator.start('c01', 'c01.foundation')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=lambda: (coordinator.session.phase, coordinator.session.last_error, coordinator.session.restore_pending, coordinator.restore_errors, phases if 'phases' in locals() else None))
    assert coordinator.session.last_error is None
    assert coordinator.state_store.chapter_status('c01.foundation') == 'skipped'
    assert not panel._teaching_suspended


@pytest.mark.parametrize('field,value', [('selection_start', QPoint(1, 1)), ('drag_action', 'move'),
                                         ('text_drag_start', QPoint(1, 1)), ('aid_drag', {'mode': 'move'})])
def test_non_ink_original_gestures_block_start(parent_coordinator, field, value):
    panel, coordinator = parent_coordinator
    setattr(panel.canvas, field, value)
    assert not coordinator.readiness().safe
    assert not coordinator.start('c01', 'c01.foundation')
    assert coordinator.session.phase == 'idle'


def test_closed_center_does_not_leave_invalid_qt_reference(parent_coordinator):
    panel, coordinator = parent_coordinator
    assert coordinator.open_center()
    center = coordinator.center
    center.close(); drain(QApplication.instance())
    assert sip.isdeleted(center)
    assert coordinator.readiness().safe
    coordinator.session.progress_saved.emit({'chapter_id': 'c01.foundation'})
    assert coordinator.open_center()
    assert coordinator.center is not center


def test_parent_pause_resume_messages_are_explicit_and_do_not_restore_original(parent_coordinator):
    panel, coordinator = parent_coordinator
    peer = Peer()
    coordinator.session._peer = peer
    coordinator.session.phase = 'running'
    assert coordinator.session.request_pause(hidden=True)
    assert coordinator.session.phase == 'paused'
    assert peer.messages[-1][1] == {'action': 'pause', 'hidden': True}
    assert coordinator.session.request_resume()
    assert coordinator.session.phase == 'running'
    assert peer.messages[-1][1] == {'action': 'resume'}
    assert not coordinator.session.request_resume()


def test_parent_f12_routes_hidden_pause_without_stopping_listener(parent_coordinator):
    import main
    panel, coordinator = parent_coordinator
    peer = Peer(); coordinator.session._peer = peer
    coordinator.session.phase = 'running'
    panel._teaching_suspended = True
    listener = Mock(); panel.listener = listener
    try:
        assert panel.on_global_key_press(main.keyboard.Key.f12) is None
        drain(QApplication.instance())
        assert coordinator.session.phase == 'paused'
        assert peer.messages[-1][1] == {'action': 'pause', 'hidden': True}
        assert listener.stop.call_count == 0
    finally:
        panel._teaching_suspended = False
        panel.listener = None


def test_startup_welcome_retries_readiness_without_ending_original_edit(parent_coordinator):
    panel, coordinator = parent_coordinator
    panel._teaching_restore_finished = False
    assert not coordinator.request_startup_welcome()
    assert coordinator._welcome_timer.isActive()
    assert coordinator.welcome.dialog is None
    panel._teaching_restore_finished = True
    until(lambda: coordinator.welcome.dialog is not None)
    assert not coordinator._welcome_timer.isActive()
    assert coordinator.session.phase == 'idle'


def test_disconnected_private_main_never_initializes_or_falls_back(practice_request):
    import os, subprocess, sys
    from teaching.bootstrap import practice_arguments
    paths = practice_request.paths
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', MYSCREENDRAW_NO_KEYBOARD='1',
        PYNPUT_BACKEND='dummy', MYSCREENDRAW_PRACTICE_NONCE=paths.nonce,
        MYSCREENDRAW_PRACTICE_TEMP_ROOT=str(paths.temp_root))
    result = subprocess.run([sys.executable, '-B', str(paths.app_dir / 'main.py'),
        *practice_arguments(paths, practice_request.channel, practice_request.course_id, practice_request.chapter_id)],
        cwd=paths.temp_root, env=environment, capture_output=True, timeout=15)
    assert result.returncode == 2
    assert not paths.data_dir.exists() and not paths.export_dir.exists()
    assert paths.marker_file.is_file()


def test_actual_launch_failure_does_not_suspend_or_mutate_original(parent_coordinator):
    panel, coordinator = parent_coordinator
    before = panel.canvas.document_signature()
    coordinator.session.command_factory = lambda request: ('Z:/missing-practice-app.exe', [])
    coordinator.start('c01', 'c01.foundation')
    until(lambda: coordinator.session.phase == 'stopped')
    assert coordinator.session.last_error == 'start_failed'
    assert not coordinator.session.restore_pending and not panel._teaching_suspended
    assert panel.canvas.document_signature() == before
    assert coordinator.state_store.chapter_status('c01.foundation') != 'completed'



def _suspend_original_for_routing(panel, coordinator):
    drain(QApplication.instance())
    peer = Peer()
    coordinator.session._peer = peer
    coordinator.session._token = panel.lifecycle.suspend_for_teaching()
    coordinator.session.phase = 'running'
    return peer


def test_tray_hide_routes_private_pause_without_changing_original(parent_coordinator, monkeypatch):
    panel, coordinator = parent_coordinator
    peer = _suspend_original_for_routing(panel, coordinator)
    mode, edit, pause = Mock(), Mock(), Mock()
    monkeypatch.setattr(panel, 'set_drawing_mode', mode)
    monkeypatch.setattr(panel.canvas, 'end_text_edit', edit)
    monkeypatch.setattr(panel, 'pause_callbacks', pause)
    state = panel.lifecycle.state
    panel.lifecycle.hide_to_background()
    assert coordinator.session.phase == 'paused'
    assert peer.messages[-1][1] == {'action': 'pause', 'hidden': True}
    assert panel.lifecycle.state == state
    assert not mode.called and not edit.called and not pause.called
    assert coordinator.session.restore_pending and panel._teaching_suspended


def test_tray_show_resumes_private_host_before_original_showing_guard(parent_coordinator):
    panel, coordinator = parent_coordinator
    peer = _suspend_original_for_routing(panel, coordinator)
    assert coordinator.hide_to_background()
    assert coordinator.session.phase == 'paused'
    panel.lifecycle.restore_from_background()
    assert coordinator.session.phase == 'running'
    assert peer.messages[-1][1] == {'action': 'resume'}
    assert coordinator.session.restore_pending and panel._teaching_suspended
    assert not panel.isVisible()


def test_tray_toggle_knows_private_hidden_state_without_changing_original_state(parent_coordinator, monkeypatch):
    from PyQt6.QtGui import QAction
    panel, coordinator = parent_coordinator
    peer = _suspend_original_for_routing(panel, coordinator)
    panel.lifecycle.action_toggle_ui = QAction(panel)
    monkeypatch.setattr(panel, 'set_drawing_mode', Mock())
    state = panel.lifecycle.state
    panel.lifecycle._toggle_main_ui()
    assert coordinator.session.phase == 'paused'
    assert panel.lifecycle.action_toggle_ui.text() == coordinator.module.tr('show_main_ui')
    panel.lifecycle._toggle_main_ui()
    assert coordinator.session.phase == 'running'
    assert peer.messages[-1][1] == {'action': 'resume'}
    assert panel.lifecycle.action_toggle_ui.text() == coordinator.module.tr('hide_main_ui')
    assert panel.lifecycle.state == state and panel._teaching_suspended


@pytest.mark.parametrize('phase', ['ready', 'running', 'paused', 'stopping', 'restoring', 'restore_failed'])
def test_tray_settings_does_not_edit_suspended_original(parent_coordinator, monkeypatch, phase):
    panel, coordinator = parent_coordinator
    _suspend_original_for_routing(panel, coordinator)
    coordinator.session.phase = phase
    opened = Mock()
    monkeypatch.setattr(panel, 'open_settings_panel', opened)
    panel.lifecycle._open_settings_from_tray()
    assert not opened.called
    # Teardown must use the real broker's stop/restore path rather than a simulated phase.
    coordinator.session.phase = 'running'


@pytest.mark.parametrize('action', ['quit', 'restart', 'direct_quit'])
def test_tray_shutdown_first_stops_practice_and_waits_for_real_restore(parent_coordinator, monkeypatch, action):
    import app_lifecycle
    panel, coordinator = parent_coordinator
    _suspend_original_for_routing(panel, coordinator)
    manager = panel.lifecycle
    stopped = Mock()
    original_stop = coordinator.session.request_stop
    monkeypatch.setattr(coordinator.session, 'request_stop', stopped)
    monkeypatch.setattr(panel, 'pause_callbacks', Mock())
    monkeypatch.setattr(panel, 'resume_callbacks', Mock())
    monkeypatch.setattr(panel, 'shutdown_autosave', Mock())
    save = Mock(return_value=False)
    monkeypatch.setattr(panel, 'save_project', save)
    monkeypatch.setattr(app_lifecycle, 'QMessageBox', Mock(side_effect=AssertionError('ordinary confirmation before restoration')))
    monkeypatch.setattr(manager.app, 'quit', Mock())
    try:
        if action == 'quit':
            manager._quit_app()
        elif action == 'restart':
            manager._restart_app()
        else:
            manager._do_quit(save=False)
        stopped.assert_called_once()
        assert not save.called and not panel.pause_callbacks.called
        assert not manager.app.quit.called and not getattr(manager, '_quit_done', False)
        assert coordinator.session.restore_pending and panel._teaching_suspended
        calls = []
        continuation = '_restart_app' if action == 'restart' else '_quit_app'
        monkeypatch.setattr(manager, continuation, lambda: calls.append(
            (coordinator.session.phase, coordinator.session.process,
             coordinator.session.restore_pending, panel._teaching_suspended)))
        # A signal alone is not proof that the original document has been restored.
        coordinator._phase_changed('stopped')
        drain(QApplication.instance())
        assert calls == []
        coordinator.session.phase = 'stopping'
        coordinator.session._finish()
        assert coordinator.session.phase == 'stopped', coordinator.restore_errors
        assert calls == []  # ordinary actions are deferred out of the broker callback
        drain(QApplication.instance())
        assert calls == [('stopped', None, False, False)]
    finally:
        manager._quit_done = False
        # Restore teardown's real stop method in case an assertion failed above.
        monkeypatch.setattr(coordinator.session, 'request_stop', original_stop)
        if coordinator.session.restore_pending:
            coordinator.session.phase = 'stopping'
            coordinator.session._finish()


def test_duplicate_shutdown_request_does_not_queue_two_ordinary_actions(parent_coordinator, monkeypatch):
    panel, coordinator = parent_coordinator
    _suspend_original_for_routing(panel, coordinator)
    original_stop = coordinator.session.request_stop
    stopped = Mock()
    monkeypatch.setattr(coordinator.session, 'request_stop', stopped)
    assert coordinator.request_lifecycle_action('quit')
    assert coordinator.request_lifecycle_action('restart')
    stopped.assert_called_once()
    actions = []
    monkeypatch.setattr(panel.lifecycle, '_quit_app', lambda: actions.append('quit'))
    monkeypatch.setattr(panel.lifecycle, '_restart_app', lambda: actions.append('restart'))
    monkeypatch.setattr(coordinator.session, 'request_stop', original_stop)
    coordinator.session.request_stop('test')
    drain(QApplication.instance())
    assert actions == ['quit']


def test_failed_original_restore_cancels_pending_quit_even_after_manual_retry(parent_coordinator, monkeypatch):
    panel, coordinator = parent_coordinator
    _suspend_original_for_routing(panel, coordinator)
    restored = coordinator.session.restore
    monkeypatch.setattr(coordinator.session, 'restore', Mock(side_effect=RuntimeError('test restore fault')))
    notice = Mock()
    monkeypatch.setattr(coordinator, '_notice', notice)
    assert coordinator.request_lifecycle_action('quit')
    assert coordinator.session.phase == 'restore_failed'
    actions = []
    monkeypatch.setattr(panel.lifecycle, '_quit_app', lambda: actions.append('quit'))
    assert coordinator.request_lifecycle_action('restart')
    assert not actions
    monkeypatch.setattr(coordinator.session, 'restore', restored)
    assert coordinator.session.retry_restore()
    drain(QApplication.instance())
    assert actions == []
    assert not coordinator.session.restore_pending
    notice.assert_any_call('teaching_session_restore_failed', recovery=True)


def test_pending_shutdown_blocks_start_of_another_practice(parent_coordinator, monkeypatch):
    panel, coordinator = parent_coordinator
    _suspend_original_for_routing(panel, coordinator)
    assert coordinator.request_lifecycle_action('quit')
    assert coordinator.session.phase == 'stopped'
    monkeypatch.setattr(coordinator, '_notice', Mock())
    launched = Mock()
    monkeypatch.setattr(coordinator.session, 'start', launched)
    assert not coordinator.start('onboarding', 'c01.foundation')
    assert not launched.called
    # Consume the pending action in a mocked ordinary confirmation, never a native dialog.
    monkeypatch.setattr(panel.lifecycle, '_quit_app', Mock())
    drain(QApplication.instance())



def test_real_chapter_completion_keeps_explicit_exit_to_original_work(application_host, practice_request):
    host, progress = application_host
    host.context.activate(); host.activate()
    canvas = host.panel.canvas
    canvas._pointer_press(1, QPoint(20, 20), 1.0)
    canvas._pointer_move(1, QPoint(80, 50), 1.0)
    canvas._pointer_release(1, QPoint(100, 60))
    assert host.panel.save_project(str(practice_request.paths.data_dir / 'summary.msd'))
    controller = host.presenter.controller
    assert controller.isVisible()
    assert controller.title_label.text() == host.module.tr('teaching_status_completed')
    assert controller.body_label.text() == host.module.tr('teaching_return_to_work')
    assert controller.exit_button.isEnabled()
    assert all(not getattr(controller, name + '_button').isEnabled()
               for name in ('previous', 'next', 'pause', 'skip', 'retry'))
    assert not host.presenter.barrier.installed
    assert progress[-1][1] == 'completed'


def test_real_chapter_skip_shows_exit_without_asserting_completion(application_host):
    host, progress = application_host
    host.context.activate(); host.activate()
    host.presenter.engine.skip_chapter()
    controller = host.presenter.controller
    assert controller.isVisible() and controller.exit_button.isEnabled()
    assert controller.title_label.text() == host.module.tr('teaching_status_skipped')
    assert not host.presenter.barrier.installed
    assert progress[-1][1] == 'skipped'
    assert not any(status == 'completed' for _, status, _ in progress)


def test_private_host_false_persistence_ack_is_visible_nonmodal_and_not_repeated(application_host, monkeypatch):
    host, progress = application_host
    host.context.activate(); host.activate()
    logged = Mock()
    monkeypatch.setattr(host.module.LOGGER, 'warning', logged)
    original = list(progress)
    host.progress_ack('c01.foundation', 'in_progress', False)
    label = host.presenter.controller.warning_label
    assert label.isVisible()
    assert label.text() == host.module.tr('teaching_progress_save_failed')
    assert label.textFormat() == host.module.Qt.TextFormat.PlainText
    host.progress_ack('c01.foundation', 'completed', False)
    host.progress_ack('c01.foundation', 'in_progress', True)
    assert label.isVisible() and logged.call_count == 1
    assert progress == original  # warning/ack must never fabricate learning results
