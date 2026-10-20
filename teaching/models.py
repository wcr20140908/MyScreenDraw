# SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable validated teaching data, independent of Qt and application state."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from types import MappingProxyType
from typing import Iterator, Literal, Mapping

Outcome = Literal['success', 'cancelled', 'failed', 'partial']
ChapterStatus = Literal['not_started', 'in_progress', 'completed', 'skipped']
Scalar = str | int | float | bool | None
OUTCOMES = frozenset({'success', 'cancelled', 'failed', 'partial'})
CHAPTER_STATUSES = frozenset({'not_started', 'in_progress', 'completed', 'skipped'})
WELCOME_DECISIONS = frozenset({'unseen', 'accepted', 'skipped', 'dismissed'})
END_CHAPTER = 'end_chapter'
_IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,127}\Z')


def require_id(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f'invalid {label}')
    return value


def require_revision(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError('invalid revision')
    return value


def is_scalar(value: object) -> bool:
    return (value is None or type(value) in (str, bool)
            or (type(value) is int and -(2 ** 63) <= value < 2 ** 63)
            or (type(value) is float and math.isfinite(value)))


def scalar_equal(actual: object, expected: Scalar) -> bool:
    # Do not treat True as one page, or False as a zero-valued setting.
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


@dataclass(frozen=True)
class WaitClause:
    event: str
    outcome: Outcome
    equals: Mapping[str, Scalar] = field(default_factory=dict)
    min_count: Mapping[str, int | float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'equals', MappingProxyType(dict(self.equals)))
        object.__setattr__(self, 'min_count', MappingProxyType(dict(self.min_count)))

    def matches(self, event: TutorialEvent) -> bool:
        if event.name != self.event or event.outcome != self.outcome:
            return False
        if any(key not in event.details or not scalar_equal(event.details[key], value)
               for key, value in self.equals.items()):
            return False
        for key, minimum in self.min_count.items():
            value = event.details.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
                return False
        return True


@dataclass(frozen=True)
class WaitSpec:
    clauses: tuple[WaitClause, ...]


@dataclass(frozen=True)
class Branch:
    condition: str
    equals: Scalar
    next: str
    argument: str | None = None


@dataclass(frozen=True)
class TutorialStep:
    id: str
    title_key: str
    body_key: str
    kind: Literal['information', 'operation']
    target: str | None
    input_policy: Literal['free', 'target_only', 'canvas']
    reveal: tuple[str, ...]
    allowed_targets: tuple[str, ...]
    wait: WaitSpec | None
    next: str
    branches: tuple[Branch, ...] = ()
    hero_image: str | None = None


@dataclass(frozen=True)
class TutorialChapter:
    id: str
    title_key: str
    fixture: str
    steps: tuple[TutorialStep, ...]

    def step_by_id(self, step_id: str) -> TutorialStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(step_id)


@dataclass(frozen=True)
class TutorialCourse:
    id: str
    revision: int
    compat_revision: int
    title_key: str
    chapters: tuple[TutorialChapter, ...]


@dataclass(frozen=True)
class TutorialGroup:
    id: str
    title_key: str
    courses: tuple[str, ...]


@dataclass(frozen=True)
class TutorialCatalog:
    courses: tuple[TutorialCourse, ...]
    groups: tuple[TutorialGroup, ...] = ()

    def course_by_id(self, course_id: str) -> TutorialCourse:
        for course in self.courses:
            if course.id == course_id:
                return course
        raise KeyError(course_id)

    def chapter_by_id(self, chapter_id: str) -> TutorialChapter:
        for course in self.courses:
            for chapter in course.chapters:
                if chapter.id == chapter_id:
                    return chapter
        raise KeyError(chapter_id)

    def all_steps(self) -> Iterator[TutorialStep]:
        for course in self.courses:
            for chapter in course.chapters:
                yield from chapter.steps

    def step_count(self, course_id: str) -> int:
        return sum(len(chapter.steps) for chapter in self.course_by_id(course_id).chapters)

    def chapter_revisions(self) -> dict[str, int]:
        return {chapter.id: course.compat_revision
                for course in self.courses for chapter in course.chapters}


@dataclass(frozen=True)
class OperationContext:
    session_id: str
    run_id: str
    step_epoch: int
    operation_id: str

    def __post_init__(self) -> None:
        for name in ('session_id', 'run_id', 'operation_id'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError(f'invalid {name}')
        if type(self.step_epoch) is not int or self.step_epoch < 0:
            raise ValueError('invalid step_epoch')


@dataclass(frozen=True)
class TutorialEvent:
    context: OperationContext
    name: str
    outcome: Outcome
    details: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.context, OperationContext):
            raise ValueError('invalid operation context')
        require_id(self.name, 'event name')
        if not isinstance(self.outcome, str) or self.outcome not in OUTCOMES:
            raise ValueError('invalid event outcome')
        if not isinstance(self.details, Mapping) or len(self.details) > 64:
            raise ValueError('invalid event details')
        details = dict(self.details)
        for key, value in details.items():
            require_id(key, 'detail key')
            if not is_scalar(value) or (isinstance(value, str) and len(value) > 2048):
                raise ValueError('invalid event detail value')
        object.__setattr__(self, 'details', MappingProxyType(details))
