# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistence contract for calculator history."""
from datetime import datetime, timedelta, timezone
import json
import pytest
from decimal import Decimal

import pytest

import calculator_history


NOW = datetime(2026, 10, 24, 8, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize('mode,payload', [
    ('base', {'source_base': []}), ('basic', {'canonical': 1}),
    ('basic', {'ans': '1e9999999999999999999'}),
    ('statistics', {'values': 4}), ('statistics', {'values': ['NaN']}),
    ('statistics', {'summary': {'mean': {}}}), ('unit', {'source_unit': []}),
])
def test_mode_payload_types_are_checked_before_display_or_restore(tmp_path, mode, payload):
    path = tmp_path / 'history.json'
    entry = calculator_history.HistoryEntry('bad', NOW, mode, '1', '1', payload)
    original = json.dumps({'schema_version': 1, 'entries': [entry.to_dict()]})
    path.write_text(original, encoding='utf-8')
    store = calculator_history.CalculatorHistoryStore(path, retention='forever')
    assert store.load() == []
    assert store.read_error
    assert path.read_text(encoding='utf-8') == original


def test_session_history_never_reads_or_writes_disk(tmp_path):
    path = tmp_path / "calculator-history.json"
    path.write_text("not json", encoding="utf-8")
    store = calculator_history.CalculatorHistoryStore(path, retention="session", now=lambda: NOW)

    store.load()
    store.add("basic", "2+3", "5")

    assert [entry.result for entry in store.entries] == ["5"]
    assert path.read_text(encoding="utf-8") == "not json"
    assert store.read_error is None


def test_persistent_history_prunes_expired_entries_and_caps_newest_100(tmp_path):
    path = tmp_path / "calculator-history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="1d", now=lambda: NOW)
    store.entries = [
        calculator_history.HistoryEntry("old", NOW - timedelta(days=2), "basic", "1+1", "2", {}),
        calculator_history.HistoryEntry("fresh", NOW - timedelta(hours=2), "scientific", "sin(30)", "0.5", {}),
    ]
    store.save()

    reopened = calculator_history.CalculatorHistoryStore(path, retention="1d", now=lambda: NOW)
    reopened.load()
    assert [entry.id for entry in reopened.entries] == ["fresh"]

    for index in range(110):
        reopened.add("basic", str(index), str(index), {"index": index})
    assert len(reopened.entries) == 100
    assert reopened.entries[0].input == "10"
    assert reopened.entries[-1].input == "109"


def test_history_search_filter_delete_and_clear_are_explicit(tmp_path):
    path = tmp_path / "calculator-history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    first = store.add("basic", "2+3", "5")
    second = store.add("unit", "1000 mm", "1 m", {"category": "length"})

    assert [item.id for item in store.search("mm")] == [second.id]
    assert [item.id for item in store.search("", mode="basic")] == [first.id]
    assert store.delete(first.id)
    assert [item.id for item in store.entries] == [second.id]
    store.clear()
    assert store.entries == []
    assert json.loads(path.read_text(encoding="utf-8")) == {"schema_version": 1, "entries": []}


def test_corrupt_history_is_visible_and_not_overwritten_until_explicit_clear(tmp_path):
    path = tmp_path / "calculator-history.json"
    original = "{broken"
    path.write_text(original, encoding="utf-8")
    store = calculator_history.CalculatorHistoryStore(path, retention="30d", now=lambda: NOW)

    store.load()
    store.add("basic", "2+3", "5")

    assert store.read_error
    assert path.read_text(encoding="utf-8") == original
    store.clear()
    assert store.read_error is None
    assert json.loads(path.read_text(encoding="utf-8"))["entries"] == []


def test_history_round_trips_canonical_payload_without_decimal_objects(tmp_path):
    path = tmp_path / "calculator-history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="7d", now=lambda: NOW)
    entry = store.add("statistics", "1;2;3", "mean=2", {
        "values": ["1", "2", "3"],
        "summary": {"mean": "2", "count": 3},
    })

    reopened = calculator_history.CalculatorHistoryStore(path, retention="7d", now=lambda: NOW)
    reopened.load()
    assert reopened.entries == [entry]



@pytest.mark.parametrize("version", [True, 1.0, "1", 2])
def test_history_requires_an_integer_schema_version_and_preserves_bad_bytes(tmp_path, version):
    path = tmp_path / "history.json"
    original = json.dumps({"schema_version": version, "entries": []})
    path.write_text(original, encoding="utf8")
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    store.load()
    store.add("basic", "1", "1")
    assert store.read_error
    assert path.read_text(encoding="utf8") == original


def test_deep_history_is_rejected_visibly_without_recursion_or_overwrite(tmp_path):
    path = tmp_path / "history.json"
    row = {"id": "a", "created_at": NOW.isoformat(), "mode": "basic", "input": "1", "result": "1"}
    prefix = json.dumps(row)[:-1] + ', "payload":{"x":'
    original = '{"schema_version":1,"entries":[' + prefix + '[' * 600 + '0' + ']' * 600 + '}}]}'
    path.write_text(original, encoding="utf8")
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    store.load()
    assert store.read_error
    store.add("basic", "2", "2")
    assert path.read_text(encoding="utf8") == original


@pytest.mark.parametrize("input_text,result,payload", [
    ("x" * (512 * 1024 + 1), "1", {}),
    ("1", "x" * (128 * 1024 + 1), {}),
    (1, "1", {}),
    ("1", "1", [1]),
    ("1", "1", {"value": float("nan")}),
    ("1", "1", {"value": Decimal("Infinity")}),
    ("1", "1", {1: "numeric dictionary key"}),
], ids=["input-size", "result-size", "input-type", "payload-type", "float-finite",
        "decimal-finite", "key-type"])
def test_invalid_add_is_rejected_before_mutating_or_writing(tmp_path, input_text, result, payload):
    path = tmp_path / "history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    first = store.add("basic", "1", "1")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        store.add("basic", input_text, result, payload)
    assert store.entries == [first]
    assert path.read_bytes() == original


def test_history_add_enforces_payload_depth_and_round_trips_supported_types(tmp_path):
    path = tmp_path / "history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    entry = store.add("statistics", "1;2", "mean=1.5", {
        "values": ["1", "2"], "summary": {"mean": Decimal("1.5"), "count": 2},
        "optional": None, "enabled": True, "weight": 0.25,
    })
    reopened = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    assert reopened.load() == [entry]
    nested = 0
    for _ in range(40):
        nested = [nested]
    with pytest.raises(ValueError):
        store.add("basic", "1", "1", {"nested": nested})
    assert store.entries == [entry]


