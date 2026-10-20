# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded adapter review: private tmp_path resources and offscreen Qt methods only."""
from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import QPoint

from teaching.application import application_catalog
from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink, mouse, prepare_edit


def _install_real_two_step_course(host, practice_request, tool):
    """Keep the actual presenter/bus and load only the fixture's private resources."""
    assert host.context.paths.practice and host.context.ui_active
    host.presenter.engine.stop()
    path = practice_request.paths.resource_dir / 'assets' / 'tutorials' / 'course.json'
    course = json.loads(path.read_text(encoding='utf-8'))
    course['chapters'][0]['steps'] = [
        {'id': 'choose', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
         'target': 'toolbar.pen', 'input_policy': 'free',
         'wait': {'event': 'tool.changed', 'outcome': 'success', 'equals': {'tool': tool}},
         'next': 'width'},
        {'id': 'width', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
         'target': 'pen.width', 'input_policy': 'target_only',
         'wait': {'event': 'pen.width_changed', 'outcome': 'success'},
         'next': 'end_chapter'},
    ]
    path.write_text(json.dumps(course), encoding='utf-8')
    catalog, _ = application_catalog(host.module, practice_request.paths.resource_dir)
    host.presenter.engine.catalog = catalog
    host.presenter.start(practice_request.course_id, practice_request.chapter_id)
    return host.presenter.engine


@pytest.mark.parametrize('method,tool', [
    ('choose_pen_tool', 'PEN'), ('choose_marker_tool', 'MARKER'),
    ('choose_laser_tool', 'LASER'), ('handle_text_click', 'TEXT'),
    ('handle_shape_click', 'SHAPE'),
])
def test_real_presenter_keeps_following_width_target_after_complete_tool_callback(
        application_host, practice_request, method, tool):
    host, _ = application_host
    host.context.activate(); host.activate()
    engine = _install_real_two_step_course(host, practice_request, tool)
    panel = host.panel
    with panel.teaching_events.suppress():
        panel.set_tool('SELECT', panel.btn_select)
    assert engine.current_step_id == 'choose' and engine.phase == 'running'
    getattr(panel, method)()
    assert panel.canvas.draw_state == tool
    assert engine.current_step_id == 'width' and engine.phase == 'running'
    assert panel.draw_sub.isVisible()
    assert host.registry.resolve('pen.width') is panel.pen_width_row
    assert host.presenter.active_target_id == 'pen.width'
    panel.pen_slider.setValue(12 if panel.canvas.pen_width != 12 else 13)
    assert engine.phase == 'completed'


def test_empty_contact_retirement_allows_third_contact_but_not_old_peer_next_stage(
        application_host, monkeypatch):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    canvas = host.panel.canvas
    engine = attach_wait(host.panel, 'ink.committed', sequence=(
        WaitClause('ink.committed', 'success'), WaitClause('ink.committed', 'success')))
    canvas._pointer_press(1, QPoint(60, 60), 1.0)
    canvas._pointer_press(2, QPoint(80, 100), 1.0)
    canvas._pointer_move(2, QPoint(130, 100), 1.0)
    peer = canvas._pointer_slots[2]['_teaching_stroke_operation']
    canvas._pointer_release(1, QPoint(60, 60))
    assert engine.sequence_index == 0 and len(engine._issued) == 1
    assert engine._issued.get(peer.operation_id) == peer
    canvas._pointer_press(3, QPoint(90, 150), 1.0)
    assert canvas._pointer_slots[3]['_teaching_stroke_operation'] is not None
    canvas._pointer_move(3, QPoint(140, 150), 1.0)
    canvas._pointer_release(3, QPoint(170, 150))
    assert engine.sequence_index == 1 and engine.phase == 'running'
    canvas._pointer_release(2, QPoint(170, 100))
    assert engine.sequence_index == 1 and engine.phase == 'running'
    draw_ink(canvas)
    assert engine.phase == 'completed'


def _raise_ui_failure(*args, **kwargs):
    raise RuntimeError('review synthetic synchronous UI failure')


