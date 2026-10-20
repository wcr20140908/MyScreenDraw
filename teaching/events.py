# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-practice event bridge. Normal application instances need no active bus."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Mapping

from .engine import TutorialEngine
from .models import OperationContext, Outcome, Scalar, TutorialEvent


class TeachingEventBus:
    def __init__(self, engine: TutorialEngine | None = None) -> None:
        self._engine = engine
        self._suppressed = 0
        self._closed = False

    def begin_operation(self, name: str) -> OperationContext | None:
        if self._closed or self._suppressed or self._engine is None:
            return None
        return self._engine.begin_operation(name)

    def discard_operation(self, context: OperationContext | None) -> bool:
        # Suppressed setup may abandon an older edit; retirement is not a result.
        if self._closed or self._engine is None:
            return False
        return self._engine.discard_operation(context)

    def emit_result(self, context: OperationContext | None, name: str,
                    outcome: Outcome, details: Mapping[str, Scalar]) -> bool:
        if context is None or self._closed or self._suppressed or self._engine is None:
            return False
        return self._engine.consume(TutorialEvent(context, name, outcome, details))

    @contextmanager
    def suppress(self) -> Iterator[None]:
        """Fixture setup and programmatic navigation cannot count as user practice."""
        self._suppressed += 1
        try:
            yield
        finally:
            self._suppressed -= 1

    def close(self) -> None:
        self._closed = True
        if self._engine is not None:
            self._engine.invalidate_pending_operations()
        self._engine = None


class TeachingOperationBatch:
    """Capture one document action and stage results until its UI cleanup succeeds.

    Nested callbacks borrow entry-time contexts, including explicit absent ones;
    they cannot sign a new operation after a chooser or menu callback changes epoch.
    The host flushes after native cleanup but before checking the next target.
    """

    def __init__(self, bus: TeachingEventBus, names: tuple[str, ...]) -> None:
        self._bus = bus
        self._operations = {name: bus.begin_operation(name) for name in dict.fromkeys(names)}
        self._queued: dict[str, tuple[OperationContext, str, Outcome, dict[str, Scalar]]] = {}
        self._submitted: set[str] = set()
        self._suppressed = 0
        self._closed = False

    def operation(self, name: str) -> OperationContext | None:
        return None if self._closed else self._operations.get(name)

    def emit_result(self, context: OperationContext | None, name: str,
                    outcome: Outcome, details: Mapping[str, Scalar]) -> bool:
        if (self._closed or self._suppressed or context is None
                or self._operations.get(name) != context or context.operation_id in self._submitted):
            return False
        self._queued[context.operation_id] = (context, name, outcome, dict(details))
        self._submitted.add(context.operation_id)
        return True

    @contextmanager
    def suppress(self) -> Iterator[None]:
        self._suppressed += 1
        try:
            with self._bus.suppress():
                yield
        finally:
            self._suppressed -= 1

    def flush(self) -> None:
        if self._closed:
            return
        queued, self._queued = tuple(self._queued.values()), {}
        for context, name, outcome, details in queued:
            self._bus.emit_result(context, name, outcome, details)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queued.clear()
        for context in self._operations.values():
            self._bus.discard_operation(context)
