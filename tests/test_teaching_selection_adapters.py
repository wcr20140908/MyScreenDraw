# SPDX-License-Identifier: GPL-3.0-or-later
"""C04 editing must report effective business results after UI cleanup."""
import uuid
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QPoint

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, mouse, prepare_edit


def test_copy_adds_distinct_objects_and_credits_the_real_result(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    original = set(canvas.selected_ids)
    original_count = len(canvas.all_segments)
    engine = attach_wait(host.panel, 'selection.duplicated', equals={'count': 1})

    canvas.duplicate_selection()

    assert len(canvas.all_segments) == 2 * original_count
    assert canvas.selected_ids and canvas.selected_ids.isdisjoint(original)
    assert original <= {segment['id'] for segment in canvas.all_segments}
    assert engine.phase == 'completed' and not engine._issued


def test_delete_removes_selected_objects_and_undo_restores_content(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    before = host.module.serialize_page(canvas.capture_page())
    engine = attach_wait(host.panel, 'selection.deleted', equals={'count': 1})

    canvas.delete_selection()

    assert not canvas.all_segments and not canvas.selected_ids
    assert engine.phase == 'completed' and not engine._issued
    assert canvas.undo() and host.module.serialize_page(canvas.capture_page()) == before


@pytest.mark.parametrize('action', ['duplicate_selection', 'delete_selection'])
@pytest.mark.parametrize('stale_id', [False, True])
def test_empty_or_stale_selection_cannot_complete_editing(application_host, action, stale_id):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'select')
    canvas.selected_ids = {uuid.uuid4()} if stale_id else set()
    before = host.module.serialize_page(canvas.capture_page())
    event = 'selection.duplicated' if action == 'duplicate_selection' else 'selection.deleted'
    engine = attach_wait(host.panel, event)

    getattr(canvas, action)()

    assert host.module.serialize_page(canvas.capture_page()) == before
    assert engine.phase == 'running' and not engine._issued


@pytest.mark.parametrize('action', ['duplicate_selection', 'delete_selection'])
def test_editing_ui_tail_failure_does_not_complete_or_leave_tokens(application_host, monkeypatch, action):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    event = 'selection.duplicated' if action == 'duplicate_selection' else 'selection.deleted'
    engine = attach_wait(host.panel, event)
    with monkeypatch.context() as patch:
        patch.setattr(host.panel, 'sync_selection_controls', Mock(side_effect=RuntimeError('editing tail')))
        with pytest.raises(RuntimeError, match='editing tail'):
            getattr(canvas, action)()
    assert engine.phase == 'running' and not engine._issued


@pytest.mark.parametrize('action', ['duplicate_selection', 'delete_selection'])
def test_editing_callback_epoch_change_cannot_credit_the_new_step(application_host, monkeypatch, action):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    event = 'selection.duplicated' if action == 'duplicate_selection' else 'selection.deleted'
    engine = attach_wait(host.panel, event)
    sync = host.panel.sync_selection_controls
    def change_epoch():
        sync()
        engine.pause()
        engine.resume()
    monkeypatch.setattr(host.panel, 'sync_selection_controls', change_epoch)

    getattr(canvas, action)()

    assert engine.phase == 'running' and not engine._issued


def test_copy_then_delete_requires_two_distinct_user_operations(application_host):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    originals = {segment['id'] for segment in canvas.all_segments}
    engine = attach_wait(host.panel, 'selection.duplicated', sequence=(
        WaitClause('selection.duplicated', 'success', {'count': 1}),
        WaitClause('selection.deleted', 'success', {'count': 1})))
    canvas.duplicate_selection()
    assert engine.sequence_index == 1 and engine.phase == 'running'
    canvas.delete_selection()
    assert engine.phase == 'completed'
    assert {segment['id'] for segment in canvas.all_segments} == originals


@pytest.mark.parametrize('target,button', [('selection.duplicate', 'btn_dup'), ('selection.delete', 'btn_del')])
def test_edit_targets_resolve_to_actual_visible_buttons_without_changing_content(application_host, target, button):
    host, _ = application_host
    host.context.activate()
    host.activate()
    canvas = prepare_edit(host.panel, 'transform')
    before = host.module.serialize_page(canvas.capture_page())
    assert host.registry.reveal(target)
    assert host.registry.resolve(target) is getattr(host.panel, button)
    assert getattr(host.panel, button).isVisible()
    assert host.module.serialize_page(canvas.capture_page()) == before


@pytest.mark.parametrize('action', ['scale', 'rotate'])
def test_transform_handle_gestures_credit_only_committed_content(application_host, action):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    handle = canvas.selection_handles()[action].center().toPoint()
    destination = handle + (QPoint(80, 30) if action == 'scale' else QPoint(60, 40))
    before = host.module.serialize_page(canvas.capture_page())
    engine = attach_wait(host.panel, 'selection.transformed', equals={'action': action})
    mouse(canvas, 'press', (handle.x(), handle.y()))
    mouse(canvas, 'move', (destination.x(), destination.y()))
    assert engine.phase == 'running'
    mouse(canvas, 'release', (destination.x(), destination.y()))
    assert host.module.serialize_page(canvas.capture_page()) != before and engine.phase == 'completed'


@pytest.mark.parametrize('action', ['scale', 'rotate'])
def test_transform_handle_without_final_change_cannot_complete(application_host, action):
    host, _ = application_host
    canvas = prepare_edit(host.panel, 'transform')
    handle = canvas.selection_handles()[action].center().toPoint()
    destination = handle + QPoint(60, 40)
    before = host.module.serialize_page(canvas.capture_page())
    engine = attach_wait(host.panel, 'selection.transformed', equals={'action': action})
    mouse(canvas, 'press', (handle.x(), handle.y()))
    mouse(canvas, 'move', (destination.x(), destination.y()))
    mouse(canvas, 'move', (handle.x(), handle.y()))
    mouse(canvas, 'release', (handle.x(), handle.y()))
    assert host.module.serialize_page(canvas.capture_page()) == before
    assert engine.phase == 'running' and not engine._issued
