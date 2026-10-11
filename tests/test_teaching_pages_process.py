# SPDX-License-Identifier: GPL-3.0-or-later
"""All C01-C05 chapters use one owned offscreen application process."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator,until
from test_teaching_selection_process import ROOT,practice_request,BRIDGE as SELECTION_BRIDGE,CHAPTERS as SELECTION_CHAPTERS

CHAPTERS=SELECTION_CHAPTERS+('c05.board','c05.add_switch','c05.rename_delete','c05.copy_position','c05.reorder')
assert 'chapters = '+repr(SELECTION_CHAPTERS) in SELECTION_BRIDGE
BRIDGE=SELECTION_BRIDGE.replace('chapters = '+repr(SELECTION_CHAPTERS),'chapters = '+repr(CHAPTERS))
BRIDGE=BRIDGE.replace('time.monotonic() + 50','time.monotonic() + 75')
BRIDGE=BRIDGE.replace("        elif chapter.startswith('c04.'):", """        elif chapter.startswith('c05.'):
            if name in ('enter','exit'):
                panel.icon_buttons['whiteboard'].click()
            elif name in ('black','white'):
                panel.icon_buttons['board_style'].click()
            elif name == 'add':
                panel.rail_new.click()
            elif name == 'previous':
                panel.rail_prev.click()
            elif name == 'next':
                panel.rail_next.click()
            elif name == 'thumbnails':
                panel.rail_count.click()
            elif name == 'rename':
                self.module.QInputDialog.getText=lambda *args,**kwargs:('Practice',True)
                panel.btn_rename_page.click()
            elif name in ('cancel_delete','delete'):
                QMessageBox.exec=lambda box: (QMessageBox.StandardButton.Cancel if name=='cancel_delete' else QMessageBox.StandardButton.Yes)
                panel.btn_delete_page.click()
                QMessageBox.exec=lambda box:QMessageBox.StandardButton.Yes
            elif name in ('before','after','first','last'):
                combo=panel.document_preferences.copy_combo
                combo.setCurrentIndex(combo.findData(name))
            elif name.startswith('copy_'):
                panel.btn_copy_page.click()
            elif name == 'select_last':
                panel.thumbnail_list.setCurrentRow(2)
            elif name == 'reorder':
                import page_list
                from types import SimpleNamespace
                widget=panel.thumbnail_list
                widget.doItemsLayout()
                class OwnedDrag:
                    def __init__(self,source):self.source=source
                    def setMimeData(self,data):assert data is not None
                    def setPixmap(self,pixmap):pass
                    def setHotSpot(self,point):pass
                    def deleteLater(self):pass
                    def exec(self,action):
                        point=widget.visualItemRect(widget.item(0)).topLeft()
                        event=SimpleNamespace(source=lambda:widget,position=lambda:QPointF(point),setDropAction=lambda _:None,accept=lambda:None,ignore=lambda:None)
                        widget.dropEvent(event)
                        return Qt.DropAction.MoveAction
                original_drag=page_list.QDrag
                try:
                    page_list.QDrag=OwnedDrag
                    widget.startDrag(Qt.DropAction.MoveAction)
                finally:
                    page_list.QDrag=original_drag
            else:
                raise AssertionError('unexpected C05 action: '+name)
        elif chapter.startswith('c04.'):""")


def test_five_courses_137_steps_share_one_process_and_restore_once(parent_coordinator,tmp_path,monkeypatch):
    panel,coordinator=parent_coordinator
    stderr=tmp_path/'pages-child.stderr'
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
          timeout=90000,diagnostic=diagnostic)
    proof=json.loads((coordinator.session.paths.data_dir/'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed']==list(CHAPTERS) and proof['all_complete']
    assert len(set(proof['pids']))==1 and proof['pids'][0]==process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count==1 and coordinator.session.restore.call_count==0
    assert panel.canvas.document_signature()==original and panel._teaching_suspended
    coordinator.session.request_stop('pages course accepted')
    until(lambda:coordinator.session.phase=='stopped',diagnostic=diagnostic)
    assert coordinator.session.restore.call_count==1 and not root.exists()
    assert panel.canvas.document_signature()==original and not panel._teaching_suspended
