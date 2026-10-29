# SPDX-License-Identifier: GPL-3.0-or-later
"""Adversarial application-boundary regressions: offscreen, test-owned paths only."""
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from test_teaching_application import (
    practice_request, application_host, parent_coordinator, Peer,
)
from test_teaching_application_isolation import private_runtime, panel
from teaching.application import PracticeChild
from teaching.practice import PracticeSession
from teaching.state import TutorialStateStore
from teaching.transport import TeachingConnection
from test_teaching_engine import make_catalog


def pump(predicate, timeout=1):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        QApplication.instance().processEvents()
        QTest.qWait(5)
    return predicate()


@pytest.fixture
def wire_pair(practice_request):
    assert QApplication.instance().platformName() == 'offscreen'
    server = QLocalServer()
    assert server.listen(practice_request.channel)
    raw = QLocalSocket()
    raw.connectToServer(practice_request.channel)
    assert raw.waitForConnected(1000)
    assert server.waitForNewConnection(1000)
    accepted = server.nextPendingConnection()
    assert accepted is not None
    paths = practice_request.paths
    parent = TeachingConnection(accepted, paths.session_id, paths.nonce)
    child = TeachingConnection(raw, paths.session_id, paths.nonce)
    yield parent, child
    child.close()
    parent.close()
    server.close()


def test_parent_accepts_progress_already_sent_before_pause(wire_pair, tmp_path):
    parent_peer, child_peer = wire_pair
    store = TutorialStateStore(tmp_path / 'progress.json')
    broker = PracticeSession(make_catalog(), app_dir=tmp_path / 'app',
        resource_dir=tmp_path / 'resources', temp_root=tmp_path / 'temp',
        state_store=store, command_factory=Mock(side_effect=AssertionError('NO LAUNCH')),
        suspend=lambda: None, restore=lambda token: None)
    broker._peer = parent_peer
    broker._chapter_id, broker._compat_revision = 'c01.save', 1
    broker.phase = 'running'
    parent_peer.received.connect(lambda packet: broker._receive(packet, broker._generation))
    child_peer.send('chapter_state', {
        'chapter_id': 'c01.save', 'status': 'completed', 'compat_revision': 1})
    assert broker.request_pause(hidden=True)
    assert pump(lambda: broker.last_error is not None or store.chapter_status('c01.save') == 'completed',
                timeout=5), (broker.phase, broker.last_error,
                             parent_peer.socket.bytesAvailable(), child_peer.socket.bytesToWrite())
    print('CROSSED_PROGRESS', broker.phase, broker.last_error, store.chapter_status('c01.save'))
    assert broker.last_error is None
    assert store.chapter_status('c01.save') == 'completed'


def test_progress_crossing_pause_waits_for_delayed_socket_dispatch(wire_pair, tmp_path, monkeypatch):
    parent_peer, _ = wire_pair
    native_start = parent_peer._read_timer.start
    monkeypatch.setattr(parent_peer._read_timer, 'start', lambda interval=0: native_start(1500))
    test_parent_accepts_progress_already_sent_before_pause(wire_pair, tmp_path)


def test_final_progress_is_delivered_before_peer_close(wire_pair):
    parent_peer, child_peer = wire_pair
    packets = []
    parent_peer.received.connect(packets.append)
    child_peer.send('chapter_state', {
        'chapter_id': 'c01.save', 'status': 'completed', 'compat_revision': 1})
    child_peer.send('stopping', {})
    child_peer.send('stopped', {})
    child_peer.close()
    pump(lambda: parent_peer.is_closed)
    print('CLOSE_PROGRESS', [p['type'] for p in packets], parent_peer.is_closed)
    assert any(p['type'] == 'chapter_state' for p in packets)


@pytest.fixture
def live_bridge(application_host, practice_request):
    host, _ = application_host
    peer = Peer()
    def factory(report):
        host._on_progress = report
        return host
    child = PracticeChild(practice_request, peer, context=host.context, host_factory=factory)
    child.start()
    peer.control('activate')
    assert child.phase == 'running'
    yield child, peer, host
    child.stop()


def test_skip_from_parent_paused_controller_is_reported(live_bridge):
    child, peer, host = live_bridge
    peer.control('pause')
    assert child.phase == 'paused'
    assert host.presenter.controller.skip_button.isEnabled()
    host.presenter.controller.skip_requested.emit()
    statuses = [payload['status'] for kind, payload, _ in peer.messages if kind == 'chapter_state']
    print('PAUSED_SKIP', child.phase, host.presenter.engine.phase, statuses, 'finished_summary', host.presenter.controller.chapter_finished)
    assert 'skipped' in statuses


