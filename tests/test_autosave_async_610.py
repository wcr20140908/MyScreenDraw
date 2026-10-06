# SPDX-License-Identifier: GPL-3.0-or-later
"""Async autosave must use revision caches and detached GUI-thread snapshots."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
from unittest.mock import Mock, patch
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication
import main
from test_document_safety_610 import document, ink, two_pages
from persistence import read_json_maybe_gz


@pytest.fixture
def autosave(document, tmp_path, monkeypatch):
    panel, canvas = document
    monkeypatch.setattr(main, "AUTOSAVE_DIR", str(tmp_path))
    monkeypatch.setattr(panel, "save_settings", lambda: None)
    yield panel, canvas, tmp_path
    panel.shutdown_autosave()


def test_unchanged_tick_does_not_clone_serialize_or_write(autosave):
    panel, canvas, root = autosave
    two_pages(canvas)
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    paths = list(root.glob("*.gz"))
    with patch.object(canvas, "capture_page", side_effect=AssertionError("unnecessary clone")), \
         patch.object(main, "serialize_page", side_effect=AssertionError("unnecessary serialize")), \
         patch.object(main, "atomic_write_autosave", side_effect=AssertionError("unnecessary write")):
        panel.auto_save()
        assert panel.wait_for_autosave(10)
    assert list(root.glob("*.gz")) == paths


def test_one_changed_page_only_serializes_that_page(autosave):
    panel, canvas, root = autosave
    two_pages(canvas)
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    canvas.switch_page(-1)
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    assert len(list(root.glob("*.gz"))) == 1
    ink(canvas, "third")
    with patch.object(main, "serialize_page", wraps=main.serialize_page) as serialize:
        panel.auto_save()
        assert panel.wait_for_autosave(10)
        assert serialize.call_count == 1
    assert len(list(root.glob("*.gz"))) == 2


def test_background_write_does_not_block_gui_or_read_live_objects(autosave, monkeypatch):
    panel, canvas, root = autosave
    ink(canvas, "before")
    started, release = threading.Event(), threading.Event()
    original = main.atomic_write_autosave
    gui_thread = threading.get_ident()
    calls = []
    def slow_write(path, data):
        calls.append(threading.get_ident())
        started.set()
        assert release.wait(10)
        original(path, data)
    monkeypatch.setattr(main, "atomic_write_autosave", slow_write)
    try:
        panel.auto_save()
        assert started.wait(3)
        ink(canvas, "during")
        # A second timer tick cannot queue another full snapshot while I/O is busy.
        with patch.object(canvas, "serialized_document_pages", side_effect=AssertionError("queued redundant snapshot")):
            panel.auto_save()
        assert calls == [calls[0]] and calls[0] != gui_thread
    finally:
        release.set()
    assert panel.wait_for_autosave(10)
    first = read_json_maybe_gz(str(next(root.glob("*.gz"))))
    assert [s["id"] for s in first["pages"][0]["segments"]] == ["before"]
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    assert len(list(root.glob("*.gz"))) == 2


def test_failed_autosave_does_not_mark_snapshot_saved(autosave, monkeypatch):
    panel, canvas, root = autosave
    ink(canvas, "must-retry")
    original = main.atomic_write_autosave
    failing = Mock(side_effect=OSError("disk unavailable"))
    monkeypatch.setattr(main, "atomic_write_autosave", failing)
    panel.auto_save()
    assert not panel.wait_for_autosave(10)
    assert not list(root.glob("*.gz"))
    monkeypatch.setattr(main, "atomic_write_autosave", original)
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    assert len(list(root.glob("*.gz"))) == 1


def test_nonwhiteboard_autosave_preserves_other_pages(autosave):
    panel, canvas, root = autosave
    two_pages(canvas)
    canvas.exit_whiteboard()
    ink(canvas, "desktop")
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    payload = read_json_maybe_gz(str(next(root.glob("*.gz"))))
    assert len(payload["pages"]) == 2
    assert payload["current_page"] == 1
    assert not payload["whiteboard_mode"]
    assert [s["id"] for s in payload["pages"][1]["segments"]] == ["second", "desktop"]


def test_same_length_text_edit_outside_whiteboard_invalidates_cache(autosave):
    panel, canvas, root = autosave
    item = {"id": "text", "text": "old", "pos": QPointF(5, 5), "color": QColor("black"),
            "size": 24, "scale": 1.0, "rotation": 0, "width": 1}
    canvas.text_items.append(item)
    canvas.mark_content_changed()
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    item["text"] = "new"
    canvas._after_text_change(item)
    panel.auto_save()
    assert panel.wait_for_autosave(10)
    values = [read_json_maybe_gz(str(path))["pages"][0]["texts"][0]["text"] for path in root.glob("*.gz")]
    assert sorted(values) == ["new", "old"]


def test_shutdown_drains_safely_and_prevents_new_jobs(autosave):
    panel, canvas, root = autosave
    ink(canvas, "complete")
    panel.auto_save()
    panel.shutdown_autosave()
    assert len(list(root.glob("*.gz"))) == 1
    ink(canvas, "not-another-job")
    panel.auto_save()
    assert len(list(root.glob("*.gz"))) == 1
