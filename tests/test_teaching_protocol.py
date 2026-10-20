# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop-free contract and hostile-stream tests for teaching IPC."""
from __future__ import annotations

import copy
import gc
import importlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tracemalloc
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SESSION = "teaching-session-1"
NONCE = "sensitive-test-nonce-DO-NOT-ECHO"
MESSAGE_TYPES = (
    "hello", "ready", "activated", "control", "chapter_state", "state_ack",
    "error", "stopping", "stopped",
)


def message(kind="ready", message_id="message-1", payload=None):
    return {
        "protocol_version": 1,
        "session_id": SESSION,
        "nonce": NONCE,
        "message_id": message_id,
        "type": kind,
        "payload": {} if payload is None else payload,
    }


def json_body(envelope):
    """Independent wire fixture, not the codec's encoder."""
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def raw_frame(body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return struct.pack(">I", len(body)) + body


def frame(envelope):
    return raw_frame(json_body(envelope))


def nested_payload(container_count):
    value = "leaf"
    for _ in range(container_count):
        value = [value]
    return {"data": value}


def sized_message(size):
    """Fill a frame without crossing the separate 4096-byte string limit."""
    envelope = message(payload={"chunks": ["x" * 4096 for _ in range(15)],
                                "padding": ""})
    padding = size - len(json_body(envelope))
    assert 0 <= padding <= 4096
    envelope["payload"]["padding"] = "x" * padding
    assert len(json_body(envelope)) == size
    return envelope


class FrameCodecTests(unittest.TestCase):
    def setUp(self):
        # A missing implementation is an explicit RED assertion, not a
        # collection error or a test-only substitute for the production API.
        try:
            self.protocol = importlib.import_module("teaching.protocol")
        except ModuleNotFoundError as error:
            if error.name not in ("teaching", "teaching.protocol"):
                raise
            self.fail("teaching.protocol is not implemented")
        self.codec = self.new_codec()

    def new_codec(self):
        return self.protocol.FrameCodec(SESSION, NONCE)

    def assert_rejected(self, envelope):
        with self.assertRaises(self.protocol.ProtocolError):
            self.new_codec().encode(envelope)
        # ensure_ascii also lets the receiver see escaped lone surrogates.
        body = json.dumps(envelope, ensure_ascii=True, separators=(",", ":"))
        self.assert_bad_frame(raw_frame(body))

    def assert_bad_frame(self, bad_frame):
        codec = self.new_codec()
        with self.assertRaises(self.protocol.ProtocolError):
            codec.feed(bad_frame)
        for suffix in (b"", frame(message(message_id="after-error"))):
            with self.assertRaises(self.protocol.ProtocolError):
                codec.feed(suffix)

    def test_public_contract(self):
        self.assertEqual(self.protocol.PROTOCOL_VERSION, 1)
        self.assertEqual(self.protocol.MAX_FRAME_BYTES, 65536)
        self.assertTrue(issubclass(self.protocol.ProtocolError, ValueError))
        self.assertEqual(self.codec.feed(b""), [])

    def test_encoder_emits_network_length_and_utf8_json(self):
        envelope = message(payload={"text": "教学 🚀"})
        original = copy.deepcopy(envelope)
        encoded = self.codec.encode(envelope)
        self.assertIs(type(encoded), bytes)
        self.assertEqual(struct.unpack(">I", encoded[:4])[0], len(encoded) - 4)
        self.assertEqual(json.loads(encoded[4:].decode("utf-8")), envelope)
        self.assertIn("教学 🚀".encode("utf-8"), encoded[4:])
        self.assertEqual(envelope, original)

    def test_all_message_types_round_trip(self):
        for kind in MESSAGE_TYPES:
            with self.subTest(kind=kind):
                payload = {"action": "activate"} if kind == "control" else {}
                envelope = message(kind, payload=payload)
                self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)),
                                 [envelope])

    def test_all_control_actions_round_trip(self):
        for action in ("activate", "pause", "resume", "stop"):
            with self.subTest(action=action):
                envelope = message("control", payload={"action": action})
                self.assertEqual(self.new_codec().feed(frame(envelope)), [envelope])
                self.assertEqual(json.loads(self.codec.encode(envelope)[4:]), envelope)

    def test_payload_json_primitives_round_trip(self):
        envelope = message(payload={
            "text": "", "null": None, "yes": True, "no": False,
            "minimum": -(1 << 63), "maximum": (1 << 63) - 1,
            "fraction": 0.125, "negative_zero": -0.0,
            "array": [None, True, 1, 0.5, "text", {"inner": [2]}],
        })
        self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])

    def test_broker_owns_catalog_membership_and_phase_transitions(self):
        envelope = message("chapter_state", payload={
            "course_id": "future-course", "chapter_id": "future-chapter",
            "step_id": "future-step", "phase": "future-phase",
        })
        self.assertEqual(self.codec.feed(frame(envelope)), [envelope])

    def test_false_persistence_ack_is_not_coerced_to_true(self):
        envelope = message("state_ack", payload={"persisted": False})
        decoded = self.codec.feed(self.codec.encode(envelope))
        self.assertIs(decoded[0]["payload"]["persisted"], False)

    def test_every_two_part_fragmentation_preserves_the_message(self):
        envelope = message(payload={"text": "fragmented 教学 🚀"})
        encoded = frame(envelope)
        for split in range(len(encoded) + 1):
            with self.subTest(split=split):
                codec = self.new_codec()
                self.assertEqual(codec.feed(encoded[:split]) + codec.feed(encoded[split:]),
                                 [envelope])

    def test_byte_at_a_time_and_empty_reads(self):
        envelope = message(payload={"text": "教学"})
        encoded = frame(envelope)
        for byte in encoded[:-1]:
            self.assertEqual(self.codec.feed(bytes((byte,))), [])
            self.assertEqual(self.codec.feed(b""), [])
        self.assertEqual(self.codec.feed(encoded[-1:]), [envelope])

    def test_multiple_frames_per_read_preserve_order(self):
        envelopes = [message(kind, str(index), {"action": "pause"} if kind == "control"
                             else {}) for index, kind in enumerate(MESSAGE_TYPES)]
        self.assertEqual(self.codec.feed(b"".join(frame(item) for item in envelopes)),
                         envelopes)

    def test_complete_frames_plus_a_partial_header(self):
        first, second = message(message_id="first"), message(message_id="second")
        encoded_second = frame(second)
        self.assertEqual(self.codec.feed(frame(first) + encoded_second[:2]), [first])
        self.assertEqual(self.codec.feed(encoded_second[2:]), [second])

    def test_complete_frames_plus_a_partial_body(self):
        first, second = message(message_id="first"), message(message_id="second")
        encoded_second = frame(second)
        self.assertEqual(self.codec.feed(frame(first) + encoded_second[:-1]), [first])
        self.assertEqual(self.codec.feed(encoded_second[-1:]), [second])

    def test_deterministic_random_transport_fragmentations(self):
        envelopes = [message(kind, str(index), {"action": "resume"} if kind == "control"
                             else {"text": "教学 🚀"})
                     for index, kind in enumerate(MESSAGE_TYPES)]
        wire = b"".join(frame(item) for item in envelopes)
        randomizer = random.Random(20261007)
        for trial in range(40):
            with self.subTest(trial=trial):
                codec, decoded, offset = self.new_codec(), [], 0
                while offset < len(wire):
                    count = randomizer.randint(1, 97)
                    decoded.extend(codec.feed(wire[offset:offset + count]))
                    offset += count
                self.assertEqual(decoded, envelopes)

    def test_maximum_frame_is_accepted_by_encoder_and_receiver(self):
        envelope = sized_message(65536)
        encoded = self.codec.encode(envelope)
        self.assertEqual(len(encoded), 65540)
        self.assertEqual(self.new_codec().feed(encoded), [envelope])

    def test_oversized_encoded_frame_is_rejected(self):
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.encode(sized_message(65537))

    def test_invalid_header_lengths_fail_without_waiting_for_a_body(self):
        for length in (0, 65537, (1 << 32) - 1):
            with self.subTest(length=length):
                self.assert_bad_frame(struct.pack(">I", length))

    def test_fragmented_invalid_header_fails_on_the_fourth_byte(self):
        for length in (0, 65537, (1 << 32) - 1):
            with self.subTest(length=length):
                codec = self.new_codec()
                header = struct.pack(">I", length)
                for byte in header[:3]:
                    self.assertEqual(codec.feed(bytes((byte,))), [])
                with self.assertRaises(self.protocol.ProtocolError):
                    codec.feed(header[3:])
                with self.assertRaises(self.protocol.ProtocolError):
                    codec.feed(frame(message()))

    def test_non_dict_envelopes_are_rejected(self):
        for envelope in (None, [], [message()], "text", 1, 1.5, True):
            with self.subTest(envelope=envelope):
                self.assert_rejected(envelope)

    def test_each_envelope_key_is_required(self):
        for key in message():
            with self.subTest(key=key):
                envelope = message()
                del envelope[key]
                self.assert_rejected(envelope)

    def test_unknown_envelope_fields_are_rejected(self):
        for key in ("extra", "action", "session", "protocolVersion", "__proto__"):
            with self.subTest(key=key):
                envelope = message()
                envelope[key] = "untrusted"
                self.assert_rejected(envelope)

    def test_version_requires_the_exact_supported_integer(self):
        for version in (None, False, True, 0, -1, 2, "1", 1.0, [], {}):
            with self.subTest(version=version):
                envelope = message()
                envelope["protocol_version"] = version
                self.assert_rejected(envelope)

    def test_unknown_or_non_string_message_types_are_rejected(self):
        for kind in ("", "HELLO", "run", "stop", "ready ", None, 1, True, [], {}):
            with self.subTest(kind=kind):
                envelope = message()
                envelope["type"] = kind
                self.assert_rejected(envelope)

    def test_wrong_session_and_nonce_are_rejected(self):
        for key in ("session_id", "nonce"):
            with self.subTest(key=key):
                envelope = message()
                envelope[key] = "another-session-or-nonce"
                self.assert_rejected(envelope)

    def test_envelope_identifiers_require_bounded_nonblank_text(self):
        for key in ("session_id", "nonce", "message_id"):
            for value in (None, 1, True, [], {}, "", " ", "\t", "x" * 129,
                          "x\x00y", "x\ny", "x\x7fy", "\ud800"):
                with self.subTest(key=key, value=repr(value)):
                    envelope = message()
                    envelope[key] = value
                    self.assert_rejected(envelope)

    def test_maximum_ascii_identifiers_are_accepted(self):
        codec = self.protocol.FrameCodec("s" * 128, "n" * 128)
        envelope = message(message_id="m" * 128)
        envelope.update(session_id="s" * 128, nonce="n" * 128)
        self.assertEqual(codec.feed(codec.encode(envelope)), [envelope])

    def test_identifier_limits_count_utf8_bytes(self):
        codec = self.protocol.FrameCodec("é" * 64, "界" * 42)
        envelope = message(message_id="é" * 64)
        envelope.update(session_id="é" * 64, nonce="界" * 42)
        self.assertEqual(codec.feed(codec.encode(envelope)), [envelope])
        for key in ("session_id", "nonce", "message_id"):
            with self.subTest(key=key):
                bad = message()
                bad[key] = "é" * 65
                self.assert_rejected(bad)

    def test_constructor_rejects_invalid_credentials(self):
        for invalid in (None, False, 1, b"text", [], {}, "", " ", "\n",
                        "x" * 129, "é" * 65, "x\x00y", "\ud800"):
            for credentials in ((invalid, NONCE), (SESSION, invalid)):
                with self.subTest(credentials=repr(credentials)):
                    with self.assertRaises(self.protocol.ProtocolError):
                        self.protocol.FrameCodec(*credentials)

    def test_payload_must_be_an_object(self):
        for payload in (None, [], "", 0, True, 0.5):
            with self.subTest(payload=payload):
                envelope = message()
                envelope["payload"] = payload
                self.assert_rejected(envelope)

    def test_control_action_is_required(self):
        self.assert_rejected(message("control"))

    def test_control_actions_cannot_invoke_arbitrary_operations(self):
        for action in (None, True, 1, [], {}, "", "run", "exec", "shutdown",
                       "ACTIVATE", "pause ", "x" * 4097):
            with self.subTest(action=action):
                self.assert_rejected(message("control", payload={"action": action}))

    def test_control_allows_bounded_selection_metadata(self):
        envelope = message("control", payload={"action": "activate", "course_id": "c01",
                                               "chapter_id": "c01.ink", "hide": False})
        self.assertEqual(self.codec.feed(self.codec.encode(envelope)), [envelope])

    def test_catalog_identifiers_and_phase_have_valid_primitive_types(self):
        for key in ("course_id", "chapter_id", "step_id", "phase"):
            for value in (None, True, 1, 1.5, [], {}, "", " ", "x" * 129,
                          "x\x00y"):
                with self.subTest(key=key, value=value):
                    self.assert_rejected(message("chapter_state", payload={key: value}))

    def test_persisted_requires_a_real_boolean(self):
        for value in (None, 0, 1, 0.0, "true", "false", [], {}):
            with self.subTest(value=value):
                self.assert_rejected(message("state_ack", payload={"persisted": value}))

    def test_duplicate_keys_are_rejected_at_every_depth(self):
        body = json_body(message()).decode("utf-8")
        cases = (
            body[:-1] + ',"message_id":"second"}',
            body[:-1] + ',"nonce":"wrong"}',
            body.replace('"payload":{}', '"payload":{"same":1,"same":2}'),
            body.replace('"payload":{}', '"payload":{"same":1,"\\u0073ame":2}'),
            body.replace('"payload":{}', '"payload":{"nested":[{"x":1,"x":2}]}'),
        )
        for bad in cases:
            with self.subTest(body=bad):
                self.assert_bad_frame(raw_frame(bad))

    def test_invalid_utf8_is_rejected(self):
        for body in (b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"\xf4\x90\x80\x80",
                     json_body(message())[:-1] + b'"bad":"\xff"}'):
            with self.subTest(body=repr(body)):
                self.assert_bad_frame(raw_frame(body))

    def test_malformed_json_and_trailing_json_are_rejected(self):
        valid = json_body(message()).decode("utf-8")
        bodies = (" ", "{", "}", valid + "{}", valid + " trailing", "\ufeff" + valid,
                  "/* comment */" + valid, '{"x":01}', '{"x":1,}', '{x:1}',
                  '{"x":"bad\\x"}', '{"x":"bad\ntext"}', '"unterminated')
        for body in bodies:
            with self.subTest(body=body):
                self.assert_bad_frame(raw_frame(body))

    def test_standard_json_whitespace_is_accepted(self):
        envelope = message()
        self.assertEqual(self.codec.feed(raw_frame(b" \r\n" + json_body(envelope) + b"\t ")),
                         [envelope])

    def test_nan_and_infinity_are_rejected_in_any_position(self):
        for token in ("NaN", "Infinity", "-Infinity", "1e309", "-1e309"):
            for location in ("number", "array", "nested"):
                with self.subTest(token=token, location=location):
                    payloads = {
                        "number": '{"number":' + token + '}',
                        "array": '{"array":[' + token + ']}',
                        "nested": '{"nested":{"number":' + token + '}}',
                    }
                    body = json_body(message()).decode("utf-8").replace(
                        '"payload":{}', '"payload":' + payloads[location])
                    self.assert_bad_frame(raw_frame(body))
        for number in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(number=repr(number)):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.encode(message(payload={"number": number}))

    def test_numeric_magnitudes_are_bounded(self):
        for number in (-(1 << 63) - 1, 1 << 63, 1 << 200, 1e20, -1e20):
            with self.subTest(number=number):
                self.assert_rejected(message(payload={"number": number}))

    def test_finite_float_boundaries_are_accepted(self):
        for number in (float(-(1 << 63)), float.fromhex("0x1.fffffffffffffp+62"),
                       1e-300, 0.0, -0.0):
            with self.subTest(number=number):
                envelope = message(payload={"number": number})
                self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])

    def test_overlong_numeric_tokens_fail_without_interpreter_exceptions(self):
        for token in ("9" * 5000, "0." + "0" * 62 + "1", "1e" + "9" * 63):
            with self.subTest(length=len(token)):
                body = json_body(message()).decode("utf-8").replace(
                    '"payload":{}', '"payload":{"number":' + token + '}')
                self.assert_bad_frame(raw_frame(body))

    def test_maximum_float_token_length_is_accepted(self):
        token = "0." + "0" * 61 + "1"
        self.assertEqual(len(token), 64)
        envelope = message(payload={"number": 1e-62})
        body = json_body(message()).decode("utf-8").replace(
            '"payload":{}', '"payload":{"number":' + token + '}')
        self.assertEqual(self.codec.feed(raw_frame(body)), [envelope])

    def test_maximum_payload_string_bytes_are_accepted(self):
        for text in ("x" * 4096, "é" * 2048, "🚀" * 1024):
            with self.subTest(byte_count=len(text.encode("utf-8"))):
                envelope = message(payload={"text": text})
                self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])

    def test_overlong_payload_strings_are_rejected(self):
        for text in ("x" * 4097, "é" * 2049, "🚀" * 1025):
            with self.subTest(byte_count=len(text.encode("utf-8"))):
                self.assert_rejected(message(payload={"text": text}))

    def test_unpaired_surrogates_are_rejected_but_valid_escaped_pairs_work(self):
        for text in ("\ud800", "\udfff", "x\ud800y"):
            with self.subTest(text=repr(text)):
                self.assert_rejected(message(payload={"text": text}))
        envelope = message(payload={"text": "🚀"})
        escaped = json.dumps(envelope, ensure_ascii=True)
        self.assertEqual(self.codec.feed(raw_frame(escaped)), [envelope])

    def test_payload_object_keys_are_bounded_utf8_strings(self):
        for key in ("x" * 128, "é" * 64):
            with self.subTest(key=key):
                envelope = message(payload={key: 1})
                self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])
        for key in ("", "x" * 129, "é" * 65, "\ud800"):
            with self.subTest(key=repr(key)):
                self.assert_rejected(message(payload={key: 1}))
        for key in (1, True, None, b"key"):
            with self.subTest(key=repr(key)):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.encode(message(payload={key: 1}))

    def test_container_item_limit_accepts_256_and_rejects_257(self):
        for size in (256, 257):
            for container in ([0] * size, {str(index): 0 for index in range(size)}):
                with self.subTest(size=size, container_type=type(container).__name__):
                    envelope = message(payload={"items": container})
                    if size == 256:
                        self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)),
                                         [envelope])
                    else:
                        self.assert_rejected(envelope)

    def test_total_json_value_budget_accepts_4096_and_rejects_4097(self):
        # Eight envelope/outer-list values + sixteen inner lists + their leaves.
        for last_count in (232, 233):
            with self.subTest(last_count=last_count):
                payload = {"nodes": [list(range(256)) for _ in range(15)]
                           + [list(range(last_count))]}
                envelope = message(payload=payload)
                if last_count == 232:
                    self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])
                else:
                    self.assert_rejected(envelope)

    def test_sixteen_container_levels_are_accepted(self):
        envelope = message(payload=nested_payload(14))
        self.assertEqual(self.codec.feed(self.codec.encode(envelope)), [envelope])

    def test_seventeen_container_levels_are_rejected(self):
        self.assert_rejected(message(payload=nested_payload(15)))

    def test_hostile_thousands_deep_json_is_rejected_before_recursion(self):
        body = json_body(message()).decode("utf-8").replace(
            '"payload":{}', '"payload":{"deep":' + "[" * 4000 + "0" + "]" * 4000 + "}")
        self.assert_bad_frame(raw_frame(body))

    def test_mixed_object_and_array_nesting_counts_both(self):
        value = "leaf"
        for index in range(14):
            value = [value] if index % 2 else {"inner": value}
        envelope = message(payload={"data": value})
        self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])
        self.assert_rejected(message(payload={"data": [value]}))

    def test_brackets_quotes_and_backslashes_in_strings_do_not_count_as_nesting(self):
        for text in ("[" * 1000, "}" * 1000, '"[\\]"' * 300, '\\\\"{{[' * 300):
            with self.subTest(text=text[:20]):
                envelope = message(payload={"text": text})
                self.assertEqual(self.new_codec().feed(self.codec.encode(envelope)), [envelope])

    def test_non_json_python_values_are_rejected_without_coercion(self):
        class CustomDict(dict):
            pass

        class CustomList(list):
            pass

        class CustomInt(int):
            pass

        class CustomText(str):
            pass

        for value in (b"bytes", bytearray(b"bytes"), memoryview(b"bytes"), {1, 2},
                      (1, 2), object(), CustomDict(a=1), CustomList([1]),
                      CustomInt(1), CustomText("text")):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.encode(message(payload={"value": value}))
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.encode(CustomDict(message()))

    def test_cyclic_python_payloads_are_rejected_without_recursion_errors(self):
        items = []
        items.append(items)
        mapping = {}
        mapping["self"] = mapping
        for value in (items, mapping):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.encode(message(payload={"value": value}))

    def test_repeated_acyclic_container_references_remain_valid_json(self):
        shared = [1, {"value": 2}]
        envelope = message(payload={"first": shared, "second": shared})
        self.assertEqual(self.codec.feed(self.codec.encode(envelope)), [envelope])

    def test_duplicate_message_ids_are_ignored_within_and_across_reads(self):
        first = message(payload={"value": 1})
        changed = message(payload={"value": 2})
        second = message(message_id="second")
        self.assertEqual(self.codec.feed(frame(first) + frame(first) + frame(changed)), [first])
        self.assertEqual(self.codec.feed(frame(changed) + frame(second)), [second])
        self.assertEqual(self.codec.feed(frame(first)), [])

    def test_encoding_does_not_mark_an_incoming_id_as_seen(self):
        envelope = message()
        self.assertEqual(self.codec.encode(envelope), self.codec.encode(envelope))
        self.assertEqual(self.codec.feed(self.codec.encode(envelope)), [envelope])

    def test_seen_ids_are_not_shared_between_codec_instances(self):
        envelope = message()
        self.assertEqual(self.codec.feed(frame(envelope)), [envelope])
        self.assertEqual(self.new_codec().feed(frame(envelope)), [envelope])

    def test_replays_are_still_authenticated_and_validated(self):
        self.assertEqual(self.codec.feed(frame(message())), [message()])
        bad = message()
        bad["nonce"] = "invalid-nonce"
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(bad))
        for key, value in (("protocol_version", 2), ("type", "exec"), ("payload", [])):
            with self.subTest(key=key):
                codec = self.new_codec()
                codec.feed(frame(message()))
                replay = message()
                replay[key] = value
                with self.assertRaises(self.protocol.ProtocolError):
                    codec.feed(frame(replay))

    def test_seen_id_budget_never_evicts_old_ids_or_grows_unbounded(self):
        for index in range(4096):
            envelope = message(message_id=f"message-{index}")
            self.assertEqual(self.codec.feed(frame(envelope)), [envelope])
        self.assertEqual(self.codec.feed(frame(message(message_id="message-0"))), [])
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(message(message_id="message-4096")))
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(message(message_id="message-0")))

    def test_duplicate_reads_do_not_spend_the_unique_id_budget(self):
        first = message()
        self.assertEqual(self.codec.feed(frame(first) * 4097), [first])
        second = message(message_id="second")
        self.assertEqual(self.codec.feed(frame(second)), [second])

    def test_bad_frame_followed_by_good_suffix_poisons_the_parser(self):
        bad_nonce = message()
        bad_nonce["nonce"] = "not-the-nonce"
        for bad in (struct.pack(">I", 0), struct.pack(">I", 65537),
                    raw_frame("{"), raw_frame(b"\xff"), frame(bad_nonce)):
            with self.subTest(bad=repr(bad[:8])):
                self.assert_bad_frame(bad + frame(message(message_id="attacker-suffix")))

    def test_failure_after_a_valid_frame_still_poisoned_on_future_reads(self):
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(message()) + raw_frame("{") + frame(message(message_id="suffix")))
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(message(message_id="later")))

    def test_invalid_outbound_messages_do_not_damage_the_parser(self):
        for envelope in (message("run"), message("control"), sized_message(65537)):
            with self.subTest(kind=envelope["type"]):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.encode(envelope)
        valid = message()
        self.assertEqual(self.codec.feed(self.codec.encode(valid)), [valid])

    def test_non_bytes_input_is_rejected_without_consuming_partial_data(self):
        envelope = message()
        encoded = frame(envelope)
        self.assertEqual(self.codec.feed(encoded[:2]), [])
        for invalid in (None, "text", 0, [], bytearray(b"bytes"), memoryview(b"bytes")):
            with self.subTest(input_type=type(invalid).__name__):
                with self.assertRaises(self.protocol.ProtocolError):
                    self.codec.feed(invalid)
        self.assertEqual(self.codec.feed(encoded[2:]), [envelope])

    def test_errors_never_include_nonce_or_untrusted_message_content(self):
        sensitive_body = json_body(message()).decode("utf-8")
        bodies = (sensitive_body + " garbage",
                  sensitive_body.replace('"payload":{}', '"payload":{"x":1,"x":2}'),
                  sensitive_body.replace('"payload":{}', '"payload":{"x":NaN}'))
        for body in bodies:
            with self.subTest(case=body[-20:]):
                try:
                    self.new_codec().feed(raw_frame(body))
                except self.protocol.ProtocolError as error:
                    rendered = "".join(traceback.format_exception(error))
                    self.assertNotIn(NONCE, str(error))
                    self.assertNotIn(NONCE, repr(error))
                    self.assertNotIn(NONCE, rendered)
                    self.assertIsNone(error.__cause__)
                    self.assertIsNone(error.__context__)
                else:
                    self.fail("Malformed sensitive frame was accepted")
        envelope = message()
        envelope["nonce"] = NONCE + "-mismatch"
        with self.assertRaises(self.protocol.ProtocolError) as caught:
            self.codec.encode(envelope)
        self.assertNotIn(NONCE, str(caught.exception))

    def test_transport_read_is_not_copied_into_an_unbounded_buffer(self):
        envelope = message(payload={"text": "x" * 4096})
        wire = frame(envelope) * 1024
        tracemalloc.start()
        try:
            decoded = self.codec.feed(wire)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(decoded, [envelope])
        self.assertLess(peak, 65536 * 8)

    def test_oversized_header_never_buffers_an_attacker_suffix(self):
        wire = struct.pack(">I", 65537) + b"x" * (2 * 1024 * 1024)
        tracemalloc.start()
        try:
            with self.assertRaises(self.protocol.ProtocolError):
                self.codec.feed(wire)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 65536 * 8)
        with self.assertRaises(self.protocol.ProtocolError):
            self.codec.feed(frame(message()))

    def test_replays_do_not_accumulate_cycles_when_cyclic_gc_is_disabled(self):
        envelope = message()
        wire = frame(envelope) * 4096
        was_enabled = gc.isenabled()
        gc.collect()
        gc.disable()
        tracemalloc.start()
        try:
            decoded = self.codec.feed(wire)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            if was_enabled:
                gc.enable()
            gc.collect()
        self.assertEqual(decoded, [envelope])
        self.assertLess(peak, 65536 * 8)

    def test_protocol_import_and_round_trip_require_no_qt_or_other_teaching_modules(self):
        code = (
            "import sys; from teaching.protocol import FrameCodec; "
            "assert not any(n.startswith(('PyQt', 'PySide')) for n in sys.modules); "
            "assert not any(n.startswith('teaching.') and n != 'teaching.protocol' "
            "for n in sys.modules); "
            f"message = {message()!r}; "
            f"codec = FrameCodec({SESSION!r}, {NONCE!r}); "
            "assert codec.feed(codec.encode(message)) == [message]"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
