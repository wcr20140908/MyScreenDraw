# SPDX-License-Identifier: GPL-3.0-or-later
"""Context hints exercise pure policy with temporary, real progress stores."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import json
import sys
from threading import Event

import pytest

from teaching.context_hints import ContextHintOffer, ContextHintPolicy
from teaching.onboarding import TeachingReadiness, TeachingStartupContext
from teaching.state import TutorialStateStore


TOPICS = {
    'file.export': ('c01', 'c01.export'),
    'tools.timer': ('c02', 'c02.timer'),
}


def ready(**changes):
    return replace(TeachingReadiness(
        lifecycle_ready=True, restore_finished=True, layout_ready=True,
        foreground=True, application_visible=True,
    ), **changes)


def make_policy(tmp_path, **kwargs):
    store = TutorialStateStore(tmp_path / 'tutorial-state.json')
    return store, ContextHintPolicy(store, TOPICS, **kwargs)


def show_into(shown):
    def show(offer):
        shown.append(offer)
        return True
    return show


def test_successful_hint_is_frozen_once_and_records_only_the_seen_context(tmp_path):
    store, policy = make_policy(tmp_path)
    before = store.snapshot()
    shown = []
    offer = policy.try_offer('file.export', ready(), show_into(shown))

    assert isinstance(offer, ContextHintOffer)
    assert (offer.context_id, offer.course_id, offer.chapter_id) == (
        'file.export', 'c01', 'c01.export',
    )
    assert shown == [offer] and shown[0] is offer
    with pytest.raises(FrozenInstanceError):
        offer.chapter_id = 'c01.other'
    assert store.snapshot() == dict(before, context_seen=['file.export'])
    assert TutorialStateStore(store.path).snapshot() == store.snapshot()
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [offer]


@pytest.mark.parametrize('field,value', [
    ('lifecycle_ready', False), ('restore_finished', False), ('layout_ready', False),
    ('foreground', False), ('application_visible', False), ('modal_active', True),
    ('gesture_active', True), ('composition_active', True), ('text_edit_active', True),
    ('file_operation_active', True), ('practice_active', True),
])
def test_busy_or_background_user_can_retry_without_implicit_edits(tmp_path, field, value):
    store, policy = make_policy(tmp_path)
    before = store.snapshot()
    shown = []
    assert policy.try_offer('file.export', ready(**{field: value}), show_into(shown)) is None
    assert shown == [] and store.snapshot() == before and not store.path.exists()
    assert policy.try_offer('file.export', ready(), show_into(shown)) is shown[0]


@pytest.mark.parametrize('context', [
    TeachingStartupContext(practice=True), TeachingStartupContext(smoke=True),
    TeachingStartupContext(automated=True),
    TeachingStartupContext.from_arguments(['--teaching-practice']),
    TeachingStartupContext.from_arguments(['--smoke-ui=basic']),
    TeachingStartupContext.from_arguments([], automated=True),
])
def test_practice_smoke_and_automated_startup_never_show_or_record(tmp_path, context):
    store, policy = make_policy(tmp_path, context=context)
    before = store.snapshot()
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [] and store.snapshot() == before and not store.path.exists()


@pytest.mark.parametrize('context_id', ['file.unknown', '', '../private', None])
def test_unknown_context_is_rejected_without_ui_or_disk(tmp_path, context_id):
    store, policy = make_policy(tmp_path)
    before = store.snapshot()
    shown = []
    assert policy.try_offer(context_id, ready(), show_into(shown)) is None
    assert shown == [] and store.snapshot() == before and not store.path.exists()


def test_read_only_store_suppresses_automatic_hints(tmp_path):
    store, policy = make_policy(tmp_path)
    store.read_only = True
    before = store.snapshot()
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [] and store.snapshot() == before and not store.path.exists()


def test_future_schema_remains_untouched_without_offers(tmp_path):
    state_path = tmp_path / 'tutorial-state.json'
    original = b'{"schema_version":999,"future_field":"preserve"}'
    state_path.write_bytes(original)
    store, policy = make_policy(tmp_path)
    before = store.snapshot()
    shown = []
    assert store.read_only and store.last_error == 'unsupported_schema'
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [] and store.snapshot() == before and state_path.read_bytes() == original
    assert sorted(tmp_path.iterdir()) == [state_path]


def test_disabled_hints_can_retry_after_the_user_enables_them(tmp_path):
    store, policy = make_policy(tmp_path)
    assert store.set_context_hints_enabled(False)
    before = store.path.read_bytes()
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [] and store.path.read_bytes() == before
    assert store.set_context_hints_enabled(True)
    assert policy.try_offer('file.export', ready(), show_into(shown)) is shown[0]


def test_previously_seen_context_is_suppressed_after_reload(tmp_path):
    store = TutorialStateStore(tmp_path / 'tutorial-state.json')
    assert store.mark_context_seen('file.export')
    before = store.path.read_bytes()
    store, policy = make_policy(tmp_path)
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [] and store.path.read_bytes() == before
    assert policy.try_offer('tools.timer', ready(), show_into(shown)) is shown[0]


@pytest.mark.parametrize('failure', [False, None, 'exception'])
def test_failed_show_is_retryable_without_marking_seen_or_warning(tmp_path, failure):
    warnings = []
    store, policy = make_policy(tmp_path, warn=warnings.append)
    before = store.snapshot()
    attempts = []

    def failed_show(offer):
        attempts.append(offer)
        assert store.should_offer_context_hint('file.export') and not store.path.exists()
        if failure == 'exception':
            raise RuntimeError('host could not show the hint')
        return failure

    for _ in range(2):
        assert policy.try_offer('file.export', ready(), failed_show) is None
    assert len(attempts) == 2 and attempts[0] is not attempts[1]
    assert store.snapshot() == before and warnings == [] and not store.path.exists()
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is shown[0]


def test_topics_are_a_host_owned_snapshot_without_default_courses(tmp_path):
    store = TutorialStateStore(tmp_path / 'tutorial-state.json')
    topics = {'host.context': ('host', 'host.chapter')}
    policy = ContextHintPolicy(store, topics)
    topics['host.context'] = ('other', 'other.chapter')
    topics['file.export'] = ('other', 'other.export')
    shown = []
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    offer = policy.try_offer('host.context', ready(), show_into(shown))
    assert (offer.course_id, offer.chapter_id) == ('host', 'host.chapter')



def test_active_offer_blocks_another_topic_until_explicit_consumption(tmp_path):
    store, policy = make_policy(tmp_path)
    shown = []
    first = policy.try_offer('file.export', ready(), show_into(shown))
    before = store.path.read_bytes()
    assert policy.try_offer('tools.timer', ready(), show_into(shown)) is None
    assert shown == [first] and store.path.read_bytes() == before
    assert policy.consume(first, ready()) is True
    assert policy.consume(first, ready()) is False
    second = policy.try_offer('tools.timer', ready(), show_into(shown))
    assert shown == [first, second] and second is not None
    assert policy.consume(first, ready()) is False
    assert policy.consume(second, ready()) is True
    assert policy.consume(second, ready()) is False
    assert store.last_started is None and store.snapshot()['chapters'] == {}


@pytest.mark.parametrize('retire', ['dismiss', 'invalidate', 'consume'])
def test_successful_display_stays_once_in_this_session_even_after_store_reset(tmp_path, retire):
    store, policy = make_policy(tmp_path)
    shown = []
    offer = policy.try_offer('file.export', ready(), show_into(shown))
    if retire == 'invalidate':
        policy.invalidate()
    elif retire == 'dismiss':
        assert policy.dismiss(offer) is True
    else:
        assert policy.consume(offer, ready()) is True
    assert store.reset()
    assert store.should_offer_context_hint('file.export')
    before = store.path.read_bytes()
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert shown == [offer] and store.path.read_bytes() == before
    assert policy.try_offer('tools.timer', ready(), show_into(shown)) is not None


def test_equal_but_forged_offer_cannot_consume_or_dismiss_the_real_offer(tmp_path):
    store, policy = make_policy(tmp_path)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    forged = ContextHintOffer(offer.context_id, offer.course_id, offer.chapter_id)
    assert forged == offer and forged is not offer
    before = store.path.read_bytes()
    assert policy.consume(forged, ready()) is False
    assert policy.dismiss(forged) is False
    assert policy.consume(offer, ready()) is True
    assert store.path.read_bytes() == before


def test_equal_offer_issued_by_another_policy_has_no_authority_here(tmp_path):
    _, policy = make_policy(tmp_path)
    _, other_policy = make_policy(tmp_path / 'other')
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    other = other_policy.try_offer('file.export', ready(), lambda _: True)
    assert other == offer and other is not offer
    assert policy.consume(other, ready()) is False
    assert policy.dismiss(other) is False
    assert policy.consume(offer, ready()) is True
    assert other_policy.consume(other, ready()) is True


@pytest.mark.parametrize('unissued', [None, object(), ContextHintOffer('file.export', 'c01', 'c01.export')])
def test_unissued_or_missing_offer_never_grants_a_start(tmp_path, unissued):
    store, policy = make_policy(tmp_path)
    assert policy.consume(unissued, ready()) is False
    assert policy.dismiss(unissued) is False
    policy.invalidate()
    assert policy.consume(unissued, ready()) is False
    assert not store.path.exists()


@pytest.mark.parametrize('retire', ['dismiss', 'invalidate'])
def test_retired_signal_cannot_start_or_retire_a_new_active_offer(tmp_path, retire):
    _, policy = make_policy(tmp_path)
    old = policy.try_offer('file.export', ready(), lambda _: True)
    if retire == 'dismiss':
        assert policy.dismiss(old) is True
        assert policy.dismiss(old) is False
    else:
        policy.invalidate()
        policy.invalidate()
    assert policy.consume(old, ready()) is False
    current = policy.try_offer('tools.timer', ready(), lambda _: True)
    assert current is not None
    assert policy.consume(old, ready()) is False
    assert policy.dismiss(old) is False
    assert policy.consume(current, ready()) is True


@pytest.mark.parametrize('field,value', [
    ('lifecycle_ready', False), ('restore_finished', False), ('layout_ready', False),
    ('foreground', False), ('application_visible', False), ('modal_active', True),
    ('gesture_active', True), ('composition_active', True), ('text_edit_active', True),
    ('file_operation_active', True), ('practice_active', True),
])
def test_consume_rechecks_readiness_without_deciding_for_a_busy_user(tmp_path, field, value):
    store, policy = make_policy(tmp_path)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    before = store.path.read_bytes()
    assert policy.consume(offer, ready(**{field: value})) is False
    assert store.path.read_bytes() == before
    assert policy.consume(offer, ready()) is True
    assert policy.consume(offer, ready()) is False
    assert store.path.read_bytes() == before


@pytest.mark.parametrize('context', [
    TeachingStartupContext(practice=True), TeachingStartupContext(smoke=True),
    TeachingStartupContext(automated=True),
])
def test_consume_rechecks_startup_context(tmp_path, context):
    _, policy = make_policy(tmp_path)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    policy.context = context
    assert policy.consume(offer, ready()) is False
    policy.context = TeachingStartupContext()
    assert policy.consume(offer, ready()) is True


def test_consume_rechecks_the_hint_setting_without_retiring_a_deferred_offer(tmp_path):
    store, policy = make_policy(tmp_path)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    assert store.set_context_hints_enabled(False)
    before = store.path.read_bytes()
    assert policy.consume(offer, ready()) is False
    assert store.path.read_bytes() == before
    assert store.set_context_hints_enabled(True)
    assert policy.consume(offer, ready()) is True
    assert policy.consume(offer, ready()) is False


@pytest.mark.parametrize('failure', [False, 'exception'])
def test_failed_display_signal_cannot_consume_a_later_real_offer(tmp_path, failure):
    _, policy = make_policy(tmp_path)
    failed = []

    def failed_show(offer):
        failed.append(offer)
        if failure == 'exception':
            raise RuntimeError('display failed')
        return False

    assert policy.try_offer('file.export', ready(), failed_show) is None
    assert policy.consume(failed[0], ready()) is False
    assert policy.dismiss(failed[0]) is False
    current = policy.try_offer('file.export', ready(), lambda _: True)
    assert current == failed[0] and current is not failed[0]
    assert policy.consume(failed[0], ready()) is False
    assert policy.consume(current, ready()) is True


def test_show_callback_cannot_reenter_to_show_another_hint_or_consume_before_success(tmp_path):
    _, policy = make_policy(tmp_path)
    nested = []
    decisions = []

    def show(offer):
        nested.append(policy.try_offer('tools.timer', ready(), lambda _: True))
        decisions.append(policy.consume(offer, ready()))
        return True

    offer = policy.try_offer('file.export', ready(), show)
    assert nested == [None] and decisions == [False]
    assert offer is not None and policy.consume(offer, ready()) is True


@pytest.mark.parametrize('retire', ['dismiss', 'invalidate'])
def test_retirement_during_show_cannot_reactivate_the_old_signal(tmp_path, retire):
    store, policy = make_policy(tmp_path)
    captured = []

    def show(offer):
        captured.append(offer)
        if retire == 'dismiss':
            assert policy.dismiss(offer) is True
        else:
            policy.invalidate()
        return True

    assert policy.try_offer('file.export', ready(), show) is None
    assert policy.consume(captured[0], ready()) is False
    assert store.snapshot()['context_seen'] == ['file.export']
    current = policy.try_offer('tools.timer', ready(), lambda _: True)
    assert policy.consume(current, ready()) is True


def test_concurrent_show_attempt_does_not_enter_a_second_callback(tmp_path):
    _, policy = make_policy(tmp_path)
    entered, release = Event(), Event()
    captured, second_shown = [], []

    def slow_show(offer):
        captured.append(offer)
        entered.set()
        assert release.wait(timeout=5)
        return True

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(policy.try_offer, 'file.export', ready(), slow_show)
        try:
            assert entered.wait(timeout=5)
            assert policy.try_offer('tools.timer', ready(), show_into(second_shown)) is None
            assert policy.consume(captured[0], ready()) is False
        finally:
            release.set()
        offer = future.result(timeout=5)
    assert second_shown == [] and offer is captured[0]
    assert policy.consume(offer, ready()) is True



def fail_replace(*args):
    raise OSError('simulated progress file replacement failure')


def test_failed_save_keeps_store_memory_warns_once_and_allows_explicit_consume(tmp_path, monkeypatch):
    import teaching.state as state
    warnings = []
    store, policy = make_policy(tmp_path, warn=warnings.append)
    assert store.ensure_writable()
    before = store.path.read_bytes()
    shown = []
    monkeypatch.setattr(state.os, 'replace', fail_replace)

    offer = policy.try_offer('file.export', ready(), show_into(shown))
    assert offer is shown[0]
    assert store.read_only and store.last_error == 'save_failed'
    assert store.snapshot()['context_seen'] == ['file.export']
    assert store.path.read_bytes() == before and sorted(tmp_path.iterdir()) == [store.path]
    assert warnings == ['teaching_progress_save_failed']
    assert policy.consume(offer, ready()) is True
    assert policy.consume(offer, ready()) is False
    for _ in range(3):
        assert policy.try_offer('file.export', ready(), show_into(shown)) is None
        assert policy.try_offer('tools.timer', ready(), show_into(shown)) is None
    assert shown == [offer] and warnings == ['teaching_progress_save_failed']
    assert store.last_started is None and store.snapshot()['chapters'] == {}


def test_warning_is_once_even_if_the_host_retries_storage_for_another_topic(tmp_path, monkeypatch):
    import teaching.state as state
    warnings = []
    store, policy = make_policy(tmp_path, warn=warnings.append)
    monkeypatch.setattr(state.os, 'replace', fail_replace)
    first = policy.try_offer('file.export', ready(), lambda _: True)
    assert policy.consume(first, ready()) is True
    store.read_only = False
    second = policy.try_offer('tools.timer', ready(), lambda _: True)
    assert second is not None and policy.consume(second, ready()) is True
    assert store.snapshot()['context_seen'] == ['file.export', 'tools.timer']
    assert warnings == ['teaching_progress_save_failed'] and not store.path.exists()


def test_warning_callback_failure_does_not_block_consumption_or_reenter_display(tmp_path, monkeypatch):
    import teaching.state as state
    warnings, nested = [], []

    def warn(key):
        warnings.append(key)
        nested.append(policy.try_offer('tools.timer', ready(), lambda _: True))
        raise RuntimeError('host warning callback failed')

    store, policy = make_policy(tmp_path, warn=warn)
    monkeypatch.setattr(state.os, 'replace', fail_replace)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    assert offer is not None and warnings == ['teaching_progress_save_failed']
    assert nested == [None]
    assert policy.consume(offer, ready()) is True
    assert policy.consume(offer, ready()) is False
    assert store.snapshot()['context_seen'] == ['file.export']


def test_without_warning_callback_save_failure_still_allows_explicit_start(tmp_path, monkeypatch):
    import teaching.state as state
    store, policy = make_policy(tmp_path)
    monkeypatch.setattr(state.os, 'replace', fail_replace)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    assert store.read_only and offer is not None
    assert policy.consume(offer, ready()) is True


def test_save_failure_cannot_bypass_the_current_hint_switch(tmp_path, monkeypatch):
    import teaching.state as state
    store, policy = make_policy(tmp_path)
    monkeypatch.setattr(state.os, 'replace', fail_replace)
    offer = policy.try_offer('file.export', ready(), lambda _: True)
    assert store.set_context_hints_enabled(False) is False
    assert store.read_only and not store.context_hints_enabled
    assert policy.consume(offer, ready()) is False
    assert store.set_context_hints_enabled(True) is False
    assert policy.consume(offer, ready()) is True


def test_warning_can_invalidate_the_offer_without_reactivating_it(tmp_path, monkeypatch):
    import teaching.state as state
    warnings, shown = [], []

    def warn(key):
        warnings.append(key)
        policy.invalidate()

    store, policy = make_policy(tmp_path, warn=warn)
    monkeypatch.setattr(state.os, 'replace', fail_replace)
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    assert warnings == ['teaching_progress_save_failed']
    assert policy.consume(shown[0], ready()) is False
    assert store.snapshot()['context_seen'] == ['file.export']


def test_recording_exception_keeps_session_once_and_explicit_start_available(tmp_path):
    state_path = tmp_path / 'tutorial-state.json'
    full = TutorialStateStore(state_path).snapshot()
    full['context_seen'] = ['other.hint' + str(index) for index in range(2048)]
    original = json.dumps(full).encode('utf-8')
    state_path.write_bytes(original)
    warnings, shown = [], []
    store, policy = make_policy(tmp_path, warn=warnings.append)
    first = policy.try_offer('file.export', ready(), show_into(shown))
    assert first is shown[0] and policy.consume(first, ready()) is True
    assert store.should_offer_context_hint('file.export')
    assert policy.try_offer('file.export', ready(), show_into(shown)) is None
    second = policy.try_offer('tools.timer', ready(), show_into(shown))
    assert second is shown[1] and policy.consume(second, ready()) is True
    assert warnings == ['teaching_progress_save_failed']
    assert store.snapshot() == full and state_path.read_bytes() == original


def test_failed_persistence_does_not_promise_once_across_restart(tmp_path, monkeypatch):
    import teaching.state as state
    store, policy = make_policy(tmp_path)
    assert store.ensure_writable()
    with monkeypatch.context() as patch:
        patch.setattr(state.os, 'replace', fail_replace)
        offer = policy.try_offer('file.export', ready(), lambda _: True)
    assert policy.dismiss(offer) is True
    assert policy.try_offer('file.export', ready(), lambda _: True) is None
    restarted_store, restarted = make_policy(tmp_path)
    assert restarted_store.should_offer_context_hint('file.export')
    replay = restarted.try_offer('file.export', ready(), lambda _: True)
    assert replay is not None and restarted.consume(replay, ready()) is True


def test_pure_policy_does_not_load_application_gui_or_input_backends():
    import subprocess
    from pathlib import Path
    code = """
import sys
import teaching.context_hints
forbidden = ('main', 'teaching.application', 'teaching.widgets',
             'PySide6', 'PyQt6', 'keyboard', 'pynput')
assert not [name for name in sys.modules
            if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden)]
"""
    result = subprocess.run([sys.executable, '-B', '-c', code],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
