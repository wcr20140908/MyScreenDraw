# SPDX-License-Identifier: GPL-3.0-or-later
"""Real center visits and one owned QProcess using authenticated local sockets."""
import copy
import json
import sys
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QProcess

from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, practice_request, until
from test_teaching_private_center import center_host, accepted_center


def visit_steps():
    return [{'id': 'visit', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
             'target': 'tools.teaching', 'input_policy': 'target_only', 'reveal': ['open_tools_panel'],
             'wait': {'event': 'center.visited', 'outcome': 'success'}, 'next': 'end_chapter'}]


@pytest.fixture
def visit_host(practice_request, request):
    root = practice_request.paths.resource_dir / 'assets/tutorials'
    data = json.loads((root / 'course.json').read_text(encoding='utf-8'))
    data['chapters'][0]['steps'] = visit_steps()
    (root / 'course.json').write_text(json.dumps(data), encoding='utf-8')
    return request.getfixturevalue('center_host')


def test_only_a_visible_center_and_successful_return_complete_the_visit(visit_host, tmp_path):
    host, progress = visit_host
    accepted_center(host, tmp_path)
    assert host.presenter.engine.phase == 'running'
    assert not any(record[1] == 'completed' for record in progress)
    host.center_closed.connect(lambda: host.finish_center(resume=True))
    host.center.close()
    assert host.presenter.engine.phase == 'completed'
    assert progress[-1] == ('c01.foundation', 'completed', 1)
    assert host.presenter._dialog_depth == 0 and host._center_batch is None


def test_center_visit_does_not_credit_pause_epoch_or_duplicate_return(visit_host, tmp_path):
    host, progress = visit_host
    accepted_center(host, tmp_path)
    host.pause(hidden=True)
    host.resume()
    host.finish_center(resume=True)
    assert host.presenter.engine.phase == 'running'
    assert not any(record[1] == 'completed' for record in progress)
    host.finish_center(resume=True)
    assert host.presenter.engine.phase == 'running'
    accepted_center(host, tmp_path)
    host.finish_center(resume=True)
    assert host.presenter.engine.phase == 'completed'
    assert sum(record[1] == 'completed' for record in progress) == 1


def test_unshown_center_never_credits_visit(visit_host, tmp_path):
    host, progress = visit_host
    assert host.request_center()
    host.finish_center(resume=True)
    assert host.presenter.engine.phase == 'running'
    assert not any(record[1] == 'completed' for record in progress)


def test_stop_from_center_never_credits_visit(visit_host, tmp_path):
    host, progress = visit_host
    accepted_center(host, tmp_path)
    host.close()
    assert host.presenter.engine.phase == 'stopped'
    assert not any(record[1] == 'completed' for record in progress)
    assert host.presenter._dialog_depth == 0


