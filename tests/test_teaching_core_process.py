# SPDX-License-Identifier: GPL-3.0-or-later
"""All formal C01 chapters in one authenticated offscreen application process."""
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QProcess

from runtime_paths import RuntimePaths
from teaching.bootstrap import PracticeRequest, practice_arguments
from test_teaching_application import parent_coordinator, until

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ('interface', 'ink', 'select', 'pages', 'files', 'finish')


@pytest.fixture
def practice_request(tmp_path):
    paths = RuntimePaths.create_practice(ROOT, ROOT, temp_root=tmp_path / 'request-root')
    return PracticeRequest(paths, 'unused-formal-core', 'c01', 'c01.interface')


_CORE_BRIDGE = r"""
import json, os, runpy, sys, time, traceback
from pathlib import Path
app_dir = Path(sys.argv[1]); resources = Path(sys.argv[2])
sys.path.insert(0, str(app_dir)); sys._MEIPASS = str(resources)
from PyQt6.QtCore import QTimer, QPoint, QPointF, QEvent, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QScreen
from PyQt6.QtWidgets import QDialog, QMessageBox
from teaching.application import ApplicationTeachingHost, PracticeChild
fail_original = PracticeChild._fail
def report_fail(self):
    sys.stderr.write("child phase=" + str(self.phase) + " center=" + str(self._center_action) + " chapter=" + str(self._active_chapter_id) + "\n")
    if sys.exc_info()[0] is not None:
        traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    fail_original(self)
PracticeChild._fail = report_fail

chapters = ('interface', 'ink', 'select', 'pages', 'files', 'finish')
trace = {'pids': [], 'completed': [], 'centers': 0, 'next': None,
         'pause_requested': False, 'resume_requested': False, 'visit_requested': False}
deadline = time.monotonic() + 25
activate_original = ApplicationTeachingHost.activate
progress_original = ApplicationTeachingHost._record_progress
center_original = ApplicationTeachingHost.accept_center

def record(self, stage):
    trace['pids'].append(os.getpid()); trace['stage'] = stage
    (self.request.paths.data_dir / 'formal-core-proof.json').write_text(json.dumps(trace), encoding='utf-8')

def guard(self, action):
    if self._closed:
        return
    try:
        action()
    except Exception:
        trace['error'] = traceback.format_exc()
        record(self, 'failed')
        sys.stderr.write(trace['error']); sys.stderr.flush()
        self.failed.emit('formal_core_test_failed')

def mouse(canvas, kind, x, y):
    event_type = {'press': QEvent.Type.MouseButtonPress, 'move': QEvent.Type.MouseMove,
                  'release': QEvent.Type.MouseButtonRelease}[kind]
    button = Qt.MouseButton.NoButton if kind == 'move' else Qt.MouseButton.LeftButton
    buttons = Qt.MouseButton.NoButton if kind == 'release' else Qt.MouseButton.LeftButton
    event = QMouseEvent(event_type, QPointF(x,y), QPointF(x,y), button, buttons, Qt.KeyboardModifier.NoModifier)
    getattr(canvas, {'press': 'mousePressEvent', 'move': 'mouseMoveEvent', 'release': 'mouseReleaseEvent'}[kind])(event)

def tick(self):
    if self._closed or trace.get('all_complete'):
        return
    assert time.monotonic() < deadline, 'formal chapter timed out: ' + str(self.presenter.engine.current_step_id)
    engine, panel, canvas = self.presenter.engine, self.panel, self.panel.canvas
    current = engine.current_step
    if engine.phase == 'paused' and current is not None and current.id == 'pause':
        if not trace['resume_requested']:
            trace['resume_requested'] = True
            self.presenter.controller.pause_button.click()
    elif engine.phase == 'running' and current is not None:
        chapter, name = engine.chapter_id, current.id
        if name in ('identity', 'done'):
            self.presenter.controller.next_button.click()
        elif name == 'pen':
            panel.handle_pen_click()
        elif name == 'stroke':
            canvas._pointer_press(1, QPoint(20,20), 1.0)
            canvas._pointer_move(1, QPoint(80,60), 1.0)
            canvas._pointer_release(1, QPoint(100,80))
        elif name == 'mode':
            panel.toggle_mode()
        elif name == 'color':
            next(button for button in panel.color_buttons if button.property('color_val')
                 and QColor(button.property('color_val')) != canvas.pen_color).click()
        elif name == 'width':
            panel.pen_slider.setValue(12 if canvas.pen_width != 12 else 13)
        elif name == 'erase':
            if engine.sequence_index == 0:
                panel.handle_eraser_click()
            else:
                mouse(canvas, 'press',170,150); mouse(canvas,'move',220,180); mouse(canvas,'release',220,180)
        elif name == 'undo':
            assert canvas.undo()
        elif name == 'redo':
            assert canvas.redo()
        elif name == 'choose':
            if engine.sequence_index == 0:
                panel.handle_select_click()
            else:
                mouse(canvas,'press',170,150); mouse(canvas,'release',170,150)
        elif name == 'move':
            mouse(canvas,'press',170,150); mouse(canvas,'move',230,210); mouse(canvas,'release',230,210)
        elif name == 'enter':
            panel.toggle_whiteboard()
        elif name == 'add':
            panel.new_whiteboard_page()
        elif name == 'previous':
            panel.switch_whiteboard_page(-1)
        elif name == 'next':
            panel.switch_whiteboard_page(1)
        elif name == 'save':
            path = self.request.paths.data_dir / '1.msd'
            self.module.QFileDialog.getSaveFileName = lambda *args: (str(path), '')
            assert panel.save_project_from_file_panel()
        elif name == 'open':
            path = self.request.paths.data_dir / '1.msd'
            self.module.QFileDialog.getOpenFileName = lambda *args: (str(path), '')
            assert panel.open_project_from_file_panel()
        elif name == 'preview':
            self.module.RecoveryDialog.exec = lambda dialog: QDialog.DialogCode.Rejected
            assert not panel.open_recovery_from_file_panel()
        elif name == 'restore':
            self.module.RecoveryDialog.exec = lambda dialog: QDialog.DialogCode.Accepted
            assert panel.open_recovery_from_file_panel()
        elif name == 'png':
            panel._show_export_result = lambda *args: None
            assert panel.do_export('PNG').success
        elif name == 'pause':
            if not trace['pause_requested']:
                trace['pause_requested'] = True
                self.presenter.controller.pause_button.click()
        elif name == 'center':
            if not trace['visit_requested']:
                trace['visit_requested'] = True
                assert panel.open_teaching_center()
        else:
            raise AssertionError('unexpected formal step: ' + name)
    QTimer.singleShot(35, lambda: guard(self, lambda: tick(self)))

def activate(self):
    activate_original(self)
    QScreen.grabWindow = lambda *args: (_ for _ in ()).throw(AssertionError('desktop capture forbidden'))
    record(self, 'activated')
    QTimer.singleShot(40, lambda: guard(self, lambda: tick(self)))

def progress(self, chapter_id, status, revision):
    progress_original(self, chapter_id, status, revision)
    if status != 'completed':
        return
    trace['completed'].append(chapter_id)
    record(self, 'chapter_complete')
    index = chapters.index(chapter_id.split('.')[1])
    if index + 1 == len(chapters):
        trace['all_complete'] = True
        record(self, 'all_complete')
    else:
        trace['next'] = 'c01.' + chapters[index + 1]
        QTimer.singleShot(50, lambda: guard(self, self.panel.open_teaching_center))

def center(self, view, **kwargs):
    center_original(self, view, **kwargs)
    trace['centers'] += 1
    def choose():
        if trace['next'] is not None:
            chapter = trace['next']; trace['next'] = None
            assert self.center.select_chapter('c01', chapter)
            QMessageBox.exec = lambda box: QMessageBox.StandardButton.Yes
            self.center.start_button.click()
        else:
            assert self.presenter.engine.current_step_id == 'center'
            self.center.close()
    QTimer.singleShot(40, lambda: guard(self, choose))

ApplicationTeachingHost.activate = activate
ApplicationTeachingHost._record_progress = progress
ApplicationTeachingHost.accept_center = center
sys.argv = [str(app_dir / 'main.py'), *sys.argv[3:]]
runpy.run_path(str(app_dir / 'main.py'), run_name='__main__')
"""


