# SPDX-License-Identifier: GPL-3.0-or-later
"""C01-C10 share one real private offscreen process; no native input."""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QWidget
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_business_adapters import draw_ink
from test_teaching_media_process import ROOT, practice_request, BRIDGE as NINE_BRIDGE, CHAPTERS as NINE_CHAPTERS

CHAPTERS = NINE_CHAPTERS + ('c10.formats', 'c10.progress_cancel', 'c10.result')
anchor = 'chapters = ' + repr(NINE_CHAPTERS)
assert anchor in NINE_BRIDGE
BRIDGE = NINE_BRIDGE.replace(anchor, 'chapters = ' + repr(CHAPTERS))
BRIDGE = BRIDGE.replace('time.monotonic() + 130', 'time.monotonic() + 150')
BRIDGE = BRIDGE.replace('from PyQt6.QtWidgets import QDialog, QMessageBox', '''from PyQt6.QtWidgets import QDialog, QMessageBox, QProgressDialog, QProgressBar, QPushButton, QWidget
from PyQt6.QtGui import QImageReader
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtSvg import QSvgRenderer
QWidget.grab = lambda *args: (_ for _ in ()).throw(AssertionError('widget capture forbidden'))''')
anchor = "        elif chapter.startswith('c09.'):"
assert anchor in BRIDGE
BRIDGE = BRIDGE.replace(anchor, r'''        elif chapter.startswith('c10.'):
            fmt = name.upper() if chapter == 'c10.formats' else 'PNG'
            before = canvas.document_signature()
            results = []
            create = self.module.ControlPanel._create_document_progress
            def create_progress(title, total):
                dialog = create(panel, title, total)
                assert isinstance(dialog, QProgressDialog)
                trace['c10_progress_dialogs'] = trace.get('c10_progress_dialogs', 0) + 1
                if name == 'cancel_png':
                    button = dialog.findChild(QPushButton)
                    assert button is not None and button.text() == self.module.tr('cancel')
                    def changed(value):
                        if value == 1:
                            def cancel():
                                button.click()
                                assert dialog.wasCanceled()
                                trace['c10_cancel_clicked'] = True
                            QTimer.singleShot(0, lambda: guard(self, cancel))
                    dialog.findChild(QProgressBar).valueChanged.connect(changed)
                return dialog
            # Capture the real result model; the exporter and completion adapter stay intact.
            panel._create_document_progress = create_progress
            panel._show_export_result = lambda result, format_name: results.append(result)
            getattr(panel, 'btn_export_'+fmt.lower()).click()
            assert len(results) == 1
            result = results[0]
            assert canvas.document_signature() == before and not engine._issued
            assert not panel._document_transition_active and self.presenter._dialog_depth == 0
            if name == 'cancel_png':
                assert trace['c10_cancel_clicked'] and result.cancelled and not result.success
                assert not result.complete and result.exported_indices == (1,) and not result.failures
                assert QImageReader(result.exported_paths[0]).canRead()
            elif name == 'partial_png':
                assert not result.success and result.complete and not result.cancelled
                assert result.exported_indices == (1,3) and len(result.failures) == 1 and result.failures[0].page == 2
                assert (self.request.paths.export_dir/'c10_result_p2.png').is_dir()
                assert all(QImageReader(path).canRead() for path in result.exported_paths)
            else:
                assert result.success and result.exported_indices == (1,2,3)
                assert len(result.exported_paths) == (1 if fmt == 'PDF' else 3)
                for path in result.exported_paths:
                    assert Path(path).is_relative_to(self.request.paths.export_dir)
                    if fmt == 'PNG': assert QImageReader(path).canRead()
                    elif fmt == 'SVG': assert QSvgRenderer(path).isValid()
                    elif fmt == 'EPS': assert Path(path).read_bytes().startswith(b'%!PS-Adobe')
                    else:
                        document = QPdfDocument(None)
                        try:
                            assert document.load(path) == QPdfDocument.Error.None_ and document.pageCount() == 3
                        finally: document.close()
            assert not list(self.request.paths.export_dir.glob('.msd-export-*'))
            trace.setdefault('c10_exports', []).append({'step': name, 'format': fmt, 'pages': list(result.exported_indices),
                'total': result.total, 'success': result.success, 'cancelled': result.cancelled,
                'complete': result.complete, 'failed_pages': [failure.page for failure in result.failures]})
            record(self, 'c10_export_checked')
        elif chapter.startswith('c09.'):''')


