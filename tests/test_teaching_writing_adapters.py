# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded C02/C03 business contracts before formal course data is added."""
from __future__ import annotations

import pytest
from unittest.mock import Mock
from PyQt6.QtCore import QPoint

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink, mouse


def test_pen_style_change_reports_real_style_and_ink_reports_style(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'pen.style_changed', equals={'style': 'fountain'})
    panel.choose_pen_style('fountain')
    assert engine.phase == 'completed'
    engine = attach_wait(panel, 'ink.committed', equals={'tool': 'PEN', 'style': 'fountain'})
    draw_ink(panel.canvas)
    assert engine.phase == 'completed'


def test_marker_selection_reports_style_and_real_marker_stroke(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'pen.style_changed', equals={'style': 'marker'})
    panel.choose_marker_tool()
    assert engine.phase == 'completed'
    engine = attach_wait(panel, 'ink.committed', equals={'tool': 'MARKER'})
    draw_ink(panel.canvas)
    assert engine.phase == 'completed'


def test_eraser_type_and_size_only_report_effective_changes(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'eraser.type_changed', equals={'eraser_type': 'CIRCLE'})
    panel.canvas.eraser_type = 'STROKE'
    panel.set_eraser_type('CIRCLE')
    assert engine.phase == 'completed'
    engine = attach_wait(panel, 'eraser.size_changed', equals={'size': 60})
    panel.e_slider.setValue(60)
    assert engine.phase == 'completed'
    engine = attach_wait(panel, 'eraser.size_changed')
    panel.e_slider.setValue(60)
    assert engine.phase == 'running'


def test_clear_reports_only_when_content_was_removed_and_undo_restores(application_host):
    host, _ = application_host
    panel = host.panel
    draw_ink(panel.canvas)
    engine = attach_wait(panel, 'history.cleared')
    panel.clear()
    assert engine.phase == 'completed' and not panel.canvas.all_segments
    assert panel.canvas.undo()
    assert panel.canvas.all_segments
    panel.clear()
    engine = attach_wait(panel, 'history.cleared')
    panel.clear()
    assert engine.phase == 'running'


def test_c02_c03_targets_resolve_to_real_controls(application_host):
    host, _ = application_host
    panel = host.panel
    expected = {
        'pen.style.fountain': 'pen_style_buttons', 'pen.marker': 'btn_ann_marker',
        'pen.laser': 'btn_ann_laser', 'pen.marker.width': 'marker_width_slider',
        'pen.marker.alpha': 'marker_alpha_slider', 'pen.laser.width': 'laser_width_slider',
        'pen.defaults': 'pen_defaults_checkbox', 'pen.defaults.capture': 'capture_button',
        'eraser.type.circle': 'btn_circ', 'eraser.type.stroke': 'btn_stroke',
        'eraser.size': 'e_slider', 'toolbar.clear': 'btn_clear',
    }
    host.context.activate(); host.activate()
    for target, name in expected.items():
        host.registry.reveal(target)
        if target == 'pen.style.fountain':
            assert host.registry.resolve(target) is panel.pen_style_buttons['fountain']
        elif target == 'pen.defaults.capture':
            assert host.registry.resolve(target) is panel.pen_defaults_editor.capture_button
        elif target == 'toolbar.clear':
            assert host.registry.resolve(target) is panel.icon_buttons['clear']
        else:
            assert host.registry.resolve(target) is getattr(host.panel, name)




def test_laser_trace_requires_a_real_gesture_and_does_not_write_ink(application_host):
    host, _ = application_host
    panel = host.panel
    panel.choose_laser_tool()
    before = panel.canvas.document_signature()
    engine = attach_wait(panel, 'laser.trace')
    mouse(panel.canvas, 'press', (30, 30))
    mouse(panel.canvas, 'move', (100, 70))
    mouse(panel.canvas, 'release', (120, 80))
    assert engine.phase == 'completed'
    assert panel.canvas.document_signature() == before and panel.canvas.laser_trail


def test_laser_click_or_stale_gesture_cannot_complete(application_host):
    host, _ = application_host
    panel = host.panel
    panel.choose_laser_tool()
    engine = attach_wait(panel, 'laser.trace')
    mouse(panel.canvas, 'press', (30, 30))
    mouse(panel.canvas, 'release', (30, 30))
    assert engine.phase == 'running'
    mouse(panel.canvas, 'press', (30, 30))
    mouse(panel.canvas, 'move', (100, 70))
    engine.pause();engine.resume()
    mouse(panel.canvas, 'release', (120, 80))
    assert engine.phase == 'running' and not engine._issued


