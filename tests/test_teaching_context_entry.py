# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted feature hints against actual offscreen application entrypoints."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from teaching.onboarding import TeachingStartupContext
from test_teaching_application import parent_coordinator, practice_request
from test_teaching_application_isolation import panel, private_runtime


@pytest.fixture
def hinted_parent(request, practice_request, monkeypatch):
    import teaching.application as application
    monkeypatch.setattr(application, 'APPLICATION_HINT_TOPICS', {
        'toolbar.pen': ('c01', 'c01.foundation'),
        'file.projects': ('c01', 'c01.foundation'),
        'absent.chapter': ('c01', 'c01.absent'),
        'absent.course': ('c02', 'c01.foundation'),
    })
    panel, coordinator = request.getfixturevalue('parent_coordinator')
    coordinator.state_store.set_welcome('skipped')
    coordinator.hint_policy.context = TeachingStartupContext()
    yield panel, coordinator


def show_hint(coordinator, context='toolbar.pen'):
    assert coordinator.request_context_hint(context)
    coordinator._hint_timer.stop()
    assert coordinator._show_pending_context_hint()
    return coordinator.context_hint, coordinator._hint_offer


def test_actual_hint_is_nonmodal_translated_and_does_not_launch(hinted_parent):
    panel, coordinator = hinted_parent
    original_focus = QApplication.focusWidget()
    hint, offer = show_hint(coordinator)
    assert hint.isVisible() and not hint.isModal()
    assert hint.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert hint.title_label.text() == coordinator.module.tr('teaching_context_hint_title')
    assert coordinator.module.tr(coordinator.catalog.chapter_by_id(offer.chapter_id).title_key) in hint.body_label.text()
    assert hint.start_button.text() == coordinator.module.tr('teaching_start')
    assert hint.close_button.text() == coordinator.module.tr('teaching_context_hint_later')
    assert QApplication.focusWidget() is original_focus
    assert coordinator.session.phase == 'idle' and coordinator.session.process is None
    assert coordinator.state_store.snapshot()['context_seen'] == ['toolbar.pen']


@pytest.mark.parametrize('context', ['unknown.context', 'absent.chapter', 'absent.course'])
def test_unknown_or_unavailable_topics_are_not_offered(hinted_parent, context):
    _, coordinator = hinted_parent
    before = coordinator.state_store.snapshot()
    assert not coordinator.request_context_hint(context)
    assert coordinator.context_hint is None and not coordinator._hint_timer.isActive()
    assert coordinator.state_store.snapshot() == before


@pytest.mark.parametrize('flag', ['gesture_active', 'text_edit_active', 'modal_active',
                                 'file_operation_active', 'composition_active'])
def test_feature_entry_waits_for_current_work_without_altering_it(hinted_parent, monkeypatch, flag):
    panel, coordinator = hinted_parent
    ready = coordinator.readiness()
    monkeypatch.setattr(coordinator, 'readiness', lambda **_: replace(ready, **{flag: True}))
    before = repr(panel.canvas.pages)
    assert coordinator.request_context_hint('toolbar.pen')
    coordinator._hint_timer.stop()
    assert not coordinator._show_pending_context_hint()
    assert coordinator.context_hint is None
    assert repr(panel.canvas.pages) == before
    assert coordinator.state_store.snapshot()['context_seen'] == []
    monkeypatch.setattr(coordinator, 'readiness', lambda **_: ready)
    assert coordinator._show_pending_context_hint()


def test_only_explicit_click_starts_matching_catalog_chapter_once(hinted_parent, monkeypatch):
    _, coordinator = hinted_parent
    hint, offer = show_hint(coordinator)
    start = Mock(return_value=True)
    monkeypatch.setattr(coordinator, 'start', start)
    hint.start_button.click()
    coordinator._start_context_hint(offer)
    assert start.call_args_list == [((offer.course_id, offer.chapter_id),)]
    assert coordinator.context_hint is None
    assert not coordinator.request_context_hint('toolbar.pen')


