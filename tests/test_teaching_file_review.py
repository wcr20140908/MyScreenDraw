# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce bounded review timing risks; private paths and offscreen Qt only."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QDialog

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink
from test_teaching_file_results import private_history, prepare_export, saved_project, wait_for


ACTIONS = [('open', 'project.opened'), ('save', 'project.saved'), ('save_as', 'project.saved'),
           ('preview', 'recovery.previewed'), ('restore', 'recovery.applied'), ('png', 'export.finished')]


def setup_action(host, monkeypatch, action):
    panel = host.panel
    path = host.request.paths.data_dir / 'review-practice.msd'
    if action == 'open':
        path = saved_project(host)
    elif action in ('save', 'save_as'):
        draw_ink(panel.canvas)
    elif action in ('preview', 'restore'):
        private_history(host)
        def choose(dialog):
            if action == 'preview':
                dialog.reject()
                return QDialog.DialogCode.Rejected
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(host.module.RecoveryDialog, 'exec', choose)
        monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: True)
    else:
        prepare_export(host, monkeypatch)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    callbacks = {'open': panel.open_project_from_file_panel, 'save': panel.save_project_from_file_panel,
                 'save_as': panel.save_project_as_from_file_panel, 'preview': panel.open_recovery_from_file_panel,
                 'restore': panel.open_recovery_from_file_panel, 'png': lambda: panel.do_export('PNG')}
    return callbacks[action]


@pytest.mark.parametrize('action,event', ACTIONS)
def test_menu_operation_predates_its_first_ui_callback(application_host, monkeypatch, action, event):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    perform = setup_action(host, monkeypatch, action)
    engine = wait_for(panel, event)
    original = panel.show_only_sub
    changed = []
    def hide(target=None):
        original(target)
        if target is None and not changed:
            changed.append(True)
            engine.pause(); engine.resume()
    monkeypatch.setattr(panel, 'show_only_sub', hide)
    result = perform()
    assert bool(result) == (action != 'preview')
    assert changed == [True]
    assert engine.phase == 'running' and not engine._issued


@pytest.mark.parametrize('action,event', ACTIONS)
def test_native_scope_cleanup_failure_never_publishes_success(application_host, monkeypatch, action, event):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    perform = setup_action(host, monkeypatch, action)
    engine = wait_for(panel, event)
    # Inject exactly at the real cleanup point, not at new-target presentation.
    monkeypatch.setattr(host.presenter.barrier, 'resume', Mock(side_effect=RuntimeError('native scope cleanup')))
    with pytest.raises(RuntimeError, match='native scope cleanup'):
        perform()
    assert engine.phase == 'running' and not engine._issued
    assert host.presenter._dialog_depth == 0
    assert not panel._document_transition_active
    assert getattr(panel, '_teaching_document_batch', None) is None


def batch_class():
    from teaching import events
    batch = getattr(events, 'TeachingOperationBatch', None)
    assert callable(batch), 'a queued result batch is required before native target recheck'
    return batch


def test_batch_stages_a_snapshot_and_only_flush_advances(application_host):
    host, _ = application_host
    panel = host.panel
    engine = wait_for(panel, 'project.saved', pages=1)
    batch = batch_class()(panel.teaching_events, ('project.saved',))
    context = batch.operation('project.saved')
    details = {'pages': 1}
    assert batch.emit_result(context, 'project.saved', 'success', details)
    details['pages'] = 9
    assert engine.phase == 'running'
    batch.flush()
    assert engine.phase == 'completed'
    batch.close()
    assert not engine._issued


def test_batch_suppression_does_not_consume_its_captured_token(application_host):
    host, _ = application_host
    panel = host.panel
    engine = wait_for(panel, 'project.saved')
    batch = batch_class()(panel.teaching_events, ('project.saved',))
    context = batch.operation('project.saved')
    with batch.suppress():
        assert panel.teaching_events.begin_operation('project.saved') is None
        assert not batch.emit_result(context, 'project.saved', 'success', {})
    assert engine.phase == 'running' and engine._issued.get(context.operation_id) == context
    assert batch.emit_result(context, 'project.saved', 'success', {})
    batch.flush(); batch.close()
    assert engine.phase == 'completed' and not engine._issued


def test_abandoned_batch_close_retires_only_its_own_context(application_host):
    host, _ = application_host
    panel = host.panel
    engine = wait_for(panel, 'project.saved')
    peer = panel.teaching_events.begin_operation('project.saved')
    batch = batch_class()(panel.teaching_events, ('project.saved',))
    assert batch.emit_result(batch.operation('project.saved'), 'project.saved', 'success', {})
    batch.close()
    batch.flush()
    assert engine.phase == 'running' and engine._issued == {peer.operation_id: peer}
    assert not batch.emit_result(peer, 'project.saved', 'success', {})
    panel.teaching_events.discard_operation(peer)


def test_batch_cannot_resign_or_replay_into_next_sequence_stage(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'project.saved', sequence=(WaitClause('project.saved', 'success'),
                                                        WaitClause('project.saved', 'success')))
    batch = batch_class()(panel.teaching_events, ('project.saved',))
    context = batch.operation('project.saved')
    assert batch.emit_result(context, 'project.saved', 'success', {})
    batch.flush()
    assert engine.sequence_index == 1 and engine.phase == 'running'
    assert batch.operation('project.opened') is None
    assert not batch.emit_result(context, 'project.saved', 'success', {})
    batch.flush(); batch.close()
    assert engine.sequence_index == 1 and engine.phase == 'running'



def test_absent_entry_context_cannot_be_signed_after_another_result(application_host):
    host, _ = application_host
    panel = host.panel
    engine = attach_wait(panel, 'project.saved', sequence=(WaitClause('project.saved', 'success'),
                                                        WaitClause('project.opened', 'success')))
    source = panel.teaching_events.begin_operation('project.saved')
    batch = batch_class()(panel.teaching_events, ('project.opened',))
    assert batch.operation('project.opened') is None
    assert panel.teaching_events.emit_result(source, 'project.saved', 'success', {})
    assert engine.sequence_index == 1
    assert batch.operation('project.opened') is None
    batch.flush(); batch.close()
    assert engine.phase == 'running' and not engine._issued


def test_outer_callback_failure_discards_already_staged_success(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    draw_ink(panel.canvas)
    path = host.request.paths.data_dir / 'staged-before-error.msd'
    engine = wait_for(panel, 'project.saved')
    original = panel.save_project
    def callback():
        assert original(str(path))
        assert engine.phase == 'running'
        raise RuntimeError('outer callback tail')
    monkeypatch.setattr(panel, 'save_project', callback)
    with pytest.raises(RuntimeError, match='outer callback tail'):
        panel.save_project_from_file_panel()
    assert path.is_file()  # The real write succeeded; only teaching credit is withheld.
    assert engine.phase == 'running' and not engine._issued
    assert panel._teaching_document_batch is None and host.presenter._dialog_depth == 0
