# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, session-authenticated teaching IPC; no UI or model dependencies.

The wire envelope has exactly six fields: protocol_version, session_id, nonce,
message_id, type and payload. The payload is an object of plain JSON values.
Control messages require action=activate/pause/resume/stop. If present, course_id,
chapter_id, step_id and phase are identifiers, and persisted is a real boolean.
Other bounded payload metadata is allowed; catalog membership, required business
fields, ACK correlation and legal phase transitions belong to the broker.

Identifiers/object keys are nonblank printable UTF-8, at most 128 bytes. Text
values are at most 4096 UTF-8 bytes; containers have at most 256 members. Numbers
are finite and within the signed 64-bit interval; wire float tokens have at most
64 characters. The complete envelope has at most 4096 JSON values (keys excluded)
and 16 container levels, counting the envelope itself as level one.

A codec retains at most one partial frame and 4096 received message IDs. IDs are
never evicted: duplicates remain idempotent, and a new ID beyond this lifetime
budget closes the session rather than reopening it to old replays. Encoding does
not consume IDs, so outbound retries can reuse their original message ID.

Any malformed inbound frame permanently poisons the parser, discarding buffered
bytes and replay state. Later reads, including empty reads, raise ProtocolError;
there is deliberately no resynchronization/reset operation. A read containing a
bad frame raises instead of returning its earlier valid messages. The caller must
close the transport and establish a new authenticated session after such an error.
Instances are for a single transport owner, not concurrent feed/encode calls.
"""
from __future__ import annotations

import hmac
import json
import math
import struct
from typing import Any, NoReturn

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 65536
MAX_IDENTIFIER_BYTES = 128
MAX_STRING_BYTES = 4096
MAX_CONTAINER_ITEMS = 256
MAX_JSON_NODES = 4096
MAX_NESTING = 16
MAX_MESSAGE_IDS = 4096
MAX_FLOAT_TOKEN_CHARS = 64
MIN_INTEGER = -(1 << 63)
MAX_INTEGER = (1 << 63) - 1

_ENVELOPE_KEYS = frozenset({
    "protocol_version", "session_id", "nonce", "message_id", "type", "payload",
})
_MESSAGE_TYPES = frozenset({
    "hello", "ready", "activated", "control", "chapter_state", "state_ack",
    "error", "stopping", "stopped",
})
_CONTROL_ACTIONS = frozenset({"activate", "pause", "resume", "stop"})
_PAYLOAD_IDENTIFIERS = ("course_id", "chapter_id", "step_id", "phase")
_HEADER = struct.Struct(">I")


class ProtocolError(ValueError):
    """Invalid protocol data; diagnostics never quote untrusted values."""


def _utf8_text(value: Any, limit: int) -> bytes:
    if type(value) is not str or len(value) > limit:
        raise ProtocolError("Expected bounded UTF-8 text.")
    encoded: bytes | None = None
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        pass
    # Raise outside the handler: no UnicodeError containing the input text is
    # retained as exception context, even for credentials with lone surrogates.
    if encoded is None or len(encoded) > limit:
        raise ProtocolError("Expected bounded UTF-8 text.")
    return encoded


def _identifier(value: Any) -> bytes:
    encoded = _utf8_text(value, MAX_IDENTIFIER_BYTES)
    if not value.strip() or not value.isprintable():
        raise ProtocolError("Expected a nonblank printable identifier.")
    return encoded


def _finite_number(value: int | float) -> None:
    if type(value) is float and not math.isfinite(value):
        raise ProtocolError("Non-finite JSON numbers are forbidden.")
    if not MIN_INTEGER <= value <= MAX_INTEGER:
        raise ProtocolError("JSON number exceeds the supported range.")


def _validate_json_tree(root: dict[str, Any]) -> None:
    remaining = MAX_JSON_NODES
    pending: list[tuple[Any, int]] = [(root, 1)]
    # An explicit stack avoids a self-referential recursive closure per frame:
    # replay traffic must not rely on cyclic GC to keep allocations bounded.
    while pending:
        value, depth = pending.pop()
        remaining -= 1
        if remaining < 0:
            raise ProtocolError("JSON value budget exceeded.")
        kind = type(value)
        if kind is dict or kind is list:
            if depth > MAX_NESTING:
                raise ProtocolError("JSON nesting limit exceeded.")
            if len(value) > MAX_CONTAINER_ITEMS:
                raise ProtocolError("JSON container member limit exceeded.")
            if kind is dict:
                for key, child in value.items():
                    _identifier(key)
                    pending.append((child, depth + 1))
            else:
                for child in value:
                    pending.append((child, depth + 1))
        elif kind is str:
            _utf8_text(value, MAX_STRING_BYTES)
        elif kind is int or kind is float:
            _finite_number(value)
        elif value is not None and kind is not bool:
            raise ProtocolError("Only plain JSON values are supported.")
    # Cycles hit the depth limit; repeated acyclic references remain legal.


def _check_nesting(text: str) -> None:
    """Check depth before json.loads can recurse on attacker-controlled JSON."""
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "{[":
            depth += 1
            if depth > MAX_NESTING:
                raise ProtocolError("JSON nesting limit exceeded.")
        elif character in "}]":
            depth -= 1
            if depth < 0:
                raise ProtocolError("Malformed JSON frame.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len(pairs) > MAX_CONTAINER_ITEMS:
        raise ProtocolError("JSON container member limit exceeded.")
    result: dict[str, Any] = {}
    for key, value in pairs:
        _identifier(key)
        if key in result:
            raise ProtocolError("Duplicate JSON object key.")
        result[key] = value
    return result


def _parse_integer(token: str) -> int:
    if len(token) > 20:
        raise ProtocolError("JSON integer token exceeds the supported range.")
    value = int(token)
    _finite_number(value)
    return value


def _parse_float(token: str) -> float:
    if len(token) > MAX_FLOAT_TOKEN_CHARS:
        raise ProtocolError("JSON float token limit exceeded.")
    value = float(token)
    _finite_number(value)
    return value


def _reject_constant(_token: str) -> NoReturn:
    raise ProtocolError("Non-finite JSON numbers are forbidden.")


def _decode_json(body: bytes) -> Any:
    text: str | None = None
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        pass
    if text is None:
        raise ProtocolError("Invalid UTF-8 frame.")
    _check_nesting(text)
    failure: str | None = None
    value: Any = None
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_int=_parse_integer, parse_float=_parse_float,
                           parse_constant=_reject_constant)
    except ProtocolError as error:
        failure = str(error)
    except (ValueError, RecursionError, OverflowError):
        failure = "Malformed JSON frame."
    if failure is not None:
        # JSONDecodeError.doc and UnicodeError.object can contain the nonce.
        # Neither their messages nor their exception chains cross this boundary.
        raise ProtocolError(failure)
    return value


class FrameCodec:
    """Encode complete envelopes and incrementally receive authenticated frames."""

    def __init__(self, session_id: str, nonce: str) -> None:
        self._session_id = _identifier(session_id)
        self._nonce = _identifier(nonce)
        self._buffer = bytearray()
        self._expected_body: int | None = None
        self._seen_ids: set[str] = set()
        self._poisoned = False

    def _validate_envelope(self, message: Any) -> None:
        if (type(message) is not dict or len(message) != len(_ENVELOPE_KEYS)
                or any(type(key) is not str for key in message)
                or message.keys() != _ENVELOPE_KEYS):
            raise ProtocolError("Envelope must contain exactly the protocol fields.")
        version = message["protocol_version"]
        if type(version) is not int or version != PROTOCOL_VERSION:
            raise ProtocolError("Unsupported protocol version.")
        session_id = _identifier(message["session_id"])
        nonce = _identifier(message["nonce"])
        session_matches = hmac.compare_digest(session_id, self._session_id)
        nonce_matches = hmac.compare_digest(nonce, self._nonce)
        if not session_matches or not nonce_matches:
            raise ProtocolError("Session authentication failed.")
        _identifier(message["message_id"])
        _identifier(message["type"])
        if message["type"] not in _MESSAGE_TYPES:
            raise ProtocolError("Unsupported message type.")
        payload = message["payload"]
        if type(payload) is not dict:
            raise ProtocolError("Message payload must be an object.")
        if message["type"] == "control":
            action = payload.get("action")
            _identifier(action)
            if action not in _CONTROL_ACTIONS:
                raise ProtocolError("Unsupported control action.")
        for key in _PAYLOAD_IDENTIFIERS:
            if key in payload:
                _identifier(payload[key])
        if "persisted" in payload and type(payload["persisted"]) is not bool:
            raise ProtocolError("Persistence acknowledgement must be a boolean.")
        _validate_json_tree(message)

    def encode(self, message: dict[str, Any]) -> bytes:
        """Validate and encode an envelope without mutating it or consuming IDs."""
        self._validate_envelope(message)
        body = bytearray()
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                                   separators=(",", ":"))
        # Do not allocate a potentially multi-megabyte serialization before
        # noticing the frame limit; each validated text chunk is itself bounded.
        for chunk in encoder.iterencode(message):
            encoded = chunk.encode("utf-8")
            if len(body) + len(encoded) > MAX_FRAME_BYTES:
                raise ProtocolError("Encoded frame exceeds the size limit.")
            body.extend(encoded)
        return _HEADER.pack(len(body)) + bytes(body)

    def _poison(self, reason: str) -> NoReturn:
        self._poisoned = True
        self._buffer.clear()
        self._expected_body = None
        self._seen_ids.clear()
        raise ProtocolError(reason)

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        """Return new complete messages; any bad frame irreversibly fails closed.

        An invalid Python argument is not a received frame: non-bytes inputs
        raise without consuming or poisoning a pending valid frame.
        """
        if self._poisoned:
            raise ProtocolError("Parser is unusable after a protocol failure.")
        if type(data) is not bytes:
            raise ProtocolError("Transport input must be bytes.")
        messages: list[dict[str, Any]] = []
        offset = 0
        view = memoryview(data)
        while offset < len(view):
            target = _HEADER.size if self._expected_body is None else self._expected_body
            take = min(target - len(self._buffer), len(view) - offset)
            self._buffer.extend(view[offset:offset + take])
            offset += take
            if len(self._buffer) < target:
                break
            if self._expected_body is None:
                length = _HEADER.unpack(self._buffer)[0]
                if not 1 <= length <= MAX_FRAME_BYTES:
                    self._poison("Invalid frame length.")
                self._buffer.clear()
                self._expected_body = length
                continue
            body = bytes(self._buffer)
            self._buffer.clear()
            self._expected_body = None
            failure: str | None = None
            try:
                message = _decode_json(body)
                self._validate_envelope(message)
            except ProtocolError as error:
                failure = str(error)
            if failure is not None:
                self._poison(failure)
            message_id = message["message_id"]
            if message_id in self._seen_ids:
                continue
            if len(self._seen_ids) >= MAX_MESSAGE_IDS:
                self._poison("Session message ID budget exceeded.")
            self._seen_ids.add(message_id)
            messages.append(message)
        return messages
