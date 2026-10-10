# SPDX-License-Identifier: GPL-3.0-or-later
"""Recovery preview evidence using only synthetic data and offscreen Qt widgets."""
from __future__ import annotations

import copy
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
os.environ["PYNPUT_BACKEND"] = "dummy"
os.environ["PYTHONIOENCODING"] = "utf-8"

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QSize
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog

from i18n import tr
from recovery_dialog import RecoveryDialog


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    assert application.platformName() == "offscreen"
    return application


def document(name="new", *, current=0, colors=("red", "blue", "green")):
    return {
        "saved_at": name,
        "current_page": current,
        "pages": [
            {"name": f"{name}-{number}", "color": color, "strokes": []}
            for number, color in enumerate(colors)
        ],
    }


def observe(dialog):
    notices = []

    def ready(path, page, total):
        pixmap = dialog.preview.pixmap()
        notices.append({
            "payload": (path, page, total),
            "state": dialog.preview_state,
            "size": QSize(pixmap.size()),
            "color": None if pixmap.isNull() else pixmap.toImage().pixelColor(0, 0).name(),
        })

    dialog.preview_ready.connect(ready)
    return notices


class ConstructorObservedDialog(RecoveryDialog):
    """Connect before the constructor's first selection without changing its flow."""

    def _select_index(self, index):
        if not hasattr(self, "notices"):
            self.notices = observe(self)
        return super()._select_index(index)


@pytest.fixture
def make_dialog(app):
    dialogs = []

    def make(candidates, documents, *, renderer=None, dialog_type=RecoveryDialog):
        loaded, rendered = [], []

        def load(path):
            loaded.append(path)
            value = documents.get(path, ValueError("synthetic invalid recovery version"))
            if isinstance(value, Exception):
                raise value
            return value

        def render(page, size):
            rendered.append((copy.deepcopy(page), QSize(size)))
            if renderer is not None:
                return renderer(page, size)
            pixmap = QPixmap(48, 32)
            pixmap.fill(QColor(page["color"]))
            return pixmap

        dialog = dialog_type(candidates, load, render)
        dialogs.append(dialog)
        return dialog, loaded, rendered

    yield make
    for dialog in reversed(dialogs):
        dialog.reject()
        dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def assert_notice(notice, expected, color):
    assert notice["payload"] == expected
    assert tuple(type(value) for value in notice["payload"]) == (str, int, int)
    assert notice["state"] == expected
    assert notice["color"] == color
    assert 0 < notice["size"].width() <= 360
    assert 0 < notice["size"].height() <= 220


def test_constructor_publishes_first_valid_preview_after_display(make_dialog):
    latest = Path("synthetic-new.msdraw")
    data = document(current=1)
    before = copy.deepcopy(data)
    dialog, loaded, rendered = make_dialog(
        ["broken", latest, "unselected"], {latest: data},
        dialog_type=ConstructorObservedDialog,
    )

    expected = ("synthetic-new.msdraw", 2, 3)
    assert dialog.preview_state == expected  # The host can read this after construction.
    assert len(dialog.notices) == 1
    assert_notice(dialog.notices[0], expected, "#0000ff")
    assert dialog.selected_path == latest
    assert dialog.selected_data is data
    assert data == before
    assert loaded == ["broken", latest]
    assert rendered == [(data["pages"][1], QSize(360, 220))]
    assert dialog.version_list.currentRow() == 1
    assert dialog.advanced_options.isHidden()
    assert not dialog.advanced_toggle.isChecked()
    assert dialog.restore_button.isEnabled()


@pytest.mark.parametrize("current,page,color", [
    (1, 2, "#0000ff"),
    (-20, 1, "#ff0000"),
    (20, 3, "#008000"),
    (True, 1, "#ff0000"),
    ("2", 1, "#ff0000"),
    (None, 1, "#ff0000"),
])
def test_constructor_publishes_the_normalized_one_based_page(make_dialog, current, page, color):
    dialog, _, _ = make_dialog(
        ["new"], {"new": document(current=current)},
        dialog_type=ConstructorObservedDialog,
    )
    assert dialog.preview_state == ("new", page, 3)
    assert len(dialog.notices) == 1
    assert_notice(dialog.notices[0], ("new", page, 3), color)


def test_preview_state_cannot_be_assigned_by_a_subscriber(make_dialog):
    dialog, _, _ = make_dialog(["new"], {"new": document()})
    assert dialog.preview_state == ("new", 1, 3)
    with pytest.raises(AttributeError):
        dialog.preview_state = None
    with pytest.raises(AttributeError):
        dialog.preview_state = ("forged", 2, 999)
    assert dialog.preview_state == ("new", 1, 3)


