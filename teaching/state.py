# SPDX-License-Identifier: GPL-3.0-or-later
"""Atomic parent-owned learning progress; no document, roster or user content."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import uuid
from typing import Mapping

from .models import CHAPTER_STATUSES, WELCOME_DECISIONS, require_id, require_revision

MAX_STATE_BYTES = 1024 * 1024
_MAX_RECORDS = 2048
_FIELDS = {'schema_version', 'welcome', 'context_hints_enabled', 'context_seen',
           'chapters', 'last_started'}


def _empty(welcome: str = 'unseen') -> dict:
    return {'schema_version': 1, 'welcome': welcome, 'context_hints_enabled': True,
            'context_seen': [], 'chapters': {}, 'last_started': None}


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate state key')
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError('non-finite state value')


def _chapter_id(value: object) -> str:
    value = require_id(value, 'chapter id')
    if '.' not in value or not value.split('.', 1)[1]:
        raise ValueError('chapter id must include course')
    return value


def _valid_state(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ValueError('invalid state fields')
    if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
        raise ValueError('invalid state schema')
    if not isinstance(raw['welcome'], str) or raw['welcome'] not in WELCOME_DECISIONS:
        raise ValueError('invalid welcome decision')
    if type(raw['context_hints_enabled']) is not bool:
        raise ValueError('invalid hint setting')
    seen = raw['context_seen']
    if not isinstance(seen, list) or len(seen) > _MAX_RECORDS:
        raise ValueError('invalid context history')
    for item in seen:
        require_id(item, 'context id')
    if len(set(seen)) != len(seen):
        raise ValueError('duplicate context')
    chapters = raw['chapters']
    if not isinstance(chapters, dict) or len(chapters) > _MAX_RECORDS:
        raise ValueError('invalid chapter history')
    for chapter, record in chapters.items():
        _chapter_id(chapter)
        if not isinstance(record, dict) or set(record) != {
                'status', 'compat_revision', 'completed_revision', 'needs_review', 'last_attempt'}:
            raise ValueError('invalid chapter record')
        for status in ('status', 'last_attempt'):
            if not isinstance(record[status], str) or record[status] not in CHAPTER_STATUSES:
                raise ValueError('invalid chapter status')
        require_revision(record['compat_revision'])
        completed = record['completed_revision']
        if completed is not None:
            require_revision(completed)
        if type(record['needs_review']) is not bool:
            raise ValueError('invalid review status')
        if record['status'] == 'completed' and completed != record['compat_revision']:
            raise ValueError('completion must match compatible revision')
        if record['needs_review'] and (completed is None or completed == record['compat_revision']):
            raise ValueError('invalid review revision')
    last = raw['last_started']
    if last is not None:
        if not isinstance(last, dict) or set(last) != {'course_id', 'chapter_id'}:
            raise ValueError('invalid last chapter')
        require_id(last['course_id'], 'course id')
        chapter = _chapter_id(last['chapter_id'])
        if chapter.split('.', 1)[0] != last['course_id']:
            raise ValueError('inconsistent last chapter')
    return copy.deepcopy(raw)


class TutorialStateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).absolute()
        self.read_only = False
        self.last_error: str | None = None
        self._data = _empty()
        self._load()

    @property
    def welcome(self) -> str:
        return self._data['welcome']

    @property
    def context_hints_enabled(self) -> bool:
        return self._data['context_hints_enabled']

    @property
    def last_started(self) -> dict | None:
        return copy.deepcopy(self._data['last_started'])

    def snapshot(self) -> dict:
        return copy.deepcopy(self._data)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open('rb') as stream:
                raw_bytes = stream.read(MAX_STATE_BYTES + 1)
        except OSError:
            self.read_only, self.last_error = True, 'read_failed'
            self._data = _empty('dismissed')
            return
        if len(raw_bytes) > MAX_STATE_BYTES:
            # Never replace the full file with a backup of only its read prefix.
            self.read_only, self.last_error = True, 'state_too_large'
            self._data = _empty('dismissed')
            return
        try:
            raw = json.loads(raw_bytes.decode('utf-8-sig'), object_pairs_hook=_pairs,
                             parse_constant=_reject_constant)
            if (isinstance(raw, dict) and type(raw.get('schema_version')) is int
                    and raw['schema_version'] > 1):
                self.read_only, self.last_error = True, 'unsupported_schema'
                self._data = _empty('dismissed')
                return
            self._data = _valid_state(raw)
        except (ValueError, UnicodeError, RecursionError):
            # Copy the exact invalid bytes before replacing the original. If the
            # copy fails, leave it untouched and remain usable in memory only.
            backup = self.path.with_name(self.path.name + '.corrupt.' + uuid.uuid4().hex)
            self._data = _empty('dismissed')
            try:
                with backup.open('xb') as stream:
                    stream.write(raw_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                self.read_only = True
            if not self.read_only:
                self._persist()
            self.last_error = 'corrupt_state'

    def _persist(self, candidate: dict | None = None) -> bool:
        candidate = self._data if candidate is None else candidate
        if self.read_only:
            # An actual disk write error retains valid session-only progress.
            # Unknown/future/corrupt input is different: never replace its safe
            # read-only view with newly asserted completion or welcome choices.
            if self.last_error == 'save_failed':
                self._data = candidate
            return False
        temporary: str | None = None
        try:
            data = json.dumps(candidate, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':'), sort_keys=True).encode('utf-8')
            if len(data) > MAX_STATE_BYTES:
                raise ValueError('state size exceeded')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.' + self.path.name + '.',
                                                     suffix='.tmp', dir=self.path.parent)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self._data = candidate
            return True
        except (OSError, ValueError):
            self._data = candidate
            self.read_only, self.last_error = True, 'save_failed'
            return False
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass  # Only our uniquely created temp file; never delete others.

    def prepare_welcome(self) -> bool:
        return self.welcome == 'unseen' and not self.read_only and self._persist()

    def ensure_writable(self) -> bool:
        """Atomically confirm persistence without changing learning decisions.

        Called once at a safe first-welcome boundary, not on every readiness poll.
        A failed write preserves the original file and disables automatic welcome.
        """
        return self._persist(copy.deepcopy(self._data))

    def set_welcome(self, decision: str) -> bool:
        if not isinstance(decision, str) or decision not in WELCOME_DECISIONS:
            raise ValueError('invalid welcome decision')
        candidate = copy.deepcopy(self._data)
        candidate['welcome'] = decision
        return self._persist(candidate)

    def chapter_record(self, chapter_id: str) -> dict:
        _chapter_id(chapter_id)
        return copy.deepcopy(self._data['chapters'].get(chapter_id, {
            'status': 'not_started', 'compat_revision': 1, 'completed_revision': None,
            'needs_review': False, 'last_attempt': 'not_started',
        }))

    def chapter_status(self, chapter_id: str) -> str:
        return self.chapter_record(chapter_id)['status']

    def completed_count(self) -> int:
        return sum(record['status'] == 'completed' and not record['needs_review']
                   for record in self._data['chapters'].values())

    def record_chapter(self, chapter_id: str, status: str, *, compat_revision: int) -> bool:
        _chapter_id(chapter_id)
        require_revision(compat_revision)
        if not isinstance(status, str) or status not in CHAPTER_STATUSES:
            raise ValueError('invalid chapter status')
        if chapter_id not in self._data['chapters'] and len(self._data['chapters']) >= _MAX_RECORDS:
            raise ValueError('chapter history full')
        record = self.chapter_record(chapter_id)
        record['compat_revision'] = compat_revision
        record['last_attempt'] = status
        if status == 'completed':
            record['completed_revision'] = compat_revision
        completed = record['completed_revision']
        record['needs_review'] = completed is not None and completed != compat_revision
        # A skipped/incomplete replay does not erase proven compatible completion.
        record['status'] = 'completed' if completed == compat_revision else status
        candidate = copy.deepcopy(self._data)
        candidate['chapters'][chapter_id] = record
        candidate['last_started'] = {'course_id': chapter_id.split('.', 1)[0], 'chapter_id': chapter_id}
        return self._persist(candidate)

    def sync_catalog(self, chapter_revisions: Mapping[str, int]) -> bool:
        validated = {}
        for chapter_id, revision in chapter_revisions.items():
            validated[_chapter_id(chapter_id)] = require_revision(revision)
        candidate = copy.deepcopy(self._data)
        changed = False
        for chapter_id, revision in validated.items():
            record = candidate['chapters'].get(chapter_id)
            if record is None or record['compat_revision'] == revision:
                continue
            record['compat_revision'] = revision
            record['needs_review'] = (record['completed_revision'] is not None
                                      and record['completed_revision'] != revision)
            record['status'] = ('completed' if record['completed_revision'] == revision else 'not_started')
            changed = True
        return self._persist(candidate) if changed else not self.read_only

    def should_offer_context_hint(self, context_id: str) -> bool:
        require_id(context_id, 'context id')
        return (self.context_hints_enabled and not self.read_only
                and context_id not in self._data['context_seen'])

    def mark_context_seen(self, context_id: str) -> bool:
        require_id(context_id, 'context id')
        candidate = copy.deepcopy(self._data)
        if context_id not in candidate['context_seen']:
            if len(candidate['context_seen']) >= _MAX_RECORDS:
                raise ValueError('context history full')
            candidate['context_seen'].append(context_id)
            candidate['context_seen'].sort()
        return self._persist(candidate)

    def set_context_hints_enabled(self, enabled: bool) -> bool:
        if type(enabled) is not bool:
            raise ValueError('hint setting must be boolean')
        candidate = copy.deepcopy(self._data)
        candidate['context_hints_enabled'] = enabled
        return self._persist(candidate)

    def reset(self, *, show_welcome: bool = False) -> bool:
        if type(show_welcome) is not bool:
            raise ValueError('welcome option must be boolean')
        hints = self.context_hints_enabled
        candidate = _empty('unseen' if show_welcome else 'dismissed')
        candidate['context_hints_enabled'] = hints
        return self._persist(candidate)
