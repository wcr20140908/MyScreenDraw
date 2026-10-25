# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned local history for the classroom calculator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import json
import os
import re
from pathlib import Path
from typing import Callable
import uuid


SCHEMA_VERSION = 1
MAX_ENTRIES = 100
MAX_HISTORY_BYTES = 2 * 1024 * 1024
MAX_INPUT_CHARS = 512 * 1024
MAX_RESULT_CHARS = 128 * 1024
MAX_PAYLOAD_DEPTH = 16
MAX_PAYLOAD_NODES = 50_000
MAX_PAYLOAD_ITEMS = 10_000
RETENTION_DAYS = {"1d": 1, "7d": 7, "30d": 30}
RETENTION_VALUES = ("session", "1d", "7d", "30d", "forever")
MODES = ("basic", "scientific", "unit", "statistics", "base")


def _payload_number(value):
    if type(value) is int:
        value = str(value)
    if (not isinstance(value, str) or len(value) > 10032
            or re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value) is None):
        raise ValueError('invalid history numeric payload')
    try:
        number = Decimal(value)
    except DecimalException as error:
        raise ValueError('invalid history numeric payload') from error
    if not number.is_finite() or number.copy_abs() > Decimal('1e10000') or number and number.adjusted() < -10000:
        raise ValueError('invalid history numeric payload')


def _validate_mode_payload(mode, payload):
    for key in ('canonical', 'full_result', 'ans', 'source_value', 'target_value', 'source_unit', 'target_unit'):
        if key in payload and not isinstance(payload[key], str):
            raise ValueError('invalid history payload field: ' + key)
    if mode in ('basic', 'scientific'):
        if 'canonical' in payload and len(payload['canonical']) > 512:
            raise ValueError('invalid history expression')
        if 'angle_mode' in payload and payload['angle_mode'] not in ('deg', 'rad'):
            raise ValueError('invalid history angle mode')
        for key in ('ans', 'full_result'):
            if key in payload:
                _payload_number(payload[key])
    elif mode == 'statistics':
        if 'values' in payload:
            if not isinstance(payload['values'], list) or len(payload['values']) > 10000:
                raise ValueError('invalid history statistics data')
            for value in payload['values']:
                _payload_number(value)
        if 'summary' in payload:
            if not isinstance(payload['summary'], dict):
                raise ValueError('invalid history statistics summary')
            for value in payload['summary'].values():
                _payload_number(value)
    elif mode == 'base':
        for key in ('source_base', 'target_base'):
            if key in payload and (type(payload[key]) is not int or payload[key] not in (2, 8, 10, 16)):
                raise ValueError('invalid history base')
    elif mode == 'unit':
        from calculator import UNIT_CATEGORIES
        category = payload.get('category')
        if 'category' in payload and (not isinstance(category, str) or category not in UNIT_CATEGORIES):
            raise ValueError('invalid history unit category')
        for key in ('source_value', 'target_value'):
            if key in payload:
                _payload_number(payload[key])
        if category in UNIT_CATEGORIES:
            for key in ('source_unit', 'target_unit'):
                if key in payload and payload[key] not in UNIT_CATEGORIES[category]:
                    raise ValueError('invalid history unit')


def normalize_retention(value: object) -> str:
    return value if isinstance(value, str) and value in RETENTION_VALUES else "session"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("invalid timestamp")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("history timestamp must include a timezone")
    return _utc(parsed)


