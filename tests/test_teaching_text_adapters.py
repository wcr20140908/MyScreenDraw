# SPDX-License-Identifier: GPL-3.0-or-later
"""C07 results come from owned offscreen editor actions, never native input."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QPushButton

from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, mouse


def prepare_text(host):
    if not host.context.ui_active:host.context.activate();host.activate()
    panel,canvas=host.panel,host.panel.canvas
    canvas.finish_active_ink()
    if canvas.editing_text_id is not None:canvas.end_text_edit()
    canvas.text_items=[];canvas.all_segments=[];canvas.shape_items=[]
    canvas.selected_ids.clear()
    panel.set_tool('TEXT',panel.btn_text)
    return panel,canvas


def box(canvas):
    mouse(canvas,'press',(300,240));mouse(canvas,'move',(560,380));mouse(canvas,'release',(560,380))
    return canvas.text_items[-1]


def type_char(panel,char):
    panel.text_input.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_unknown,
                                            Qt.KeyboardModifier.NoModifier,char))


def action_button(panel,key):
    return next(btn for btn in panel.text_panel.findChildren(QPushButton)
                if btn.text()==__import__('i18n').tr(key))


def test_text_box_creation_waits_for_release_and_has_a_real_editor(application_host):
    host,_=application_host
    panel,canvas=prepare_text(host)
    engine=attach_wait(panel,'text.box_created',equals={'count':1})
    mouse(canvas,'press',(300,240));mouse(canvas,'move',(560,380))
    assert engine.phase=='running' and not canvas.text_items
    mouse(canvas,'release',(560,380))
    assert len(canvas.text_items)==1 and canvas.editing_text_id==canvas.text_items[0]['id']
    assert panel.text_panel.isVisible() and engine.phase=='completed' and not engine._issued


def test_click_and_tiny_text_drag_never_count_as_a_created_box(application_host):
    host,_=application_host
    panel,canvas=prepare_text(host)
    engine=attach_wait(panel,'text.box_created')
    mouse(canvas,'press',(300,240));mouse(canvas,'release',(301,241))
    assert not canvas.text_items and engine.phase=='running' and not engine._issued


def test_real_qt_text_input_reports_change_without_input_content(application_host):
    host,_=application_host
    panel,canvas=prepare_text(host)
    item=box(canvas)
    engine=attach_wait(panel,'text.changed',equals={'action':'insert','characters':1})
    type_char(panel,'A')
    assert item['text']=='A' and engine.phase=='completed' and not engine._issued


def test_existing_text_enters_edit_then_done_closes_and_retains_content(application_host):
    host,_=application_host
    panel,canvas=prepare_text(host)
    item=box(canvas);type_char(panel,'A');canvas.end_text_edit()
    engine=attach_wait(panel,'text.edit_started')
    mouse(canvas,'press',(310,250));mouse(canvas,'release',(310,250))
    assert canvas.editing_text_id==item['id'] and panel.text_panel.isVisible() and engine.phase=='completed'
    engine=attach_wait(panel,'text.edit_finished',equals={'retained':True})
    panel._text_done()
    assert canvas.editing_text_id is None and not panel.text_panel.isVisible() and item in canvas.text_items
    assert engine.phase=='completed' and not engine._issued


def test_finishing_empty_text_removes_it_without_claiming_retained_edit(application_host):
    host,_=application_host
    panel,canvas=prepare_text(host)
    box(canvas)
    engine=attach_wait(panel,'text.edit_finished',equals={'retained':True})
    panel._text_done()
    assert not canvas.text_items and engine.phase=='running' and not engine._issued


def test_text_creation_release_tail_failure_does_not_complete(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_text(host)
    engine=attach_wait(panel,'text.box_created')
    mouse(canvas,'press',(300,240));mouse(canvas,'move',(560,380))
    with monkeypatch.context() as patch:
        patch.setattr(panel,'heartbeat_refresh',Mock(side_effect=RuntimeError('text release tail')))
        with pytest.raises(RuntimeError,match='text release tail'):mouse(canvas,'release',(560,380))
    assert canvas.text_items and engine.phase=='running' and not engine._issued


def press_key(panel, key):
    panel.text_input.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key,
                                            Qt.KeyboardModifier.NoModifier))


def symbol_button(panel, group, entry):
    if panel._open_symbol_group != group:
        panel._symbol_group_buttons[group].click()
    return next(panel.symbol_grid_layout.itemAt(index).widget()
                for index in range(panel.symbol_grid_layout.count())
                if panel.symbol_grid_layout.itemAt(index).widget().property('teaching_symbol') == entry)


def click_slot(canvas, path):
    import formula
    from PyQt6.QtCore import QPointF
    item = canvas.editing_text_item()
    layout = canvas.formula_box(item)
    local = canvas.text_local_rect(item)
    if not path:
        x, y = 2, 0
    else:
        _, x, y, width, height = next(row for row in formula.slot_rects(layout) if row[0] == path)
        x += width / 2
        y += height / 2
    point = canvas.text_transform(item).map(QPointF(
        local.left()+canvas.TEXT_PAD+x, local.top()+canvas.TEXT_PAD+layout.ascent+y)).toPoint()
    mouse(canvas, 'press', (point.x(), point.y()))
    mouse(canvas, 'release', (point.x(), point.y()))
    assert tuple(canvas.editing_slot or ()) == path


def test_text_event_contains_only_counts_and_action_metadata(application_host, monkeypatch):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    engine = attach_wait(panel, 'text.changed')
    received = []
    consume = engine.consume
    monkeypatch.setattr(engine, 'consume', lambda event: (received.append(event), consume(event))[1])
    type_char(panel, 'private-input-甲')
    assert engine.phase == 'completed' and item['text'] == 'private-input-甲'
    assert len(received) == 1 and 'private-input' not in repr(dict(received[0].details))
    assert received[0].details['symbol'] is None


def test_real_cursor_middle_insertion_backspace_and_newline(application_host):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    type_char(panel, 'AB')
    engine = attach_wait(panel, 'text.changed', equals={'action':'insert', 'at_end':False})
    press_key(panel, Qt.Key.Key_Home)
    press_key(panel, Qt.Key.Key_Right)
    type_char(panel, 'X')
    assert item['text'] == 'AXB' and engine.phase == 'completed'
    engine = attach_wait(panel, 'text.changed', equals={'action':'backspace', 'removed':1})
    panel._text_backspace()
    assert item['text'] == 'AB' and engine.phase == 'completed'
    engine = attach_wait(panel, 'text.changed', equals={'action':'newline'})
    panel._text_newline()
    assert item['text'] == 'A\nB' and engine.phase == 'completed'


def test_plain_ime_preedit_does_not_count_but_committed_content_does(application_host):
    from PyQt6.QtGui import QInputMethodEvent
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    engine = attach_wait(panel, 'text.changed', equals={'action':'insert', 'characters':1})
    panel.text_input.inputMethodEvent(QInputMethodEvent('ni', []))
    assert item['text'] == '' and engine.phase == 'running' and not engine._issued
    commit = QInputMethodEvent()
    commit.setCommitString('你')
    panel.text_input.inputMethodEvent(commit)
    assert item['text'] == '你' and engine.phase == 'completed' and not engine._issued


@pytest.mark.parametrize('kind', ['frac', 'sup', 'sub', 'sqrt', 'sum', 'int'])
def test_structure_buttons_count_one_real_structure_excluding_text_nodes(application_host, kind):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    type_char(panel, 'F = ')
    button = symbol_button(panel, 'structure', kind)
    engine = attach_wait(panel, 'formula.inserted', equals={
        'kind':kind, 'structures':1, 'depth':0, 'parent_kind':'plain'})
    button.click()
    assert item['formula'][1]['k'] == kind and engine.phase == 'completed' and not engine._issued


def test_nested_fraction_uses_square_root_slot_and_real_denominator_edit(application_host):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    symbol_button(panel, 'structure', 'sqrt').click()
    engine = attach_wait(panel, 'formula.inserted', equals={
        'kind':'frac', 'parent_kind':'sqrt', 'slot':'arg', 'depth':1, 'structures':2})
    symbol_button(panel, 'structure', 'frac').click()
    assert engine.phase == 'completed'
    type_char(panel, 'a')
    click_slot(canvas, (0, 'arg', 0, 'den'))
    type_char(panel, 'xy')
    engine = attach_wait(panel, 'text.changed', equals={
        'action':'insert', 'slot':'den', 'parent_kind':'frac', 'depth':2, 'at_end':False})
    press_key(panel, Qt.Key.Key_Home)
    press_key(panel, Qt.Key.Key_Right)
    type_char(panel, 'Z')
    assert item['formula'][0]['arg'][0]['den'][0]['v'] == 'xZy'
    assert engine.phase == 'completed' and not engine._issued


def test_literal_typing_cannot_impersonate_a_symbol_button(application_host):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    box(canvas)
    alpha = symbol_button(panel, 'greek', 'α')
    engine = attach_wait(panel, 'text.changed', equals={'symbol':'α'})
    type_char(panel, 'α')
    assert engine.phase == 'running'
    panel._symbol_pressed('β')
    assert engine.phase == 'running'
    alpha.click()
    assert engine.phase == 'completed' and panel._teaching_symbol_entry is None


def test_formula_slot_click_is_not_completed_at_press(application_host):
    import formula
    from PyQt6.QtCore import QPointF
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    symbol_button(panel, 'structure', 'frac').click()
    engine = attach_wait(panel, 'formula.slot_changed', equals={'slot':'den', 'depth':1})
    layout = canvas.formula_box(item)
    _, x, y, w, h = next(row for row in formula.slot_rects(layout) if row[0] == (0, 'den'))
    local = canvas.text_local_rect(item)
    point = canvas.text_transform(item).map(QPointF(local.left()+canvas.TEXT_PAD+x+w/2,
        local.top()+canvas.TEXT_PAD+layout.ascent+y+h/2)).toPoint()
    mouse(canvas, 'press', (point.x(), point.y()))
    assert engine.phase == 'running' and canvas.editing_slot == (0, 'den')
    mouse(canvas, 'release', (point.x(), point.y()))
    assert engine.phase == 'completed' and not engine._issued


def test_formula_preedit_and_unsupported_newline_never_count(application_host):
    from PyQt6.QtGui import QInputMethodEvent
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    symbol_button(panel, 'structure', 'frac').click()
    engine = attach_wait(panel, 'text.changed')
    panel.text_input.inputMethodEvent(QInputMethodEvent('ni', []))
    panel._text_newline()
    press_key(panel, Qt.Key.Key_Return)
    assert engine.phase == 'running' and item['formula'][0]['num'] == [] and not engine._issued
    commit = QInputMethodEvent(); commit.setCommitString('你')
    panel.text_input.inputMethodEvent(commit)
    assert item['formula'][0]['num'][0]['v'] == '你' and engine.phase == 'completed'


def test_empty_formula_slots_cannot_claim_a_complete_finished_formula(application_host):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    box(canvas)
    symbol_button(panel, 'structure', 'frac').click()
    type_char(panel, 'a')
    engine = attach_wait(panel, 'text.edit_finished', equals={'retained':True, 'complete':True})
    panel._text_done()
    assert engine.phase == 'running' and canvas.editing_text_id is None and len(canvas.text_items) == 1
    assert not engine._issued


@pytest.mark.parametrize('action', ['symbol', 'backspace', 'newline'])
def test_outer_text_panel_tail_failure_never_publishes_queued_change(application_host, monkeypatch, action):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas); type_char(panel, 'AB')
    engine = attach_wait(panel, 'text.changed')
    with monkeypatch.context() as patch:
        patch.setattr(panel, '_refocus_input', Mock(side_effect=RuntimeError('panel tail')))
        with pytest.raises(RuntimeError, match='panel tail'):
            {'symbol':lambda:panel._symbol_pressed('α'), 'backspace':panel._text_backspace,
             'newline':panel._text_newline}[action]()
    assert item['text'] != 'AB' and engine.phase == 'running' and not engine._issued
    assert panel._teaching_document_batch is None


def test_formula_input_tail_failure_never_publishes_queued_change(application_host, monkeypatch):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas); symbol_button(panel, 'structure', 'frac').click()
    engine = attach_wait(panel, 'text.changed')
    with monkeypatch.context() as patch:
        patch.setattr(panel.text_input, 'sync_from_canvas', Mock(side_effect=RuntimeError('input tail')))
        with pytest.raises(RuntimeError, match='input tail'):type_char(panel, 'a')
    assert item['formula'][0]['num'][0]['v'] == 'a'
    assert engine.phase == 'running' and not engine._issued and panel._teaching_document_batch is None


def test_finish_close_failure_never_claims_retained_editor(application_host, monkeypatch):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    box(canvas); type_char(panel, 'AB')
    engine = attach_wait(panel, 'text.edit_finished', equals={'retained':True})
    with monkeypatch.context() as patch:
        patch.setattr(panel, 'close_text_input', Mock(side_effect=RuntimeError('close tail')))
        with pytest.raises(RuntimeError, match='close tail'):panel._text_done()
    assert engine.phase == 'running' and not engine._issued


def test_text_input_old_epoch_cannot_complete_after_pause_resume(application_host, monkeypatch):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    engine = attach_wait(panel, 'text.changed')
    after = canvas._after_text_change
    def interrupt(item):
        engine.pause(); engine.resume(); after(item)
    with monkeypatch.context() as patch:
        patch.setattr(canvas, '_after_text_change', interrupt)
        type_char(panel, 'AB')
    assert item['text'] == 'AB' and engine.phase == 'running' and not engine._issued


def test_reedit_press_old_epoch_cannot_complete_later_release(application_host):
    host, _ = application_host
    panel, canvas = prepare_text(host)
    box(canvas); type_char(panel, 'AB'); panel._text_done()
    engine = attach_wait(panel, 'text.edit_started')
    mouse(canvas, 'press', (310,250)); engine.pause(); engine.resume()
    mouse(canvas, 'release', (310,250))
    assert canvas.editing_text_id is not None and engine.phase == 'running' and not engine._issued


def test_plain_input_without_teaching_never_takes_a_teaching_snapshot(application_host, monkeypatch):
    import teaching.text_actions as actions
    host, _ = application_host
    panel, canvas = prepare_text(host)
    item = box(canvas)
    panel.teaching_events = None
    monkeypatch.setattr(actions, 'text_snapshot', Mock(side_effect=AssertionError('unexpected teaching snapshot')))
    type_char(panel, 'AB')
    panel._text_backspace(); panel._text_newline()
    assert item['text'] == 'A\n'
