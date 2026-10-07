# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict offline course loading; JSON provides data, never executable code."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

from .models import (Branch, END_CHAPTER, OUTCOMES, TutorialCatalog, TutorialChapter,
                     TutorialCourse, TutorialGroup, TutorialStep, WaitClause, WaitSpec,
                     is_scalar, require_id, require_revision)

MAX_JSON_BYTES = 2 * 1024 * 1024
REVEAL_ACTIONS = frozenset({
    'expand_toolbar', 'open_pen_panel', 'open_eraser_panel', 'open_select_panel',
    'open_text_panel', 'open_shape_panel', 'open_tools_panel', 'open_file_panel',
    'open_aid_panel', 'open_settings', 'open_settings_document', 'open_settings_display',
    'open_teaching_center', 'show_pages', 'scroll_target',
})
CONDITIONS = frozenset({'touch_available', 'multiple_monitors', 'pdf_available',
                        'ui_mode', 'tool', 'document_type', 'chapter_completed'})


def _object(value: object, allowed: set[str], required: set[str], label: str) -> dict:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - allowed:
        raise ValueError(f'invalid {label} fields')
    return value


def _list(value: object, maximum: int, label: str, *, empty: bool = False) -> list:
    if not isinstance(value, list) or len(value) > maximum or (not empty and not value):
        raise ValueError(f'invalid {label} list')
    return value


def _unique(items: list[str], label: str) -> None:
    if len(set(items)) != len(items):
        raise ValueError(f'duplicate {label}')


def _json_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError('non-finite JSON value')