def test_private_preset_capture_enable_and_apply_have_actual_results(application_host):
    host, _ = application_host
    panel = host.panel
    panel.canvas.pen_width = 12
    panel.open_settings_panel()
    panel.pen_defaults_editor.set_current_key('pen')
    engine = attach_wait(panel, 'pen.default_saved', equals={'key': 'pen'})
    panel.pen_defaults_editor.capture_button.click()
    assert engine.phase == 'completed' and panel.pen_defaults['pen']['width'] == 12
    engine = attach_wait(panel, 'pen.defaults_changed', equals={'enabled': True})
    panel.pen_defaults_checkbox.click()
    assert engine.phase == 'completed'
    panel.choose_marker_tool()
    engine = attach_wait(panel, 'pen.default_applied', equals={'key': 'pen'})
    panel.choose_pen_style('pen')
    assert engine.phase == 'completed' and panel.canvas.pen_width == 12


@pytest.mark.parametrize('style',['pen','fountain','brush','calligraphy','pencil','crayon','chalk','neon','dashed','rainbow','arrow'])
def test_each_pen_style_changes_and_commits_its_own_style(application_host,style):
    host,_=application_host;panel=host.panel
    panel.canvas.pen_style='fountain' if style=='pen' else 'pen'
    engine=attach_wait(panel,'pen.style_changed',equals={'style':style})
    panel.choose_pen_style(style)
    assert engine.phase=='completed'
    engine=attach_wait(panel,'ink.committed',equals={'style':style,'tool':'PEN'})
    draw_ink(panel.canvas)
    assert engine.phase=='completed'


def test_style_same_value_and_callback_tail_failure_do_not_complete(application_host,monkeypatch):
    host,_=application_host;panel=host.panel;panel.choose_pen_style('pen')
    engine=attach_wait(panel,'pen.style_changed')
    panel.choose_pen_style('pen')
    assert engine.phase=='running' and not engine._issued
    monkeypatch.setattr(panel,'refresh_ui',Mock(side_effect=RuntimeError('tool tail')))
    with pytest.raises(RuntimeError,match='tool tail'):panel.choose_pen_style('fountain')
    assert engine.phase=='running' and not engine._issued


def test_failed_private_preset_write_is_not_saved(application_host,monkeypatch):
    host,_=application_host;panel=host.panel;panel.canvas.pen_width=12
    panel.open_settings_panel();panel.pen_defaults_editor.set_current_key('pen')
    monkeypatch.setattr(host.module,'atomic_write_json',Mock(side_effect=OSError('readonly')))
    engine=attach_wait(panel,'pen.default_saved')
    panel.pen_defaults_editor.capture_button.click()
    assert engine.phase=='running' and not engine._issued


def test_laser_stationary_moves_do_not_count_as_a_trace(application_host):
    host,_=application_host;panel=host.panel;panel.choose_laser_tool()
    engine=attach_wait(panel,'laser.trace')
    mouse(panel.canvas,'press',(30,30));mouse(panel.canvas,'move',(30,30));mouse(panel.canvas,'release',(30,30))
    assert engine.phase=='running' and not engine._issued


def test_clear_callback_tail_failure_does_not_count_as_completed(application_host,monkeypatch):
    host,_=application_host;panel=host.panel;draw_ink(panel.canvas)
    engine=attach_wait(panel,'history.cleared')
    with monkeypatch.context() as patch:
        patch.setattr(panel.select_panel,'hide',Mock(side_effect=RuntimeError('clear tail')))
        with pytest.raises(RuntimeError,match='clear tail'):panel.clear()
    assert engine.phase=='running' and not engine._issued



def test_laser_release_callback_failure_cannot_credit_a_new_step(application_host,monkeypatch):
    host,_=application_host;panel=host.panel;panel.choose_laser_tool()
    engine=attach_wait(panel,'laser.trace')
    mouse(panel.canvas,'press',(30,30));mouse(panel.canvas,'move',(100,70))
    with monkeypatch.context() as patch:
        patch.setattr(panel,'heartbeat_refresh',Mock(side_effect=RuntimeError('laser tail')))
        with pytest.raises(RuntimeError,match='laser tail'):mouse(panel.canvas,'release',(120,80))
    assert engine.phase=='running' and not engine._issued
