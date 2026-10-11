# SPDX-License-Identifier: GPL-3.0-or-later
"""Context hint policy independent of Qt, user documents and process launching."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from threading import RLock

from .onboarding import TeachingReadiness, TeachingStartupContext
from .state import TutorialStateStore


@dataclass(frozen=True)
class ContextHintOffer:
    """Immutable topic identity; only the issuing policy can grant its consumption."""

    context_id: str
    course_id: str
    chapter_id: str


class ContextHintPolicy:
    """Offer each context once per policy session, without starting a chapter.

    The host supplies trusted topics already filtered against its actual catalog,
    fresh readiness snapshots and a display callback returning exactly True on
    success. Showing is reserved against concurrent or reentrant offers, but its
    signal cannot be consumed until successful display and progress recording.
    Dismissal or invalidation also retires a reservation still being displayed.

    Successful display is remembered in this session before attempting storage.
    Storage failure retains the store's existing memory semantics and warns at
    most once; it cannot prevent explicit consumption of a genuine shown offer.
    Persistence failure cannot guarantee once-only behavior across restarts.
    """

    def __init__(self, state_store: TutorialStateStore,
                 topics: Mapping[str, tuple[str, str]], *,
                 context: TeachingStartupContext | None = None,
                 warn: Callable[[str], None] | None = None) -> None:
        self._store = state_store
        self._topics = dict(topics)
        self.context = context or TeachingStartupContext()
        self._warn = warn
        self._warned = False
        self._seen: set[str] = set()
        self._active: ContextHintOffer | None = None
        self._showing = False
        self._lock = RLock()

    def _allowed(self, readiness: TeachingReadiness) -> bool:
        return (self.context.automatic_allowed and readiness.safe
                and self._store.context_hints_enabled)

    def try_offer(self, context_id: str, readiness: TeachingReadiness,
                  show_callback: Callable[[ContextHintOffer], bool]) -> ContextHintOffer | None:
        """Display an eligible hint; return only a successfully shown active offer."""
        with self._lock:
            if (context_id not in self._topics or self._active is not None or self._showing
                    or context_id in self._seen or not self._allowed(readiness)
                    or not self._store.should_offer_context_hint(context_id)):
                return None
            course_id, chapter_id = self._topics[context_id]
            offer = ContextHintOffer(context_id, course_id, chapter_id)
            self._active = offer
            self._showing = True
        try:
            shown = show_callback(offer) is True
        except Exception:
            shown = False
        with self._lock:
            if not shown:
                if self._active is offer:
                    self._active = None
                self._showing = False
                return None
            self._seen.add(context_id)
            try:
                persisted = self._store.mark_context_seen(context_id)
            except Exception:
                persisted = False
            self._showing = False
            notify = not persisted and not self._warned
            if notify:
                self._warned = True
        if notify and self._warn is not None:
            with suppress(Exception):
                self._warn('teaching_progress_save_failed')
        with self._lock:
            return offer if self._active is offer else None

    def consume(self, offer: ContextHintOffer, readiness: TeachingReadiness) -> bool:
        """Grant the host one related chapter start, without requiring writable state."""
        with self._lock:
            if (self._active is None or offer is not self._active or self._showing
                    or not self._allowed(readiness)):
                return False
            self._active = None
            return True

    def dismiss(self, offer: ContextHintOffer) -> bool:
        """Retire the current offer by identity; stale signals cannot dismiss another."""
        with self._lock:
            if self._active is None or offer is not self._active:
                return False
            self._active = None
            return True

    def invalidate(self) -> None:
        """Retire any current offer while retaining this session's seen contexts."""
        with self._lock:
            self._active = None
