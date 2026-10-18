# SPDX-License-Identifier: GPL-3.0-or-later
"""C01-C08 share one authenticated private offscreen QProcess."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_text_process import ROOT, practice_request, BRIDGE as SEVEN_BRIDGE, CHAPTERS as SEVEN_CHAPTERS

CHAPTERS = SEVEN_CHAPTERS + ('c08.save', 'c08.open_guard', 'c08.recovery', 'c08.interval')
anchor = 'chapters = ' + repr(SEVEN_CHAPTERS)
assert anchor in SEVEN_BRIDGE
BRIDGE = SEVEN_BRIDGE.replace(anchor, 'chapters = ' + repr(CHAPTERS))
BRIDGE = BRIDGE.replace('time.monotonic() + 100', 'time.monotonic() + 115')
anchor = "        elif chapter.startswith('c07.'):"
assert anchor in BRIDGE
BRIDGE = BRIDGE.replace(anchor, r'''        elif chapter.startswith('c08.'):
            if chapter == 'c08.save':
                primary = self.request.paths.data_dir / 'c08-first.msd'
                copied = self.request.paths.data_dir / 'c08-copy.msd'
                if name in ('save_first', 'save_again', 'save_as'):
                    path = copied if name == 'save_as' else primary
                    self.module.QFileDialog.getSaveFileName = lambda *args: (str(path), '')
                    (panel.btn_save_project_as if name == 'save_as' else panel.btn_save_project).click()
                    assert path.is_file()
                    trace['file_saves'] = trace.get('file_saves', 0) + 1
                elif name == 'edit':
                    mouse(canvas, 'press', 420,310); mouse(canvas, 'move', 520,320); mouse(canvas, 'release', 550,330)
                    trace['c08_saved_document'] = canvas.serialized_document_pages()
                elif name == 'reopen':
                    self.module.QFileDialog.getOpenFileName = lambda *args: (str(copied), '')
                    panel.btn_open_project.click()
                    assert canvas.serialized_document_pages() == trace['c08_saved_document']
                else:
                    raise AssertionError('unexpected save lesson: '+name)
            elif chapter == 'c08.open_guard':
                sample = Path(panel._teaching_file_open_path)
                self.module.QFileDialog.getOpenFileName = lambda *args: (str(sample), '')
                if name in ('make_dirty', 'make_dirty_again'):
                    mouse(canvas, 'press', 420,310); mouse(canvas, 'move', 520,320); mouse(canvas, 'release', 550,330)
                    trace['c08_unsaved_signature'] = canvas.document_signature()
                    trace['c08_unsaved_document'] = canvas.serialized_document_pages()
                else:
                    choice = {'cancel_open': QMessageBox.StandardButton.Cancel,
                              'discard_open': QMessageBox.StandardButton.Discard,
                              'save_then_open': QMessageBox.StandardButton.Save}[name]
                    QMessageBox.exec = lambda self: choice
                    panel.btn_open_project.click()
                    if name == 'cancel_open':
                        assert canvas.document_signature() == trace['c08_unsaved_signature']
                    elif name == 'discard_open':
                        assert canvas.document_signature() != trace['c08_unsaved_signature']
                    else:
                        assert canvas.serialized_document_pages() == trace['c08_unsaved_document']
                        assert not panel.has_unsaved_changes()
                        trace['file_saves'] += 1
            elif chapter == 'c08.recovery':
                if name in ('preview', 'restore'):
                    before = canvas.document_signature()
                    self.module.RecoveryDialog.exec = lambda dialog: QDialog.DialogCode.Rejected if name == 'preview' else QDialog.DialogCode.Accepted
                    panel.btn_recovery.click()
                    if name == 'preview':
                        assert canvas.document_signature() == before
                    else:
                        assert canvas.document_signature() != before and panel.project_path is None
                        assert len(canvas.pages) == 2 and panel.project_dirty
                elif name == 'save_restored':
                    path = self.request.paths.data_dir / 'c08-restored.msd'
                    self.module.QFileDialog.getSaveFileName = lambda *args: (str(path), '')
                    panel.btn_save_project.click()
                    assert path.is_file() and not panel.has_unsaved_changes()
                    trace['file_saves'] += 1
                else:
                    raise AssertionError('unexpected recovery lesson: '+name)
            elif chapter == 'c08.interval':
                preferences = panel.document_preferences
                if name == 'custom':
                    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(-1))
                elif name == 'custom_75':
                    assert preferences.interval_custom.isVisible()
                    preferences.interval_custom.setValue(75)
                else:
                    seconds = {'preset_60': 60, 'preset_30': 30}[name]
                    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(seconds))
                    assert panel.autosave_interval_seconds == seconds
            else:
                raise AssertionError('unexpected C08 chapter: '+chapter)
        elif chapter.startswith('c07.'):''')


def test_eight_courses_294_steps_share_one_process_and_restore_once(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    stderr = tmp_path / 'project-child.stderr'
    original_stderr = QProcess.setStandardErrorFile
    monkeypatch.setattr(QProcess, 'setStandardErrorFile', lambda process, _: original_stderr(process, str(stderr)))
    coordinator.session.command_factory = lambda request: (sys.executable, ['-B', '-c', BRIDGE, str(ROOT), str(ROOT),
        *practice_arguments(request.paths, request.channel, request.course_id, request.chapter_id)])
    coordinator.session.suspend = Mock(wraps=coordinator.session.suspend)
    coordinator.session.restore = Mock(wraps=coordinator.session.restore)
    original = panel.canvas.document_signature()
    assert coordinator.start('c01', 'c01.interface')
    process = coordinator.session.process
    until(lambda: coordinator.session.phase == 'running')
    token = coordinator.session._token
    root = coordinator.session.paths.runtime_root
    def diagnostic():
        return (coordinator.session.phase, coordinator.session.last_error,
                {id: coordinator.state_store.chapter_status(id) for id in CHAPTERS},
                stderr.read_text(encoding='utf-8', errors='replace')[-5000:] if stderr.exists() else '')
    until(lambda: all(coordinator.state_store.chapter_status(id) == 'completed' for id in CHAPTERS),
          timeout=125000, diagnostic=diagnostic)
    proof = json.loads((coordinator.session.paths.data_dir / 'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed'] == list(CHAPTERS) and proof['all_complete']
    assert len(proof['steps']) == 294 and proof['file_saves'] == 5
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count == 1 and coordinator.session.restore.call_count == 0
    assert panel.canvas.document_signature() == original and panel._teaching_suspended
    coordinator.session.request_stop('project courses accepted')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=diagnostic)
    assert coordinator.session.restore.call_count == 1 and not root.exists()
    assert panel.canvas.document_signature() == original and not panel._teaching_suspended
