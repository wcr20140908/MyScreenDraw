# SPDX-License-Identifier: GPL-3.0-or-later
"""Real C01 operations under owned private paths; no native input or screenshots."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF
from PyQt6.QtGui import QColor
import pytest

from teaching.engine import TutorialEngine
from teaching.events import TeachingEventBus
from teaching.models import (TutorialCatalog, TutorialChapter, TutorialCourse,
                             TutorialStep, WaitClause, WaitSpec)
from test_teaching_application import application_host, practice_request


def attach_wait(panel, event, *, equals=None, sequence=None):
    clauses = sequence or (WaitClause(event, 'success', equals or {}),)
    step = TutorialStep('operation', 'teaching_center_title', 'teaching_resume',
                        'operation', None, 'free', (), (), WaitSpec(tuple(clauses)), 'end_chapter')
    chapter = TutorialChapter('c01.adapters', 'teaching_center_title', 'blank', (step,))
    course = TutorialCourse('c01', 1, 1, 'teaching_center_title', (chapter,))
    engine = TutorialEngine(TutorialCatalog((course,)), session_id='business-adapter-test')
    panel.teaching_events = TeachingEventBus(engine)
    engine.start('c01', 'c01.adapters')
    return engine


def draw_ink(canvas):
    canvas._pointer_press(1, QPoint(50, 70), 1.0)
    canvas._pointer_move(1, QPoint(160, 70), 1.0)
    canvas._pointer_release(1, QPoint(200, 70))


def test_passthrough_then_drawing_requires_real_ordered_state_changes(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'mode.changed', sequence=(
        WaitClause('mode.changed', 'success', {'drawing_mode': False}),
        WaitClause('mode.changed', 'success', {'drawing_mode': True})))
    panel.set_drawing_mode(True)  # Already drawing: no terminal result.
    assert engine.sequence_index == 0
    panel.set_drawing_mode(False)
    assert not panel.canvas.is_drawing_mode and engine.sequence_index == 1
    panel.set_drawing_mode(False)
    assert engine.sequence_index == 1
    panel.set_drawing_mode(True)
    assert panel.canvas.is_drawing_mode and engine.phase == 'completed'


@pytest.mark.parametrize('initial_drawing,initial_tool', [(True, 'SELECT'), (False, 'PEN')])
def test_select_pen_reports_effective_tool_after_activation(application_host, initial_drawing, initial_tool):
    host, _ = application_host
    panel = host.panel
    panel.set_tool(initial_tool, panel.btn_select if initial_tool == 'SELECT' else panel.btn_pen)
    panel.set_drawing_mode(initial_drawing)
    engine = attach_wait(panel, 'tool.changed', equals={'tool': 'PEN', 'drawing_mode': True})
    panel.set_tool('PEN', panel.btn_pen)
    assert panel.canvas.draw_state == 'PEN' and panel.canvas.is_drawing_mode
    assert engine.phase == 'completed'


def test_reselecting_same_active_tool_is_not_completion(application_host):
    host, _ = application_host
    engine = attach_wait(host.panel, 'tool.changed', equals={'tool': 'PEN'})
    host.panel.set_tool('PEN', host.panel.btn_pen)
    assert engine.phase == 'running'


def test_palette_reports_applied_color_not_button_click(application_host):
    host, _ = application_host
    panel = host.panel
    button = next(value for value in panel.color_buttons
                  if value.property('color_val') and QColor(value.property('color_val')) != panel.canvas.pen_color)
    expected = QColor(button.property('color_val')).name()
    engine = attach_wait(panel, 'pen.color_changed', equals={'color': expected})
    button.click()
    assert panel.canvas.pen_color.name() == expected
    assert engine.phase == 'completed'


def test_same_palette_color_does_not_complete(application_host):
    host, _ = application_host
    panel = host.panel
    button = next(value for value in panel.color_buttons if value.property('color_val'))
    panel.canvas.pen_color = QColor(button.property('color_val'))
    engine = attach_wait(panel, 'pen.color_changed')
    button.click()
    assert engine.phase == 'running'


def test_width_reports_real_effective_change(application_host):
    host, _ = application_host
    engine = attach_wait(host.panel, 'pen.width_changed', equals={'width': 12})
    host.panel.pen_slider.setValue(12)
    assert host.panel.canvas.pen_width == 12
    assert engine.phase == 'completed'


def test_unchanged_width_callback_does_not_complete(application_host):
    host, _ = application_host
    engine = attach_wait(host.panel, 'pen.width_changed')
    host.panel.on_pen_slider_changed(host.panel.canvas.pen_width)
    assert engine.phase == 'running'


def test_custom_color_reports_accepted_actual_value(application_host, monkeypatch):
    host, _ = application_host
    monkeypatch.setattr(host.module.QColorDialog, 'exec', lambda self: 1)
    monkeypatch.setattr(host.module.QColorDialog, 'selectedColor', lambda self: QColor('#123456'))
    engine = attach_wait(host.panel, 'pen.color_changed', equals={'color': '#123456'})
    host.panel.open_custom_color()
    assert host.panel.canvas.pen_color.name() == '#123456'
    assert engine.phase == 'completed'


@pytest.mark.parametrize('result', ['cancelled', 'unchanged', 'stale'])
def test_custom_color_cannot_credit_cancel_noop_or_new_step(application_host, monkeypatch, result):
    host, _ = application_host
    panel = host.panel
    before = QColor(panel.canvas.pen_color)
    engine = attach_wait(panel, 'pen.color_changed')
    def dialog_result(dialog):
        if result == 'stale':
            engine.pause(); engine.resume()
        return 0 if result == 'cancelled' else 1
    monkeypatch.setattr(host.module.QColorDialog, 'exec', dialog_result)
    monkeypatch.setattr(host.module.QColorDialog, 'selectedColor',
                        lambda self: before if result == 'unchanged' else QColor('#123456'))
    panel.open_custom_color()
    assert engine.phase == 'running'
    if result in ('cancelled', 'unchanged'):
        assert panel.canvas.pen_color == before


@pytest.mark.parametrize('action,event', [('undo', 'history.undone'), ('redo', 'history.redone')])
def test_history_only_credits_successfully_applied_change(application_host, action, event):
    host, _ = application_host
    canvas = host.panel.canvas
    draw_ink(canvas)
    if action == 'redo':
        assert canvas.undo()
    engine = attach_wait(host.panel, event, equals={'undo_depth': 0 if action == 'undo' else 1,
                                                 'redo_depth': 1 if action == 'undo' else 0})
    assert getattr(canvas, action)()
    assert bool(canvas.all_segments) == (action == 'redo')
    assert engine.phase == 'completed'


@pytest.mark.parametrize('action,event', [('undo', 'history.undone'), ('redo', 'history.redone')])
def test_empty_history_does_not_credit_success(application_host, action, event):
    host, _ = application_host
    engine = attach_wait(host.panel, event)
    assert not getattr(host.panel.canvas, action)()
    assert engine.phase == 'running'


@pytest.mark.parametrize('action,event', [('enter_whiteboard', 'whiteboard.entered'),
                                        ('exit_whiteboard', 'whiteboard.exited')])
def test_whiteboard_reports_completed_transition_only(application_host, action, event):
    host, _ = application_host
    canvas = host.panel.canvas
    if action == 'exit_whiteboard':
        canvas.enter_whiteboard()
    engine = attach_wait(host.panel, event, equals={'whiteboard_mode': action == 'enter_whiteboard', 'pages': 1})
    getattr(canvas, action)()
    assert canvas.whiteboard_mode == (action == 'enter_whiteboard')
    assert engine.phase == 'completed'
    engine = attach_wait(host.panel, event)
    getattr(canvas, action)()
    assert engine.phase == 'running'


def test_new_page_reports_after_owned_page_is_loaded(application_host):
    host, _ = application_host
    canvas = host.panel.canvas
    canvas.enter_whiteboard()
    engine = attach_wait(host.panel, 'page.created', equals={'page': 2, 'pages': 2})
    canvas.new_page()
    assert len(canvas.pages) == 2 and canvas.current_page == 1
    assert canvas._page_id == canvas.pages[1]['page_id']
    assert engine.phase == 'completed'


def test_page_limit_does_not_credit_creation(application_host, monkeypatch):
    host, _ = application_host
    canvas = host.panel.canvas
    canvas.enter_whiteboard()
    monkeypatch.setattr(host.module, 'MAX_PAGES', 1)
    engine = attach_wait(host.panel, 'page.created')
    assert canvas.new_page() is False
    assert len(canvas.pages) == 1 and engine.phase == 'running'


def test_page_switch_reports_real_direction_and_destination(application_host):
    host, _ = application_host
    canvas = host.panel.canvas
    canvas.new_page()
    engine = attach_wait(host.panel, 'page.changed', sequence=(
        WaitClause('page.changed', 'success', {'previous_page': 2, 'page': 1, 'pages': 2}),
        WaitClause('page.changed', 'success', {'previous_page': 1, 'page': 2, 'pages': 2})))
    canvas.switch_page(-1)
    assert canvas.current_page == 0 and engine.sequence_index == 1
    canvas.switch_page(-1)
    assert engine.sequence_index == 1
    canvas.switch_page(1)
    assert canvas.current_page == 1 and engine.phase == 'completed'


@pytest.mark.parametrize('offset', [0, -1, 1])
def test_unavailable_page_switch_never_completes(application_host, offset):
    host, _ = application_host
    canvas = host.panel.canvas
    canvas.enter_whiteboard()
    engine = attach_wait(host.panel, 'page.changed')
    canvas.switch_page(offset)
    assert canvas.current_page == 0 and engine.phase == 'running'


@pytest.mark.parametrize('operation,event', [('undo', 'history.undone'), ('new_page', 'page.created'),
                                           ('enter_whiteboard', 'whiteboard.entered'),
                                           ('color', 'pen.color_changed'), ('width', 'pen.width_changed'),
                                           ('mode', 'mode.changed'), ('tool', 'tool.changed')])
def test_suppressed_setup_does_not_masquerade_as_learning(application_host, operation, event):
    host, _ = application_host
    panel, canvas = host.panel, host.panel.canvas
    if operation == 'undo':
        draw_ink(canvas)
    engine = attach_wait(panel, event)
    with panel.teaching_events.suppress():
        if operation == 'color':
            next(value for value in panel.color_buttons if value.property('color_val')
                 and QColor(value.property('color_val')) != canvas.pen_color).click()
        elif operation == 'width':
            panel.pen_slider.setValue(12)
        elif operation == 'mode':
            panel.set_drawing_mode(False)
        elif operation == 'tool':
            panel.set_tool('SELECT', panel.btn_select)
        else:
            getattr(canvas, operation)()
    assert engine.phase == 'running'

# Qt events are delivered straight to owned offscreen widgets, never to the desktop.
def mouse(canvas, kind, point, *, button=None):
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    event_type = {'press': QEvent.Type.MouseButtonPress, 'move': QEvent.Type.MouseMove,
                  'release': QEvent.Type.MouseButtonRelease}[kind]
    active_button = button if button is not None else (
        Qt.MouseButton.NoButton if kind == 'move' else Qt.MouseButton.LeftButton)
    buttons = Qt.MouseButton.NoButton if kind == 'release' else Qt.MouseButton.LeftButton
    event = QMouseEvent(event_type, QPointF(*point), QPointF(*point),
                        active_button, buttons, Qt.KeyboardModifier.NoModifier)
    getattr(canvas, {'press': 'mousePressEvent', 'move': 'mouseMoveEvent',
                     'release': 'mouseReleaseEvent'}[kind])(event)


def prepare_edit(panel, operation):
    canvas = panel.canvas
    draw_ink(canvas)
    if operation == 'erase':
        panel.set_tool('ERASER', panel.btn_eraser)
        canvas.eraser_size = 50
    else:
        panel.set_tool('SELECT', panel.btn_select)
        if operation == 'transform':
            canvas.selected_ids = {canvas.all_segments[0]['id']}
    return canvas


def test_erasing_credits_only_after_changed_content_is_committed(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'erase')
    before, undo_depth = len(canvas.all_segments), len(canvas.undo_stack)
    engine = attach_wait(host.panel, 'ink.erased', equals={'eraser_type': 'CIRCLE'})
    mouse(canvas, 'press', (130, 70))
    assert len(canvas.all_segments) < before and engine.phase == 'running'
    mouse(canvas, 'release', (130, 70))
    assert len(canvas.undo_stack) == undo_depth + 1 and engine.phase == 'completed'
    assert canvas.undo() and len(canvas.all_segments) == before


def test_empty_erase_does_not_credit_completion(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'erase')
    before, undo_depth = len(canvas.all_segments), len(canvas.undo_stack)
    engine = attach_wait(host.panel, 'ink.erased')
    mouse(canvas, 'press', (400, 400)); mouse(canvas, 'release', (400, 400))
    assert len(canvas.all_segments) == before and len(canvas.undo_stack) == undo_depth
    assert engine.phase == 'running'


def test_click_selection_reports_actual_new_nonempty_selection_on_release(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'select')
    engine = attach_wait(host.panel, 'selection.changed', equals={'count': 1, 'method': 'click'})
    mouse(canvas, 'press', (130, 70))
    assert canvas.selected_ids and engine.phase == 'running'
    mouse(canvas, 'release', (130, 70))
    assert canvas.selected_ids == {canvas.all_segments[0]['id']}
    assert engine.phase == 'completed'


@pytest.mark.parametrize('same_selection', [False, True])
def test_empty_or_unchanged_selection_does_not_complete(application_host, same_selection):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'select')
    if same_selection:
        canvas.selected_ids = {canvas.all_segments[0]['id']}
    engine = attach_wait(host.panel, 'selection.changed')
    point = (130, 70) if same_selection else (400, 400)
    mouse(canvas, 'press', point); mouse(canvas, 'release', point)
    assert engine.phase == 'running'


def test_rectangle_selection_reports_committed_object_selection(application_host):
    host, _ = application_host
    canvas = host.panel.canvas
    canvas.shape_type = 'RECT'
    canvas.shape_items = [canvas.make_shape_item(QRectF(100, 150, 80, 80))]
    host.panel.set_tool('SELECT', host.panel.btn_select)
    engine = attach_wait(host.panel, 'selection.changed', equals={'count': 1, 'method': 'rectangle'})
    mouse(canvas, 'press', (40, 130)); mouse(canvas, 'move', (270, 300))
    assert engine.phase == 'running'
    mouse(canvas, 'release', (270, 300))
    assert canvas.selected_ids == {canvas.shape_items[0]['id']}
    assert engine.phase == 'completed'


def test_object_move_only_completes_after_undoable_transform_is_committed(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    from PyQt6.QtCore import QLineF
    before = QLineF(canvas.all_segments[0]['line'])
    undo_depth = len(canvas.undo_stack)
    engine = attach_wait(host.panel, 'selection.transformed', equals={'action': 'move', 'count': 1})
    mouse(canvas, 'press', (130, 70)); mouse(canvas, 'move', (170, 100))
    assert canvas.all_segments[0]['line'] != before and engine.phase == 'running'
    mouse(canvas, 'release', (170, 100))
    assert len(canvas.undo_stack) == undo_depth + 1 and engine.phase == 'completed'
    assert canvas.undo() and canvas.all_segments[0]['line'] == before


@pytest.mark.parametrize('move_back', [False, True])
def test_noop_object_transform_does_not_complete(application_host, move_back):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    engine = attach_wait(host.panel, 'selection.transformed')
    mouse(canvas, 'press', (130, 70))
    if move_back:
        mouse(canvas, 'move', (170, 100)); mouse(canvas, 'move', (130, 70))
    mouse(canvas, 'release', (130, 70))
    assert engine.phase == 'running'


def test_single_gesture_cannot_credit_selection_then_following_transform(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'select')
    engine = attach_wait(host.panel, 'selection.changed', sequence=(
        WaitClause('selection.changed', 'success', {'count': 1}),
        WaitClause('selection.transformed', 'success', {'action': 'move'})))
    mouse(canvas, 'press', (130, 70)); mouse(canvas, 'move', (170, 100))
    mouse(canvas, 'release', (170, 100))
    assert engine.sequence_index == 1 and engine.phase == 'running'
    mouse(canvas, 'release', (170, 100))  # Duplicate release isn't a new operation.
    assert engine.sequence_index == 1
    mouse(canvas, 'press', (170, 100)); mouse(canvas, 'move', (200, 140))
    mouse(canvas, 'release', (200, 140))
    assert engine.phase == 'completed'


@pytest.mark.parametrize('operation,event', [('erase', 'ink.erased'), ('select', 'selection.changed'),
                                           ('transform', 'selection.transformed')])
@pytest.mark.parametrize('boundary', ['epoch', 'tool_change', 'touch_cancel'])
def test_gesture_result_cannot_outlive_its_start_context(application_host, operation, event, boundary):
    host, _ = application_host
    canvas = prepare_edit(host.panel, operation)
    engine = attach_wait(host.panel, event)
    mouse(canvas, 'press', (130, 70))
    if operation == 'transform':
        mouse(canvas, 'move', (170, 100))
    if boundary == 'epoch':
        engine.pause(); engine.resume()
    elif boundary == 'tool_change':
        host.panel.set_tool('PEN', host.panel.btn_pen)
        host.panel.set_tool('ERASER' if operation == 'erase' else 'SELECT',
                            host.panel.btn_eraser if operation == 'erase' else host.panel.btn_select)
    else:
        from PyQt6.QtCore import QEvent
        canvas.event(QEvent(QEvent.Type.TouchCancel))
    mouse(canvas, 'release', (170, 100) if operation == 'transform' else (130, 70))
    assert engine.phase == 'running'


def test_other_mouse_button_release_does_not_end_active_left_gesture(application_host):
    from PyQt6.QtCore import Qt
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'erase')
    engine = attach_wait(host.panel, 'ink.erased')
    mouse(canvas, 'press', (130, 70))
    mouse(canvas, 'release', (130, 70), button=Qt.MouseButton.RightButton)
    assert engine.phase == 'running'
    mouse(canvas, 'release', (130, 70))
    assert engine.phase == 'completed'

@pytest.mark.parametrize('key,tool', [('pen', 'PEN'), ('eraser', 'ERASER'), ('select', 'SELECT')])
def test_actual_toolbar_reactivates_retained_tool_as_one_completed_action(application_host, key, tool):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel.set_tool(tool, {'PEN': panel.btn_pen, 'ERASER': panel.btn_eraser, 'SELECT': panel.btn_select}[tool])
    panel.set_drawing_mode(False)
    engine = attach_wait(panel, 'tool.changed', equals={'tool': tool, 'drawing_mode': True})
    panel.icon_buttons[key].click()
    assert panel.canvas.draw_state == tool and panel.canvas.is_drawing_mode
    assert engine.phase == 'completed'


@pytest.mark.parametrize('key,tool', [('pen', 'PEN'), ('eraser', 'ERASER'), ('select', 'SELECT')])
def test_toolbar_result_is_delivered_after_submenu_work_not_before(application_host, monkeypatch, key, tool):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel.set_tool('SELECT' if tool == 'PEN' else 'PEN', panel.btn_select if tool == 'PEN' else panel.btn_pen)
    engine = attach_wait(panel, 'tool.changed', equals={'tool': tool})
    transitions = []
    original = panel.show_only_sub
    def trace(target=None):
        original(target)
        transitions.append((engine.phase, target is panel.file_sub, panel.file_sub.isVisible(), panel.menu_panel.isVisible()))
    monkeypatch.setattr(panel, 'show_only_sub', trace)
    # A following teaching step reveals its own panel synchronously on result.
    engine._on_step = lambda step: panel.show_only_sub(panel.file_sub) if step is None else None
    panel.icon_buttons[key].click()
    assert engine.phase == 'completed'
    assert panel.file_sub.isVisible(), transitions


@pytest.mark.parametrize('key', ['pen', 'eraser', 'select'])
def test_toolbar_side_effects_do_not_credit_a_second_sequence_stage(application_host, key):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel.set_tool('PEN' if key != 'pen' else 'SELECT', panel.btn_pen if key != 'pen' else panel.btn_select)
    panel.set_drawing_mode(False)
    engine = attach_wait(panel, 'mode.changed', sequence=(
        WaitClause('mode.changed', 'success', {'drawing_mode': True}),
        WaitClause('tool.changed', 'success', {'tool': {'pen': 'PEN', 'eraser': 'ERASER', 'select': 'SELECT'}[key]})))
    panel.icon_buttons[key].click()
    assert engine.sequence_index == 1 and engine.phase == 'running'


@pytest.mark.parametrize('operation,event,hook', [
    ('undo', 'history.undone', '_revert_delta'), ('new_page', 'page.created', 'load_page'),
    ('switch_page', 'page.changed', 'load_page'), ('width', 'pen.width_changed', 'apply_selection_width'),
    ('color', 'pen.color_changed', 'update_button_highlight'), ('mode', 'mode.changed', 'sync_canvas_input_mode'),
    ('tool', 'tool.changed', 'set_active_tool')])
def test_reentrant_operation_completion_never_borrows_new_epoch(application_host, monkeypatch, operation, event, hook):
    host, _ = application_host
    panel, canvas = host.panel, host.panel.canvas
    if operation == 'undo':
        draw_ink(canvas)
    elif operation == 'switch_page':
        canvas.new_page()
    engine = attach_wait(panel, event)
    owner = canvas if hasattr(canvas, hook) else panel
    original = getattr(owner, hook)
    def change_epoch(*args, **kwargs):
        result = original(*args, **kwargs)
        engine.pause(); engine.resume()
        return result
    monkeypatch.setattr(owner, hook, change_epoch)
    if operation == 'width':
        panel.pen_slider.setValue(12)
    elif operation == 'color':
        next(value for value in panel.color_buttons if value.property('color_val')
             and QColor(value.property('color_val')) != canvas.pen_color).click()
    elif operation == 'mode':
        panel.set_drawing_mode(False)
    elif operation == 'tool':
        panel.set_tool('SELECT', panel.btn_select)
    elif operation == 'switch_page':
        canvas.switch_page(-1)
    else:
        getattr(canvas, operation)()
    assert engine.phase == 'running'


@pytest.mark.parametrize('operation,event', [('erase', 'ink.erased'), ('select', 'selection.changed'),
                                           ('transform', 'selection.transformed')])
def test_gesture_started_during_suppressed_setup_cannot_complete_later(application_host, operation, event):
    host, _ = application_host
    canvas = prepare_edit(host.panel, operation)
    engine = attach_wait(host.panel, event)
    with host.panel.teaching_events.suppress():
        mouse(canvas, 'press', (130, 70))
        if operation == 'transform':
            mouse(canvas, 'move', (170, 100))
    mouse(canvas, 'release', (170, 100) if operation == 'transform' else (130, 70))
    assert engine.phase == 'running'


@pytest.mark.parametrize('event,target', [
    ('mode.changed', 'toolbar.mode'), ('tool.changed', 'toolbar.pen'),
    ('pen.color_changed', 'pen.palette'), ('pen.width_changed', 'pen.width'),
    ('history.undone', 'toolbar.undo'), ('history.redone', 'toolbar.redo'),
    ('whiteboard.entered', 'toolbar.whiteboard'), ('whiteboard.exited', 'toolbar.whiteboard'),
    ('page.created', 'pages.add'), ('page.changed', 'pages.previous'),
    ('ink.erased', 'canvas.ink'), ('selection.changed', 'canvas.ink'),
    ('selection.transformed', 'canvas.ink')])
def test_application_catalog_accepts_only_newly_adapted_business_contracts(practice_request, event, target):
    import json
    import main
    from teaching.application import application_catalog
    path = practice_request.paths.resource_dir / 'assets' / 'tutorials' / 'course.json'
    course = json.loads(path.read_text(encoding='utf-8'))
    first = course['chapters'][0]['steps'][0]
    first['target'] = target
    first['wait'] = {'event': event, 'outcome': 'success'}
    path.write_text(json.dumps(course), encoding='utf-8')
    catalog, _ = application_catalog(main, practice_request.paths.resource_dir)
    assert catalog.chapter_by_id('c01.foundation').steps[0].wait.clauses[0].event == event


@pytest.mark.parametrize('target,key', [
    ('toolbar.mode', 'mode'), ('toolbar.pen', 'pen'), ('toolbar.eraser', 'eraser'),
    ('toolbar.select', 'select'), ('toolbar.undo', 'undo'), ('toolbar.redo', 'redo'),
    ('toolbar.whiteboard', 'whiteboard'), ('toolbar.file', 'folder'), ('toolbar.tools', 'tools')])
def test_semantic_toolbar_targets_resolve_actual_visible_icon_controls(application_host, target, key):
    host, _ = application_host
    host.context.activate(); host.activate()
    expected = host.panel.icon_buttons[key]
    assert expected.isVisible()
    assert host.registry.resolve(target) is expected
    host.panel.toolbar_window.hide()
    assert host.registry.resolve(target) is None


@pytest.mark.parametrize('target,field', [('pages.add', 'rail_new'), ('pages.previous', 'rail_prev'),
                                        ('pages.next', 'rail_next')])
def test_page_targets_follow_actual_whiteboard_rail_visibility(application_host, target, field):
    host, _ = application_host
    host.context.activate(); host.activate()
    expected = getattr(host.panel, field)
    assert expected.isVisible() and host.registry.resolve(target) is expected
    host.panel.canvas.exit_whiteboard(); host.panel.update_whiteboard_ui()
    assert host.registry.resolve(target) is None


@pytest.mark.parametrize('target', ['pen.palette', 'pen.width'])
def test_pen_target_reveal_only_opens_precise_control_without_changing_business_state(application_host, target):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel.set_tool('SELECT', panel.btn_select)
    before = (panel.canvas.draw_state, QColor(panel.canvas.pen_color), panel.canvas.pen_width)
    assert host.registry.resolve(target) is None
    assert host.registry.reveal(target)
    resolved = host.registry.resolve(target)
    assert resolved is not None and resolved is not panel.draw_sub
    if target == 'pen.palette':
        assert all(resolved.isAncestorOf(value) for value in panel.color_buttons)
        assert not resolved.isAncestorOf(panel.pen_slider)
    else:
        assert resolved.isAncestorOf(panel.pen_slider)
        assert not any(resolved.isAncestorOf(value) for value in panel.color_buttons)
    assert (panel.canvas.draw_state, panel.canvas.pen_color, panel.canvas.pen_width) == before
    assert host.presenter.engine.current_step_id == 'ink'
    panel.show_only_sub(None)
    assert host.registry.resolve(target) is None


def test_trusted_pen_reveal_hook_is_available_without_synthetic_learning(application_host):
    host, _ = application_host
    host.context.activate(); host.activate()
    action = host.presenter._reveal_actions.get('open_pen_panel')
    assert callable(action)
    action()
    assert host.panel.draw_sub.isVisible()
    assert host.registry.resolve('pen.palette') is not None
    assert host.registry.resolve('pen.width') is not None
    assert host.presenter.engine.current_step_id == 'ink'
