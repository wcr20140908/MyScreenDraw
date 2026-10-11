# SPDX-License-Identifier: GPL-3.0-or-later
"""C01-C04 share one authenticated practice process; no native input."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_writing_process import ROOT, practice_request, BRIDGE as WRITING_BRIDGE, CHAPTERS as WRITING_CHAPTERS

CHAPTERS = WRITING_CHAPTERS + ('c04.select_move', 'c04.transform', 'c04.copy_delete')
assert 'chapters = ' + repr(WRITING_CHAPTERS) in WRITING_BRIDGE
BRIDGE = WRITING_BRIDGE.replace('chapters = ' + repr(WRITING_CHAPTERS), 'chapters = ' + repr(CHAPTERS))
BRIDGE = BRIDGE.replace("        elif name.startswith('choose_'):", """        elif chapter.startswith('c04.'):
            if name == 'tool':
                panel.handle_select_click()
            elif name == 'select':
                mouse(canvas,'press',170,150);mouse(canvas,'release',170,150)
            elif name == 'move':
                mouse(canvas,'press',170,150);mouse(canvas,'move',210,190);mouse(canvas,'release',210,190)
            elif name in ('scale','rotate'):
                point=canvas.selection_handles()[name].center().toPoint()
                end=point+(QPoint(70,30) if name=='scale' else QPoint(60,40))
                mouse(canvas,'press',point.x(),point.y());mouse(canvas,'move',end.x(),end.y());mouse(canvas,'release',end.x(),end.y())
            elif name == 'box':
                mouse(canvas,'press',90,100);mouse(canvas,'move',460,450);mouse(canvas,'release',460,450)
            elif name == 'copy':
                panel.btn_dup.click()
            elif name == 'delete':
                panel.btn_del.click()
            elif name == 'undo':
                assert canvas.undo()
            else:
                raise AssertionError('unexpected C04 action: '+name)
        elif name.startswith('choose_'):""")


def test_four_courses_98_steps_share_one_process_and_restore_once(parent_coordinator,tmp_path,monkeypatch):
    panel,coordinator=parent_coordinator
    stderr=tmp_path/'selection-child.stderr'
    original_stderr=QProcess.setStandardErrorFile
    monkeypatch.setattr(QProcess,'setStandardErrorFile',lambda process,_:original_stderr(process,str(stderr)))
    coordinator.session.command_factory=lambda request:(sys.executable,['-B','-c',BRIDGE,str(ROOT),str(ROOT),
        *practice_arguments(request.paths,request.channel,request.course_id,request.chapter_id)])
    coordinator.session.suspend=Mock(wraps=coordinator.session.suspend)
    coordinator.session.restore=Mock(wraps=coordinator.session.restore)
    original=panel.canvas.document_signature()
    assert coordinator.start('c01','c01.interface')
    process=coordinator.session.process
    until(lambda:coordinator.session.phase=='running')
    token=coordinator.session._token;root=coordinator.session.paths.runtime_root
    def diagnostic():
        return(coordinator.session.phase,coordinator.session.last_error,
               {id:coordinator.state_store.chapter_status(id) for id in CHAPTERS},
               stderr.read_text(encoding='utf-8',errors='replace')[-3000:] if stderr.exists() else '')
    until(lambda:all(coordinator.state_store.chapter_status(id)=='completed' for id in CHAPTERS),
          timeout=60000,diagnostic=diagnostic)
    proof=json.loads((coordinator.session.paths.data_dir/'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed']==list(CHAPTERS) and proof['all_complete']
    assert len(set(proof['pids']))==1 and proof['pids'][0]==process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count==1 and coordinator.session.restore.call_count==0
    assert panel.canvas.document_signature()==original and panel._teaching_suspended
    coordinator.session.request_stop('selection course accepted')
    until(lambda:coordinator.session.phase=='stopped',diagnostic=diagnostic)
    assert coordinator.session.restore.call_count==1 and not root.exists()
    assert panel.canvas.document_signature()==original and not panel._teaching_suspended