def test_deferred_target_failure_closes_practice_child(live_bridge, monkeypatch):
    child, peer, host = live_bridge
    errors = []
    host.presenter.failed.connect(errors.append)
    def broken():
        raise ValueError('synthetic late resolver failure')
    monkeypatch.setitem(host.registry._entries, 'canvas.ink', (broken, None))
    host.registry._notify()
    print('TARGET_FAILURE', errors, child.phase, host.presenter.engine.phase,
          host.presenter.controller.isVisible(), [kind for kind, _, _ in peer.messages])
    assert errors == ['presentation_failed']
    assert child.phase == 'stopped'


@pytest.mark.parametrize('fmt', ['PNG', 'PDF', 'SVG', 'EPS'])
def test_export_revalidates_boundary_after_progress_yield(private_runtime, panel, tmp_path, monkeypatch, fmt):
    main, paths, context, _ = private_runtime
    panel.canvas.whiteboard_mode = True
    outside = tmp_path / 'test-owned-external-exports'
    outside.mkdir()
    swapped = False
    class Progress:
        def setLabelText(self, text): pass
        def setValue(self, value):
            nonlocal swapped
            if not swapped:
                assert paths.export_dir.resolve().is_relative_to(paths.runtime_root)
                assert not list(paths.export_dir.iterdir())
                paths.export_dir.rmdir()
                try:
                    os.symlink(outside, paths.export_dir, target_is_directory=True)
                except OSError as exc:
                    paths.export_dir.mkdir()
                    pytest.skip(str(exc))
                swapped = True
        def wasCanceled(self): return False
        def close(self): pass
        def deleteLater(self): pass
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress())
    monkeypatch.setattr(panel, '_show_export_result', lambda *args: None)
    try:
        result = panel.export_pages(fmt)
        produced = [p.name for p in outside.iterdir()]
        print('EXPORT_BOUNDARY_SWAP', fmt, result.success, produced)
        assert not produced and not result.success
    finally:
        if paths.export_dir.is_symlink():
            paths.export_dir.unlink()
            paths.export_dir.mkdir()


