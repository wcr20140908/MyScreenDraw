# SPDX-License-Identifier: GPL-3.0-or-later
"""C01-C07 run in one authenticated private offscreen QProcess."""
import json
import sys
from unittest.mock import Mock

from PyQt6.QtCore import QProcess
from teaching.bootstrap import practice_arguments
from test_teaching_application import parent_coordinator, until
from test_teaching_pages_process import ROOT, practice_request, BRIDGE as SIX_BRIDGE, CHAPTERS as SIX_CHAPTERS

CHAPTERS = SIX_CHAPTERS + ('c07.edit', 'c07.format', 'c07.formula')
assert 'chapters = '+repr(SIX_CHAPTERS) in SIX_BRIDGE
BRIDGE = SIX_BRIDGE.replace('chapters = '+repr(SIX_CHAPTERS), 'chapters = '+repr(CHAPTERS))
BRIDGE = BRIDGE.replace('time.monotonic() + 75', 'time.monotonic() + 100')
BRIDGE = BRIDGE.replace('def tick(self):', r'''
def text_key(self, key, text=''):
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtWidgets import QApplication
    editor = self.panel.text_input
    event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)
    assert not self.presenter.barrier.eventFilter(editor, event), 'current input target is blocked'
    QApplication.sendEvent(editor, event)
    trace['text_keys'] = trace.get('text_keys', 0) + 1

def input_text(self, text):
    for char in text:
        text_key(self, Qt.Key.Key_unknown, char)

def text_click(canvas, item):
    point = item['pos'] + QPointF(8, 20)
    mouse(canvas, 'press', int(point.x()), int(point.y()))
    mouse(canvas, 'release', int(point.x()), int(point.y()))

def symbol_click(panel, entry):
    layout = panel.symbol_grid_layout
    next(layout.itemAt(index).widget() for index in range(layout.count())
         if layout.itemAt(index).widget().property('teaching_symbol') == entry).click()

def formula_click(canvas, path):
    import formula
    item = canvas.editing_text_item()
    box = canvas.formula_box(item)
    rect = canvas.text_local_rect(item)
    if path:
        _, x, y, width, height = next(row for row in formula.slot_rects(box) if row[0] == path)
        x += width/2; y += height/2
    else:
        x, y = 2, -box.ascent/2
    point = canvas.text_transform(item).map(QPointF(
        rect.left()+canvas.TEXT_PAD+x, rect.top()+canvas.TEXT_PAD+box.ascent+y)).toPoint()
    assert canvas.text_bounds(item).contains(QPointF(point)), 'formula slot outside its object'
    assert canvas.rect().contains(point), 'formula slot outside the private canvas'
    mouse(canvas, 'press', point.x(), point.y()); mouse(canvas, 'release', point.x(), point.y())
    assert tuple(canvas.editing_slot or ()) == path

def tick(self):''')
assert "        elif chapter.startswith('c06.'):" in BRIDGE
BRIDGE = BRIDGE.replace("        elif chapter.startswith('c06.'):", r'''        elif chapter.startswith('c07.'):
            if name == 'choose_text':
                panel.btn_text.click()
            elif name == 'choose_select':
                panel.btn_select.click()
            elif chapter == 'c07.edit':
                if name == 'create_box':
                    mouse(canvas, 'press', 300,240); mouse(canvas,'move',560,380); mouse(canvas,'release',560,380)
                    trace['edit_id'] = str(canvas.editing_text_id)
                elif name == 'type_text':
                    input_text(self, 'AB')
                elif name == 'insert_middle':
                    item = canvas.editing_text_item()
                    rect = canvas.text_local_rect(item)
                    metrics = canvas.text_metrics(canvas.text_font(item))
                    point = canvas.text_transform(item).map(QPointF(
                        rect.left()+canvas.TEXT_PAD+metrics.horizontalAdvance('A'),
                        rect.top()+canvas.TEXT_PAD+metrics.lineSpacing()/2)).toPoint()
                    mouse(canvas, 'press', point.x(),point.y()); mouse(canvas,'release',point.x(),point.y())
                    assert canvas.caret_offset == 1
                    input_text(self, 'C')
                elif name in ('backspace','newline'):
                    panel.text_action_buttons['text_'+name].click()
                elif name in ('finish','finish_again'):
                    panel.text_action_buttons['text_done'].click()
                    assert any(str(item['id']) == trace['edit_id'] for item in canvas.text_items)
                elif name == 'reedit':
                    if engine.sequence_index == 0:
                        text_click(canvas, next(item for item in canvas.text_items if str(item['id']) == trace['edit_id']))
                    else:
                        input_text(self, 'C')
                else:
                    raise AssertionError('unexpected C07 edit action: '+name)
            elif chapter == 'c07.format':
                if name == 'select_box':
                    text_click(canvas, canvas.text_items[0])
                elif name == 'size':
                    panel.select_width_slider.setValue(6)
                elif name == 'color':
                    from PyQt6.QtWidgets import QColorDialog
                    original_exec = QColorDialog.exec
                    original_selected = QColorDialog.selectedColor
                    try:
                        QColorDialog.exec = lambda dialog: True
                        QColorDialog.selectedColor = lambda dialog: QColor('#aa2255')
                        panel.selection_color_button.click()
                    finally:
                        QColorDialog.exec = original_exec
                        QColorDialog.selectedColor = original_selected
                elif name in ('move','scale','rotate'):
                    point = (canvas.selection_bounds().center().toPoint() if name == 'move'
                             else canvas.selection_handles()[name].center().toPoint())
                    end = point + (QPoint(70,30) if name != 'rotate' else QPoint(55,35))
                    mouse(canvas,'press',point.x(),point.y()); mouse(canvas,'move',end.x(),end.y()); mouse(canvas,'release',end.x(),end.y())
                elif name == 'copy':
                    panel.btn_dup.click()
                elif name == 'delete_copy':
                    panel.btn_del.click()
                else:
                    raise AssertionError('unexpected C07 format action: '+name)
            elif chapter == 'c07.formula':
                if name in ('open_symbols','open_formula'):
                    text_click(canvas, next(item for item in canvas.text_items
                        if item.get('text') == ('Symbols: ' if name == 'open_symbols' else 'F = ')))
                elif name in ('greek','operator','relation','calculus'):
                    symbol_click(panel, {'greek':'α','operator':'±','relation':'∈','calculus':'∫'}[name])
                elif name == 'structure':
                    panel._symbol_group_buttons['structure'].click()
                elif name in ('frac','sup','sub','sqrt','sqrt_frac','sum','integral'):
                    kind = 'int' if name == 'integral' else 'frac' if name == 'sqrt_frac' else name
                    symbol_click(panel, kind)
                    trace['formula_prefix'] = list(canvas.editing_slot[:-1])
                elif name == 'frac_edit':
                    text_key(self,Qt.Key.Key_Home); text_key(self,Qt.Key.Key_Right); input_text(self,'Z')
                elif name.startswith('root_after_'):
                    formula_click(canvas, ())
                    text_key(self,Qt.Key.Key_End); input_text(self,'+')
                elif name == 'finish':
                    panel.text_action_buttons['text_done'].click()
                else:
                    slot = name.rsplit('_',1)[1]
                    assert slot in ('num','den','base','exp','sub','lo','hi','arg')
                    path = tuple(trace['formula_prefix'])+(slot,)
                    if tuple(canvas.editing_slot or ()) != path:
                        formula_click(canvas,path)
                    input_text(self,'xy' if name == 'frac_den' else 'x')
            else:
                raise AssertionError('unexpected C07 chapter: '+chapter)
        elif chapter.startswith('c06.'):''')


