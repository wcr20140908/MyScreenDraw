# SPDX-License-Identifier: GPL-3.0-or-later
"""6.1.0 document safety: actual widgets, isolated files, no visible desktop."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QLine
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QApplication, QMessageBox

import main
from persistence import read_json_maybe_gz


@pytest.fixture
def document(monkeypatch):
    app = QApplication.instance() or QApplication([])
    previous_windows = set(app.topLevelWidgets())
    panel = main.ControlPanel()
    canvas = main.DrawingCanvas(panel)
    panel.canvas = canvas
    panel.pause_callbacks()
    monkeypatch.setattr(main, "notify_user", Mock())
    monkeypatch.setattr(panel, "resume_callbacks", lambda: None)
    yield panel, canvas
    # Each parametrized case owns a complete Qt tree. Merely hiding it defers
    # native object destruction until arbitrary Python GC during a later ctor.
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(app, set(app.topLevelWidgets()) - previous_windows)


def ink(canvas, name):
    canvas.all_segments.append({"line": QLine(1, 2, 30, 40), "pen": QPen(), "id": name})
    canvas.mark_content_changed()


def two_pages(canvas):
    canvas.enter_whiteboard()
    ink(canvas, "first")
    canvas.new_page()
    ink(canvas, "second")


def test_save_after_exiting_whiteboard_retains_every_page(document, tmp_path):
    panel, canvas = document
    two_pages(canvas)
    canvas.exit_whiteboard()
    path = tmp_path / "all-pages.msd"
    assert panel.save_project(str(path))
    saved = read_json_maybe_gz(str(path))
    assert len(saved["pages"]) == 2
    assert saved["current_page"] == 1
    assert not saved["whiteboard_mode"]
    assert [p["segments"][0]["id"] for p in saved["pages"]] == ["first", "second"]
    assert panel.open_project_from_path(str(path))
    assert len(canvas.pages) == 2
    canvas.enter_whiteboard()
    canvas.switch_page(-1)
    assert str(canvas.all_segments[0]["id"]) == "first"


def test_autosave_restore_preserves_pages_when_not_in_whiteboard(document):
    panel, canvas = document
    two_pages(canvas)
    canvas.exit_whiteboard()
    data = main.make_project_data(
        pages=[main.serialize_page(p) for p in canvas.pages], current_page=1,
        whiteboard_mode=False, board_style="WHITE", app_version=main.APP_VERSION,
        kind=main.AUTOSAVE_KIND,
    )
    assert panel.apply_autosave_data(data)
    assert len(canvas.pages) == 2
    assert canvas.current_page == 1
    assert panel.has_unsaved_changes()


def test_real_ink_marks_unsaved_but_page_navigation_does_not(document, tmp_path):
    panel, canvas = document
    two_pages(canvas)
    assert panel.has_unsaved_changes()
    assert panel.save_project(str(tmp_path / "saved.msd"))
    assert not panel.has_unsaved_changes()
    canvas.switch_page(-1)
    assert not panel.has_unsaved_changes()
    canvas.switch_page(1)
    assert not panel.has_unsaved_changes()
    ink(canvas, "new")
    assert panel.has_unsaved_changes()


def target_file(tmp_path):
    path = tmp_path / "new.msd"
    main.atomic_write_json(str(path), main.make_project_data(
        pages=[{"segments": [], "texts": [], "shapes": [], "images": []}],
        current_page=0, whiteboard_mode=True, board_style="BLACK",
        app_version=main.APP_VERSION))
    return str(path)


@pytest.mark.parametrize("choice", [QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.NoButton])
def test_open_cancel_or_close_keeps_live_document(document, tmp_path, monkeypatch, choice):
    panel, canvas = document
    ink(canvas, "unsaved")
    before = canvas.capture_page()
    monkeypatch.setattr(QMessageBox, "exec", lambda box: int(choice))
    assert not panel.open_project_from_path(target_file(tmp_path))
    assert main.page_signature(canvas.capture_page()) == main.page_signature(before)
    assert panel.project_path is None


def test_open_discard_replaces_only_after_user_chooses(document, tmp_path, monkeypatch):
    panel, canvas = document
    ink(canvas, "unsaved")
    seen = []
    def choose(box):
        seen.append(box)
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.Cancel)
        assert box.escapeButton() == box.button(QMessageBox.StandardButton.Cancel)
        assert canvas.all_segments
        return int(QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, "exec", choose)
    assert panel.open_project_from_path(target_file(tmp_path))
    assert len(seen) == 1
    assert not canvas.all_segments
    assert not panel.has_unsaved_changes()


@pytest.mark.parametrize("saved", [False, True])
def test_open_save_choice_requires_success(document, tmp_path, monkeypatch, saved):
    panel, canvas = document
    ink(canvas, "unsaved")
    monkeypatch.setattr(QMessageBox, "exec", lambda box: int(QMessageBox.StandardButton.Save))
    save = Mock(return_value=saved)
    monkeypatch.setattr(panel, "save_project", save)
    assert panel.open_project_from_path(target_file(tmp_path)) is saved
    save.assert_called_once()
    assert bool(canvas.all_segments) is (not saved)


def test_invalid_target_never_replaces_or_prompts(document, tmp_path, monkeypatch):
    panel, canvas = document
    ink(canvas, "unsaved")
    path = tmp_path / "bad.msd"
    path.write_text("{}", encoding="utf-8")
    prompt = Mock(side_effect=AssertionError("Invalid file must be rejected before confirmation"))
    monkeypatch.setattr(QMessageBox, "exec", prompt)
    assert not panel.open_project_from_path(str(path))
    assert str(canvas.all_segments[0]["id"]) == "unsaved"
    prompt.assert_not_called()
