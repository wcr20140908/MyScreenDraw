# SPDX-License-Identifier: GPL-3.0-or-later
"""First-use policy never commits edits or decides on behalf of the user."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from teaching.state import TutorialStateStore


def ready():
    from teaching.onboarding import TeachingReadiness
    return TeachingReadiness(lifecycle_ready=True, restore_finished=True, layout_ready=True,
                             foreground=True, application_visible=True)


def make_policy(tmp_path, **kwargs):
    from teaching.onboarding import WelcomePolicy
    store = TutorialStateStore(tmp_path / 'tutorial-state.json')
    return store, WelcomePolicy(store, **kwargs)


def test_new_user_is_offered_once_only_after_all_startup_work_is_ready(tmp_path):
    from teaching.onboarding import TeachingReadiness
    store, policy = make_policy(tmp_path)
    assert not policy.claim_welcome(TeachingReadiness())
    assert not store.path.exists()
    assert policy.claim_welcome(ready())
    assert store.welcome == 'unseen'
    assert not policy.claim_welcome(ready())


@pytest.mark.parametrize('field,value', [
    ('lifecycle_ready', False), ('restore_finished', False), ('layout_ready', False),
    ('foreground', False), ('application_visible', False), ('modal_active', True),
    ('gesture_active', True), ('composition_active', True), ('text_edit_active', True),
    ('file_operation_active', True), ('practice_active', True),
])
def test_busy_or_background_user_is_deferred_without_writes(tmp_path, field, value):
    store, policy = make_policy(tmp_path)
    busy = replace(ready(), **{field: value})
    assert not busy.safe
    assert not policy.claim_welcome(busy)
    assert not store.path.exists() and store.welcome == 'unseen'
    assert policy.claim_welcome(ready())


@pytest.mark.parametrize('decision', ['accepted', 'skipped', 'dismissed'])
def test_explicit_decision_is_separate_from_completion_and_survives_restart(tmp_path, decision):
    store, policy = make_policy(tmp_path)
    starts = []
    assert policy.claim_welcome(ready())
    result = policy.decide(decision, start_core=lambda: starts.append((store.welcome, store.path.read_bytes())))
    assert result.decision == decision and result.persisted
    assert store.welcome == decision and store.completed_count() == 0
    assert len(starts) == (1 if decision == 'accepted' else 0)
    if starts:
        assert starts[0][0] == 'accepted'
        assert json.loads(starts[0][1])['welcome'] == 'accepted'
    assert policy.decide('accepted', start_core=lambda: starts.append('duplicate')) is None
    store, restarted = make_policy(tmp_path)
    assert not restarted.claim_welcome(ready())


def test_failed_practice_launch_keeps_accepted_welcome_without_false_completion(tmp_path):
    store, policy = make_policy(tmp_path)
    assert policy.claim_welcome(ready())
    def fail():
        raise RuntimeError('practice not yet available')
    with pytest.raises(RuntimeError, match='not yet available'):
        policy.decide('accepted', start_core=fail)
    assert store.welcome == 'accepted' and store.completed_count() == 0
    assert not make_policy(tmp_path)[1].claim_welcome(ready())


@pytest.mark.parametrize('args,practice,automated', [
    (['--smoke'], False, False), (['--smoke-ui'], False, False),
    (['--smoke-ui=basic'], False, False), (['--teaching-practice'], False, False),
    ([], True, False), ([], False, True),
])
def test_smoke_practice_and_automation_never_offer_or_record_welcome(tmp_path, args, practice, automated):
    from teaching.onboarding import TeachingStartupContext
    context = TeachingStartupContext.from_arguments(args, practice=practice, automated=automated)
    store, policy = make_policy(tmp_path, context=context)
    assert not policy.claim_welcome(ready())
    assert policy.decide('accepted') is None
    assert not store.path.exists() and store.welcome == 'unseen'


def test_unknown_future_state_is_preserved_and_manual_center_can_still_open(tmp_path):
    path = tmp_path / 'tutorial-state.json'
    original = b'{"schema_version":999,"private_future_field":"untouched"}'
    path.write_bytes(original)
    store, policy = make_policy(tmp_path)
    assert not policy.claim_welcome(ready())
    assert policy.can_open_center(ready())
    assert policy.decide('accepted') is None
    assert path.read_bytes() == original and store.read_only


def test_unwritable_valid_state_suppresses_automatic_offer_before_it_is_shown(tmp_path, monkeypatch):
    import teaching.state as state
    store, policy = make_policy(tmp_path)
    def fail(*args):
        raise OSError('simulated unwritable progress path')
    monkeypatch.setattr(state.os, 'replace', fail)
    assert not policy.claim_welcome(ready())
    assert store.read_only and store.last_error == 'save_failed'
    assert store.welcome == 'unseen' and not store.path.exists()
    assert policy.can_open_center(ready())
    assert not list(tmp_path.glob('*.tmp'))


def test_write_failure_after_offer_keeps_memory_decision_warns_once_and_allows_manual_practice(tmp_path, monkeypatch):
    import teaching.state as state
    warnings, starts = [], []
    store, policy = make_policy(tmp_path, warn=warnings.append)
    assert policy.claim_welcome(ready())
    before = store.path.read_bytes()
    def fail(*args):
        raise OSError('simulated decision write failure')
    monkeypatch.setattr(state.os, 'replace', fail)
    result = policy.decide('accepted', start_core=lambda: starts.append(store.welcome))
    assert result.decision == 'accepted' and not result.persisted
    assert store.welcome == 'accepted' and store.path.read_bytes() == before
    assert starts == ['accepted'] and warnings == ['teaching_progress_save_failed']
    assert policy.decide('dismissed') is None
    assert warnings == ['teaching_progress_save_failed']


def test_decision_and_warning_callbacks_cannot_reenter_to_start_twice(tmp_path, monkeypatch):
    import teaching.state as state
    starts = []
    def warn(key):
        assert policy.decide('accepted', start_core=lambda: starts.append('duplicate')) is None
        raise RuntimeError('nonblocking warning failed')
    store, policy = make_policy(tmp_path, warn=warn)
    assert policy.claim_welcome(ready())
    def fail(*args):
        raise OSError('simulated write failure')
    monkeypatch.setattr(state.os, 'replace', fail)
    policy.decide('accepted', start_core=lambda: starts.append('accepted'))
    assert starts == ['accepted']


def test_manual_entry_uses_same_readiness_without_requiring_persistable_state(tmp_path):
    store, policy = make_policy(tmp_path)
    assert policy.can_open_center(ready())
    assert not policy.can_open_center(replace(ready(), text_edit_active=True))
    assert not store.path.exists()


def test_explicit_reset_controls_future_welcome_but_content_revisions_do_not(tmp_path):
    store, policy = make_policy(tmp_path)
    assert policy.claim_welcome(ready())
    policy.decide('skipped')
    store.sync_catalog({'c01.intro': 8})
    assert not make_policy(tmp_path)[1].claim_welcome(ready())
    store.reset(show_welcome=False)
    assert not make_policy(tmp_path)[1].claim_welcome(ready())
    store.reset(show_welcome=True)
    assert make_policy(tmp_path)[1].claim_welcome(ready())


@pytest.mark.parametrize('decision', ['unseen', 'completed', '', None])
def test_invalid_welcome_decision_cannot_mutate_state(tmp_path, decision):
    store, policy = make_policy(tmp_path)
    assert policy.claim_welcome(ready())
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        policy.decide(decision)
    assert store.path.read_bytes() == before and store.welcome == 'unseen'


def test_readiness_rejects_truthy_non_boolean_flags():
    from teaching.onboarding import TeachingReadiness
    with pytest.raises(ValueError):
        TeachingReadiness(lifecycle_ready='false')
