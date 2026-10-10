# SPDX-License-Identifier: GPL-3.0-or-later
"""Abandoned edits must not exhaust the bounded authentic-operation pool."""
from __future__ import annotations

from dataclasses import replace

import pytest
from PyQt6.QtCore import QEvent

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, mouse, prepare_edit


@pytest.mark.parametrize('operation,event', [('erase', 'ink.erased'), ('select', 'selection.changed'),
                                           ('transform', 'selection.transformed')])
def test_repeated_noop_gestures_leave_capacity_for_a_real_operation(application_host, monkeypatch, operation, event):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    canvas = prepare_edit(host.panel, operation)
    engine = attach_wait(host.panel, event)
    point = (130, 70) if operation == 'transform' else (400, 400)
    for _ in range(3):
        mouse(canvas, 'press', point); mouse(canvas, 'release', point)
        assert engine.phase == 'running'
    mouse(canvas, 'press', (130, 70))
    if operation == 'transform':
        mouse(canvas, 'move', (170, 100))
    mouse(canvas, 'release', (170, 100) if operation == 'transform' else (130, 70))
    assert engine.phase == 'completed'


@pytest.mark.parametrize('operation,event', [('erase', 'ink.erased'), ('select', 'selection.changed'),
                                           ('transform', 'selection.transformed')])
@pytest.mark.parametrize('boundary', ['tool_change', 'touch_cancel', 'load_page', 'new_press'])
def test_abandoned_gestures_release_only_their_authentic_operation(application_host, monkeypatch, operation, event, boundary):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    panel = host.panel
    canvas = prepare_edit(panel, operation)
    engine = attach_wait(panel, event)
    point = (130, 70) if operation == 'transform' else (400, 400)
    for _ in range(3):
        if operation == 'transform':
            canvas.selected_ids = {canvas.all_segments[0]['id']}
        mouse(canvas, 'press', point)
        if boundary == 'tool_change':
            panel.set_tool('PEN', panel.btn_pen)
            panel.set_tool('ERASER' if operation == 'erase' else 'SELECT',
                           panel.btn_eraser if operation == 'erase' else panel.btn_select)
        elif boundary == 'touch_cancel':
            canvas.event(QEvent(QEvent.Type.TouchCancel))
        elif boundary == 'load_page':
            canvas.load_page(canvas.capture_page())
        # A new accepted left press is itself another explicit boundary.
        assert engine.phase == 'running'
    if operation == 'transform':
        canvas.selected_ids = {canvas.all_segments[0]['id']}
    mouse(canvas, 'press', (130, 70))
    if operation == 'transform':
        mouse(canvas, 'move', (170, 100))
    mouse(canvas, 'release', (170, 100) if operation == 'transform' else (130, 70))
    assert engine.phase == 'completed'


def test_discard_does_not_dispatch_or_invalidate_another_real_operation(application_host, monkeypatch):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    engine = attach_wait(host.panel, 'ink.committed', sequence=(
        WaitClause('ink.committed', 'success'), WaitClause('ink.committed', 'success')))
    bus = host.panel.teaching_events
    abandoned = bus.begin_operation('ink.committed')
    surviving = bus.begin_operation('ink.committed')
    discard = getattr(bus, 'discard_operation', None)
    assert callable(discard), 'No trusted operation-retirement path exists'
    assert discard(abandoned)
    assert engine.sequence_index == 0
    assert not bus.emit_result(abandoned, 'ink.committed', 'success', {'segments': 1})
    assert bus.emit_result(surviving, 'ink.committed', 'success', {'segments': 1})
    assert engine.sequence_index == 1
    fresh = bus.begin_operation('ink.committed')
    assert fresh is not None
    assert bus.emit_result(fresh, 'ink.committed', 'success', {'segments': 1})
    assert engine.phase == 'completed'


def test_discard_rejects_forged_context_and_still_allows_real_completion(application_host):
    host, _ = application_host
    engine = attach_wait(host.panel, 'ink.committed')
    bus = host.panel.teaching_events
    context = bus.begin_operation('ink.committed')
    discard = getattr(bus, 'discard_operation', None)
    assert callable(discard), 'No trusted operation-retirement path exists'
    assert not discard(None)
    assert not discard(replace(context, step_epoch=context.step_epoch + 1))
    assert bus.emit_result(context, 'ink.committed', 'success', {'segments': 1})
    assert engine.phase == 'completed'


def test_empty_pen_taps_do_not_exhaust_authentic_stroke_capacity(application_host, monkeypatch):
    import teaching.engine
    from PyQt6.QtCore import QPoint
    from test_teaching_business_adapters import draw_ink
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    canvas = host.panel.canvas
    engine = attach_wait(host.panel, 'ink.committed')
    for _ in range(3):
        canvas._pointer_press(1, QPoint(60, 60), 1.0)
        canvas._pointer_release(1, QPoint(60, 60))
        assert not canvas.all_segments and engine.phase == 'running'
    draw_ink(canvas)
    assert canvas.all_segments and engine.phase == 'completed'


def test_retiring_empty_contact_does_not_invalidate_another_active_pen(application_host, monkeypatch):
    import teaching.engine
    from PyQt6.QtCore import QPoint
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    canvas = host.panel.canvas
    engine = attach_wait(host.panel, 'ink.committed')
    canvas._pointer_press(1, QPoint(60, 60), 1.0)
    canvas._pointer_press(2, QPoint(90, 90), 1.0)
    canvas._pointer_move(2, QPoint(170, 100), 1.0)
    canvas._pointer_release(1, QPoint(60, 60))
    assert engine.phase == 'running'
    canvas._pointer_release(2, QPoint(190, 110))
    assert engine.phase == 'completed'


def test_failed_toolbar_callback_releases_context_without_claiming_success(application_host, monkeypatch):
    import teaching.engine
    monkeypatch.setattr(teaching.engine, 'MAX_PENDING_OPERATIONS', 2)
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'tool.changed', equals={'tool': 'ERASER'})
    original = panel.refresh_ui
    def broken_refresh():
        raise RuntimeError('synthetic UI failure')
    monkeypatch.setattr(panel, 'refresh_ui', broken_refresh)
    for _ in range(3):
        with panel.teaching_events.suppress():
            panel.set_tool('PEN', panel.btn_pen)
        with pytest.raises(RuntimeError, match='synthetic UI failure'):
            panel.handle_eraser_click()
        assert engine.phase == 'running'
    with panel.teaching_events.suppress():
        panel.set_tool('PEN', panel.btn_pen)
    monkeypatch.setattr(panel, 'refresh_ui', original)
    panel.handle_eraser_click()
    assert engine.phase == 'completed'
