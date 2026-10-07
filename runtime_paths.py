# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable paths and owned private-practice roots, without starting Qt or writing user data."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tempfile
import uuid

_MARKER = '.myscreendraw-teaching-session.json'
_MAGIC = 'org.myscreendraw.teaching'
_UUID = re.compile(r'[0-9a-f]{32}\Z')
_NONCE = re.compile(r'[0-9a-f]{64}\Z')
_MARKER_FIELDS = {'magic', 'schema_version', 'app_key', 'session_id', 'nonce', 'owner_pid'}


def _identity(session_id: object, nonce: object) -> None:
    if not isinstance(session_id, str) or not _UUID.fullmatch(session_id):
        raise ValueError('invalid practice identity')
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ValueError('invalid practice identity')


def _app_key(app_dir: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(app_dir.resolve())).encode('utf-8')).hexdigest()[:16]


def _reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _reject_links(base: Path, path: Path) -> None:
    """Inspect original components, not just the resolved destination."""
    if not path.is_relative_to(base):
        raise ValueError('path outside private root')
    current = path
    while True:
        if _reparse(current):
            raise ValueError('linked practice paths are not allowed')
        if current == base:
            break
        current = current.parent


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError('duplicate marker field')
        record[key] = value
    return record


@dataclass(frozen=True)
class RuntimePaths:
    app_dir: Path
    resource_dir: Path
    runtime_root: Path
    practice: bool = False
    temp_root: Path | None = None
    session_id: str | None = None
    nonce: str | None = field(default=None, repr=False)

    @classmethod
    def for_normal(cls, app_dir: Path, resource_dir: Path | None = None) -> RuntimePaths:
        app = Path(app_dir).resolve()
        return cls(app, Path(resource_dir).resolve() if resource_dir is not None else app, app)

    @staticmethod
    def namespace(app_dir: Path, temp_root: Path) -> Path:
        temporary = Path(temp_root).resolve()
        namespace = temporary / 'MyScreenDraw' / 'teaching' / _app_key(Path(app_dir))
        _reject_links(temporary, namespace)
        if not namespace.resolve().is_relative_to(temporary):
            raise ValueError('practice namespace outside temporary root')
        return namespace

    @classmethod
    def create_practice(cls, app_dir: Path, resource_dir: Path, *,
                        temp_root: Path | None = None, session_id: str | None = None,
                        nonce: str | None = None) -> RuntimePaths:
        session_id = session_id or uuid.uuid4().hex
        nonce = nonce or os.urandom(32).hex()
        _identity(session_id, nonce)
        temporary = Path(temp_root if temp_root is not None else tempfile.gettempdir()).resolve()
        app, resources = Path(app_dir).resolve(), Path(resource_dir).resolve()
        namespace = cls.namespace(app, temporary)
        private = namespace / session_id
        if app.is_relative_to(private) or private.is_relative_to(app):
            raise ValueError('practice root overlaps program data')
        namespace.mkdir(parents=True, exist_ok=True)
        _reject_links(temporary, namespace)
        try:
            private.mkdir()
        except FileExistsError as exc:
            raise ValueError('practice session already exists') from exc
        record = {'magic': _MAGIC, 'schema_version': 1, 'app_key': _app_key(app),
                  'session_id': session_id, 'nonce': nonce, 'owner_pid': os.getpid()}
        # Exclusive write; do not adopt or overwrite an existing user directory.
        with (private / _MARKER).open('x', encoding='utf-8') as stream:
            json.dump(record, stream, separators=(',', ':'), sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        return cls.for_practice(app, resources, private, temp_root=temporary,
                                session_id=session_id, nonce=nonce)

    @classmethod
    def for_practice(cls, app_dir: Path, resource_dir: Path, private_root: Path, *,
                     temp_root: Path, session_id: str, nonce: str) -> RuntimePaths:
        _identity(session_id, nonce)
        app, resources = Path(app_dir).resolve(), Path(resource_dir).resolve()
        temporary = Path(temp_root).resolve()
        expected = cls.namespace(app, temporary) / session_id
        private = Path(private_root).absolute()
        _reject_links(temporary, private)
        if private != expected or private.resolve() != expected:
            raise ValueError('practice root identity mismatch')
        marker = private / _MARKER
        _reject_links(private, marker)
        try:
            with marker.open('rb') as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError('invalid marker size')
            record = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            raise ValueError('invalid practice marker') from exc
        if (not isinstance(record, dict) or set(record) != _MARKER_FIELDS
                or record['magic'] != _MAGIC or type(record['schema_version']) is not int
                or record['schema_version'] != 1 or record['app_key'] != _app_key(app)
                or record['session_id'] != session_id or type(record['owner_pid']) is not int
                or record['owner_pid'] < 1 or not isinstance(record['nonce'], str)
                or not hmac.compare_digest(record['nonce'].encode('utf-8'), nonce.encode('utf-8'))):
            raise ValueError('practice marker identity mismatch')
        if app.is_relative_to(private) or private.is_relative_to(app):
            raise ValueError('practice root overlaps program data')
        return cls(app, resources, private, True, temporary, session_id, nonce)

    @property
    def marker_file(self) -> Path:
        if not self.practice:
            raise ValueError('normal runtime has no practice marker')
        return self.runtime_root / _MARKER

    @property
    def data_dir(self) -> Path:
        return self.runtime_root / 'data'

    @property
    def export_dir(self) -> Path:
        return self.runtime_root / 'exports'

    @property
    def autosave_dir(self) -> Path:
        return self.data_dir / 'autosave'

    @property
    def config_file(self) -> Path:
        return self.data_dir / 'config.json'

    @property
    def roster_file(self) -> Path:
        return self.data_dir / 'roster.json'

    @property
    def telemetry_file(self) -> Path:
        return self.data_dir / 'events.jsonl'

    @property
    def log_file(self) -> Path:
        return self.data_dir / 'app.log'

    def module_aliases(self) -> dict[str, str]:
        return {name: str(path) for name, path in {
            'DATA_DIR': self.data_dir, 'EXPORT_DIR': self.export_dir,
            'AUTOSAVE_DIR': self.autosave_dir, 'CONFIG_FILE': self.config_file,
            'ROSTER_FILE': self.roster_file, 'TELEMETRY_FILE': self.telemetry_file,
            'LOG_FILE': self.log_file,
        }.items()}

    def _private_path(self, value: Path | str) -> Path:
        text = str(value)
        windows = PureWindowsPath(text)
        if windows.drive and not windows.is_absolute():
            raise ValueError('drive-relative path outside private root')
        original = Path(value)
        if not original.is_absolute():
            original = self.runtime_root / original
        original = Path(os.path.abspath(original))
        if not original.is_relative_to(self.runtime_root):
            raise ValueError('path outside private root')
        _reject_links(self.runtime_root, original)
        path = original.resolve()
        if not path.is_relative_to(self.runtime_root):
            raise ValueError('path outside private root')
        if path == self.marker_file:
            raise ValueError('practice marker is not a document')
        return path

    def require_read_path(self, path: Path | str) -> Path:
        value = self._private_path(path) if self.practice else Path(path).resolve()
        if not value.is_file():
            raise ValueError('input must be an existing file')
        return value

    def require_write_path(self, path: Path | str) -> Path:
        value = self._private_path(path) if self.practice else Path(path).resolve()
        if value.exists() and not value.is_file():
            raise ValueError('output must be a file path')
        return value

    def resource_path(self, relative: str) -> Path:
        windows = PureWindowsPath(relative)
        if not relative or windows.drive or windows.is_absolute() or '\\' in relative:
            raise ValueError('resource outside bundled root')
        candidate = (self.resource_dir / relative).resolve()
        if not candidate.is_relative_to(self.resource_dir) or not candidate.is_file():
            raise ValueError('invalid bundled resource')
        return candidate


@dataclass
class RuntimeContext:
    paths: RuntimePaths
    ui_active: bool = field(init=False)

    def __post_init__(self) -> None:
        self.ui_active = not self.paths.practice

    @property
    def global_keyboard(self) -> bool:
        return not self.paths.practice

    @property
    def tray(self) -> bool:
        return not self.paths.practice

    @property
    def updates(self) -> bool:
        return not self.paths.practice

    @property
    def autostart(self) -> bool:
        return not self.paths.practice

    @property
    def usage_tracking(self) -> bool:
        return not self.paths.practice

    def activate(self) -> None:
        self.ui_active = True