_CENTER_BRIDGE = r"""
import json, os, runpy, sys, traceback
from pathlib import Path
app_dir = Path(sys.argv[1]); resources = Path(sys.argv[2])
sys.path.insert(0, str(app_dir)); sys._MEIPASS = str(resources)
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox
from teaching.application import ApplicationTeachingHost
original_activate = ApplicationTeachingHost.activate
original_accept = ApplicationTeachingHost.accept_center
original_finish = ApplicationTeachingHost.finish_center
original_commit = ApplicationTeachingHost.commit_chapter
trace = {'pids': [], 'centers': 0}

def record(self, stage):
    trace['pids'].append(os.getpid())
    trace['stage'] = stage
    (self.request.paths.data_dir / 'center-proof.json').write_text(json.dumps(trace), encoding='utf-8')

def guarded(self, fn):
    try:
        fn()
    except Exception:
        trace['error'] = traceback.format_exc()
        record(self, 'failed')
        self.failed.emit('test_center_bridge_failed')

def activate(self):
    original_activate(self)
    record(self, 'active')
    QTimer.singleShot(40, lambda: guarded(self, lambda: self.panel.open_teaching_center()))

def accept(self, view, **kwargs):
    original_accept(self, view, **kwargs)
    trace['centers'] += 1
    record(self, 'center_open')
    def choose():
        assert self.center.isVisible() and self.panel._teaching_suspended
        assert not self.center.reset_button.isEnabled()
        if trace['centers'] == 1:
            self.center.close()
        else:
            assert self.view.chapter_record('c01.foundation')['status'] == 'completed'
            assert self.center.select_chapter('c01', 'c01.second')
            QMessageBox.exec = lambda box: QMessageBox.StandardButton.Yes
            self.center.start_button.click()
    QTimer.singleShot(40, lambda: guarded(self, choose))

def finish(self, **kwargs):
    original_finish(self, **kwargs)
    assert self.presenter.engine.phase == 'completed'
    record(self, 'returned')
    QTimer.singleShot(40, lambda: guarded(self, self.panel.open_teaching_center))

def commit(self):
    original_commit(self)
    assert self.request.chapter_id == 'c01.foundation'
    assert self.presenter.engine.chapter_id == 'c01.second'
    assert self.presenter.engine.phase == 'running'
    assert not self.panel._teaching_suspended and self.panel.canvas.isVisible()
    self.presenter.engine.next()
    assert self.presenter.engine.phase == 'completed'
    record(self, 'second_complete')

ApplicationTeachingHost.activate = activate
ApplicationTeachingHost.accept_center = accept
ApplicationTeachingHost.finish_center = finish
ApplicationTeachingHost.commit_chapter = commit
sys.argv = [str(app_dir / 'main.py'), *sys.argv[3:]]
runpy.run_path(str(app_dir / 'main.py'), run_name='__main__')
"""


def test_actual_same_process_center_return_switch_and_progress_ack(practice_request, request):
    root = practice_request.paths.resource_dir / 'assets/tutorials'
    data = json.loads((root / 'course.json').read_text(encoding='utf-8'))
    data['chapters'][0]['steps'] = visit_steps()
    data['chapters'].append({'id': 'c01.second', 'title_key': 'teaching_center_title', 'fixture': 'blank',
                             'steps': [{'id': 'read', 'title_key': 'teaching_center_title',
                                        'body_key': 'teaching_resume', 'kind': 'information', 'next': 'end_chapter'}]})
    (root / 'course.json').write_text(json.dumps(data), encoding='utf-8')
    panel, coordinator = request.getfixturevalue('parent_coordinator')
    def command(req):
        return sys.executable, ['-B', '-c', _CENTER_BRIDGE, str(req.paths.app_dir),
                                str(req.paths.resource_dir), *practice_arguments(
                                    req.paths, req.channel, req.course_id, req.chapter_id)]
    coordinator.session.command_factory = command
    suspend, restore = coordinator.session.suspend, coordinator.session.restore
    coordinator.session.suspend = Mock(wraps=suspend)
    coordinator.session.restore = Mock(wraps=restore)
    before = panel.canvas.document_signature()
    assert coordinator.start('c01', 'c01.foundation')
    process = coordinator.session.process
    until(lambda: coordinator.session.phase == 'running', diagnostic=lambda: coordinator.session.last_error)
    token = coordinator.session._token
    private_root = coordinator.session.paths.runtime_root
    until(lambda: coordinator.state_store.chapter_record('c01.second')['status'] == 'completed',
          diagnostic=lambda: (coordinator.session.phase, coordinator.session.last_error,
                              coordinator.state_store.snapshot()))
    proof = json.loads((coordinator.session.paths.data_dir / 'center-proof.json').read_text(encoding='utf-8'))
    assert proof['stage'] == 'second_complete' and proof['centers'] == 2
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session.process is process and process.state() == QProcess.ProcessState.Running
    assert coordinator.session._token is token and coordinator.session.suspend.call_count == 1
    assert coordinator.session.restore.call_count == 0
    assert coordinator.state_store.chapter_record('c01.foundation')['status'] == 'completed'
    assert panel.canvas.document_signature() == before and panel._teaching_suspended
    coordinator.session.request_stop('test finished')
    until(lambda: coordinator.session.phase == 'stopped')
    assert coordinator.session.restore.call_count == 1 and not private_root.exists()
    assert panel.canvas.document_signature() == before and not panel._teaching_suspended
