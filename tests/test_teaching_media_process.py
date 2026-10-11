# SPDX-License-Identifier: GPL-3.0-or-later
"""C01-C09 share one private offscreen application process."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_project_process import ROOT, practice_request, BRIDGE as EIGHT_BRIDGE, CHAPTERS as EIGHT_CHAPTERS

CHAPTERS = EIGHT_CHAPTERS + ('c09.image', 'c09.pdf_pages')
anchor = 'chapters = ' + repr(EIGHT_CHAPTERS)
assert anchor in EIGHT_BRIDGE
BRIDGE = EIGHT_BRIDGE.replace(anchor, 'chapters = ' + repr(CHAPTERS))
BRIDGE = BRIDGE.replace('time.monotonic() + 115', 'time.monotonic() + 130')
anchor = "        elif chapter.startswith('c08.'):"
assert anchor in BRIDGE
BRIDGE = BRIDGE.replace(anchor, r'''        elif chapter.startswith('c09.'):
            if name in ('import_image', 'import_pdf'):
                path = panel._teaching_media_source_path
                self.module.QFileDialog.getOpenFileName = lambda *args, **kwargs: (path, '')
                def acknowledge_notice(remaining=100):
                    for notice in panel.findChildren(QMessageBox):
                        if notice.isVisible() and notice.windowTitle() == self.module.tr('import_done'):
                            button = notice.button(QMessageBox.StandardButton.Ok)
                            assert button is not None
                            button.click()
                            trace['media_notices'] = trace.get('media_notices', 0) + 1
                            return
                    assert remaining > 0, 'import information dialog did not appear'
                    QTimer.singleShot(50, lambda: guard(self, lambda: acknowledge_notice(remaining-1)))
                QTimer.singleShot(0, lambda: guard(self, acknowledge_notice))
                panel.btn_import_media.click()
                if name == 'import_image':
                    assert len(canvas.image_items) == 1
                    trace['c09_image_id'] = str(canvas.image_items[0]['id'])
                else:
                    assert len(canvas.pages) == 3 and canvas.current_page == 1
                    assert len({page['page_id'] for page in canvas.pages}) == 3
                    trace['c09_page_ids'] = [page['page_id'] for page in canvas.pages]
            elif name == 'select_mode':
                panel.btn_select.click()
            elif name == 'resize_image':
                image = canvas.image_items[0]
                before = image['size'].width(), image['size'].height()
                start = canvas.selection_handles()['scale'].center().toPoint()
                end = start + QPoint(45, 30)
                mouse(canvas, 'press', start.x(), start.y()); mouse(canvas, 'move', end.x(), end.y()); mouse(canvas, 'release', end.x(), end.y())
                assert (image['size'].width(), image['size'].height()) != before
                assert str(image['id']) == trace['c09_image_id']
                trace['media_resized'] = True
            elif name == 'next_page':
                panel.rail_next.click()
                assert canvas._page_id == trace['c09_page_ids'][2] and len(canvas.image_items) == 1
            elif name == 'annotate':
                mouse(canvas, 'press', 420,310); mouse(canvas, 'move', 520,320); mouse(canvas, 'release', 550,330)
                assert canvas.all_segments
            elif name == 'previous_page':
                panel.rail_prev.click()
                assert canvas._page_id == trace['c09_page_ids'][1] and not canvas.all_segments
                assert canvas.pages[2]['segments'] and not canvas.pages[0]['segments']
                trace['media_pages_isolated'] = True
            else:
                raise AssertionError('unexpected C09 action: '+name)
        elif chapter.startswith('c08.'):''')


def test_nine_courses_297_steps_share_one_process_and_restore_once(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    stderr = tmp_path / 'media-child.stderr'
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
          timeout=140000, diagnostic=diagnostic)
    proof = json.loads((coordinator.session.paths.data_dir / 'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed'] == list(CHAPTERS) and proof['all_complete']
    assert len(proof['steps']) == 297 and proof['media_resized'] and proof['media_pages_isolated']
    assert proof['media_notices'] == 2
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count == 1 and coordinator.session.restore.call_count == 0
    assert panel.canvas.document_signature() == original and panel._teaching_suspended
    coordinator.session.request_stop('media courses accepted')
    until(lambda: coordinator.session.phase == 'stopped', diagnostic=diagnostic)
    assert coordinator.session.restore.call_count == 1 and not root.exists()
    assert panel.canvas.document_signature() == original and not panel._teaching_suspended
