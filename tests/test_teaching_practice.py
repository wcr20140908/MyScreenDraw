# SPDX-License-Identifier: GPL-3.0-or-later
"""Practice broker tests run an owned Qt child, never the normal drawing app."""
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtCore import QProcess
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from teaching.state import TutorialStateStore

_PROBE = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtNetwork import QLocalSocket
from teaching.bootstrap import parse_practice_request
from teaching.transport import TeachingConnection
app_dir=Path(sys.argv[1]); role=sys.argv[3]
request=parse_practice_request(sys.argv[4:], app_dir=app_dir, resource_dir=app_dir/'_internal')
app=QCoreApplication([])
peer=TeachingConnection(QLocalSocket(), request.paths.session_id, request.paths.nonce)
def connected():
    peer.send('hello', {})
    if role=='exit_before_ready':
        QTimer.singleShot(10, lambda: app.exit(7))
    elif role=='early_progress':
        peer.send('chapter_state', {'chapter_id':request.chapter_id,'status':'completed','compat_revision':1})
    elif role!='no_ready':
        peer.send('ready', {})
def packet(message):
    if message['type']=='state_ack':
        (request.paths.runtime_root/'ack.json').write_text(json.dumps(message['payload']),encoding='utf-8')
        return
    if message['type']!='control': return
    action=message['payload']['action']
    if action=='activate':
        (request.paths.runtime_root/'private-activity.txt').write_text('private only', encoding='utf-8')
        if role=='crash':
            os._exit(9)
        if role=='no_activation_ack': return
        peer.send('activated', {})
        if role=='progress':
            peer.send('chapter_state', {'chapter_id':request.chapter_id,'status':'completed','compat_revision':1})
        if role in ('bad_revision','bool_revision','wrong_registered','extra_progress','skip'):
            payload={'chapter_id':request.chapter_id,'status':'completed','compat_revision':1}
            if role=='bad_revision': payload['compat_revision']=2
            if role=='bool_revision': payload['compat_revision']=True
            if role=='wrong_registered': payload['chapter_id']='c01.other'
            if role=='extra_progress': payload['arbitrary']='not allowed'
            if role=='skip': payload['status']='skipped'
            peer.send('chapter_state',payload)
        if role=='invalid_progress':
            peer.send('chapter_state', {'chapter_id':'unknown.chapter','status':'completed','compat_revision':1})
    elif action=='pause':
        pass
    elif action=='stop' and role!='ignore_stop':
        peer.send('stopped', {})
        peer.socket.flush()
        QTimer.singleShot(50, app.quit)