def run_course_process(parent_coordinator, tmp_path, monkeypatch, *, chapters, bridge_source, expected_steps):
    import main
    panel, coordinator = parent_coordinator
    def forbidden(*args, **kwargs):
        raise AssertionError('capture forbidden')
    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)
    monkeypatch.setattr(QWidget, 'grab', forbidden)
    monkeypatch.setattr(main.ControlPanel, 'grab_screen', forbidden)
    stderr = tmp_path/'export-child.stderr'
    original_stderr = QProcess.setStandardErrorFile
    monkeypatch.setattr(QProcess, 'setStandardErrorFile', lambda process, _: original_stderr(process, str(stderr)))
    # A file avoids Windows' command-line limit for the existing nine-course bridge.
    bridge = tmp_path/'export-child.py'
    bridge.write_text(bridge_source, encoding='utf-8')
    coordinator.session.command_factory = lambda request: (sys.executable, ['-B', str(bridge), str(ROOT), str(ROOT),
        *practice_arguments(request.paths, request.channel, request.course_id, request.chapter_id)])
    coordinator.session.suspend = Mock(wraps=coordinator.session.suspend)
    coordinator.session.restore = Mock(wraps=coordinator.session.restore)
    data, exports = Path(main.DATA_DIR), Path(main.EXPORT_DIR)
    assert not data.resolve().is_relative_to(ROOT) and not exports.resolve().is_relative_to(ROOT)
    panel.canvas.enter_whiteboard(); draw_ink(panel.canvas)
    panel.canvas.new_page(); draw_ink(panel.canvas)
    project = data/'c10-parent-original.msd'
    assert panel.save_project(str(project))
    draw_ink(panel.canvas)
    (Path(main.AUTOSAVE_DIR)/'c10-parent-synthetic.msd').write_bytes(project.read_bytes())
    (exports/'c10-parent-existing.txt').write_text('synthetic parent export', encoding='utf-8')
    def hashes():
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for base in (data, exports) for path in base.rglob('*') if path.is_file()}
    original_hashes = hashes()
    original = panel.canvas.document_signature()
    original_pages = panel.canvas.serialized_document_pages()
    history, redo = panel.canvas.undo_stack, panel.canvas.redo_stack
    before = (panel.project_path, panel.project_dirty, panel.canvas.draw_state, panel.canvas.current_page,
              set(panel.canvas.selected_ids), panel.lifecycle.state, len(history), len(redo))
    assert coordinator.start(chapters[0].split('.')[0], chapters[0])
    process = coordinator.session.process
    until(lambda: coordinator.session.phase == 'running')
    exits=[]
    process.finished.connect(lambda code,status:exits.append((code,str(status))))
    token, root = coordinator.session._token, coordinator.session.paths.runtime_root
    def diagnostic():
        return (coordinator.session.phase, coordinator.session.last_error, exits,
                {key: coordinator.state_store.chapter_status(key) for key in chapters},
                stderr.read_text(encoding='utf-8', errors='replace')[-4000:] if stderr.exists() else '')
    until(lambda: all(coordinator.state_store.chapter_status(key) == 'completed' for key in chapters)
          or coordinator.session.phase == 'stopped',
          timeout=90000, diagnostic=diagnostic)
    assert all(coordinator.state_store.chapter_status(key) == 'completed' for key in chapters), diagnostic()
    proof = json.loads((coordinator.session.paths.data_dir/'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed'] == list(chapters) and proof['all_complete'] and len(proof['steps']) == expected_steps
    if 'c10.formats' in chapters:
        assert len(proof['c10_exports']) == 7 and proof['c10_progress_dialogs'] == 7
        assert proof['c10_cancel_clicked']
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session.process is process and coordinator.session._token is token
    assert coordinator.session.suspend.call_count == 1 and coordinator.session.restore.call_count == 0
    assert panel.canvas.document_signature() == original and panel._teaching_suspended
    assert hashes() == original_hashes
    proof['parent_original_hashes'] = original_hashes
    proof['private_root'] = str(root)
    coordinator.session.request_stop('Tutorial chapters accepted')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=diagnostic)
    assert exits == [(0, str(QProcess.ExitStatus.NormalExit))] and coordinator.session.process is None
    assert coordinator.session.restore.call_count == 1 and not root.exists()
    assert panel.canvas.document_signature() == original and panel.canvas.serialized_document_pages() == original_pages
    assert panel.canvas.undo_stack is history and panel.canvas.redo_stack is redo
    assert (panel.project_path, panel.project_dirty, panel.canvas.draw_state, panel.canvas.current_page,
            set(panel.canvas.selected_ids), panel.lifecycle.state, len(history), len(redo)) == before
    assert hashes() == original_hashes and not panel._teaching_suspended and not coordinator.restore_errors
    proof.update(parent_restored=True, parent_hashes_unchanged=True, child_stopped=True, private_root_removed=True)
    (tmp_path/'c10-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    return proof


def test_ten_courses_314_steps_one_process_preserves_parent_files_and_cleans_up(parent_coordinator, tmp_path, monkeypatch):
    run_course_process(parent_coordinator, tmp_path, monkeypatch,
                       chapters=CHAPTERS, bridge_source=BRIDGE, expected_steps=314)
