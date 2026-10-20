# SPDX-License-Identifier: GPL-3.0-or-later
"""First-use policy, independent of Qt, application edits and process launching."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, fields

from .state import TutorialStateStore


@dataclass(frozen=True)
class TeachingReadiness:
    """Trusted host snapshot. Uninitialized or background hosts are not ready."""
    lifecycle_ready: bool = False
    restore_finished: bool = False
    layout_ready: bool = False
    foreground: bool = False
    application_visible: bool = False
    modal_active: bool = False
    gesture_active: bool = False
    composition_active: bool = False
    text_edit_active: bool = False
    file_operation_active: bool = False
    practice_active: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, field.name)) is not bool for field in fields(self)):
            raise ValueError('readiness flags must be explicit booleans')

    @property
    def safe(self) -> bool:
        return (self.lifecycle_ready and self.restore_finished and self.layout_ready
                and self.foreground and self.application_visible
                and not (self.modal_active or self.gesture_active or self.composition_active
                         or self.text_edit_active or self.file_operation_active or self.practice_active))


@dataclass(frozen=True)
class TeachingStartupContext:
    practice: bool = False
    smoke: bool = False
    automated: bool = False

    @classmethod
    def from_arguments(cls, arguments: Sequence[str], *, practice: bool = False,
                       automated: bool = False) -> TeachingStartupContext:
        return cls(practice=practice or any(value.startswith('--teaching-practice') for value in arguments),
                   smoke=any(value.startswith('--smoke') for value in arguments), automated=automated)

    @property
    def automatic_allowed(self) -> bool:
        return not (self.practice or self.smoke or self.automated)


@dataclass(frozen=True)
class WelcomeDecision:
    decision: str
    persisted: bool


class WelcomePolicy:
    """Offer at most once per startup; record explicit choices before launch.

    The host polls its own readiness without committing/cancelling user work.
    claim_welcome() is a claim, not merely a predicate: only its successful caller
    may construct the nonmodal welcome. A writable-state check happens once and
    only after readiness is safe. Manual teaching remains possible with read-only
    progress. If persistence subsequently fails, accepted memory state and a
    single nonblocking warning are retained; cross-restart persistence cannot be
    promised in that case.
    """

    def __init__(self, state_store: TutorialStateStore, *,
                 context: TeachingStartupContext | None = None,
                 warn: Callable[[str], None] | None = None) -> None:
        self._store = state_store
        self.context = context or TeachingStartupContext()
        self._warn = warn
        self._claim_attempted = self._offered = self._decided = self._warned = False

    def claim_welcome(self, readiness: TeachingReadiness) -> bool:
        if (self._claim_attempted or not self.context.automatic_allowed
                or self._store.read_only or self._store.welcome != 'unseen' or not readiness.safe):
            return False
        self._claim_attempted = True
        self._offered = self._store.ensure_writable()
        return self._offered

    def can_open_center(self, readiness: TeachingReadiness) -> bool:
        # Deliberately does not require writable progress or change welcome state.
        return readiness.safe

    def decide(self, decision: str, *, start_core: Callable[[], None] | None = None) -> WelcomeDecision | None:
        if not isinstance(decision, str) or decision not in ('accepted', 'skipped', 'dismissed'):
            raise ValueError('an explicit welcome decision is required')
        if not self._offered or self._decided:
            return None
        self._decided = True  # Guard synchronous callbacks before any side effect.
        persisted = self._store.set_welcome(decision)
        if not persisted and not self._warned:
            self._warned = True
            if self._warn is not None:
                with suppress(Exception):
                    self._warn('teaching_progress_save_failed')
        if decision == 'accepted' and start_core is not None:
            start_core()
        return WelcomeDecision(decision, persisted)
