# SPDX-License-Identifier: GPL-3.0-or-later
"""All three formal courses in one authenticated offscreen practice process."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_core_process import ROOT, practice_request, _CORE_BRIDGE

CHAPTERS = ('c01.interface','c01.ink','c01.select','c01.pages','c01.files','c01.finish',
            'c02.styles','c02.color_width','c02.transient','c03.erase','c03.history_clear')

BRIDGE = _CORE_BRIDGE.replace("chapters = ('interface', 'ink', 'select', 'pages', 'files', 'finish')",
                              'chapters = '+repr(CHAPTERS))
BRIDGE = BRIDGE.replace('time.monotonic() + 25','time.monotonic() + 50')
BRIDGE = BRIDGE.replace("chapters.index(chapter_id.split('.')[1])","chapters.index(chapter_id)")
BRIDGE = BRIDGE.replace("'c01.' + chapters[index + 1]","chapters[index + 1]")
BRIDGE = BRIDGE.replace("if name in ('identity', 'done'):","if current.kind == 'information':")
BRIDGE = BRIDGE.replace("        elif name == 'pen':", """        elif name.startswith('choose_'):
            panel.pen_style_buttons[name.removeprefix('choose_')].click()
        elif name.startswith('try_') or name == 'marker_stroke':
            canvas._pointer_press(1,QPoint(20,20),1.0)
            canvas._pointer_move(1,QPoint(80,60),1.0)
            canvas._pointer_release(1,QPoint(100,80))
        elif name == 'marker':
            panel.btn_ann_marker.click()
        elif name == 'laser':
            panel.btn_ann_laser.click()
        elif name == 'laser_trace':
            mouse(canvas,'press',30,30);mouse(canvas,'move',100,70);mouse(canvas,'release',120,80)
        elif name == 'preset_capture':
            panel.pen_defaults_editor.capture_button.click()
        elif name == 'preset_enable':
            panel.pen_defaults_checkbox.click()
        elif name == 'preset_apply':
            (panel.btn_ann_marker if engine.sequence_index==0 else panel.pen_style_buttons['pen']).click()
        elif name == 'eraser':
            panel.handle_eraser_click()
        elif name == 'circle':
            panel.btn_circ.click()
        elif name == 'size':
            panel.e_slider.setValue(60)
        elif name == 'stroke_mode':
            panel.btn_stroke.click()
        elif name in ('circle_erase','stroke_erase'):
            y=150 if name=='circle_erase' else 390
            mouse(canvas,'press',170,y);mouse(canvas,'move',220,y+30);mouse(canvas,'release',220,y+30)
        elif name == 'clear':
            panel.clear()
        elif name == 'undo_clear':
            assert canvas.undo()
        elif name == 'pen':""")
BRIDGE = BRIDGE.replace("self.center.select_chapter('c01', chapter)","self.center.select_chapter(chapter.split('.')[0], chapter)")


def test_three_courses_79_steps_share_one_process_and_restore_once(parent_coordinator,tmp_path,monkeypatch):
    panel,coordinator=parent_coordinator
    stderr=tmp_path/'writing-child.stderr'
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
    coordinator.session.request_stop('writing courses accepted')
    until(lambda:coordinator.session.phase=='stopped',diagnostic=diagnostic)
    assert coordinator.session.restore.call_count==1 and not root.exists()
    assert panel.canvas.document_signature()==original and not panel._teaching_suspended