class CatalogLoader:
    def __init__(self, root: Path, *, string_keys: set[str], target_ids: set[str],
                 event_names: set[str], fixtures: Mapping[str, str] | None = None) -> None:
        self.root = Path(root).resolve()
        self.string_keys = frozenset(string_keys)
        self.target_ids = frozenset(target_ids)
        self.event_names = frozenset(event_names)
        self.fixtures = dict(fixtures or {})

    def asset_path(self, relative: object) -> Path:
        if (not isinstance(relative, str) or not relative
                or PureWindowsPath(relative).drive or '\\' in relative
                or PurePosixPath(relative).is_absolute()):
            raise ValueError('asset outside resource root')
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('asset outside resource root')
        if not path.is_file():
            raise ValueError('asset does not exist')
        return path

    def _read_json(self, relative: str) -> dict:
        with self.asset_path(relative).open('rb') as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise ValueError('JSON resource size exceeded')
        try:
            value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_json_pairs,
                               parse_constant=_reject_constant)
        except (UnicodeError, RecursionError) as exc:
            raise ValueError('invalid JSON resource') from exc
        if not isinstance(value, dict):
            raise ValueError('JSON resource must be an object')
        return value

    def _key(self, key: object) -> str:
        if not isinstance(key, str) or key not in self.string_keys:
            raise ValueError('unknown language key')
        return key

    def _wait_clause(self, raw: object) -> WaitClause:
        raw = _object(raw, {'event', 'outcome', 'equals', 'min_count'},
                      {'event', 'outcome'}, 'wait')
        if not isinstance(raw['event'], str) or raw['event'] not in self.event_names:
            raise ValueError('unknown event')
        if not isinstance(raw['outcome'], str) or raw['outcome'] not in OUTCOMES:
            raise ValueError('unknown outcome')
        equals = raw.get('equals', {})
        minimum = raw.get('min_count', {})
        if not isinstance(equals, dict) or len(equals) > 32:
            raise ValueError('invalid equals predicate')
        if not isinstance(minimum, dict) or len(minimum) > 32:
            raise ValueError('invalid min_count predicate')
        for key, value in equals.items():
            require_id(key, 'predicate key')
            if not is_scalar(value) or (isinstance(value, str) and len(value) > 2048):
                raise ValueError('invalid equals value')
        for key, value in minimum.items():
            require_id(key, 'predicate key')
            if type(value) not in (int, float) or not is_scalar(value) or value < 0:
                raise ValueError('invalid min_count value')
        return WaitClause(raw['event'], raw['outcome'], equals, minimum)

    def _wait(self, raw: object) -> WaitSpec:
        if isinstance(raw, dict) and 'sequence' in raw:
            _object(raw, {'sequence'}, {'sequence'}, 'sequence')
            clauses = tuple(self._wait_clause(item)
                            for item in _list(raw['sequence'], 16, 'sequence'))
        else:
            clauses = (self._wait_clause(raw),)
        return WaitSpec(clauses)

    def _step(self, raw: object, default_next: str) -> TutorialStep:
        allowed = {'id', 'title_key', 'body_key', 'kind', 'target', 'input_policy',
                   'reveal', 'allowed_targets', 'wait', 'next', 'branches', 'hero_image'}
        raw = _object(raw, allowed, {'id', 'title_key', 'body_key'}, 'step')
        step_id = require_id(raw['id'], 'step id')
        if step_id == END_CHAPTER:
            raise ValueError('reserved step id')
        kind = raw.get('kind', 'operation' if 'wait' in raw else 'information')
        if kind not in ('information', 'operation'):
            raise ValueError('invalid step kind')
        wait = self._wait(raw.get('wait')) if kind == 'operation' else None
        if kind == 'information' and 'wait' in raw:
            raise ValueError('information step cannot wait for an operation')
        target = raw.get('target')
        if target is not None and (not isinstance(target, str) or target not in self.target_ids):
            raise ValueError('unknown target')
        policy = raw.get('input_policy', 'free')
        if policy not in ('free', 'target_only', 'canvas') or (policy == 'target_only' and target is None):
            raise ValueError('invalid input policy')
        reveal = _list(raw.get('reveal', []), 16, 'reveal', empty=True)
        if any(not isinstance(action, str) or action not in REVEAL_ACTIONS for action in reveal):
            raise ValueError('unknown reveal action')
        targets = _list(raw.get('allowed_targets', []), 16, 'targets', empty=True)
        if any(not isinstance(item, str) or item not in self.target_ids for item in targets):
            raise ValueError('unknown allowed target')
        branches = []
        for branch in _list(raw.get('branches', []), 16, 'branches', empty=True):
            branch = _object(branch, {'condition', 'equals', 'next', 'argument'},
                             {'condition', 'equals', 'next'}, 'branch')
            condition = branch['condition']
            if not isinstance(condition, str) or condition not in CONDITIONS or not is_scalar(branch['equals']):
                raise ValueError('invalid branch condition')
            argument = branch.get('argument')
            if condition == 'chapter_completed':
                require_id(argument, 'chapter condition argument')
            elif argument is not None:
                raise ValueError('unexpected condition argument')
            branches.append(Branch(condition, branch['equals'], require_id(branch['next'], 'jump'), argument))
        image = raw.get('hero_image')
        if image is not None:
            self.asset_path(image)
        return TutorialStep(step_id, self._key(raw['title_key']), self._key(raw['body_key']),
                            kind, target, policy, tuple(reveal), tuple(targets), wait,
                            require_id(raw.get('next', default_next), 'jump'), tuple(branches), image)

    @staticmethod
    def _validate_graph(steps: tuple[TutorialStep, ...]) -> None:
        ids = {step.id for step in steps}
        edges = {step.id: {step.next, *(branch.next for branch in step.branches)} for step in steps}
        if any(destination not in ids and destination != END_CHAPTER
               for destinations in edges.values() for destination in destinations):
            raise ValueError('dangling jump')
        reachable = set()
        pending = [steps[0].id]
        while pending:
            node = pending.pop()
            if node == END_CHAPTER or node in reachable:
                continue
            reachable.add(node)
            pending.extend(edges[node])
        if reachable != ids:
            raise ValueError('unreachable step')
        # Courses are acyclic; user-operated Previous is a separate engine action.
        visiting, finished = set(), set()
        def visit(node: str) -> None:
            if node == END_CHAPTER or node in finished:
                return
            if node in visiting:
                raise ValueError('cycle cannot safely reach end')
            visiting.add(node)
            for destination in edges[node]:
                visit(destination)
            visiting.remove(node)
            finished.add(node)
        visit(steps[0].id)

    def validate(self, raw: object) -> TutorialCourse:
        raw = _object(raw, {'schema_version', 'id', 'revision', 'compat_revision', 'title_key', 'chapters'},
                      {'schema_version', 'id', 'revision', 'compat_revision', 'title_key', 'chapters'}, 'course')
        if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
            raise ValueError('unsupported course schema')
        course_id = require_id(raw['id'], 'course id')
        if '.' in course_id:
            raise ValueError('invalid course id')
        title = self._key(raw['title_key'])
        revision, compat = require_revision(raw['revision']), require_revision(raw['compat_revision'])
        chapters = []
        for chapter in _list(raw['chapters'], 128, 'chapters'):
            chapter = _object(chapter, {'id', 'title_key', 'fixture', 'steps'}, {'id', 'fixture', 'steps'}, 'chapter')
            chapter_id = require_id(chapter['id'], 'chapter id')
            if not chapter_id.startswith(course_id + '.'):
                raise ValueError('chapter id must belong to course')
            fixture = chapter['fixture']
            if not isinstance(fixture, str) or fixture not in self.fixtures:
                raise ValueError('unknown fixture')
            self.asset_path(self.fixtures[fixture])
            raw_steps = _list(chapter['steps'], 256, 'steps')
            steps = tuple(self._step(item, raw_steps[index + 1].get('id', '')
                                    if index + 1 < len(raw_steps) and isinstance(raw_steps[index + 1], dict)
                                    else END_CHAPTER) for index, item in enumerate(raw_steps))
            _unique([step.id for step in steps], 'step id')
            self._validate_graph(steps)
            chapters.append(TutorialChapter(chapter_id, self._key(chapter.get('title_key', title)), fixture, steps))
        _unique([chapter.id for chapter in chapters], 'chapter id')
        return TutorialCourse(course_id, revision, compat, title, tuple(chapters))

    def load(self, index: str = 'catalog.json') -> TutorialCatalog:
        raw = _object(self._read_json(index), {'schema_version', 'courses', 'groups', 'fixtures'},
                      {'schema_version', 'courses', 'groups'}, 'catalog')
        if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
            raise ValueError('unsupported catalog schema')
        if 'fixtures' in raw:
            fixtures = raw['fixtures']
            if not isinstance(fixtures, dict) or len(fixtures) > 128:
                raise ValueError('invalid fixtures')
            for name, path in fixtures.items():
                require_id(name, 'fixture id')
                self.asset_path(path)
            self.fixtures = dict(fixtures)
        courses = tuple(self.validate(self._read_json(path)) for path in _list(raw['courses'], 128, 'courses'))
        ids = [course.id for course in courses]
        _unique(ids, 'course id')
        groups = []
        assigned = []
        for group in _list(raw['groups'], 32, 'groups'):
            group = _object(group, {'id', 'title_key', 'courses'}, {'id', 'title_key', 'courses'}, 'group')
            members = _list(group['courses'], 128, 'group courses')
            if any(not isinstance(member, str) or member not in ids for member in members):
                raise ValueError('unknown group course')
            assigned.extend(members)
            groups.append(TutorialGroup(require_id(group['id'], 'group id'), self._key(group['title_key']), tuple(members)))
        _unique([group.id for group in groups], 'group id')
        _unique(assigned, 'group course')
        if set(assigned) != set(ids):
            raise ValueError('ungrouped course')
        catalog = TutorialCatalog(courses, tuple(groups))
        chapter_ids = {chapter.id for course in courses for chapter in course.chapters}
        for step in catalog.all_steps():
            for branch in step.branches:
                if branch.condition == 'chapter_completed' and branch.argument not in chapter_ids:
                    raise ValueError('unknown chapter condition')
        return catalog