def test_add_without_load_never_overwrites_unread_corrupt_history(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{broken", encoding="utf8")
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    entry = store.add("basic", "2+3", "5")
    assert store.entries == [entry]
    assert store.read_error
    assert path.read_text(encoding="utf8") == "{broken"


def test_session_to_persistent_merges_existing_and_session_entries(tmp_path):
    path = tmp_path / "history.json"
    old = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW - timedelta(hours=1))
    existing = old.add("basic", "1+1", "2")
    session = calculator_history.CalculatorHistoryStore(path, retention="session", now=lambda: NOW)
    current = session.add("scientific", "root(64,3)", "4")
    session.set_retention("forever")
    assert session.entries == [existing, current]
    reopened = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    assert reopened.load() == [existing, current]


def test_session_to_persistent_keeps_session_entries_when_disk_is_corrupt(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{broken", encoding="utf8")
    session = calculator_history.CalculatorHistoryStore(path, retention="session", now=lambda: NOW)
    current = session.add("basic", "1", "1")
    session.set_retention("7d")
    assert session.entries == [current]
    assert session.read_error
    assert path.read_text(encoding="utf8") == "{broken"


def test_failed_atomic_replace_preserves_original_and_removes_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    store.add("basic", "1", "1")
    original = path.read_bytes()
    def fail_replace(source, target):
        raise OSError("simulated replace failure")
    monkeypatch.setattr(calculator_history.os, "replace", fail_replace)
    store.add("basic", "2", "2")
    assert store.write_error == "simulated replace failure"
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]



def test_history_payload_total_size_and_collection_limits_are_bounded(tmp_path):
    path = tmp_path / "history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="session", now=lambda: NOW)
    for payload in (
        {"items": [0] * 10001},
        {str(index): "x" * (512 * 1024) for index in range(5)},
        {"escaped": "\x00" * (512 * 1024)},
    ):
        with pytest.raises(ValueError):
            store.add("basic", "1", "1", payload)
    assert store.entries == []
    assert not path.exists()


def test_history_payload_depth_boundary_round_trips(tmp_path):
    path = tmp_path / "history.json"
    nested = 0
    for _ in range(calculator_history.MAX_PAYLOAD_DEPTH - 1):
        nested = [nested]
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    entry = store.add("basic", "1", "1", {"nested": nested})
    reopened = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    assert reopened.load() == [entry]
    with pytest.raises(ValueError):
        store.add("basic", "1", "1", {"nested": [nested]})


def test_history_rejects_nonfinite_payloads_duplicate_ids_and_naive_timestamps(tmp_path):
    path = tmp_path / "history.json"
    row = calculator_history.HistoryEntry("same", NOW, "basic", "1", "1", {}).to_dict()
    documents = [
        {"schema_version": 1, "entries": [row, row]},
        {"schema_version": 1, "entries": [{**row, "created_at": "2026-10-24T08:00:00"}]},
        {"schema_version": 1, "entries": [{**row, "payload": {"value": float("inf")}}]},
    ]
    for document in documents:
        original = json.dumps(document)
        path.write_text(original, encoding="utf8")
        store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
        store.load()
        assert store.read_error
        store.add("basic", "2", "2")
        assert path.read_text(encoding="utf8") == original



def test_history_byte_cap_keeps_newest_entries_and_the_file_can_reopen(tmp_path):
    path = tmp_path / "history.json"
    store = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    last = None
    for index in range(5):
        last = store.add("basic", "x" * (512 * 1024), str(index))
    assert path.stat().st_size <= calculator_history.MAX_HISTORY_BYTES
    assert store.entries[-1] == last
    assert len(store.entries) == 3
    reopened = calculator_history.CalculatorHistoryStore(path, retention="forever", now=lambda: NOW)
    assert reopened.load() == store.entries