def _json_safe(value, *, depth: int = 0, budget: list[int] | None = None):
    """Validate bounded finite JSON values; Decimal payload values become strings."""
    if budget is None:
        budget = [MAX_PAYLOAD_NODES, MAX_HISTORY_BYTES]
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_PAYLOAD_DEPTH:
        raise ValueError("history payload exceeds structure limit")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if len(value) > MAX_INPUT_CHARS:
            raise ValueError("history payload string is too large")
        budget[1] -= len(value.encode("utf-8"))
        if budget[1] < 0:
            raise ValueError("history payload exceeds size limit")
        return value
    if type(value) is int:
        if value.bit_length() > 4096:
            raise ValueError("history payload integer is too large")
        return value
    if isinstance(value, float):
        if not (float("-inf") < value < float("inf")):
            raise ValueError("non-finite history value")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite history value")
        return _json_safe(str(value), depth=depth, budget=budget)
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_PAYLOAD_ITEMS:
            raise ValueError("history payload collection is too large")
        return [_json_safe(item, depth=depth + 1, budget=budget) for item in value]
    if isinstance(value, dict):
        if len(value) > MAX_PAYLOAD_ITEMS:
            raise ValueError("history payload collection is too large")
        safe = {}
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 512:
                raise ValueError("invalid history payload key")
            safe[key] = _json_safe(item, depth=depth + 1, budget=budget)
        return safe
    raise ValueError("unsupported history value")


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    created_at: datetime
    mode: str
    input: str
    result: str
    payload: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": _timestamp(self.created_at),
            "mode": self.mode,
            "input": self.input,
            "result": self.result,
            "payload": _json_safe(self.payload),
        }

    @classmethod
    def from_dict(cls, raw: object) -> "HistoryEntry":
        if not isinstance(raw, dict):
            raise ValueError("invalid history entry")
        entry_id = raw.get("id")
        mode = raw.get("mode")
        input_text = raw.get("input")
        result = raw.get("result")
        payload = raw.get("payload", {})
        if not isinstance(entry_id, str) or not entry_id or len(entry_id) > 128:
            raise ValueError("invalid history id")
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError("invalid history mode")
        if not isinstance(input_text, str) or len(input_text) > MAX_INPUT_CHARS:
            raise ValueError("invalid history input")
        if not isinstance(result, str) or len(result) > MAX_RESULT_CHARS:
            raise ValueError("invalid history result")
        if not isinstance(payload, dict):
            raise ValueError("invalid history payload")
        safe_payload = _json_safe(payload)
        _validate_mode_payload(mode, safe_payload)
        entry = cls(entry_id, _parse_timestamp(raw.get("created_at")), mode,
                    input_text, result, safe_payload)
        encoded = json.dumps(entry.to_dict(), ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_HISTORY_BYTES - 64:
            raise ValueError("history entry exceeds size limit")
        return entry


class CalculatorHistoryStore:
    """Bounded history with explicit corruption and retention semantics."""

    def __init__(self, path: str | os.PathLike, *, retention: str = "session",
                 now: Callable[[], datetime] | None = None):
        self.path = Path(path)
        self.retention = normalize_retention(retention)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.entries: list[HistoryEntry] = []
        self.read_error: str | None = None
        self.write_error: str | None = None
        self._disk_checked = False

    @property
    def persistent(self) -> bool:
        return self.retention != "session"

    def set_retention(self, retention: object) -> None:
        previous = self.retention
        self.retention = normalize_retention(retention)
        if not self.persistent:
            return
        if previous == "session":
            self._disk_checked = False
            self._load_and_merge()
        else:
            self._prune()
        self.save()

    def _load_and_merge(self) -> None:
        current = list(self.entries)
        self.load()
        merged = {entry.id: entry for entry in self.entries}
        merged.update({entry.id: entry for entry in current})
        self.entries = sorted(merged.values(), key=lambda entry: _utc(entry.created_at))
        self._prune()

    def load(self) -> list[HistoryEntry]:
        if not self.persistent:
            return self.entries
        self.read_error = None
        self.write_error = None
        self._disk_checked = True
        try:
            if not self.path.exists():
                self.entries = []
                return self.entries
            if self.path.stat().st_size > MAX_HISTORY_BYTES:
                raise ValueError("history file is too large")
            # Read a bounded amount even if another process grows the file after stat.
            with self.path.open("rb") as handle:
                encoded = handle.read(MAX_HISTORY_BYTES + 1)
            if len(encoded) > MAX_HISTORY_BYTES:
                raise ValueError("history file is too large")
            raw = json.loads(encoded.decode("utf-8-sig"))
            if (not isinstance(raw, dict) or type(raw.get("schema_version")) is not int
                    or raw["schema_version"] != SCHEMA_VERSION
                    or set(raw) != {"schema_version", "entries"}):
                raise ValueError("unsupported history schema")
            rows = raw.get("entries")
            if not isinstance(rows, list) or len(rows) > MAX_ENTRIES:
                raise ValueError("invalid history entries")
            loaded = [HistoryEntry.from_dict(row) for row in rows]
            if len({entry.id for entry in loaded}) != len(loaded):
                raise ValueError("duplicate history id")
            if loaded != sorted(loaded, key=lambda item: item.created_at):
                raise ValueError("history entries are not ordered")
            self.entries = loaded
            if self._prune():
                self.save()
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self.entries = []
            self.read_error = str(exc) or exc.__class__.__name__
        return self.entries

    def _prune(self) -> bool:
        original = list(self.entries)
        if self.retention in RETENTION_DAYS:
            threshold = _utc(self.now()) - timedelta(days=RETENTION_DAYS[self.retention])
            self.entries = [entry for entry in self.entries if _utc(entry.created_at) >= threshold]
        self.entries = self.entries[-MAX_ENTRIES:]
        return self.entries != original

    def add(self, mode: str, input_text: str, result: str,
            payload: dict | None = None) -> HistoryEntry:
        # Readers and writers accept exactly the same canonical entry contract.
        entry = HistoryEntry.from_dict({
            "id": uuid.uuid4().hex,
            "created_at": _timestamp(self.now()),
            "mode": mode,
            "input": input_text,
            "result": result,
            "payload": {} if payload is None else payload,
        })
        if self.persistent and not self._disk_checked:
            self._load_and_merge()
        self.entries.append(entry)
        self.entries.sort(key=lambda item: item.created_at)
        self._prune()
        self.save()
        return entry

    def delete(self, entry_id: str) -> bool:
        if self.persistent and not self._disk_checked:
            self._load_and_merge()
        remaining = [entry for entry in self.entries if entry.id != entry_id]
        if len(remaining) == len(self.entries):
            return False
        self.entries = remaining
        self.save()
        return True

    def clear(self) -> None:
        self.entries = []
        self.read_error = None
        self.write_error = None
        self._disk_checked = True
        self.save(force=True)

    def search(self, query: str = "", *, mode: str | None = None) -> list[HistoryEntry]:
        needle = str(query).casefold().strip()
        return [entry for entry in self.entries
                if (mode is None or entry.mode == mode)
                and (not needle or needle in entry.input.casefold()
                     or needle in entry.result.casefold()
                     or needle in json.dumps(entry.payload, ensure_ascii=False).casefold())]

    def _document(self) -> dict:
        rows = [HistoryEntry.from_dict(entry.to_dict()).to_dict() for entry in self.entries]
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError("duplicate history id")
        if rows != sorted(rows, key=lambda row: _parse_timestamp(row["created_at"])):
            raise ValueError("history entries are not ordered")
        return {"schema_version": SCHEMA_VERSION, "entries": rows}

    def save(self, *, force: bool = False) -> bool:
        self.write_error = None
        if not self.persistent:
            return False
        if not self._disk_checked and not force:
            self._load_and_merge()
        if self.read_error and not force:
            return False
        self._disk_checked = True
        try:
            self._prune()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            document = self._document()
            prefix = b'{"schema_version":1,"entries":['
            suffix = b"]}"
            rows: list[bytes] = []
            kept: list[HistoryEntry] = []
            size = len(prefix) + len(suffix)
            for entry, row in zip(self.entries, document["entries"]):
                encoded_row = json.dumps(row, ensure_ascii=False, separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")
                rows.append(encoded_row)
                kept.append(entry)
                size += len(encoded_row) + (1 if len(rows) > 1 else 0)
                while size > MAX_HISTORY_BYTES and rows:
                    removed = rows.pop(0)
                    kept.pop(0)
                    size -= len(removed) + (1 if rows else 0)
            self.entries = kept
            encoded = prefix + b",".join(rows) + suffix
            temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with open(temporary, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            return True
        except (OSError, TypeError, ValueError, RecursionError) as exc:
            self.write_error = str(exc) or exc.__class__.__name__
            return False