peer.socket.connected.connect(connected)
peer.received.connect(packet)
peer.closed.connect(app.quit)
peer.socket.connectToServer(request.channel)
QTimer.singleShot(12000, lambda: app.exit(12))
sys.exit(app.exec())
"""


def until(predicate, timeout=5000):
    app=QApplication.instance() or QApplication([])
    deadline=time.monotonic()+timeout/1000
    while not predicate() and time.monotonic()<deadline:
        app.processEvents();QTest.qWait(5)
    assert predicate(), 'Practice broker did not reach expected state'


@pytest.fixture
def factory(tmp_path):
    probe=tmp_path/'probe.py';probe.write_text(_PROBE,encoding='utf-8')
    def make(role):
        from teaching.bootstrap import practice_arguments
        def command(request):
            return sys.executable, ['-B', str(probe), str(request.paths.app_dir), str(Path.cwd()), role,
                *practice_arguments(request.paths,request.channel,request.course_id,request.chapter_id)]
        return command
    return make


@pytest.fixture
def broker(tmp_path,factory):
    from teaching.practice import PracticeSession
    from test_teaching_engine import make_catalog
    app=QApplication.instance() or QApplication([])
    app_dir=tmp_path/'app';app_dir.mkdir()
    (app_dir/'original.msd').write_bytes(b'original-document-undo-sentinel')
    calls=[]
    token=object()
    store=TutorialStateStore(tmp_path/'progress.json')
    value=PracticeSession(make_catalog(), app_dir=app_dir,resource_dir=app_dir/'_internal',
        temp_root=tmp_path/'temp',state_store=store,command_factory=factory('normal'),
        suspend=lambda:(calls.append('suspend') or token),
        restore=lambda original:calls.append(('restore',original)),
        startup_timeout_ms=3000,activation_timeout_ms=3000,stop_timeout_ms=100,kill_timeout_ms=100)
    value.test_calls=calls;value.test_token=token
    yield value
    if value.phase not in ('idle','stopped'):
        value.request_stop('test teardown')
        until(lambda:value.phase in ('stopped','restore_failed'))
        if value.phase == 'restore_failed':
            value.restore=lambda original:calls.append(('restore',original))
            assert value.retry_restore()
    value.deleteLater()


@pytest.fixture
def cleanup_calls(broker, monkeypatch):
    calls = []
    cleanup = broker._cleanup
    def watched_cleanup():
        calls.append(broker.paths)
        cleanup()
    monkeypatch.setattr(broker, '_cleanup', watched_cleanup)
    return calls


def test_child_ready_then_activation_preserves_original_and_stops(broker):
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='running')
    root=broker.paths.runtime_root
    assert (root/'private-activity.txt').read_text(encoding='utf-8')=='private only'
    assert broker.test_calls==['suspend']
    assert (broker.app_dir/'original.msd').read_bytes()==b'original-document-undo-sentinel'
    broker.request_stop('finished')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==['suspend',('restore',broker.test_token)]
    assert not root.exists()


def test_safe_gate_defers_activation_without_hiding_original(broker):
    broker.suspend=lambda:None
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='ready')
    root=broker.paths.runtime_root
    assert not (root/'private-activity.txt').exists()
    assert broker.test_calls==[]
    broker.suspend=lambda:broker.test_token
    assert broker.try_activate()
    until(lambda:broker.phase=='running')


def test_duplicate_start_is_rejected(broker):
    broker.start('c01','c01.save')
    with pytest.raises(RuntimeError,match='active'):
        broker.start('c01','c01.other')


def test_invalid_course_is_rejected_before_creating_session(broker):
    with pytest.raises(KeyError):
        broker.start('unknown','unknown.chapter')
    assert broker.phase=='idle' and broker.paths is None


def test_progress_is_validated_and_acknowledged_by_parent(broker,factory):
    broker.command_factory=factory('progress')
    broker.start('c01','c01.save')
    until(lambda:broker.state_store.completed_count()==1)
    assert broker.state_store.chapter_status('c01.save')=='completed'
    assert broker.phase=='running'


def test_bad_progress_does_not_write_false_completion(broker,factory):
    broker.command_factory=factory('invalid_progress')
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.state_store.completed_count()==0
    assert broker.last_error=='invalid_progress'
    assert broker.test_calls[-1]==('restore',broker.test_token)


def test_child_crash_restores_exactly_once(broker,factory):
    broker.command_factory=factory('crash')
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls.count(('restore',broker.test_token))==1
    assert broker.state_store.completed_count()==0


def test_no_ready_times_out_without_suspending_original(broker,factory):
    broker.command_factory=factory('no_ready')
    broker.startup_timeout_ms=700
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==[]
    assert broker.last_error=='startup_timeout'


def test_exit_before_ready_leaves_original_untouched(broker,factory):
    broker.command_factory=factory('exit_before_ready')
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==[]
    assert broker.last_error=='child_exited'


def test_unresponsive_child_is_owned_and_force_stopped(broker,factory):
    broker.command_factory=factory('ignore_stop')
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='running')
    broker.request_stop('user exit')
    until(lambda:broker.phase=='stopped')
    assert broker.process is None
    assert broker.test_calls.count(('restore',broker.test_token))==1


def test_failed_to_start_restores_no_unsuspended_windows(broker):
    broker.command_factory=lambda request:('Z:/nonexistent/myscreendraw-test.exe',[])
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==[]
    assert broker.last_error=='start_failed'


def test_cleanup_refuses_replaced_ownership_marker(broker):
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='running')
    root=broker.paths.runtime_root
    broker.paths.marker_file.write_bytes(b'{}')
    broker.request_stop('user exit')
    until(lambda:broker.phase=='stopped')
    assert root.exists()
    assert broker.cleanup_retained
    assert broker.test_calls[-1]==('restore',broker.test_token)


def test_repeat_stop_is_idempotent_and_new_session_can_start(broker):
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='running')
    broker.request_stop('user exit');broker.request_stop('again')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls.count(('restore',broker.test_token))==1
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='running')
    assert broker.test_calls.count('suspend')==2


@pytest.mark.parametrize('role',['bad_revision','bool_revision','wrong_registered','extra_progress'])
def test_progress_must_match_selected_chapter_and_exact_revision(broker,factory,role):
    broker.command_factory=factory(role)
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.state_store.completed_count()==0
    assert broker.last_error=='invalid_progress'


def test_progress_before_activation_is_rejected(broker,factory):
    broker.command_factory=factory('early_progress')
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==[]
    assert broker.state_store.completed_count()==0
    assert broker.last_error=='invalid_message'


def test_activation_timeout_restores_original_once(broker,factory):
    broker.command_factory=factory('no_activation_ack')
    broker.activation_timeout_ms=100
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.last_error=='activation_timeout'
    assert broker.test_calls==['suspend',('restore',broker.test_token)]


def test_skipped_progress_is_acknowledged_without_completion(broker,factory):
    import json
    broker.command_factory=factory('skip')
    broker.start('c01','c01.save')
    until(lambda:broker.paths is not None and (broker.paths.runtime_root/'ack.json').exists())
    ack=json.loads((broker.paths.runtime_root/'ack.json').read_text(encoding='utf-8'))
    assert ack['persisted'] is True and ack['chapter_id']=='c01.save'
    assert broker.state_store.chapter_status('c01.save')=='skipped'
    assert broker.state_store.completed_count()==0


def test_future_schema_is_read_only_and_acknowledged_as_not_persisted(broker,factory,tmp_path):
    import json
    future=tmp_path/'future.json';future.write_text('{"schema_version":99}',encoding='utf-8')
    broker.state_store=TutorialStateStore(future)
    before=broker.state_store.snapshot()
    broker.command_factory=factory('progress')
    broker.start('c01','c01.save')
    until(lambda:broker.paths is not None and (broker.paths.runtime_root/'ack.json').exists())
    ack=json.loads((broker.paths.runtime_root/'ack.json').read_text(encoding='utf-8'))
    assert ack['persisted'] is False
    assert future.read_text(encoding='utf-8')=='{"schema_version":99}'
    assert broker.state_store.completed_count()==0
    assert broker.state_store.snapshot()==before


def test_stop_at_starting_signal_never_launches_child(broker):
    broker.phase_changed.connect(lambda phase:broker.request_stop('cancelled immediately') if phase=='starting' else None)
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.process is None and broker.paths is None
    assert broker.test_calls==[]


def test_stop_inside_suspend_never_activates_child(broker):
    def suspend():
        broker.request_stop('cancelled at safe gate')
        return broker.test_token
    broker.suspend=suspend
    broker.start('c01','c01.save')
    until(lambda:broker.phase=='stopped')
    assert broker.test_calls==[('restore',broker.test_token)]
    assert broker.state_store.completed_count()==0



def test_restore_failure_blocks_restart_until_explicit_idempotent_retry(broker, cleanup_calls):
    restores, process_states, failures, phases = [], [], [], []
    broker.failed.connect(failures.append)
    broker.phase_changed.connect(phases.append)
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'running')
    owned = broker.process
    root = broker.paths.runtime_root
    def restore(token):
        restores.append(token)
        if len(restores) == 1:
            process_states.append(owned.state())
            raise OSError('restore temporarily unavailable')
    broker.restore = restore
    broker.request_stop('finished')
    until(lambda: broker.phase in ('restore_failed', 'stopped'))
    assert broker.phase == 'restore_failed'
    assert 'stopped' not in phases
    assert broker.restore_pending
    assert broker.process is None
    assert process_states == [QProcess.ProcessState.NotRunning]
    assert failures == ['restore_failed']
    assert broker.last_error == 'restore_failed'
    assert not root.exists() and len(cleanup_calls) == 1
    assert not broker._timers
    with pytest.raises(RuntimeError):
        broker.start('c01', 'c01.save')
    broker.request_stop('duplicate stop')
    broker._finish()  # A late/duplicate exit notification must not retry or clean again.
    assert restores == [broker.test_token] and len(cleanup_calls) == 1
    assert broker.retry_restore() is True
    assert broker.phase == 'stopped' and not broker.restore_pending
    assert restores == [broker.test_token, broker.test_token]
    assert broker.retry_restore() is True
    broker.request_stop('already restored')
    assert len(restores) == 2 and len(cleanup_calls) == 1
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'running')


def test_restore_retry_failure_keeps_token_and_reports_both_failures(broker, factory, cleanup_calls):
    restores, failures, reentrant = [], [], []
    broker.failed.connect(failures.append)
    def restore(token):
        restores.append(token)
        raise OSError('restore still unavailable')
    broker.restore = restore
    broker.command_factory = factory('invalid_progress')
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase in ('restore_failed', 'stopped'))
    assert broker.phase == 'restore_failed'
    assert broker.last_error == 'invalid_progress'
    assert failures == ['invalid_progress', 'restore_failed']
    def during_failure(source):
        broker.request_stop('stop inside restore failure signal')
        reentrant.append((source, broker.retry_restore()))
    broker.phase_changed.connect(
        lambda phase: during_failure('phase') if phase == 'restore_failed' else None)
    broker.failed.connect(
        lambda code: during_failure('failed') if code == 'restore_failed' else None)
    assert broker.retry_restore() is False
    assert broker.phase == 'restore_failed' and broker.restore_pending
    assert restores == [broker.test_token, broker.test_token]
    assert failures == ['invalid_progress', 'restore_failed', 'restore_failed']
    assert reentrant == [('phase', False), ('failed', False)]
    assert len(cleanup_calls) == 1 and not broker._timers
    with pytest.raises(RuntimeError):
        broker.start('c01', 'c01.save')
    QTest.qWait(300)  # No timer-driven restore retries after either failure.
    broker.request_stop('still stopped')
    broker._finish()
    assert len(restores) == 2 and len(cleanup_calls) == 1


def test_stop_during_restore_does_not_repeat_restore_or_cleanup(broker, cleanup_calls):
    restores, phases = [], []
    broker.phase_changed.connect(phases.append)
    def restore(token):
        restores.append(token)
        broker.request_stop('stop inside restore')
        broker._finish()
    broker.restore = restore
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'running')
    broker.request_stop('finished')
    until(lambda: broker.phase == 'stopped')
    assert restores == [broker.test_token]
    assert len(cleanup_calls) == 1
    assert phases.count('stopped') == 1
    assert not broker.restore_pending
    assert broker.retry_restore() is True
    assert len(restores) == 1 and len(cleanup_calls) == 1


def test_retry_restore_cannot_restore_while_owned_child_is_running(broker, cleanup_calls):
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'running')
    owned = broker.process
    assert broker.restore_pending
    assert broker.retry_restore() is False
    broker.request_stop('finished')
    assert owned.state() != QProcess.ProcessState.NotRunning
    assert broker.retry_restore() is False
    broker._finish()
    assert broker.test_calls == ['suspend'] and cleanup_calls == []
    until(lambda: broker.phase == 'stopped')
    assert broker.test_calls == ['suspend', ('restore', broker.test_token)]
    assert len(cleanup_calls) == 1


def test_stop_at_activating_signal_never_sends_activate_or_arms_activation(broker, monkeypatch):
    broker.suspend = lambda: None
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'ready')
    controls, timers = [], []
    send, arm = broker._send, broker._arm
    def watched_send(kind, payload):
        if kind == 'control':
            controls.append(payload['action'])
        return send(kind, payload)
    def watched_arm(name, milliseconds, callback):
        timers.append(name)
        arm(name, milliseconds, callback)
    monkeypatch.setattr(broker, '_send', watched_send)
    monkeypatch.setattr(broker, '_arm', watched_arm)
    broker.suspend = lambda: broker.test_calls.append('suspend') or broker.test_token
    broker.phase_changed.connect(
        lambda phase: broker.request_stop('cancelled while activating')
        if phase == 'activating' else None)
    assert broker.try_activate() is False
    assert controls == ['stop']
    assert 'activation' not in timers and 'activation' not in broker._timers
    until(lambda: broker.phase == 'stopped')
    assert broker.test_calls == ['suspend', ('restore', broker.test_token)]


def test_stop_and_child_exit_inside_suspend_keeps_failed_restore_retryable(broker, cleanup_calls):
    broker.suspend = lambda: None
    broker.start('c01', 'c01.save')
    until(lambda: broker.phase == 'ready')
    restores, phases = [], []
    broker.phase_changed.connect(phases.append)
    def suspend():
        broker.request_stop('cancel inside suspend')
        until(lambda: broker.process is None or
              broker.process.state() == QProcess.ProcessState.NotRunning)
        return broker.test_token
    def restore(token):
        restores.append(token)
        if len(restores) == 1:
            raise OSError('restore temporarily unavailable')
    broker.suspend, broker.restore = suspend, restore
    assert broker.try_activate() is False
    assert broker.phase == 'restore_failed'
    assert 'stopped' not in phases
    assert broker.restore_pending and broker.process is None
    assert restores == [broker.test_token] and len(cleanup_calls) == 1
    assert broker.retry_restore() is True
    assert broker.phase == 'stopped' and not broker.restore_pending
    assert restores == [broker.test_token, broker.test_token]
    assert len(cleanup_calls) == 1


def test_disk_write_failure_keeps_valid_memory_progress_but_ack_is_not_persisted(
        broker, factory, monkeypatch):
    import json
    import teaching.state as state
    assert broker.state_store.set_welcome('accepted')
    before = broker.state_store.path.read_bytes()
    saved = []
    broker.progress_saved.connect(saved.append)
    replace = state.os.replace
    def failed_replace(source, destination):
        if Path(destination) == broker.state_store.path:
            raise OSError('simulated progress write failure')
        return replace(source, destination)
    monkeypatch.setattr(state.os, 'replace', failed_replace)
    broker.command_factory = factory('progress')
    broker.start('c01', 'c01.save')
    until(lambda: broker.paths is not None and (broker.paths.runtime_root / 'ack.json').exists())
    ack = json.loads((broker.paths.runtime_root / 'ack.json').read_text(encoding='utf-8'))
    assert ack['persisted'] is False
    assert broker.state_store.completed_count() == 1
    assert broker.state_store.chapter_status('c01.save') == 'completed'
    assert broker.state_store.path.read_bytes() == before
    assert broker.state_store.last_error == 'save_failed'
    assert broker.state_store.read_only and saved == []
