# SPDX-License-Identifier: GPL-3.0-or-later
"""A single validated course, driven by fresh real-operation result contexts."""
from __future__ import annotations

import contextlib
from typing import Callable
import uuid

from .models import (END_CHAPTER, OperationContext, TutorialCatalog, TutorialChapter,
                     TutorialCourse, TutorialEvent, TutorialStep, is_scalar,
                     require_id, scalar_equal)

MAX_PENDING_OPERATIONS = 512


class TutorialEngineError(RuntimeError):
    """The presentation/progress bridge failed; the engine has stopped input."""


class TutorialEngine:
    def __init__(self, catalog: TutorialCatalog, *, session_id: str,
                 on_step: Callable[[TutorialStep | None], None] | None = None,
                 on_progress: Callable[[str, str, int], object] | None = None,
                 condition_reader: Callable[[str, str | None], object] | None = None) -> None:
        if not isinstance(catalog, TutorialCatalog):
            raise ValueError('a validated catalog is required')
        if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
            raise ValueError('invalid session id')
        self.catalog = catalog
        self.session_id = session_id
        self.phase = 'idle'
        self.run_id: str | None = None
        self.sequence_index = 0
        self.last_error: str | None = None
        self._on_step = on_step
        self._on_progress = on_progress
        self._condition_reader = condition_reader or (lambda name, argument: False)
        self._course: TutorialCourse | None = None
        self._chapter: TutorialChapter | None = None
        self._step_id: str | None = None
        self._epoch = 0
        self._issued: dict[str, OperationContext] = {}
        self._history: list[str] = []
        self._presenting = False

    @property
    def current_step_id(self) -> str | None:
        return self._step_id

    @property
    def current_step(self) -> TutorialStep | None:
        if self._chapter is None or self._step_id is None:
            return None
        return self._chapter.step_by_id(self._step_id)

    @property
    def chapter_id(self) -> str | None:
        return self._chapter.id if self._chapter is not None else None

    @property
    def step_epoch(self) -> int:
        return self._epoch

    def invalidate_pending_operations(self) -> None:
        self._issued.clear()
        self._epoch += 1

    def _fail(self, code: str) -> None:
        self.phase = 'error'
        self.last_error = code
        self.invalidate_pending_operations()
        if self._on_step is not None:
            with contextlib.suppress(Exception):
                self._on_step(None)

    def _present(self, step: TutorialStep | None) -> None:
        if self._on_step is None:
            return
        previous = self._presenting
        self._presenting = True
        try:
            self._on_step(step)
        except Exception as exc:
            self._fail('presentation_failed')
            raise TutorialEngineError('failed to present teaching step') from exc
        finally:
            self._presenting = previous

    def _report(self, status: str) -> None:
        if self._on_progress is None or self._chapter is None or self._course is None:
            return
        try:
            # False is a persisted=false acknowledgement, not failure to learn.
            self._on_progress(self._chapter.id, status, self._course.compat_revision)
        except Exception as exc:
            self._fail('progress_bridge_failed')
            raise TutorialEngineError('failed to report teaching progress') from exc

    def start(self, course_id: str, chapter_id: str) -> None:
        if self.phase in ('running', 'paused'):
            raise RuntimeError('a teaching run is already active')
        course = self.catalog.course_by_id(course_id)
        chapter = next((item for item in course.chapters if item.id == chapter_id), None)
        if chapter is None:
            raise KeyError(chapter_id)
        self._course, self._chapter = course, chapter
        self.run_id = uuid.uuid4().hex
        self._history.clear()
        self.last_error = None
        self.phase = 'running'
        self._report('in_progress')
        self._enter(chapter.steps[0].id)

    def _enter(self, step_id: str) -> None:
        if self._chapter is None:
            raise TutorialEngineError('no active chapter')
        step = self._chapter.step_by_id(step_id)
        self.invalidate_pending_operations()
        self._step_id = step_id
        self.sequence_index = 0
        self._present(step)

    def begin_operation(self, name: str) -> OperationContext | None:
        if self.phase != 'running' or self._presenting:
            return None
        step = self.current_step
        if (step is None or step.wait is None
                or self.sequence_index >= len(step.wait.clauses)
                or step.wait.clauses[self.sequence_index].event != name
                or len(self._issued) >= MAX_PENDING_OPERATIONS):
            return None
        require_id(name, 'operation event')
        context = OperationContext(self.session_id, self.run_id, self._epoch, uuid.uuid4().hex)
        self._issued[context.operation_id] = context
        return context

    def consume(self, event: TutorialEvent) -> bool:
        if self.phase != 'running' or self._presenting or not isinstance(event, TutorialEvent):
            return False
        context = event.context
        if (context.session_id != self.session_id or context.run_id != self.run_id
                or context.step_epoch != self._epoch
                or self._issued.get(context.operation_id) != context):
            return False
        step = self.current_step
        if step is None or step.wait is None:
            return False
        if self.sequence_index >= len(step.wait.clauses):
            return False
        clause = step.wait.clauses[self.sequence_index]
        if event.name != clause.event:
            return False
        # Each relevant operation is terminal exactly once, successful or not.
        self._issued.pop(context.operation_id)
        if not clause.matches(event):
            return False
        self.sequence_index += 1
        # A result started before this substep cannot satisfy the following one.
        self._issued.clear()
        if self.sequence_index == len(step.wait.clauses):
            self._advance()
        return True

    def _advance(self) -> None:
        step = self.current_step
        if step is None:
            return
        destination = step.next
        try:
            for branch in step.branches:
                actual = self._condition_reader(branch.condition, branch.argument)
                if not is_scalar(actual):
                    raise ValueError('condition reader returned non-scalar')
                if scalar_equal(actual, branch.equals):
                    destination = branch.next
                    break
        except Exception as exc:
            self._fail('condition_failed')
            raise TutorialEngineError('failed to resolve teaching branch') from exc
        if destination == END_CHAPTER:
            self.phase = 'completing'
            self.invalidate_pending_operations()
            self._present(None)
            self.phase = 'completed'
            self._step_id = None
            self._report('completed')
        else:
            self._history.append(step.id)
            self._enter(destination)

    def next(self) -> bool:
        step = self.current_step
        if self.phase != 'running' or self._presenting or step is None or step.kind != 'information':
            return False
        self._advance()
        return True

    def previous(self) -> bool:
        if self.phase != 'running' or self._presenting or not self._history:
            return False
        self._enter(self._history.pop())
        return True

    def pause(self) -> None:
        if self.phase != 'running':
            return
        self.phase = 'paused'
        self.invalidate_pending_operations()
        self._present(None)

    def resume(self) -> None:
        if self.phase != 'paused':
            return
        self.phase = 'running'
        self.invalidate_pending_operations()
        self._present(self.current_step)

    def _stop(self, status: str) -> None:
        if self.phase not in ('running', 'paused', 'error'):
            return
        self.phase = 'stopping'
        self.invalidate_pending_operations()
        self._present(None)
        self.phase = 'stopped'
        self._step_id = None
        self._report(status)

    def skip_chapter(self) -> None:
        self._stop('skipped')

    def stop(self) -> None:
        self._stop('in_progress')