@pytest.mark.parametrize('phase', ['starting', 'ready'])
def test_updater_handoff_waits_for_practice_exit(parent_coordinator, tmp_path, monkeypatch, phase):
    import main
    panel, coordinator = parent_coordinator
    coordinator.session.phase = phase
    order = []
    monkeypatch.setattr(coordinator.session, 'request_stop', lambda reason: order.append(('stop', phase)))
    monkeypatch.setattr(main, 'validate_update_zip', Mock())
    monkeypatch.setattr(main, 'install_layout_supported', Mock(return_value=True))
    monkeypatch.setattr(main, 'make_update_batch', Mock(return_value=str(tmp_path / 'NOT-RUN.ps1')))
    launch = Mock(side_effect=lambda *args, **kwargs: order.append(('MOCK_INSTALLER', phase)))
    monkeypatch.setattr(main.subprocess, 'Popen', launch)
    monkeypatch.setattr(main.shutil, 'rmtree', Mock(side_effect=AssertionError('NO DELETE')))
    monkeypatch.setattr(main.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(panel, 'save_settings', Mock())
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', Mock(return_value=True))
    monkeypatch.setattr(main, 'track_event', Mock())
    buttons = main.QMessageBox.StandardButton
    class NoNativeDialog:
        StandardButton = buttons
        def __init__(self, *args): pass
        def __getattr__(self, name): return lambda *args, **kwargs: None
        def exec(self): return buttons.Yes
    monkeypatch.setattr(main, 'QMessageBox', NoNativeDialog)
    panel._pending_update_release = {'tag': '6.2.0'}
    panel._on_update_downloaded(str(tmp_path / 'test-owned-download.zip'), None)
    print('UPDATER_ORDER', order, 'pending_action', coordinator._pending_lifecycle_action,
          'handoff', panel._update_install_handoff, 'phase', coordinator.session.phase)
    assert not launch.called



@pytest.mark.parametrize('fmt', ['PNG', 'PDF'])
def test_export_revalidates_ownership_after_cancellation_callback(private_runtime, fmt):
    import export_pipeline
    from PyQt6.QtGui import QColor, QPixmap
    main, paths, context, _ = private_runtime
    marker = paths.runtime_root / '.myscreendraw-teaching-session.json'
    original = marker.read_bytes()
    revoked = False
    def cancelled():
        nonlocal revoked
        if not revoked and list(paths.export_dir.glob('.msd-export-*')):
            marker.write_text('{}', encoding='utf-8')
            revoked = True
        return False
    def render(*args):
        pixmap = QPixmap(80, 60)
        pixmap.fill(QColor('blue'))
        return pixmap
    try:
        result = export_pipeline.export_document(fmt, paths.export_dir / ('commit.' + fmt.lower()),
            [None], render, cancelled=cancelled,
            validate_path=lambda value: main.runtime_file_path(value, write=True))
        assert revoked and not result.success
        assert not (paths.export_dir / ('commit.' + fmt.lower())).exists()
    finally:
        marker.write_bytes(original)



@pytest.mark.parametrize('phase', ['starting', 'ready', 'running', 'paused', 'restore_failed'])
def test_update_download_metadata_is_deferred_without_read_write_or_install(parent_coordinator, tmp_path, monkeypatch, phase):
    panel, coordinator = parent_coordinator
    coordinator.session.phase = phase
    reads = Mock(side_effect=AssertionError('no update validation during teaching'))
    monkeypatch.setattr(coordinator.module, 'validate_update_zip', reads)
    pending_path = str(tmp_path / 'test-owned-deferred-download.zip')
    panel._on_update_downloaded(pending_path, None)
    assert panel._teaching_deferred_update_download == (pending_path, None)
    assert not reads.called and not panel._update_install_handoff
    coordinator.session.phase = 'stopped'


def test_deferred_updates_resume_only_after_original_restore_and_outside_quit_confirmation(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    coordinator.session.phase = 'starting'
    pending_path = str(tmp_path / 'test-owned-deferred-download.zip')
    release = {'tag': '6.2.0', 'download_url': 'test-only-no-network'}
    panel._on_update_downloaded(pending_path, None)
    panel._on_update_result(release, None)
    downloaded, checked = Mock(), Mock()
    monkeypatch.setattr(panel, '_on_update_downloaded', downloaded)
    monkeypatch.setattr(panel, '_on_update_result', checked)
    panel._resume_teaching_updates()
    QApplication.instance().processEvents()
    assert not downloaded.called and not checked.called
    coordinator.session.phase = 'restore_failed'
    panel._resume_teaching_updates()
    QApplication.instance().processEvents()
    assert not downloaded.called and not checked.called
    coordinator.session.phase = 'stopped'
    panel.lifecycle._quit_dialog_showing = True
    panel._resume_teaching_updates()
    QApplication.instance().processEvents()
    assert not downloaded.called and not checked.called
    panel.lifecycle._quit_dialog_showing = False
    panel._resume_teaching_updates()
    assert not downloaded.called and not checked.called
    QApplication.instance().processEvents()
    downloaded.assert_called_once_with(pending_path, None)
    checked.assert_called_once_with(release, None)
    assert panel._teaching_deferred_update_download is None
    assert panel._teaching_deferred_update_result is None


def test_update_checks_are_not_started_while_practice_is_starting(parent_coordinator, monkeypatch):
    panel, coordinator = parent_coordinator
    coordinator.session.phase = 'starting'
    worker = Mock(side_effect=AssertionError('no network worker during teaching'))
    monkeypatch.setattr(coordinator.module, 'UpdateCheckWorker', worker)
    panel.check_for_updates()
    assert not worker.called
    coordinator.session.phase = 'stopped'



def test_parent_paused_child_cannot_report_stale_async_completion(live_bridge):
    child, peer, host = live_bridge
    peer.control('pause')
    before = list(peer.messages)
    child.record_progress('c01.foundation', 'completed', 1)
    assert peer.messages == before
    assert host.presenter.engine.phase == 'paused'


@pytest.mark.parametrize('replacement', [
    {'chapter_id': 'c01.other'}, {'compat_revision': 2}, {'status': 'not_started'}])
def test_parent_paused_progress_still_validates_bound_chapter_revision_and_status(wire_pair, tmp_path, replacement):
    parent_peer, child_peer = wire_pair
    store = TutorialStateStore(tmp_path / 'progress.json')
    broker = PracticeSession(make_catalog(), app_dir=tmp_path / 'app',
        resource_dir=tmp_path / 'resources', temp_root=tmp_path / 'temp',
        state_store=store, command_factory=Mock(side_effect=AssertionError('NO LAUNCH')),
        suspend=lambda: None, restore=lambda token: None)
    broker._peer = parent_peer
    broker._chapter_id, broker._compat_revision = 'c01.save', 1
    broker.phase = 'paused'
    parent_peer.received.connect(lambda packet: broker._receive(packet, broker._generation))
    payload = {'chapter_id': 'c01.save', 'status': 'completed', 'compat_revision': 1}
    payload.update(replacement)
    child_peer.send('chapter_state', payload)
    assert pump(lambda: broker.last_error is not None)
    assert broker.last_error == 'invalid_progress'
    assert store.chapter_status('c01.save') == 'not_started'



def test_local_resume_of_parent_pause_reports_real_completion(live_bridge, practice_request, monkeypatch):
    from PyQt6.QtCore import QPoint
    child, peer, host = live_bridge
    peer.control('pause', hidden=False)
    assert child.phase == 'paused'
    requests = []
    send = peer.send
    def reply(kind, payload):
        message_id = send(kind, payload)
        if kind == 'control':
            requests.append(dict(payload))
            peer.control(payload['action'])  # authoritative parent response, not a local engine toggle
        return message_id
    monkeypatch.setattr(peer, 'send', reply)
    host.presenter.controller.pause_requested.emit()
    assert child.phase == 'running' and host.presenter.engine.phase == 'running'
    assert requests == [{'action': 'resume'}]
    canvas = host.panel.canvas
    canvas._pointer_press(1, QPoint(20, 20), 1.0)
    canvas._pointer_move(1, QPoint(80, 50), 1.0)
    canvas._pointer_release(1, QPoint(100, 60))
    assert host.panel.save_project(str(practice_request.paths.data_dir / 'resumed.msd'))
    assert 'completed' in [payload['status'] for kind, payload, _ in peer.messages if kind == 'chapter_state']


def test_deferred_update_rechecks_quit_gate_at_delivery_and_retains_metadata(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    pending = (str(tmp_path / 'not-an-update.zip'), None)
    panel._teaching_deferred_update_download = pending
    validator = Mock(side_effect=AssertionError('no validation during quit confirmation'))
    monkeypatch.setattr(coordinator.module, 'validate_update_zip', validator)
    monkeypatch.setattr(coordinator.module.shutil, 'rmtree', Mock())
    panel._resume_teaching_updates()
    panel.lifecycle._quit_dialog_showing = True
    try:
        QApplication.instance().processEvents()
        assert not validator.called
        assert panel._teaching_deferred_update_download == pending
    finally:
        panel.lifecycle._quit_dialog_showing = False



def test_real_socket_local_pause_resume_keeps_parent_child_and_completion_in_sync(application_host, practice_request, wire_pair, tmp_path):
    from PyQt6.QtCore import QPoint
    host, _ = application_host
    parent_peer, child_peer = wire_pair
    store = TutorialStateStore(tmp_path / 'synchronized-progress.json')
    broker = PracticeSession(host.catalog, app_dir=practice_request.paths.app_dir,
        resource_dir=practice_request.paths.resource_dir, temp_root=tmp_path / 'unused-temp',
        state_store=store, command_factory=Mock(side_effect=AssertionError('NO LAUNCH')),
        suspend=lambda: object(), restore=lambda token: None)
    broker.phase = 'starting'
    broker._peer = parent_peer
    broker._chapter_id, broker._compat_revision = practice_request.chapter_id, 1
    parent_peer.received.connect(lambda packet: broker._receive(packet, broker._generation))
    def factory(report):
        host._on_progress = report
        return host
    child = PracticeChild(practice_request, child_peer, context=host.context, host_factory=factory)
    try:
        child.start()
        assert pump(lambda: child.phase == broker.phase == 'running')
        host.presenter.controller.pause_requested.emit()
        assert pump(lambda: child.phase == broker.phase == 'paused')
        assert host.presenter.engine.phase == 'paused'
        host.presenter.controller.pause_requested.emit()
        assert pump(lambda: child.phase == broker.phase == 'running')
        canvas = host.panel.canvas
        canvas._pointer_press(1, QPoint(20, 20), 1.0)
        canvas._pointer_move(1, QPoint(80, 50), 1.0)
        canvas._pointer_release(1, QPoint(100, 60))
        assert host.panel.save_project(str(practice_request.paths.data_dir / 'synchronized.msd'))
        assert pump(lambda: store.chapter_status(practice_request.chapter_id) == 'completed')
        assert not child._control_timer.isActive() and broker.last_error is None
    finally:
        child.stop()
        pump(lambda: broker.phase == 'stopped')


def test_child_controller_control_requests_are_bounded_and_wait_for_parent(live_bridge):
    child, peer, host = live_bridge
    host.presenter.controller.pause_requested.emit()
    host.presenter.controller.pause_requested.emit()
    requests = [payload for kind, payload, _ in peer.messages if kind == 'control']
    assert requests == [{'action': 'pause'}]
    assert child.phase == host.presenter.engine.phase == 'running'
    assert child._control_timer.isActive()
    peer.control('pause')
    assert child.phase == host.presenter.engine.phase == 'paused'
    assert not child._control_timer.isActive()
    host.presenter.controller.pause_requested.emit()
    assert child._pending_control == 'resume'
    child._control_timer.timeout.emit()
    assert child.phase == 'stopped' and not child._control_timer.isActive()
    assert not any(payload.get('status') == 'completed' for kind, payload, _ in peer.messages if kind == 'chapter_state')
