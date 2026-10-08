# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed practice argument parsing and pre-initialization path binding."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Mapping, Sequence

from runtime_paths import RuntimeContext, RuntimePaths
from .models import require_id

_MODE = '--teaching-practice'
_ARGUMENTS = frozenset({'--session-root', '--session-id', '--channel', '--course-id', '--chapter-id'})
_CHANNEL = re.compile(r'myscreendraw-teaching-[0-9a-f]{32}\Z')
_NONCE_ENV = 'MYSCREENDRAW_PRACTICE_NONCE'
_TEMP_ENV = 'MYSCREENDRAW_PRACTICE_TEMP_ROOT'


@dataclass(frozen=True)
class PracticeRequest:
    paths: RuntimePaths
    channel: str
    course_id: str
    chapter_id: str


def parse_practice_request(argv: Sequence[str], *, app_dir: Path, resource_dir: Path,
                           environ: Mapping[str, str] | None = None) -> PracticeRequest | None:
    if not any(isinstance(argument, str) and argument.startswith(_MODE) for argument in argv):
        return None
    if any(not isinstance(argument, str) for argument in argv) or len(argv) != 11:
        raise ValueError('invalid practice argument set')
    values = {}
    mode_count = 0
    position = 0
    while position < len(argv):
        key = argv[position]
        if key == _MODE:
            mode_count += 1
            position += 1
            continue
        if key not in _ARGUMENTS or key in values or position + 1 >= len(argv):
            raise ValueError('unknown or duplicate practice argument')
        value = argv[position + 1]
        if not value or value.startswith('--'):
            raise ValueError('missing practice argument value')
        values[key] = value
        position += 2
    if mode_count != 1 or set(values) != _ARGUMENTS:
        raise ValueError('missing practice arguments')
    channel = values['--channel']
    if not _CHANNEL.fullmatch(channel):
        raise ValueError('invalid practice channel')
    course = require_id(values['--course-id'], 'course id')
    chapter = require_id(values['--chapter-id'], 'chapter id')
    if '.' in course or not chapter.startswith(course + '.'):
        raise ValueError('chapter does not belong to course')
    environment = os.environ if environ is None else environ
    nonce, temporary = environment.get(_NONCE_ENV), environment.get(_TEMP_ENV)
    if not isinstance(nonce, str) or not isinstance(temporary, str) or not Path(temporary).is_absolute():
        raise ValueError('missing private environment')
    root = Path(values['--session-root'])
    if not root.is_absolute():
        raise ValueError('private root must be absolute')
    paths = RuntimePaths.for_practice(app_dir, resource_dir, root, temp_root=Path(temporary),
                                     session_id=values['--session-id'], nonce=nonce)
    return PracticeRequest(paths, channel, course, chapter)


def practice_arguments(paths: RuntimePaths, channel: str, course_id: str, chapter_id: str) -> list[str]:
    if not paths.practice or not _CHANNEL.fullmatch(channel):
        raise ValueError('an owned practice context is required')
    require_id(course_id, 'course id')
    require_id(chapter_id, 'chapter id')
    if '.' in course_id or not chapter_id.startswith(course_id + '.'):
        raise ValueError('chapter does not belong to course')
    return [_MODE, '--session-root', str(paths.runtime_root), '--session-id', paths.session_id,
            '--channel', channel, '--course-id', course_id, '--chapter-id', chapter_id]


def bind_practice_paths(module: object, request: PracticeRequest) -> RuntimeContext:
    """Only before logging/widgets: keep program/resources separate from runtime."""
    if not isinstance(request, PracticeRequest):
        raise ValueError('invalid practice request')
    app_dir = getattr(module, 'APP_DIR', None)
    if not isinstance(app_dir, (str, Path)) or Path(app_dir).resolve() != request.paths.app_dir:
        raise ValueError('practice binding installation mismatch')
    logger = getattr(module, 'LOGGER', None)
    if logger is not None and getattr(logger, 'handlers', ()):
        raise ValueError('practice paths must be bound before logging')
    previous = getattr(module, 'RUNTIME_CONTEXT', None)
    if previous is not None and previous.paths.practice:
        raise ValueError('practice paths are already bound')
    paths = request.paths
    verified = RuntimePaths.for_practice(paths.app_dir, paths.resource_dir, paths.runtime_root,
        temp_root=paths.temp_root, session_id=paths.session_id, nonce=paths.nonce)
    context = RuntimeContext(verified)
    aliases = verified.module_aliases()
    # Module and SimpleNamespace support a single non-I/O assignment boundary.
    namespace = vars(module)
    namespace.update(aliases)
    namespace['RUNTIME_CONTEXT'] = context
    return context
