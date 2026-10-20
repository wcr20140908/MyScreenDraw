# SPDX-License-Identifier: GPL-3.0-or-later
"""Parent-owned learning settings, exercised only with Qt offscreen widgets."""
from __future__ import annotations

import copy
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QSignalSpy

from teaching.state import TutorialStateStore
from test_teaching_widgets import application, catalog, qt_app, store, translate
from test_teaching_application import parent_coordinator, practice_request


def make_center(catalog, store, translate):
    from teaching.widgets import TeachingCenter
    value = TeachingCenter(catalog, store, translate)
    value.show()
    return value


def test_center_settings_are_localized_and_show_current_preference(qt_app, catalog, store, translate):
    assert store.set_context_hints_enabled(False)
    before = store.path.read_bytes()
    center = make_center(catalog, store, translate)
    assert center.context_hints_check.text() == translate('teaching_context_hints')
    assert not center.context_hints_check.isChecked()
    assert center.reset_button.text() == translate('teaching_reset_progress')
    assert center.reset_confirm_label.text() == translate('teaching_reset_confirm')
    assert center.reset_confirm_label.textFormat() == Qt.TextFormat.PlainText
    assert center.reset_welcome_check.text() == translate('teaching_reset_welcome')
    assert center.reset_confirm_button.text() == translate('teaching_reset_accept')
    assert center.reset_cancel_button.text() == translate('teaching_cancel')
    assert center.reset_confirmation.isHidden()
    center.refresh()
    assert store.path.read_bytes() == before


def test_hint_toggle_only_requests_host_change_and_refresh_never_emits(qt_app, catalog, store, translate):
    assert store.set_welcome('accepted')
    before = store.snapshot()
    disk = store.path.read_bytes()
    center = make_center(catalog, store, translate)
    requests = QSignalSpy(center.context_hints_requested)
    center.context_hints_check.click()
    assert list(requests) == [[False]]
    assert store.snapshot() == before and store.path.read_bytes() == disk
    assert center.context_hints_check.isChecked()  # Unacknowledged requests aren't displayed as saved.
    center.refresh()
    assert list(requests) == [[False]]


def test_reset_requires_visible_confirmation_and_cancel_discards_welcome_opt_in(qt_app, catalog, store, translate):
    assert store.record_chapter('c01.complete', 'completed', compat_revision=2)
    before = store.snapshot()
    disk = store.path.read_bytes()
    center = make_center(catalog, store, translate)
    requests = QSignalSpy(center.reset_requested)
    center.reset_confirm_button.click()
    assert not requests
    center.reset_button.click()
    assert not center.reset_confirmation.isHidden() and not requests
    assert not center.reset_welcome_check.isChecked()
    center.reset_welcome_check.setChecked(True)
    center.reset_cancel_button.click()
    assert center.reset_confirmation.isHidden() and not requests
    center.reset_button.click()
    assert not center.reset_welcome_check.isChecked()
    center.reset_confirm_button.click()
    center.reset_confirm_button.click()
    assert list(requests) == [[False]]
    assert center.reset_confirmation.isHidden()
    assert store.snapshot() == before and store.path.read_bytes() == disk


def test_reset_welcome_requires_explicit_opt_in(qt_app, catalog, store, translate):
    center = make_center(catalog, store, translate)
    requests = QSignalSpy(center.reset_requested)
    center.reset_button.click()
    center.reset_welcome_check.setChecked(True)
    center.reset_confirm_button.click()
    assert list(requests) == [[True]]


def test_readonly_center_can_browse_but_cannot_request_settings(qt_app, catalog, store, translate):
    store.read_only = True
    center = make_center(catalog, store, translate)
    hints, resets = QSignalSpy(center.context_hints_requested), QSignalSpy(center.reset_requested)
    assert not center.context_hints_check.isEnabled()
    assert not center.reset_button.isEnabled()
    assert center.select_chapter('c01', 'c01.new') and center.start_button.isEnabled()
    center.context_hints_check.click()
    center.reset_button.click()
    center._request_context_hints(False)  # A queued/direct callback still has to recheck the gate.
    center._confirm_reset()
    assert not hints and not resets and center.reset_confirmation.isHidden()


def test_activity_revokes_pending_reset_consent_without_disabling_catalog(qt_app, catalog, store, translate):
    center = make_center(catalog, store, translate)
    resets = QSignalSpy(center.reset_requested)
    center.reset_button.click()
    center.reset_welcome_check.setChecked(True)
    center.set_mutations_allowed(False)
    assert center.reset_confirmation.isHidden()
    assert not center.reset_welcome_check.isChecked()
    assert not center.reset_button.isEnabled() and not center.context_hints_check.isEnabled()
    center._confirm_reset()
    assert not resets
    center.set_mutations_allowed(True)
    assert center.reset_button.isEnabled()
    center.reset_confirm_button.click()
    assert not resets  # Old consent must not become valid again.


