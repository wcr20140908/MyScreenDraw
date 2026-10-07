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
