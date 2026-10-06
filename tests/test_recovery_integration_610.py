# SPDX-License-Identifier: GPL-3.0-or-later
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import Mock
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QDialog
import main
from persistence import atomic_write_autosave, make_project_data, AUTOSAVE_KIND
from test_document_safety_610 import document


def autosave(path, name, style="WHITE"):
    page = {"segments": [], "shapes": [], "texts": [
        {"id": name, "text": name, "pos": [80, 60], "color": "#ff0000", "width": 1,
         "size": 24, "scale": 1, "rotation": 0}]}
    atomic_write_autosave(str(path), make_project_data(pages=[page], current_page=0,
                         whiteboard_mode=False, board_style=style, app_version="6.1.0", kind=AUTOSAVE_KIND))


def test_recover_older_selected_version_not_just_latest(document, tmp_path, monkeypatch):
    panel, canvas = document
    latest = tmp_path / "autosave_20261005_130000.json.gz"
    older = tmp_path / "autosave_20261005_120000.json.gz"
    autosave(latest, "new")
    autosave(older, "old", "BLACK")
    monkeypatch.setattr(main, "AUTOSAVE_DIR", str(tmp_path))
    seen = []
    def choose(dialog):
        assert not dialog.advanced_options.isVisible()
        dialog.version_list.setCurrentRow(1)
        assert dialog.preview.pixmap() is not None and not dialog.preview.pixmap().isNull()
        seen.append(dialog.selected_path)
        dialog.accept()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(main.RecoveryDialog, "exec", choose)
    assert panel.offer_autosave_restore()
    assert str(seen[0]) == str(older)
    assert canvas.text_items[0]["text"] == "old"
    assert canvas.board_style == "BLACK"
    assert panel.project_path is None
    assert panel.has_unsaved_changes()
    assert not canvas.whiteboard_mode


def test_recovery_cancel_keeps_document_and_preview_does_not_change_style(document, tmp_path, monkeypatch):
    panel, canvas = document
    path = tmp_path / "autosave_20261005_130000.json.gz"
    autosave(path, "old", "BLACK")
    monkeypatch.setattr(main, "AUTOSAVE_DIR", str(tmp_path))
    before = canvas.document_signature()
    def cancel(dialog):
        assert canvas.board_style == "WHITE"
        dialog.reject()
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(main.RecoveryDialog, "exec", cancel)
    assert not panel.offer_autosave_restore()
    assert canvas.document_signature() == before
    assert not canvas.text_items
    assert path.exists()


def test_all_corrupt_or_empty_autosaves_do_not_prompt(document, tmp_path, monkeypatch):
    panel, canvas = document
    (tmp_path / "autosave_20261005_130000.json.gz").write_bytes(b"broken")
    monkeypatch.setattr(main, "AUTOSAVE_DIR", str(tmp_path))
    execute = Mock()
    monkeypatch.setattr(main.RecoveryDialog, "exec", execute)
    assert not panel.offer_autosave_restore()
    execute.assert_not_called()


def test_serialized_text_only_page_can_be_previewed(document):
    panel, canvas = document
    page = {"texts": [{"id": "text", "text": "hello", "pos": [80, 60], "color": "#ff0000",
                       "width": 1, "size": 24, "scale": 1, "rotation": 0}]}
    image = canvas.render_page_pixmap(page, QSize(360, 220))
    assert not image.isNull()
