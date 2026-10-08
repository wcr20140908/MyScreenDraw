# SPDX-License-Identifier: GPL-3.0-or-later
"""Learning history must not conflate skipping, replay and actual completion."""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path):
    from teaching.state import TutorialStateStore
    return TutorialStateStore(tmp_path / 'tutorial-state.json')


def test_missing_state_allows_once_only_welcome(store):
    from teaching.state import TutorialStateStore
    assert store.welcome == 'unseen'
    assert store.prepare_welcome() is True
    assert store.set_welcome('accepted') is True
    restored = TutorialStateStore(store.path)
    assert restored.welcome == 'accepted'
    assert restored.prepare_welcome() is False


@pytest.mark.parametrize('decision', ['accepted', 'skipped', 'dismissed'])
def test_welcome_decision_is_not_repeated(store, decision):
    from teaching.state import TutorialStateStore
    store.set_welcome(decision)
    assert TutorialStateStore(store.path).prepare_welcome() is False


def test_skipping_is_not_completion(store):
    store.record_chapter('c01.ink', 'skipped', compat_revision=1)
    assert store.completed_count() == 0
    assert store.chapter_status('c01.ink') == 'skipped'


def test_progress_and_last_started_survive_restart(store):
    from teaching.state import TutorialStateStore
    store.record_chapter('c01.ink', 'in_progress', compat_revision=1)
    restored = TutorialStateStore(store.path)
    assert restored.chapter_status('c01.ink') == 'in_progress'
    assert restored.last_started == {'course_id': 'c01', 'chapter_id': 'c01.ink'}
    assert restored.completed_count() == 0


def test_replay_does_not_remove_completed_history(store):
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    store.record_chapter('c01.ink', 'in_progress', compat_revision=1)
    store.record_chapter('c01.ink', 'skipped', compat_revision=1)
    assert store.completed_count() == 1
    assert store.chapter_status('c01.ink') == 'completed'
    assert store.chapter_record('c01.ink')['last_attempt'] == 'skipped'


def test_compat_revision_requires_review_but_keeps_history(store):
    store.set_welcome('accepted')
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    store.sync_catalog({'c01.ink': 2})
    assert store.completed_count() == 0
    assert store.chapter_record('c01.ink')['completed_revision'] == 1
    assert store.chapter_record('c01.ink')['needs_review'] is True
    assert store.prepare_welcome() is False
    store.record_chapter('c01.ink', 'completed', compat_revision=2)
    assert store.completed_count() == 1


def test_same_revision_and_new_course_do_not_reset(store):
    store.set_welcome('accepted')
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    store.sync_catalog({'c01.ink': 1, 'c02.styles': 1})
    assert store.completed_count() == 1
    assert store.chapter_status('c02.styles') == 'not_started'
    assert store.prepare_welcome() is False


def test_context_hint_is_once_only_and_switchable(store):
    assert store.should_offer_context_hint('file.export')
    store.mark_context_seen('file.export')
    assert not store.should_offer_context_hint('file.export')
    store.set_context_hints_enabled(False)
    assert not store.should_offer_context_hint('tools.timer')


def test_reset_requires_explicit_welcome_opt_in(store):
    store.set_welcome('accepted')
    store.set_context_hints_enabled(False)
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    store.reset()
    assert store.completed_count() == 0
    assert not store.prepare_welcome()
    assert not store.context_hints_enabled
    store.reset(show_welcome=True)
    assert store.prepare_welcome()


@pytest.mark.parametrize('data', [b'{broken', b'[]', b'{"schema_version":true}',
    b'{"schema_version":1,"welcome":"unseen","welcome":"accepted"}',
    b'{"schema_version":1,"welcome":"unseen","extra":"script"}',
])
def test_corrupt_state_is_preserved_and_does_not_repeat_welcome(tmp_path, data):
    from teaching.state import TutorialStateStore
    path = tmp_path / 'tutorial-state.json'
    path.write_bytes(data)
    store = TutorialStateStore(path)
    assert store.prepare_welcome() is False
    backups = list(tmp_path.glob('tutorial-state.json.corrupt.*'))
    assert len(backups) == 1
    assert backups[0].read_bytes() == data
    assert store.welcome == 'dismissed'
    assert store.last_error == 'corrupt_state'


def test_unknown_future_schema_is_not_overwritten(tmp_path):
    from teaching.state import TutorialStateStore
    path = tmp_path / 'tutorial-state.json'
    original = b'{"schema_version":99,"future_private_field":"preserve"}'
    path.write_bytes(original)
    store = TutorialStateStore(path)
    assert store.read_only
    assert not store.prepare_welcome()
    assert store.set_welcome('accepted') is False
    assert path.read_bytes() == original
    assert not list(tmp_path.glob('*.corrupt.*'))