def test_seven_courses_256_steps_share_one_process_and_restore_once(parent_coordinator, tmp_path, monkeypatch):
    panel, coordinator = parent_coordinator
    stderr = tmp_path/'text-child.stderr'
    original_stderr = QProcess.setStandardErrorFile
    monkeypatch.setattr(QProcess,'setStandardErrorFile',lambda process,_:original_stderr(process,str(stderr)))
    coordinator.session.command_factory = lambda request:(sys.executable,['-B','-c',BRIDGE,str(ROOT),str(ROOT),
        *practice_arguments(request.paths,request.channel,request.course_id,request.chapter_id)])
    coordinator.session.suspend = Mock(wraps=coordinator.session.suspend)
    coordinator.session.restore = Mock(wraps=coordinator.session.restore)
    original = panel.canvas.document_signature()
    assert coordinator.start('c01','c01.interface')
    process = coordinator.session.process
    until(lambda:coordinator.session.phase == 'running')
    token = coordinator.session._token
    root = coordinator.session.paths.runtime_root
    def diagnostic():
        return (coordinator.session.phase, coordinator.session.last_error,
                {id:coordinator.state_store.chapter_status(id) for id in CHAPTERS},
                stderr.read_text(encoding='utf-8',errors='replace')[-5000:] if stderr.exists() else '')
    until(lambda:all(coordinator.state_store.chapter_status(id)=='completed' for id in CHAPTERS),
          timeout=110000,diagnostic=diagnostic)
    proof = json.loads((coordinator.session.paths.data_dir/'formal-core-proof.json').read_text(encoding='utf-8'))
    assert proof['completed'] == list(CHAPTERS) and proof['all_complete']
    assert len(proof['steps']) == 256 and proof['hold_elapsed'] >= 0.65 and proof['text_keys'] > 0
    assert len(set(proof['pids'])) == 1 and proof['pids'][0] == process.processId()
    assert coordinator.session._token is token and coordinator.session.process is process
    assert coordinator.session.suspend.call_count == 1 and coordinator.session.restore.call_count == 0
    assert panel.canvas.document_signature() == original and panel._teaching_suspended
    coordinator.session.request_stop('text course accepted')
    until(lambda:coordinator.session.phase == 'stopped',diagnostic=diagnostic)
    assert coordinator.session.restore.call_count == 1 and not root.exists()
    assert panel.canvas.document_signature() == original and not panel._teaching_suspended
