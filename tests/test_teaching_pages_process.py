# SPDX-License-Identifier: GPL-3.0-or-later
"""All C01-C06 chapters use one owned offscreen application process."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator,until
from test_teaching_selection_process import ROOT,practice_request,BRIDGE as SELECTION_BRIDGE,CHAPTERS as SELECTION_CHAPTERS

CHAPTERS=SELECTION_CHAPTERS+('c05.board','c05.add_switch','c05.rename_delete','c05.copy_position','c05.reorder','c05.roam','c06.plane','c06.solid','c06.points','c06.recognition_snap')
assert 'chapters = '+repr(SELECTION_CHAPTERS) in SELECTION_BRIDGE
BRIDGE=SELECTION_BRIDGE.replace('chapters = '+repr(SELECTION_CHAPTERS),'chapters = '+repr(CHAPTERS))
BRIDGE=BRIDGE.replace('time.monotonic() + 50','time.monotonic() + 75')
assert "        elif chapter.startswith('c04.'):" in BRIDGE
BRIDGE=BRIDGE.replace("        elif chapter.startswith('c04.'):", """        elif chapter.startswith('c06.'):
            if name.startswith('choose_'):
                kind=name.removeprefix('choose_').upper()
                next(btn for btn in panel.shape_buttons if btn.property('shape_type')==kind).click()
            elif name.startswith('draw_'):
                kind=name.removeprefix('draw_').upper()
                points={
                    'LINE':((100,160),(360,160)),
                    'DASHED_LINE':((100,160),(360,160)),
                    'TRIANGLE':((100,160),(360,160),(240,340)),
                    'RECT':((100,160),(360,340)),
                    'PARALLELOGRAM':((100,160),(300,160),(360,340)),
                    'TRAPEZOID':((100,340),(360,340),(320,160),(140,160)),
                    'DIAMOND':((100,250),(360,250),(240,340)),
                    'ANGLE':((240,240),(100,240),(240,360)),
                    'CIRCLE':((240,240),(340,240)),
                    'ELLIPSE':((100,160),(360,340)),
                }.get(kind)
                if points is not None:
                    for x,y in points:
                        mouse(canvas,'press',x,y); mouse(canvas,'release',x,y)
                else:
                    mouse(canvas,'press',100,160); mouse(canvas,'move',360,340); mouse(canvas,'release',360,340)
            elif name == 'enable':
                panel.btn_settings_smart.click()
            elif name == 'pen':
                panel.pen_style_buttons['pen'].click()
            elif name == 'recognize_line':
                if not trace.get('hold_started'):
                    trace['hold_started']=time.perf_counter()
                    trace['hold_shapes']=len(canvas.shape_items)
                    mouse(canvas,'press',100,460)
                    for x in range(112,365,12): mouse(canvas,'move',x,460+(x%3))
                elif len(canvas.shape_items)>trace['hold_shapes']:
                    trace['hold_elapsed']=time.perf_counter()-trace['hold_started']
                    assert trace['hold_elapsed']>=canvas.SMART_HOLD_MS/1000
                    mouse(canvas,'release',364,460)
            elif name in ('undo_recognition','redo_recognition'):
                panel.icon_buttons['undo' if name.startswith('undo') else 'redo'].click()
            elif name == 'point1':
                mouse(canvas,'press',120,160); mouse(canvas,'release',120,160)
            elif name == 'point2':
                mouse(canvas,'press',360,160); mouse(canvas,'release',360,160)
            elif name == 'cancel':
                panel.btn_cancel_points.click()
            elif name == 'restart1':
                mouse(canvas,'press',120,160); mouse(canvas,'release',120,160)
            elif name == 'restart2':
                mouse(canvas,'press',360,160); mouse(canvas,'release',360,160)
            elif name == 'finish3':
                mouse(canvas,'press',240,340); mouse(canvas,'release',240,340)
            elif name == 'snap_line':
                for point in ((240,340),(248,157)):
                    mouse(canvas,'press',*point); mouse(canvas,'release',*point)
            elif name in ('midpoint','perp_bisector'):
                line=canvas.single_flat_shape()
                assert line['type']=='LINE'
                label=dict(canvas.shape_op_list(line))[name]
                self.module.QMenu.exec=lambda menu,*args: next(action for action in menu.actions() if action.text()==label).trigger()
                panel.btn_more.click()
            else:
                raise AssertionError('unexpected C06 action: '+name)
        elif chapter == 'c05.roam':
            if name == 'enter_roam':
                panel.icon_buttons['mode'].click()
            elif name in ('pan', 'ink'):
                mouse(canvas, 'press', 360, 420)
                mouse(canvas, 'move', 460, 470)
                mouse(canvas, 'release', 460, 470)
            elif name in ('zoom_in', 'zoom_out'):
                from PyQt6.QtGui import QWheelEvent
                point = QPointF(360, 280)
                event = QWheelEvent(point, QPointF(canvas.mapToGlobal(point.toPoint())),
                    QPoint(), QPoint(0, 120 if name == 'zoom_in' else -120),
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase, False)
                self.module.QApplication.sendEvent(canvas, event)
            elif name in ('fit', 'home'):
                getattr(panel, 'btn_view_' + name).click()
            elif name == 'pen':
                panel.icon_buttons['pen'].click()
            else:
                raise AssertionError('unexpected C05 roaming action: ' + name)
        elif chapter.startswith('c05.'):
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

assert "elif chapter.startswith('c05.')" in BRIDGE
assert "elif chapter.startswith('c06.')" in BRIDGE
BRIDGE=BRIDGE.replace("        chapter, name = engine.chapter_id, current.id", """        chapter, name = engine.chapter_id, current.id
        key=[chapter,name]
        if key not in trace.setdefault('steps',[]):
            trace['steps'].append(key)""")

def test_six_courses_202_steps_share_one_process_and_restore_once(parent_coordinator,tmp_path,monkeypatch):
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
    until(lambda:all(coordinator.state_store.chapter_status(id)=='completed' for id in CHAPTERS)
          or coordinator.session.phase=='stopped', timeout=90000,diagnostic=diagnostic)
    assert all(coordinator.state_store.chapter_status(id)=='completed' for id in CHAPTERS), diagnostic()
    proof=json.loads((coordinator.session.paths.data_dir/'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed']==list(CHAPTERS) and proof['all_complete']
    assert len(proof['steps'])==202 and proof['hold_elapsed']>=0.65
    assert len(set(proof['pids']))==1 and proof['pids'][0]==process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count==1 and coordinator.session.restore.call_count==0
    assert panel.canvas.document_signature()==original and panel._teaching_suspended
    coordinator.session.request_stop('geometry course accepted')
    until(lambda:coordinator.session.phase=='stopped',diagnostic=diagnostic)
    assert coordinator.session.restore.call_count==1 and not root.exists()
    assert panel.canvas.document_signature()==original and not panel._teaching_suspended