def test_formal_six_chapters_complete_in_one_process_and_restore_original(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    stderr = tmp_path / 'formal-core-child.stderr'
    original_stderr = QProcess.setStandardErrorFile
    monkeypatch.setattr(QProcess, 'setStandardErrorFile', lambda process, _: original_stderr(process, str(stderr)))
    def command(request):
        return sys.executable, ['-B', '-c', _CORE_BRIDGE, str(ROOT), str(ROOT), *practice_arguments(
            request.paths, request.channel, request.course_id, request.chapter_id)]
    coordinator.session.command_factory = command
    wire = []
    receive = coordinator.session._receive
    def observe(message, generation):
        payload = message.get('payload', {})
        wire.append((message['type'], coordinator.session.phase,
                     {key: payload[key] for key in ('chapter_id', 'status', 'course_id') if key in payload}))
        return receive(message, generation)
    coordinator.session._receive = observe
    restore, suspend = coordinator.session.restore, coordinator.session.suspend
    coordinator.session.restore = Mock(wraps=restore)
    coordinator.session.suspend = Mock(wraps=suspend)
    original = panel.canvas.document_signature()
    assert coordinator.start('c01', 'c01.interface')
    process = coordinator.session.process
    until(lambda: coordinator.session.phase == 'running')
    token = coordinator.session._token
    root = coordinator.session.paths.runtime_root
    def diagnostic():
        return (coordinator.session.phase, coordinator.session.last_error, wire,
                {name: coordinator.state_store.chapter_status('c01.' + name) for name in CHAPTERS},
                stderr.read_text(encoding='utf-8', errors='replace')[-3000:] if stderr.exists() else '')
    until(lambda: all(coordinator.state_store.chapter_record('c01.' + name)['status'] == 'completed'
                      for name in CHAPTERS), timeout=30000, diagnostic=diagnostic)
    proof = json.loads((coordinator.session.paths.data_dir / 'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['stage'] == 'all_complete' and proof['completed'] == ['c01.' + name for name in CHAPTERS]
    assert proof['centers'] == 6 and proof['pause_requested'] and proof['resume_requested']
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session.process is process and coordinator.session._token is token
    assert coordinator.session.suspend.call_count == 1 and coordinator.session.restore.call_count == 0
    assert panel.canvas.document_signature() == original and panel._teaching_suspended
    assert not coordinator.session.last_error
    coordinator.session.request_stop('formal course accepted')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=diagnostic)
    assert coordinator.session.restore.call_count == 1 and not root.exists()
    assert not panel._teaching_suspended and panel.canvas.document_signature() == original