@pytest.mark.parametrize('operation', ['reset', 'hints'])
def test_durable_settings_failure_preserves_memory_and_disk(tmp_path, monkeypatch, operation):
    value = TutorialStateStore(tmp_path / 'progress.json')
    assert value.set_welcome('accepted')
    assert value.record_chapter('c01.ink', 'completed', compat_revision=1)
    assert value.mark_context_seen('file.save')
    before, disk = value.snapshot(), value.path.read_bytes()

    def denied(*args):
        raise OSError('controlled atomic replace failure')

    monkeypatch.setattr('teaching.state.os.replace', denied)
    mutate = (lambda: value.reset(show_welcome=True, require_persistence=True)) if operation == 'reset' else (
        lambda: value.set_context_hints_enabled(False, require_persistence=True))
    assert mutate() is False
    assert value.read_only and value.last_error == 'save_failed'
    assert value.snapshot() == before and value.path.read_bytes() == disk
    assert mutate() is False
    assert value.snapshot() == before and value.path.read_bytes() == disk
    assert not list(tmp_path.glob('.*.tmp'))


@pytest.fixture
def coordinator(qt_app, parent_coordinator):
    panel, value = parent_coordinator
    value._notice = Mock()
    assert value.open_center()
    return panel, value


def test_actual_center_hint_setting_persists_without_resetting_history(coordinator):
    panel, value = coordinator
    assert value.state_store.set_welcome('accepted')
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    assert value.state_store.mark_context_seen('file.save')
    value.center.context_hints_check.click()
    assert not value.state_store.context_hints_enabled
    assert value.state_store.chapter_status('c01.foundation') == 'completed'
    assert value.state_store.welcome == 'accepted'
    assert value.state_store.snapshot()['context_seen'] == ['file.save']
    reloaded = TutorialStateStore(value.state_store.path)
    assert not reloaded.context_hints_enabled
    assert not value.center.context_hints_check.isChecked()
    assert value.session.phase == 'idle' and not panel._teaching_suspended


@pytest.mark.parametrize('show_welcome', [False, True])
def test_actual_center_reset_is_explicit_durable_and_preserves_original_work(coordinator, show_welcome):
    panel, value = coordinator
    assert value.state_store.set_welcome('accepted')
    assert value.state_store.set_context_hints_enabled(False)
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    assert value.state_store.mark_context_seen('file.save')
    panel.canvas.enter_whiteboard()
    assert panel.canvas.rename_page(0, 'Original work')
    before_pages = copy.deepcopy(panel.canvas.pages)
    before = value.state_store.snapshot()
    value.center.refresh()
    value.center.search_edit.setText('foundation')
    assert value.center.select_chapter('c01', 'c01.foundation')
    value.center.reset_button.click()
    assert value.state_store.snapshot() == before
    value.center.reset_welcome_check.setChecked(show_welcome)
    value.center.reset_confirm_button.click()
    reloaded = TutorialStateStore(value.state_store.path)
    assert reloaded.snapshot()['chapters'] == {} and reloaded.last_started is None
    assert reloaded.snapshot()['context_seen'] == []
    assert reloaded.welcome == ('unseen' if show_welcome else 'dismissed')
    assert not reloaded.context_hints_enabled
    assert panel.canvas.pages == before_pages
    assert value.session.phase == 'idle' and not panel._teaching_suspended
    assert value.center.search_edit.text() == 'foundation'
    assert value.center.selected_chapter == ('c01', 'c01.foundation')
    assert not value.center.resume_button.isEnabled()
    assert not value.request_startup_welcome() and not value.maybe_show_welcome()
    assert value.welcome.dialog is None  # Opt-in is for NEXT startup, not this one.
    assert not value._welcome_timer.isActive()


@pytest.mark.parametrize('phase', ['starting', 'ready', 'activating', 'running', 'paused', 'stopping', 'restoring', 'restore_failed'])
def test_host_rejects_settings_requests_in_every_active_phase(coordinator, phase):
    panel, value = coordinator
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    before, disk = value.state_store.snapshot(), value.state_store.path.read_bytes()
    value.session.phase = phase
    try:
        assert value.reset_progress(show_welcome=True) is False
        assert value.set_context_hints_enabled(False) is False
        assert value.state_store.snapshot() == before and value.state_store.path.read_bytes() == disk
        assert not value.center.reset_button.isEnabled()
        assert not value.center.context_hints_check.isEnabled()
    finally:
        value.session.phase = 'idle'


