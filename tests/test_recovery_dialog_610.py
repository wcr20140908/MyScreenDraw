# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen widget coverage for standalone autosave recovery."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog

from recovery_dialog import RecoveryDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def document(name, count=2, current=1):
    return {"saved_at": name, "current_page": current,
            "pages": [{"name": f"{name}-{i}"} for i in range(count)]}


def harness(app, candidates, documents, *, fail_preview=False):
    loaded, rendered = [], []

    def load(path):
        loaded.append(path)
        if path not in documents:
            raise ValueError("corrupt")
        return documents[path]

    def render(page, size):
        rendered.append((page["name"], QSize(size)))
        if fail_preview:
            raise RuntimeError("render failed")
        pixmap = QPixmap(800, 600)  # Hostile oversized callback result is bounded by UI.
        pixmap.fill(QColor("red"))
        return pixmap

    dialog = RecoveryDialog(candidates, load, render)
    return dialog, loaded, rendered


def test_collapsed_default_latest_valid_and_single_render(app):
    latest = document("2026-10-05T09:30:00")
    dialog, loaded, rendered = harness(app, ["new", "old", "oldest"],
                                       {"new": latest, "old": document("old")})
    dialog.show()  # Qt offscreen platform; no real screen access.
    assert not dialog.advanced_options.isVisible()
    assert not dialog.advanced_toggle.isChecked()
    assert dialog.selected_path == "new"
    assert dialog.selected_data is latest
    assert loaded == ["new"]
    assert rendered == [("2026-10-05T09:30:00-1", QSize(360, 220))]
    assert dialog.preview.pixmap().width() <= 360
    assert dialog.preview.pixmap().height() <= 220
    assert "2026-10-05T09:30:00" in dialog.details.text()
    assert "2" in dialog.details.text()
    assert dialog.restore_button.isEnabled()
    dialog.close()


def test_skips_corrupt_latest_without_decoding_older(app):
    valid = document("valid")
    dialog, loaded, rendered = harness(app, ["broken", "valid", "unused"], {"valid": valid})
    assert dialog.selected_path == "valid"
    assert dialog.selected_data is valid
    assert loaded == ["broken", "valid"]
    assert len(rendered) == 1
    dialog.close()


def test_older_selection_loads_only_selected_and_page_switch_rerenders(app):
    dialog, loaded, rendered = harness(app, ["new", "old", "untouched"],
                                       {"new": document("new"), "old": document("old", 3, 2)})
    dialog.advanced_toggle.click()
    assert not dialog.advanced_options.isHidden()
    assert loaded == ["new"]
    dialog.version_list.setCurrentRow(1)
    assert loaded == ["new", "old"]
    assert dialog.selected_path == "old"
    assert dialog.selected_data["saved_at"] == "old"
    assert rendered[-1] == ("old-2", QSize(360, 220))
    assert "3" in dialog.details.text()
    dialog.page_selector.setCurrentIndex(0)
    assert rendered[-1] == ("old-0", QSize(360, 220))
    assert loaded == ["new", "old"]
    dialog.close()


def test_corrupt_selection_invalidates_then_valid_selection_recovers(app):
    dialog, loaded, rendered = harness(app, ["valid", "bad", "older"],
                                       {"valid": document("valid"), "older": document("older")})
    dialog.advanced_toggle.click()
    dialog.version_list.setCurrentRow(1)
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    assert not dialog.restore_button.isEnabled()
    assert dialog.preview.pixmap().isNull()
    assert len(rendered) == 1
    dialog.version_list.setCurrentRow(2)
    assert dialog.selected_path == "older"
    assert dialog.restore_button.isEnabled()
    assert loaded == ["valid", "bad", "older"]
    dialog.close()


def test_no_valid_candidate_and_cancel_does_not_apply(app):
    dialog, loaded, rendered = harness(app, ["bad1", "bad2"], {})
    assert loaded == ["bad1", "bad2"]
    assert not rendered
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    from i18n import tr
    assert dialog.details.text() == tr("recovery_no_valid")
    assert not dialog.restore_button.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.close()

    dialog, _, _ = harness(app, ["valid"], {"valid": document("valid")})
    dialog.not_now_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    dialog.close()


def test_render_failure_never_leaves_stale_preview_or_changes_document(app):
    dialog, loaded, rendered = harness(app, ["valid"], {"valid": document("valid")},
                                       fail_preview=True)
    assert dialog.selected_path == "valid"
    assert dialog.selected_data["saved_at"] == "valid"
    assert dialog.preview.pixmap().isNull()
    assert dialog.restore_button.isEnabled()
    assert len(rendered) == 1
    dialog.restore_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert loaded == ["valid"]
    dialog.close()


def test_preview_failure_after_success_clears_prior_image(app):
    calls = []

    def render(page, size):
        calls.append(page["name"])
        if page["name"].endswith("-0"):
            raise ValueError("invalid image")
        pixmap = QPixmap(size)
        pixmap.fill(QColor("blue"))
        return pixmap

    dialog = RecoveryDialog(["version"], lambda path: document("version"), render)
    assert not dialog.preview.pixmap().isNull()
    dialog.page_selector.setCurrentIndex(0)
    assert calls == ["version-1", "version-0"]
    assert dialog.preview.pixmap().isNull()
    assert dialog.selected_path == "version"
    dialog.close()


def test_malformed_callback_result_is_not_restorable_and_files_untouched(app, tmp_path):
    path = tmp_path / "recovery.autosave"
    path.write_bytes(b"unchanged")
    dialog = RecoveryDialog([path], lambda _: {"pages": [None]},
                            lambda page, size: pytest.fail("must not render"))
    assert dialog.selected_data is None
    assert not dialog.restore_button.isEnabled()
    dialog.not_now_button.click()
    assert path.read_bytes() == b"unchanged"
    dialog.close()