def test_write_failure_keeps_memory_state_and_does_not_damage_disk(store, monkeypatch):
    store.set_welcome('accepted')
    before = store.path.read_bytes()
    def fail_replace(*args):
        raise PermissionError('synthetic failure')
    monkeypatch.setattr(os, 'replace', fail_replace)
    assert store.record_chapter('c01.ink', 'completed', compat_revision=1) is False
    assert store.completed_count() == 1
    assert store.path.read_bytes() == before
    assert not list(store.path.parent.glob('*.tmp'))
    assert not store.prepare_welcome()
    assert store.last_error == 'save_failed'


def test_first_welcome_is_not_shown_when_initial_write_fails(store, monkeypatch):
    def fail_replace(*args):
        raise PermissionError('synthetic failure')
    monkeypatch.setattr(os, 'replace', fail_replace)
    assert store.prepare_welcome() is False
    assert store.read_only


@pytest.mark.parametrize('args', [
    ('../escape', 'completed', 1), ('c01.ink', 'completed', True),
    ('c01.ink', 'completed', 0), ('c01.ink', 'unknown', 1),
])
def test_invalid_progress_is_rejected_before_write(store, args):
    before = store.path.exists()
    with pytest.raises(ValueError):
        store.record_chapter(args[0], args[1], compat_revision=args[2])
    assert store.path.exists() == before


def test_state_accessors_return_copies(store):
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    record = store.chapter_record('c01.ink')
    record['status'] = 'skipped'
    started = store.last_started
    started['chapter_id'] = 'c01.changed'
    assert store.chapter_status('c01.ink') == 'completed'
    assert store.last_started['chapter_id'] == 'c01.ink'


def test_state_serialization_has_no_document_or_roster_data(store):
    store.record_chapter('c01.ink', 'completed', compat_revision=1)
    keys = set(json.loads(store.path.read_text(encoding='utf-8')))
    assert keys == {'schema_version', 'welcome', 'context_hints_enabled',
                    'context_seen', 'chapters', 'last_started'}


def test_oversized_state_is_left_intact_not_truncated(tmp_path):
    from teaching.state import MAX_STATE_BYTES, TutorialStateStore
    path = tmp_path / 'tutorial-state.json'
    original = b'x' * (MAX_STATE_BYTES + 100)
    path.write_bytes(original)
    store = TutorialStateStore(path)
    assert store.read_only
    assert store.last_error == 'state_too_large'
    assert not store.prepare_welcome()
    assert path.read_bytes() == original
    assert not list(tmp_path.glob('*.corrupt.*'))


_MUTATIONS = [
    lambda value:value.set_welcome('skipped'),
    lambda value:value.record_chapter('c02.edit','completed',compat_revision=1),
    lambda value:value.sync_catalog({'c01.ink':2}),
    lambda value:value.mark_context_seen('file.save'),
    lambda value:value.set_context_hints_enabled(False),
    lambda value:value.reset(show_welcome=True),
]


@pytest.mark.parametrize('mutate',_MUTATIONS,ids=['welcome','chapter','compatibility','context','hints','reset'])
def test_failed_atomic_write_retains_valid_memory_progress_but_never_damages_disk(store,monkeypatch,mutate):
    store.set_welcome('accepted')
    store.record_chapter('c01.ink','completed',compat_revision=1)
    before=store.snapshot()
    disk=store.path.read_bytes()
    def denied(*args,**kwargs):
        raise OSError('controlled replacement failure')
    monkeypatch.setattr('teaching.state.os.replace',denied)
    assert mutate(store) is False
    assert store.read_only
    assert store.snapshot()!=before
    retained=store.snapshot()
    assert store.last_error=='save_failed'
    assert store.path.read_bytes()==disk
    assert not list(store.path.parent.glob('.tutorial-state.json.*.tmp'))
    # The approved plan keeps valid session progress after a disk error.
    # Repeating an idempotent change stays memory-only and cannot damage disk.
    assert mutate(store) is False
    assert store.snapshot()==retained
    assert store.path.read_bytes()==disk


@pytest.mark.parametrize('mutate',_MUTATIONS,ids=['welcome','chapter','compatibility','context','hints','reset'])
def test_future_schema_read_only_attempts_never_change_memory_or_disk(tmp_path,mutate):
    from teaching.state import TutorialStateStore
    path=tmp_path/'future.json'
    original=b'{"schema_version":99,"private":"leave intact"}'
    path.write_bytes(original)
    value=TutorialStateStore(path)
    before=value.snapshot()
    assert mutate(value) is False
    assert value.snapshot()==before
    assert path.read_bytes()==original
