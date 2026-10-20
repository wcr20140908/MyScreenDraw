# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent-call-chain review reproductions, using only private offscreen Qt."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink, mouse


@pytest.mark.parametrize('action,event', [('undo', 'history.undone'), ('redo', 'history.redone')])
def test_same_color_history_roundtrip_does_not_claim_real_content_change(application_host, action, event):
    host, _ = application_host
    panel, canvas = host.panel, host.panel.canvas
    draw_ink(canvas)
    canvas.selected_ids = {canvas.all_segments[0]['id']}
    same_color = next(button for button in panel.color_buttons if button.property('color_val')
                      and QColor(button.property('color_val')) == canvas.pen_color)
    before = host.module.page_signature(canvas.live_page())
    same_color.click()  # Existing business path may retain a redundant history entry.
    assert len(canvas.undo_stack) == 2
    assert host.module.page_signature(canvas.live_page()) == before
    if action == 'redo':
        assert canvas.undo()
    engine = attach_wait(panel, event)
    assert getattr(canvas, action)()  # Preserve the existing history/UI return contract.
    assert host.module.page_signature(canvas.live_page()) == before
    assert engine.phase == 'running'


@pytest.mark.parametrize('input_path', ['mouse', 'touch_entry'])
def test_automatic_page_pen_return_is_not_a_second_user_tutorial_operation(application_host, input_path):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel, canvas = host.panel, host.panel.canvas
    panel.whiteboard_auto_pen = True
    panel.set_tool('ERASER', panel.btn_eraser)
    canvas.new_page()
    assert canvas._page_return_pending
    engine = attach_wait(panel, 'tool.changed', sequence=(
        WaitClause('tool.changed', 'success', {'tool': 'PEN'}),
        WaitClause('ink.committed', 'success')))
    if input_path == 'mouse':
        mouse(canvas, 'press', (80, 90)); mouse(canvas, 'move', (160, 110))
        mouse(canvas, 'release', (200, 120))
    else:
        # _dispatch_touch invokes this same trusted business entry before contacts.
        canvas.consume_page_pen_return()
        canvas._pointer_press(1, QPoint(80, 90), 1.0)
        canvas._pointer_move(1, QPoint(160, 110), 1.0)
        canvas._pointer_release(1, QPoint(200, 120))
    assert canvas.draw_state == 'PEN' and canvas.all_segments
    assert not canvas._page_return_pending
    assert engine.sequence_index == 0 and engine.phase == 'running'


@pytest.mark.parametrize('method,tool', [
    ('choose_marker_tool', 'MARKER'), ('choose_laser_tool', 'LASER'),
    ('handle_text_click', 'TEXT'), ('handle_shape_click', 'SHAPE'), ('choose_pen_tool', 'PEN')])
def test_every_emitting_annotation_entry_finishes_its_menus_before_next_target(application_host, method, tool):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel.set_tool('SELECT', panel.btn_select)
    engine = attach_wait(panel, 'tool.changed', equals={'tool': tool})
    engine._on_step = lambda step: panel.show_only_sub(panel.draw_sub) if step is None else None
    getattr(panel, method)()
    assert panel.canvas.draw_state == tool and engine.phase == 'completed'
    assert panel.draw_sub.isVisible()
    assert host.registry.resolve('pen.palette') is not None