def _assert_own_token_retired_without_losing_peer(bus, engine, event, abandoned, peer):
    assert engine.phase == 'running'
    assert engine._issued.get(peer.operation_id) == peer, 'Retirement invalidated the peer'
    replacement = bus.begin_operation(event)
    assert replacement is not None, (
        f'Failed {event} blocks a fresh authentic operation: pending={len(engine._issued)}; '
        f'own_token_retired={abandoned.operation_id not in engine._issued}')
    assert abandoned.operation_id not in engine._issued, 'Failed operation retained its own token'
    assert bus.discard_operation(replacement)
    assert bus.emit_result(peer, event, 'success', {})
    assert engine.phase == 'completed'


@pytest.mark.parametrize('action,event', [('undo', 'history.undone'), ('redo', 'history.redone')])
def test_history_early_ui_exception_retires_own_token_and_preserves_peer(
        application_host, monkeypatch, action, event):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    panel, canvas = host.panel, host.panel.canvas
    draw_ink(canvas)
    if action == 'redo':
        assert canvas.undo()
    engine = attach_wait(panel, event)
    bus = panel.teaching_events
    peer = bus.begin_operation(event)
    captured = []
    def broken_history_ui(*args, **kwargs):
        captured.append(next(context for context in engine._issued.values() if context != peer))
        _raise_ui_failure()
    with monkeypatch.context() as failure:
        failure.setattr(panel, 'update_history_ui', broken_history_ui)
        with pytest.raises(RuntimeError, match='review synthetic synchronous UI failure'):
            getattr(canvas, action)()
    assert len(captured) == 1
    _assert_own_token_retired_without_losing_peer(bus, engine, event, captured[0], peer)


@pytest.mark.parametrize('operation,event', [
    ('erase', 'ink.erased'), ('select', 'selection.changed'),
    ('transform', 'selection.transformed'),
])
def test_edit_release_early_ui_exception_retires_own_token_and_preserves_peer(
        application_host, monkeypatch, operation, event):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    panel = host.panel
    canvas = prepare_edit(panel, operation)
    engine = attach_wait(panel, event)
    bus = panel.teaching_events
    peer = bus.begin_operation(event)
    mouse(canvas, 'press', (130, 70))
    abandoned = canvas._teaching_edit[0]
    if operation == 'transform':
        mouse(canvas, 'move', (170, 100))
    with monkeypatch.context() as failure:
        failure.setattr(panel, 'position_selection_panel', _raise_ui_failure)
        with pytest.raises(RuntimeError, match='review synthetic synchronous UI failure'):
            mouse(canvas, 'release', (170, 100) if operation == 'transform' else (130, 70))
    assert canvas._teaching_edit is None
    _assert_own_token_retired_without_losing_peer(bus, engine, event, abandoned, peer)


def test_ink_commit_early_ui_exception_retires_own_token_and_preserves_peer(
        application_host, monkeypatch):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    panel, canvas = host.panel, host.panel.canvas
    engine = attach_wait(panel, 'ink.committed')
    bus = panel.teaching_events
    peer = bus.begin_operation('ink.committed')
    canvas._pointer_press(1, QPoint(60, 60), 1.0)
    abandoned = canvas._pointer_slots[1]['_teaching_stroke_operation']
    canvas._pointer_move(1, QPoint(130, 100), 1.0)
    with monkeypatch.context() as failure:
        failure.setattr(panel, 'update_history_ui', _raise_ui_failure)
        with pytest.raises(RuntimeError, match='review synthetic synchronous UI failure'):
            canvas._pointer_release(1, QPoint(170, 120))
    _assert_own_token_retired_without_losing_peer(bus, engine, 'ink.committed', abandoned, peer)



def test_history_without_current_history_context_does_not_compute_content_fingerprint(
        application_host, monkeypatch):
    host, _ = application_host
    canvas = host.panel.canvas
    draw_ink(canvas)
    engine = attach_wait(host.panel, 'ink.committed')
    def unexpected_fingerprint(*args, **kwargs):
        raise AssertionError('Non-teaching history performed the new teaching fingerprint')
    monkeypatch.setattr(host.module, 'page_signature', unexpected_fingerprint)
    assert canvas.undo()
    assert canvas.redo()
    assert canvas.all_segments and engine.phase == 'running'
