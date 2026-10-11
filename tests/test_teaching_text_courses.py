# SPDX-License-Identifier: GPL-3.0-or-later
"""Formal C07 text, formatting, and formula courses through private Qt actions."""
from string import Formatter

import pytest
from PyQt6.QtCore import QPoint, QPointF, QEvent, Qt
from PyQt6.QtGui import QColor, QInputMethodEvent, QKeyEvent
from PyQt6.QtWidgets import QApplication

from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step as _assert_step, finished


def assert_step(host, name):
    _assert_step(host, name)


def type_text(panel, text):
    for char in text:
        QApplication.sendEvent(panel.text_input, QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier, char))


def press_key(panel, key):
    QApplication.sendEvent(panel.text_input, QKeyEvent(
        QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def action_button(panel, key):
    return panel.text_action_buttons['text_' + key]


def symbol_button(panel, entry):
    return next(panel.symbol_grid_layout.itemAt(index).widget()
                for index in range(panel.symbol_grid_layout.count())
                if panel.symbol_grid_layout.itemAt(index).widget().property('teaching_symbol') == entry)


def click_text(panel, item, x=None, y=None):
    x = item['pos'].x() + 8 if x is None else x
    y = item['pos'].y() + 20 if y is None else y
    mouse(panel.canvas, 'press', (int(x), int(y)))
    mouse(panel.canvas, 'release', (int(x), int(y)))


def click_root(canvas):
    item = canvas.editing_text_item()
    box = canvas.formula_box(item)
    rect = canvas.text_local_rect(item)
    point = canvas.text_transform(item).map(QPointF(
        rect.left() + canvas.TEXT_PAD + 2,
        rect.top() + canvas.TEXT_PAD + box.ascent / 2)).toPoint()
    mouse(canvas, 'press', (point.x(), point.y()))
    mouse(canvas, 'release', (point.x(), point.y()))


def click_formula_slot(canvas, path):
    import formula
    item = canvas.editing_text_item()
    box = canvas.formula_box(item)
    row = next(row for row in formula.slot_rects(box) if row[0] == path)
    _, x, y, width, height = row
    rect = canvas.text_local_rect(item)
    point = canvas.text_transform(item).map(QPointF(
        rect.left() + canvas.TEXT_PAD + x + width / 2,
        rect.top() + canvas.TEXT_PAD + box.ascent + y + height / 2)).toPoint()
    mouse(canvas, 'press', (point.x(), point.y()))
    mouse(canvas, 'release', (point.x(), point.y()))


def open_group(panel, key):
    if panel._open_symbol_group != key:
        panel._toggle_symbol_group(key)


def fixture_text_item(canvas, text):
    return next(item for item in canvas.text_items if item.get('text') == text)


def test_c07_catalog_and_copy_are_complete():
    import i18n
    import main
    from teaching.application import application_catalog
    from teaching.text_copy import TEXT_COPY
    catalog, _ = application_catalog(main, ROOT)
    course = catalog.course_by_id('c07')
    assert [chapter.id for chapter in course.chapters] == ['c07.edit', 'c07.format', 'c07.formula']
    assert [len(chapter.steps) for chapter in course.chapters] == [12, 12, 40]
    assert len(TEXT_COPY) == 132 and sum(len(values) for values in TEXT_COPY.values()) == 1056
    for key, values in TEXT_COPY.items():
        assert len(values) == 8
        for language, value in zip(i18n._LANGS, values):
            assert i18n.TEXT[language][key] == value and value.strip()
            assert not any(field is not None for _, field, _, _ in Formatter().parse(value))


@pytest.mark.parametrize('writing_host', ['c07.edit'], indirect=True)
def test_c07_edit_course_uses_real_text_entry_and_same_original(writing_host):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    assert_step(host, 'choose_text')
    panel.btn_text.click()
    assert_step(host, 'create_box')
    mouse(canvas, 'press', (300, 240)); mouse(canvas, 'move', (560, 380)); mouse(canvas, 'release', (560, 380))
    assert canvas.editing_text_id is not None
    assert_step(host, 'type_text')
    type_text(panel, 'AB')
    assert_step(host, 'insert_middle')
    item = canvas.editing_text_item()
    rect = canvas.text_local_rect(item)
    metrics = canvas.text_metrics(canvas.text_font(item))
    point = canvas.text_transform(item).map(QPointF(
        rect.left()+canvas.TEXT_PAD+metrics.horizontalAdvance('A'),
        rect.top()+canvas.TEXT_PAD+metrics.lineSpacing()/2)).toPoint()
    mouse(canvas, 'press', (point.x(), point.y())); mouse(canvas, 'release', (point.x(), point.y()))
    assert canvas.caret_offset == 1
    type_text(panel, 'C')
    assert canvas.editing_text_item()['text'] == 'ACB'
    assert_step(host, 'backspace')
    action_button(panel, 'backspace').click()
    assert canvas.editing_text_item()['text'] == 'AB'
    assert_step(host, 'newline')
    action_button(panel, 'newline').click()
    assert canvas.editing_text_item()['text'] == 'A\nB'
    original_id = canvas.editing_text_id
    assert_step(host, 'finish')
    action_button(panel, 'done').click()
    assert canvas.editing_text_id is None and any(item['id'] == original_id for item in canvas.text_items)
    assert_step(host, 'reedit')
    item = next(item for item in canvas.text_items if item['id'] == original_id)
    click_text(panel, item)
    assert_step(host, 'reedit')
    type_text(panel, 'C')
    assert_step(host, 'finish_again')
    action_button(panel, 'done').click()
    assert canvas.editing_text_id is None and next(item for item in canvas.text_items if item['id'] == original_id)['text'].endswith('C')
    assert_step(host, 'keyboard_ime_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c07.format'], indirect=True)
def test_c07_format_course_changes_only_the_real_text_object(writing_host, monkeypatch):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    original = canvas.text_items[0]
    original_id = original['id']
    next_info(host)
    assert_step(host, 'choose_select'); panel.btn_select.click()
    assert_step(host, 'select_box'); click_text(panel, original)
    assert_step(host, 'size'); panel.select_width_slider.setValue(6)
    assert original['width'] == 6 and original['size'] == 36
    assert_step(host, 'color')

    class FakeColorDialog:
        ColorDialogOption = type('ColorDialogOption', (), {'DontUseNativeDialog': object()})
        def __init__(self, *args, **kwargs): self._color = QColor('#aa2255')
        def setWindowTitle(self, *args): pass
        def setOption(self, *args): pass
        def exec(self): return True
        def selectedColor(self): return self._color

    monkeypatch.setattr(host.module, 'QColorDialog', FakeColorDialog)
    panel.selection_color_button.click()
    assert original['color'].name() == '#aa2255'
    for action, destination in [('move', (430, 250)), ('scale', None), ('rotate', None)]:
        assert_step(host, action)
        if action == 'move':
            start = canvas.selection_bounds().center().toPoint()
            mouse(canvas, 'press', (start.x(), start.y())); mouse(canvas, 'move', destination); mouse(canvas, 'release', destination)
        else:
            start = canvas.selection_handles()[action].center().toPoint()
            delta = QPoint(60, 24) if action == 'scale' else QPoint(55, 35)
            end = start + delta
            mouse(canvas, 'press', (start.x(), start.y())); mouse(canvas, 'move', (end.x(), end.y())); mouse(canvas, 'release', (end.x(), end.y()))
    assert_step(host, 'copy'); panel.btn_dup.click()
    copies = [item for item in canvas.text_items if item['id'] != original_id]
    assert len(copies) == 1 and canvas.selected_ids == {copies[0]['id']}
    assert_step(host, 'delete_copy'); panel.btn_del.click()
    assert [item['id'] for item in canvas.text_items] == [original_id]
    assert_step(host, 'font_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
def test_c07_formula_course_fills_each_structure_and_preserves_symbols(writing_host):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    symbols = fixture_text_item(canvas, 'Symbols: ')
    formula_item = fixture_text_item(canvas, 'F = ')
    next_info(host)
    assert_step(host, 'choose_text'); panel.btn_text.click()
    assert_step(host, 'open_symbols'); click_text(panel, symbols)
    for step, group, entry in [('greek', 'greek', 'α'), ('operator', 'operator', '±'), ('relation', 'relation', '∈'), ('calculus', 'calculus', '∫')]:
        from test_teaching_application_isolation import drain
        from PyQt6.QtWidgets import QApplication
        drain(QApplication.instance())
        assert host.presenter.engine.phase == 'running', (
            step, host.presenter.engine.current_step_id, host.presenter.active_target_id,
            host.registry.resolve(host.presenter.active_target_id), panel._open_symbol_group)
        assert_step(host, step); symbol_button(panel, entry).click()
    assert 'α' in symbols['text'] and '±' in symbols['text'] and '∈' in symbols['text'] and '∫' in symbols['text']
    assert_step(host, 'open_formula'); click_text(panel, formula_item)
    assert_step(host, 'structure'); panel._symbol_group_buttons['structure'].click()
    for name, kind, slots in [('frac','frac',('num','den')), ('sup','sup',('base','exp')),
                              ('sub','sub',('base','sub')), ('sqrt','sqrt',()),
                              ('sum','sum',('lo','hi','arg')), ('integral','int',('lo','hi','arg'))]:
        assert_step(host, name); symbol_button(panel, kind).click()
        prefix = tuple(canvas.editing_slot[:-1])
        if kind == 'sqrt':
            assert_step(host, 'sqrt_frac'); symbol_button(panel, 'frac').click()
            prefix = tuple(canvas.editing_slot[:-1])
            assert_step(host, 'sqrt_num'); type_text(panel, '1')
            assert_step(host, 'sqrt_den'); click_formula_slot(canvas, prefix+('den',)); type_text(panel, '2')
        else:
            for index, slot in enumerate(slots):
                step_name = name+'_'+slot
                if name == 'sub' and slot == 'sub': step_name = 'sub_sub'
                assert_step(host, step_name)
                if index: click_formula_slot(canvas, prefix+(slot,))
                assert canvas.editing_slot == prefix+(slot,)
                type_text(panel, 'xy' if kind == 'frac' and slot == 'den' else 'x')
            if kind == 'frac':
                assert_step(host, 'frac_edit')
                press_key(panel, Qt.Key.Key_Home); press_key(panel, Qt.Key.Key_Right); type_text(panel, 'Z')
        if kind != 'int':
            assert_step(host, 'root_after_'+kind)
            click_root(canvas)
            assert canvas.editing_slot == () or canvas.editing_slot is None
            press_key(panel, Qt.Key.Key_End); type_text(panel, '+')
    assert_step(host, 'navigate_info'); next_info(host)
    assert_step(host, 'finish'); action_button(panel, 'done').click()
    assert canvas.editing_text_id is None and formula_item in canvas.text_items and symbols in canvas.text_items
    from teaching.text_actions import content_counts
    assert content_counts(formula_item)[1:] == (7, True)
    assert_step(host, 'limits_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
def test_new_symbol_grid_targets_are_available_before_the_next_event_loop(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host); panel.btn_text.click()
    click_text(panel, fixture_text_item(canvas, 'Symbols: '))
    assert host.presenter.engine.current_step_id == 'greek'
    assert host.presenter.engine.phase == 'running'
    assert host.registry.resolve('text.symbol.alpha') is not None
    from test_teaching_application_isolation import drain
    from PyQt6.QtWidgets import QApplication
    for entry in ('α', '±', '∈', '∫'):
        symbol_button(panel, entry).click()
        drain(QApplication.instance())
    click_text(panel, fixture_text_item(canvas, 'F = '))
    assert_step(host, 'structure'); panel._symbol_group_buttons['structure'].click()
    assert host.presenter.engine.current_step_id == 'frac'
    assert host.presenter.engine.phase == 'running'
    assert host.registry.resolve('text.structure.frac') is not None


@pytest.mark.parametrize('writing_host', ['c07.edit'], indirect=True)
def test_typing_at_the_start_does_not_satisfy_between_existing_characters(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host); panel.btn_text.click()
    mouse(canvas,'press',(300,240)); mouse(canvas,'move',(560,380)); mouse(canvas,'release',(560,380))
    type_text(panel,'AB'); assert_step(host,'insert_middle')
    press_key(panel,Qt.Key.Key_Home); type_text(panel,'C')
    assert canvas.editing_text_item()['text'] == 'CAB'
    assert host.presenter.engine.current_step_id == 'insert_middle'


@pytest.mark.parametrize('writing_host', ['c07.edit'], indirect=True)
def test_reedit_replacement_cannot_impersonate_preserving_append(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host); panel.btn_text.click()
    mouse(canvas,'press',(300,240)); mouse(canvas,'move',(560,380)); mouse(canvas,'release',(560,380))
    type_text(panel,'AB'); press_key(panel,Qt.Key.Key_Home); press_key(panel,Qt.Key.Key_Right); type_text(panel,'C')
    action_button(panel,'backspace').click(); action_button(panel,'newline').click(); action_button(panel,'done').click()
    assert_step(host,'reedit'); click_text(panel,canvas.text_items[0])
    from PyQt6.QtGui import QTextCursor
    cursor = panel.text_input.textCursor(); cursor.select(QTextCursor.SelectionType.Document)
    panel.text_input.setTextCursor(cursor)
    type_text(panel,'replacement')
    assert host.presenter.engine.current_step_id == 'reedit'


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
def test_root_return_requires_current_end_key_before_append(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host); panel.btn_text.click(); click_text(panel,fixture_text_item(canvas,'Symbols: '))
    for symbol in ('α','±','∈','∫'):symbol_button(panel,symbol).click()
    click_text(panel,fixture_text_item(canvas,'F = ')); panel._symbol_group_buttons['structure'].click()
    symbol_button(panel,'frac').click(); type_text(panel,'a')
    path = tuple(canvas.editing_slot[:-1])+('den',); click_formula_slot(canvas,path); type_text(panel,'xy')
    press_key(panel,Qt.Key.Key_Home); press_key(panel,Qt.Key.Key_Right); type_text(panel,'Z')
    assert_step(host,'root_after_frac'); click_root(canvas)
    from PyQt6.QtGui import QTextCursor
    cursor = panel.text_input.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
    panel.text_input.setTextCursor(cursor)
    type_text(panel,'+')
    assert host.presenter.engine.current_step_id == 'root_after_frac'


@pytest.mark.parametrize('writing_host', ['c07.edit'], indirect=True)
def test_replacing_an_existing_character_does_not_satisfy_middle_insertion(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host); panel.btn_text.click()
    mouse(canvas,'press',(300,240)); mouse(canvas,'move',(560,380)); mouse(canvas,'release',(560,380))
    type_text(panel,'AB'); assert_step(host,'insert_middle')
    from PyQt6.QtGui import QTextCursor
    cursor = panel.text_input.textCursor(); cursor.setPosition(0); cursor.setPosition(1,QTextCursor.MoveMode.KeepAnchor)
    panel.text_input.setTextCursor(cursor)
    QApplication.sendEvent(panel.text_input, QKeyEvent(
        QEvent.Type.KeyPress,Qt.Key.Key_unknown,Qt.KeyboardModifier.NoModifier,'CCC'))
    assert canvas.editing_text_item()['text'] == 'CCCB'
    assert host.presenter.engine.current_step_id == 'insert_middle'