def test_page_switch_notifies_only_after_the_new_pixmap_is_displayed(make_dialog):
    data = document()
    before = copy.deepcopy(data)
    dialog, loaded, rendered = make_dialog(["new"], {"new": data})
    notices = observe(dialog)

    dialog.page_selector.setCurrentIndex(1)
    dialog.page_selector.setCurrentIndex(2)

    assert len(notices) == 2
    assert_notice(notices[0], ("new", 2, 3), "#0000ff")
    assert_notice(notices[1], ("new", 3, 3), "#008000")
    assert dialog.preview_state == ("new", 3, 3)
    assert loaded == ["new"]
    assert rendered == [(page, QSize(360, 220)) for page in data["pages"]]
    assert data == before


def test_version_switch_is_lazy_and_publishes_its_actual_path_and_page_count(make_dialog):
    older = Path("synthetic-old.msdraw")
    documents = {
        "new": document(),
        older: document("old", current=1, colors=("yellow", "cyan")),
        "unselected": document("unselected"),
    }
    before = copy.deepcopy(documents)
    dialog, loaded, rendered = make_dialog(["new", older, "unselected"], documents)
    notices = observe(dialog)
    assert loaded == ["new"]

    dialog.advanced_toggle.setChecked(True)
    assert notices == []  # Merely revealing a control is not preview success.
    assert loaded == ["new"]
    dialog.version_list.setCurrentRow(1)

    assert len(notices) == 1
    assert_notice(notices[0], ("synthetic-old.msdraw", 2, 2), "#00ffff")
    assert dialog.preview_state == ("synthetic-old.msdraw", 2, 2)
    assert dialog.selected_path == older
    assert dialog.selected_data is documents[older]
    assert loaded == ["new", older]
    assert rendered == [
        (documents["new"]["pages"][0], QSize(360, 220)),
        (documents[older]["pages"][1], QSize(360, 220)),
    ]
    assert documents == before


INVALID_DOCUMENTS = [
    pytest.param(None, id="none"),
    pytest.param([], id="not-a-dict"),
    pytest.param({}, id="missing-pages"),
    pytest.param({"pages": ()}, id="pages-not-a-list"),
    pytest.param({"pages": []}, id="empty-pages"),
    pytest.param({"pages": ["broken"]}, id="bad-page"),
    pytest.param({"pages": [{}, None]}, id="bad-later-page"),
    pytest.param(ValueError("synthetic load failure"), id="loader-exception"),
]


@pytest.mark.parametrize("invalid", INVALID_DOCUMENTS)
def test_invalid_constructor_data_never_publishes_preview_success(make_dialog, invalid):
    dialog, loaded, rendered = make_dialog(
        ["bad"], {"bad": invalid}, dialog_type=ConstructorObservedDialog,
    )
    assert dialog.preview_state is None
    assert dialog.notices == []
    assert loaded == ["bad"]
    assert rendered == []
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    assert dialog.preview.pixmap().isNull()
    assert dialog.details.text() == tr("recovery_no_valid")
    assert not dialog.restore_button.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted


@pytest.mark.parametrize("invalid", INVALID_DOCUMENTS)
def test_invalid_version_clears_success_without_emitting_and_can_recover(make_dialog, invalid):
    documents = {"new": document(), "bad": invalid, "old": document("old", colors=("cyan",))}
    dialog, loaded, rendered = make_dialog(["new", "bad", "old"], documents)
    notices = observe(dialog)
    dialog.version_list.setCurrentRow(1)

    assert dialog.preview_state is None
    assert notices == []
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    assert dialog.preview.pixmap().isNull()
    assert dialog.preview.text() == tr("recovery_preview_unavailable")
    assert dialog.details.text() == tr("recovery_invalid_version")
    assert not dialog.restore_button.isEnabled()
    assert len(rendered) == 1
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted

    dialog.version_list.setCurrentRow(2)
    assert len(notices) == 1
    assert_notice(notices[0], ("old", 1, 1), "#00ffff")
    assert dialog.preview_state == ("old", 1, 1)
    assert loaded == ["new", "bad", "old"]
    assert len(rendered) == 2
    assert dialog.page_selector.isHidden()


class NullScaledPixmap(QPixmap):
    def scaled(self, *args, **kwargs):
        return QPixmap()


class FailedScaledPixmap(QPixmap):
    def scaled(self, *args, **kwargs):
        raise RuntimeError("synthetic scaling failure")


def failed_pixmap(mode):
    if mode == "null":
        return QPixmap()
    if mode == "not-pixmap":
        return None
    if mode == "render-exception":
        raise RuntimeError("synthetic rendering failure")
    pixmap_type = NullScaledPixmap if mode == "scaled-null" else FailedScaledPixmap
    pixmap = pixmap_type(48, 32)
    pixmap.fill(QColor("magenta"))
    return pixmap


PREVIEW_FAILURES = ["null", "not-pixmap", "render-exception", "scaled-null", "scaled-exception"]


