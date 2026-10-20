# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded learning-only parent snapshots and an in-memory, non-writing child view."""
from __future__ import annotations

import copy
from .models import TutorialCatalog
from .state import TutorialStateStore, _valid_state

MAX_VIEW_CHAPTERS=256


def require_transaction_id(value):
    if not isinstance(value,str) or len(value)!=32 or any(char not in '0123456789abcdef' for char in value):
        raise ValueError('invalid teaching transaction identifier')
    return value


def _chapters(catalog: TutorialCatalog) -> frozenset[str]:
    values=frozenset(chapter.id for course in catalog.courses for chapter in course.chapters)
    if len(values)>MAX_VIEW_CHAPTERS:
        raise ValueError('learning view exceeds its bounded wire budget')
    return values


def parent_progress_view(catalog: TutorialCatalog, store: TutorialStateStore) -> dict:
    chapters=_chapters(catalog)
    last=store.last_started
    if last is not None and last['chapter_id'] not in chapters:
        last=None
    return {'records':{name:store.chapter_record(name) for name in sorted(chapters)},
            'last_started':last,'read_only':bool(store.read_only),
            'context_hints_enabled':store.context_hints_enabled}


class PracticeProgressView:
    """An acknowledged parent view; no path, persistence or mutation capabilities."""
    def __init__(self, catalog: TutorialCatalog):
        self._chapters=_chapters(catalog)
        self._records={name:{'status':'not_started','compat_revision':1,
                             'completed_revision':None,'needs_review':False,
                             'last_attempt':'not_started'} for name in self._chapters}
        self._last_started=None
        self.read_only=True
        self.context_hints_enabled=False

    @property
    def last_started(self):
        return copy.deepcopy(self._last_started)

    def chapter_record(self, name):
        if name not in self._chapters:
            raise ValueError('unknown learning chapter')
        return copy.deepcopy(self._records[name])

    def replace(self, view):
        if (not isinstance(view,dict)
                or set(view)!={'records','last_started','read_only','context_hints_enabled'}
                or type(view['read_only']) is not bool
                or not isinstance(view['records'],dict) or set(view['records'])!=self._chapters):
            raise ValueError('invalid parent learning view')
        state=_valid_state({'schema_version':1,'welcome':'dismissed','context_seen':[],
                            'context_hints_enabled':view['context_hints_enabled'],
                            'chapters':view['records'],'last_started':view['last_started']})
        last=state['last_started']
        if last is not None and last['chapter_id'] not in self._chapters:
            raise ValueError('unknown last learning chapter')
        self._records=state['chapters'];self._last_started=last
        self.read_only=view['read_only'];self.context_hints_enabled=state['context_hints_enabled']
