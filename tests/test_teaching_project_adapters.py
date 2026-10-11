# SPDX-License-Identifier: GPL-3.0-or-later
"""C08 file decisions and persisted settings through private offscreen business paths."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QMessageBox

from teaching.application import APPLICATION_EVENTS, APPLICATION_TARGETS
from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink
from test_teaching_file_results import saved_project, wait_for


def test_c08_targets_and_result_events_are_registered():
    assert {'settings.autosave_preset', 'settings.autosave_custom'} <= APPLICATION_TARGETS
    assert {'unsaved.decision', 'settings.autosave_changed', 'settings.autosave_custom_opened'} <= APPLICATION_EVENTS


@pytest.mark.parametrize('reuse', [False, True])
def test_save_reports_real_destination_reuse_and_dirty_state(application_host, reuse):
    host, _ = application_host
    panel = host.panel
    destination = host.request.paths.data_dir / 'first.msd'
    if reuse:
        assert panel.save_project(str(destination))
    draw_ink(panel.canvas)
    engine = wait_for(panel, 'project.saved', action='save', reuse_path=reuse, modified_before=True)
    assert panel.save_project(str(destination))
    assert destination.is_file() and not panel.has_unsaved_changes()
    assert engine.phase == 'completed'


@pytest.mark.parametrize('different', [False, True])
def test_save_as_reports_whether_destination_actually_changed(application_host, monkeypatch, different):
    host, _ = application_host
    original = saved_project(host)
    destination = original.with_name('another.msd') if different else original
    engine = wait_for(host.panel, 'project.saved', action='save_as', changed_path=True)
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(destination), ''))
    assert host.panel.save_project_as_from_file_panel()
    assert destination.is_file()
    assert engine.phase == ('completed' if different else 'running')
    assert not engine._issued


@pytest.mark.parametrize('choice,decision,proceeded', [
    ('Cancel', 'cancel', False), ('Discard', 'discard', True), ('Save', 'save', True)])
def test_unsaved_choice_is_delivered_after_prompt_cleanup(application_host, monkeypatch, choice, decision, proceeded):
    host, _ = application_host
    panel = host.panel
    saved_project(host)
    draw_ink(panel.canvas)
    engine = wait_for(panel, 'unsaved.decision', decision=decision, proceeded=proceeded)
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: getattr(QMessageBox.StandardButton, choice))
    states, resumed = [], []
    original_resume = panel.resume_callbacks
    def resume():
        original_resume()
        resumed.append(True)
    monkeypatch.setattr(panel, 'resume_callbacks', resume)
    engine._on_step = lambda step: states.append((panel._unsaved_prompt_active, bool(resumed))) if step is None else None
    assert panel.confirm_unsaved_changes('private lesson') is proceeded
    assert engine.phase == 'completed' and states == [(False, True)]


@pytest.mark.parametrize('choice,saved', [('Discard', False), ('Save', True)])
def test_open_result_combines_actual_choice_and_applied_document(application_host, monkeypatch, choice, saved):
    host, _ = application_host
    panel = host.panel
    target = saved_project(host)
    draw_ink(panel.canvas)
    old_generation = panel._document_generation
    engine = wait_for(panel, 'project.opened', unsaved_choice=choice.lower(), saved_before_open=saved)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(target), ''))
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: getattr(QMessageBox.StandardButton, choice))
    assert panel.open_project_from_file_panel()
    assert engine.phase == 'completed' and not engine._issued
    assert panel._document_generation == old_generation + 1
    assert not panel._document_transition_active and getattr(panel, '_teaching_document_batch', None) is None


def test_unsaved_cancel_keeps_document_and_counts_only_actual_cancel_choice(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    target = saved_project(host)
    draw_ink(panel.canvas)
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'unsaved.decision', decision='cancel', proceeded=False)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(target), ''))
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Cancel)
    assert not panel.open_project_from_file_panel()
    assert panel.canvas.document_signature() == before and engine.phase == 'completed'


def test_failed_save_cannot_claim_successful_unsaved_decision(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    target = saved_project(host)
    draw_ink(panel.canvas)
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'unsaved.decision', decision='save', proceeded=True)
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(panel, 'save_project', lambda *args: False)
    assert not panel.open_project_from_path(str(target))
    assert panel.canvas.document_signature() == before and engine.phase == 'running'
    assert not engine._issued


def test_unsaved_cleanup_exception_never_publishes_choice(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    draw_ink(panel.canvas)
    engine = wait_for(panel, 'unsaved.decision')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Discard)
    original = panel.resume_callbacks
    def fail_cleanup():
        original()
        raise RuntimeError('choice cleanup')
    monkeypatch.setattr(panel, 'resume_callbacks', fail_cleanup)
    with pytest.raises(RuntimeError, match='choice cleanup'):
        panel.confirm_unsaved_changes('private lesson')
    assert engine.phase == 'running' and not engine._issued
    assert not panel._unsaved_prompt_active and getattr(panel, '_teaching_document_batch', None) is None


def test_unsaved_dialog_old_epoch_cannot_credit_resumed_step(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    draw_ink(panel.canvas)
    engine = wait_for(panel, 'unsaved.decision')
    def choose(self):
        engine.pause(); engine.resume()
        return QMessageBox.StandardButton.Discard
    monkeypatch.setattr(QMessageBox, 'exec', choose)
    assert panel.confirm_unsaved_changes('private lesson')
    assert engine.phase == 'running' and not engine._issued


def test_clean_document_does_not_claim_an_unsaved_choice(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    saved_project(host)
    engine = wait_for(panel, 'unsaved.decision')
    monkeypatch.setattr(QMessageBox, 'exec', Mock(side_effect=AssertionError('unexpected dialog')))
    assert panel.confirm_unsaved_changes('private lesson')
    assert engine.phase == 'running' and not engine._issued


def test_autosave_setting_is_delivered_only_after_real_persistence(application_host):
    host, _ = application_host
    panel = host.panel
    panel.set_autosave_interval(30)
    engine = wait_for(panel, 'settings.autosave_changed', seconds=60)
    assert panel.set_autosave_interval(60) == 60
    assert panel.autosave_timer.interval() == 60000 and engine.phase == 'completed'
    assert not engine._issued


@pytest.mark.parametrize('case', ['same', 'transient', 'failure'])
def test_autosave_noop_transient_or_failed_persistence_is_not_a_success(application_host, monkeypatch, case):
    host, _ = application_host
    panel = host.panel
    panel.set_autosave_interval(30)
    engine = wait_for(panel, 'settings.autosave_changed')
    if case == 'failure':
        monkeypatch.setattr(panel, 'save_settings', Mock(side_effect=RuntimeError('settings write')))
        with pytest.raises(RuntimeError, match='settings write'):
            panel.set_autosave_interval(60)
    else:
        panel.set_autosave_interval(30 if case == 'same' else 60, persist=case != 'transient')
    assert engine.phase == 'running' and not engine._issued


def test_custom_interval_choice_requires_a_real_visible_custom_control(application_host):
    host, _ = application_host
    panel = host.panel
    panel.set_autosave_interval(60)
    panel.open_settings_panel()
    preferences = panel.document_preferences
    assert preferences.interval_custom.isHidden()
    engine = wait_for(panel, 'settings.autosave_custom_opened', custom=True)
    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(-1))
    assert not preferences.interval_custom.isHidden() and engine.phase == 'completed'
    engine = wait_for(panel, 'settings.autosave_changed', seconds=75)
    preferences.interval_custom.setValue(75)
    assert panel.autosave_interval_seconds == 75 and engine.phase == 'completed'


@pytest.mark.parametrize('failure', ['quiet_return', 'atomic_write'])
def test_quiet_settings_write_failure_never_claims_persisted_interval(application_host, monkeypatch, failure):
    host, _ = application_host
    panel = host.panel
    panel.set_autosave_interval(30)
    engine = wait_for(panel, 'settings.autosave_changed', seconds=60)
    if failure == 'quiet_return':
        monkeypatch.setattr(panel, 'save_settings', lambda: None)
    else:
        monkeypatch.setattr(host.module, 'atomic_write_json', Mock(side_effect=OSError('private write failed')))
    panel.set_autosave_interval(60)
    assert engine.phase == 'running' and not engine._issued


def test_clean_open_does_not_reuse_a_previous_unsaved_choice(application_host):
    host, _ = application_host
    panel = host.panel
    target = saved_project(host)
    panel._teaching_unsaved_choice = {'decision': 'save', 'saved': True}
    engine = wait_for(panel, 'project.opened', unsaved_choice='save', saved_before_open=True)
    assert panel.open_project_from_path(str(target))
    assert engine.phase == 'running' and not engine._issued


def test_autosave_write_from_an_old_epoch_cannot_credit_resumed_step(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    panel.set_autosave_interval(30)
    engine = wait_for(panel, 'settings.autosave_changed', seconds=60)
    original = panel.save_settings
    def save_and_pause():
        original()
        engine.pause(); engine.resume()
    monkeypatch.setattr(panel, 'save_settings', save_and_pause)
    panel.set_autosave_interval(60)
    assert engine.phase == 'running' and not engine._issued
    assert panel._teaching_document_batch is None


def test_save_then_open_same_file_reloads_newly_saved_content_without_teaching(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    target = saved_project(host)
    panel.teaching_events = None
    draw_ink(panel.canvas)
    expected = panel.canvas.serialized_document_pages()
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Save)
    assert panel.open_project_from_path(str(target))
    assert panel.canvas.serialized_document_pages() == expected
    assert not panel.has_unsaved_changes()