@pytest.mark.parametrize("mode", PREVIEW_FAILURES)
def test_valid_data_still_accepts_when_constructor_preview_fails(make_dialog, mode):
    data = document()
    before = copy.deepcopy(data)
    dialog, loaded, rendered = make_dialog(
        ["new"], {"new": data}, renderer=lambda _page, _size: failed_pixmap(mode),
        dialog_type=ConstructorObservedDialog,
    )
    assert dialog.preview_state is None
    assert dialog.notices == []
    assert dialog.preview.pixmap().isNull()
    assert dialog.preview.text() == tr("recovery_preview_unavailable")
    assert dialog.selected_data is data
    assert dialog.selected_path == "new"
    assert dialog.restore_button.isEnabled()
    assert loaded == ["new"]
    assert rendered == [(data["pages"][0], QSize(360, 220))]

    dialog.restore_button.click()  # Qt business method, not native input injection.
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_data is data
    assert data == before
    assert dialog.selected_path == "new"
    assert dialog.preview_state is None
    assert dialog.notices == []  # Restoration must not manufacture preview evidence.


@pytest.mark.parametrize("mode", PREVIEW_FAILURES)
def test_failed_page_render_clears_stale_state_without_success(make_dialog, mode):
    def render(page, _size):
        if page["name"] == "new-1":
            return failed_pixmap(mode)
        pixmap = QPixmap(48, 32)
        pixmap.fill(QColor(page["color"]))
        return pixmap

    data = document()
    dialog, loaded, rendered = make_dialog(["new"], {"new": data}, renderer=render)
    assert dialog.preview_state == ("new", 1, 3)
    notices = observe(dialog)
    dialog.page_selector.setCurrentIndex(1)

    assert dialog.preview_state is None
    assert notices == []
    assert dialog.preview.pixmap().isNull()
    assert dialog.selected_data is data
    assert dialog.restore_button.isEnabled()
    assert loaded == ["new"]
    assert len(rendered) == 2

    dialog.page_selector.setCurrentIndex(0)
    assert len(notices) == 1
    assert_notice(notices[0], ("new", 1, 3), "#ff0000")
    assert dialog.preview_state == ("new", 1, 3)


def test_set_pixmap_exception_does_not_publish_success(make_dialog, monkeypatch):
    dialog, _, _ = make_dialog(["new"], {"new": document()})
    notices = observe(dialog)

    def fail_display(_pixmap):
        raise RuntimeError("synthetic QLabel display failure")

    with monkeypatch.context() as patch:
        patch.setattr(dialog.preview, "setPixmap", fail_display)
        dialog.page_selector.setCurrentIndex(1)
        assert dialog.preview_state is None
        assert notices == []
        assert dialog.preview.pixmap().isNull()
        assert dialog.restore_button.isEnabled()

    dialog.page_selector.setCurrentIndex(0)
    assert len(notices) == 1
    assert_notice(notices[0], ("new", 1, 3), "#ff0000")


@pytest.mark.parametrize("clear_selector", [False, True], ids=["no-current-page", "empty-selector"])
def test_invalid_page_index_does_not_render_the_last_page(make_dialog, clear_selector):
    dialog, _, rendered = make_dialog(["new"], {"new": document()})
    notices = observe(dialog)
    if clear_selector:
        dialog.page_selector.clear()
    else:
        dialog.page_selector.setCurrentIndex(-1)

    assert dialog.preview_state is None
    assert notices == []
    assert len(rendered) == 1
    assert dialog.preview.pixmap().isNull()
    assert dialog.restore_button.isEnabled()


@pytest.mark.parametrize("action", ["clear", "reset-row", "invalid-index", "reject", "not-now"])
def test_clear_or_reject_discards_preview_state_without_success(make_dialog, action):
    dialog, loaded, rendered = make_dialog(["new"], {"new": document()})
    notices = observe(dialog)
    if action == "clear":
        dialog._clear_selection()
    elif action == "reset-row":
        dialog.version_list.setCurrentRow(-1)
    elif action == "invalid-index":
        assert not dialog._select_index(999)
    elif action == "reject":
        dialog.reject()
    else:
        dialog.not_now_button.click()

    assert dialog.preview_state is None
    assert notices == []
    assert dialog.selected_data is None
    assert dialog.selected_path is None
    assert dialog.preview.pixmap().isNull()
    assert dialog.page_selector.count() == 0
    assert dialog.page_selector.isHidden()
    assert not dialog.restore_button.isEnabled()
    dialog._show_preview()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert loaded == ["new"]
    assert len(rendered) == 1
    assert notices == []


def test_empty_candidate_list_has_no_preview_state(make_dialog):
    dialog, loaded, rendered = make_dialog([], {})
    assert dialog.preview_state is None
    notices = observe(dialog)
    dialog._show_preview()
    dialog.accept()
    dialog.reject()
    assert notices == []
    assert loaded == rendered == []
    assert dialog.preview_state is None
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_restore_button_preserves_data_semantics_without_new_preview_notice(make_dialog):
    data = document()
    before = copy.deepcopy(data)
    dialog, _, _ = make_dialog(["new"], {"new": data})
    notices = observe(dialog)
    dialog.restore_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_data is data
    assert dialog.selected_path == "new"
    assert data == before
    assert dialog.preview_state == ("new", 1, 3)
    assert notices == []