@pytest.mark.parametrize('operation', ['reset', 'hints'])
def test_actual_settings_write_failure_rolls_back_and_shows_warning(coordinator, monkeypatch, operation):
    panel, value = coordinator
    assert value.state_store.set_welcome('accepted')
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    before, disk = value.state_store.snapshot(), value.state_store.path.read_bytes()

    def denied(*args):
        raise OSError('controlled replace failure')

    monkeypatch.setattr('teaching.state.os.replace', denied)
    if operation == 'reset':
        value.center.reset_button.click()
        value.center.reset_welcome_check.setChecked(True)
        value.center.reset_confirm_button.click()
    else:
        value.center.context_hints_check.click()
    assert value.state_store.snapshot() == before and value.state_store.path.read_bytes() == disk
    assert value.center.context_hints_check.isChecked()
    assert not value.center.warning_label.isHidden()
    assert not value.center.reset_button.isEnabled()
    value._notice.assert_called_once_with('teaching_progress_save_failed')


def test_readonly_or_closed_host_cannot_change_preferences(coordinator):
    panel, value = coordinator
    before = value.state_store.snapshot()
    value.state_store.read_only = True
    assert value.reset_progress(show_welcome=True) is False
    assert value.set_context_hints_enabled(False) is False
    assert value.state_store.snapshot() == before
    value.state_store.read_only = False
    value.close()
    assert value.reset_progress() is False
    assert value.set_context_hints_enabled(False) is False
    assert value.state_store.snapshot() == before


@pytest.mark.parametrize('transition', ['hide', 'close'])
def test_hidden_or_closed_center_revokes_pending_reset(coordinator, transition):
    panel, value = coordinator
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    before, disk = value.state_store.snapshot(), value.state_store.path.read_bytes()
    center = value.center
    center.reset_button.click()
    center.reset_welcome_check.setChecked(True)
    getattr(center, transition)()
    center._confirm_reset()
    assert value.state_store.snapshot() == before and value.state_store.path.read_bytes() == disk
    assert center.reset_confirmation.isHidden() and not center.reset_welcome_check.isChecked()
    if transition == 'hide':
        center.show()
        center._confirm_reset()
        assert value.state_store.snapshot() == before  # Re-show cannot revive old consent.


def test_hidden_center_cannot_deliver_old_hint_request(qt_app, catalog, store, translate):
    center = make_center(catalog, store, translate)
    requests = QSignalSpy(center.context_hints_requested)
    center.hide()
    center._request_context_hints(False)
    assert not requests


@pytest.mark.parametrize('late_action', ['shutdown', 'skipped', 'accepted'])
def test_retired_welcome_cannot_override_next_start_or_launch_course(coordinator, late_action):
    panel, value = coordinator
    assert value.maybe_show_welcome()
    old_welcome = value.welcome.dialog
    value.welcome._start_core = Mock()
    value.center.reset_button.click()
    value.center.reset_welcome_check.setChecked(True)
    value.center.reset_confirm_button.click()
    assert value.state_store.welcome == 'unseen'
    if late_action == 'shutdown':
        value.close()
    else:
        value.welcome._decide(late_action)  # Already-posted old dialog callback.
    assert value.state_store.welcome == 'unseen'
    assert TutorialStateStore(value.state_store.path).welcome == 'unseen'
    value.welcome._start_core.assert_not_called()
    assert not old_welcome.isVisible()


def test_failed_reset_does_not_retire_the_existing_welcome(coordinator, monkeypatch):
    panel, value = coordinator
    assert value.maybe_show_welcome()
    old_welcome = value.welcome.dialog
    assert value.state_store.record_chapter('c01.foundation', 'completed', compat_revision=1)
    before, disk = value.state_store.snapshot(), value.state_store.path.read_bytes()

    def denied(*args):
        raise OSError('controlled atomic replace failure')

    monkeypatch.setattr('teaching.state.os.replace', denied)
    value.center.reset_button.click()
    value.center.reset_welcome_check.setChecked(True)
    value.center.reset_confirm_button.click()
    assert value.state_store.snapshot() == before and value.state_store.path.read_bytes() == disk
    assert value.welcome.dialog is old_welcome and old_welcome.isVisible()
    assert not value._welcome_deferred_to_next_start


def test_hint_callback_can_synchronously_delete_visible_center(qt_app, catalog, store, translate):
    from PyQt6 import sip
    center = make_center(catalog, store, translate)
    center.context_hints_requested.connect(lambda _: sip.delete(center))
    center._request_context_hints(False)
    assert sip.isdeleted(center)