def test_dismiss_and_stale_click_cannot_launch(hinted_parent, monkeypatch):
    _, coordinator = hinted_parent
    hint, offer = show_hint(coordinator)
    start = Mock()
    monkeypatch.setattr(coordinator, 'start', start)
    hint.close_button.click()
    coordinator._start_context_hint(offer)
    assert not start.called and coordinator.context_hint is None
    assert not coordinator.request_context_hint('toolbar.pen')
    assert coordinator.request_context_hint('file.projects')


def test_readiness_is_rechecked_on_explicit_start(hinted_parent, monkeypatch):
    _, coordinator = hinted_parent
    hint, offer = show_hint(coordinator)
    ready = coordinator.readiness()
    monkeypatch.setattr(coordinator, 'readiness', lambda **_: replace(ready, gesture_active=True))
    start = Mock()
    monkeypatch.setattr(coordinator, 'start', start)
    hint.start_button.click()
    assert not start.called and coordinator.context_hint is None
    assert coordinator.last_notice == 'teaching_waiting_operation'
    assert not coordinator.hint_policy.consume(offer, ready)


@pytest.mark.parametrize('context', [TeachingStartupContext(smoke=True),
                                     TeachingStartupContext(automated=True),
                                     TeachingStartupContext(practice=True)])
def test_automatic_suppression_does_not_record_visits(hinted_parent, context):
    _, coordinator = hinted_parent
    coordinator.hint_policy.context = context
    assert not coordinator.request_context_hint('toolbar.pen')
    assert coordinator.state_store.snapshot()['context_seen'] == []


def test_offscreen_default_does_not_automatically_offer(parent_coordinator):
    _, coordinator = parent_coordinator
    assert coordinator.hint_policy.context.automated
    assert not coordinator.request_context_hint('toolbar.pen')


@pytest.mark.parametrize('change', ['disable', 'reset', 'center', 'background', 'close', 'practice'])
def test_state_transitions_retire_existing_hint_and_pending_callback(hinted_parent, monkeypatch, change):
    _, coordinator = hinted_parent
    hint, offer = show_hint(coordinator)
    if change == 'disable':
        assert coordinator.set_context_hints_enabled(False)
    elif change == 'reset':
        assert coordinator.reset_progress()
    elif change == 'center':
        assert coordinator.open_center()
    elif change == 'background':
        coordinator.hide_to_background()
    elif change == 'practice':
        coordinator._phase_changed('starting')
    else:
        coordinator.close()
    assert coordinator.context_hint is None
    assert sip.isdeleted(hint) or not hint.isVisible()
    assert not coordinator.hint_policy.consume(offer, coordinator.readiness())
    start = Mock()
    monkeypatch.setattr(coordinator, 'start', start)
    coordinator._start_context_hint(offer)
    assert not start.called and not coordinator._hint_timer.isActive()


def test_readonly_and_disabled_preferences_never_offer(hinted_parent):
    _, coordinator = hinted_parent
    coordinator.state_store.read_only = True
    assert not coordinator.request_context_hint('toolbar.pen')
    coordinator.state_store.read_only = False
    assert coordinator.set_context_hints_enabled(False)
    assert not coordinator.request_context_hint('toolbar.pen')


def test_pending_hint_does_not_stack_with_welcome_or_center(hinted_parent):
    _, coordinator = hinted_parent
    assert coordinator.open_center()
    assert not coordinator.request_context_hint('toolbar.pen')
    coordinator.center.hide()
    coordinator.state_store.set_welcome('unseen')
    assert not coordinator.request_context_hint('toolbar.pen')


def test_actual_subpanel_entry_requests_hint_only_after_opening(hinted_parent, monkeypatch):
    panel, coordinator = hinted_parent
    request = Mock(return_value=True)
    monkeypatch.setattr(coordinator, 'request_context_hint', request)
    panel.show_only_sub(panel.annotate_sub)
    assert panel.annotate_sub.isVisible() and request.call_args.args == ('toolbar.pen',)
    request.reset_mock()
    panel.show_only_sub(None)
    assert not request.called


def test_practice_entry_never_builds_normal_coordinator(panel, monkeypatch):
    request = Mock()
    monkeypatch.setattr(panel, '_ensure_teaching_coordinator', request)
    assert not panel.maybe_show_teaching_context_hint('toolbar.pen')
    assert not request.called
