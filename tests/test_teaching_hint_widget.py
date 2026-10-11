# SPDX-License-Identifier: GPL-3.0-or-later
"""Behavioral tests for the isolated context teaching hint view."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import traceback
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MYSCREENDRAW_NO_KEYBOARD", "1")
os.environ.setdefault("PYNPUT_BACKEND", "dummy")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QWidget

from teaching.hint_widget import ContextTeachingHint


@pytest.fixture
def qt_app(monkeypatch):
    app = QApplication.instance() or QApplication([])
    existing = set(app.topLevelWidgets())
    callback_errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *error: callback_errors.append(error))
    yield app
    for widget in app.topLevelWidgets():
        if widget not in existing and not sip.isdeleted(widget):
            widget.hide()
            widget.deleteLater()
    drain_deferred_deletes(app)
    assert not callback_errors, "".join(
        line for error in callback_errors for line in traceback.format_exception(*error)
    )


def drain_deferred_deletes(app: QApplication) -> None:
    for _ in range(4):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def make_hint(**overrides) -> ContextTeachingHint:
    values = {
        "title": "Context teaching hint",
        "body": "Use the current context to learn this feature.",
        "start_label": "Start",
        "close_label": "Close",
    }
    values.update(overrides)
    return ContextTeachingHint(**values)


def test_hint_is_a_nonmodal_tool_window_with_plain_text_public_fields(qt_app):
    hint = make_hint(title="<b>Title</b>", body="<i>Body</i>")

    assert hint.isWindow()
    assert hint.windowFlags() & Qt.WindowType.Tool
    assert hint.windowModality() == Qt.WindowModality.NonModal
    assert hint.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    assert hint.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert hint.windowTitle() == "<b>Title</b>"
    assert hint.title_label.text() == "<b>Title</b>"
    assert hint.body_label.text() == "<i>Body</i>"
    assert hint.title_label.textFormat() == Qt.TextFormat.PlainText
    assert hint.body_label.textFormat() == Qt.TextFormat.PlainText
    assert hint.title_label.wordWrap()
    assert hint.body_label.wordWrap()
    assert hint.start_button.text() == "Start"
    assert hint.close_button.text() == "Close"

    hint.close()
    drain_deferred_deletes(qt_app)


def test_hint_accepts_optional_parent_but_remains_a_tool_window(qt_app):
    parent = QWidget()
    hint = make_hint(parent=parent)

    assert hint.parentWidget() is parent
    assert hint.isWindow()

    hint.close()
    parent.deleteLater()
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)


def test_hidden_hint_cannot_start_and_visible_start_is_emitted_once(qt_app):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)

    hint.start_button.click()
    assert len(started) == 0

    hint.show()
    qt_app.processEvents()
    assert hint.isVisible()
    hint.start_button.click()
    hint.start_button.click()

    assert len(started) == 1
    assert len(dismissed) == 0
    assert not hint.isVisible()

    hint.start_button.click()
    assert len(started) == 1
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)


def test_visible_close_button_and_window_close_emit_dismissed_once(qt_app):
    button_hint = make_hint()
    button_dismissed = QSignalSpy(button_hint.dismissed)
    button_started = QSignalSpy(button_hint.start_requested)
    button_hint.show()
    qt_app.processEvents()

    button_hint.close_button.click()
    button_hint.close_button.click()
    button_hint.start_button.click()

    assert len(button_dismissed) == 1
    assert len(button_started) == 0
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(button_hint)

    window_hint = make_hint()
    window_dismissed = QSignalSpy(window_hint.dismissed)
    window_hint.show()
    qt_app.processEvents()
    window_hint.close()
    window_hint.close()

    assert len(window_dismissed) == 1
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(window_hint)


def test_start_then_close_does_not_emit_dismissed(qt_app):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    hint.show()
    qt_app.processEvents()

    hint.start_button.click()
    hint.close()

    assert len(started) == 1
    assert len(dismissed) == 0
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)


def test_synchronous_start_callback_can_destroy_hint_without_followup_sip_access(qt_app):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    hint.start_requested.connect(lambda: sip.delete(hint))
    hint.show()
    qt_app.processEvents()

    hint.start_button.click()

    assert len(started) == 1
    assert sip.isdeleted(hint)


def test_long_multilingual_body_is_scrollable_and_buttons_remain_reachable(qt_app):
    body = (
        "中文教学内容需要完整换行。 "
        "Deutsche Hinweise müssen ohne abgeschnittene Schaltflächen umbrechen. "
        "Русский текст должен оставаться читаемым. "
    ) * 45
    hint = make_hint(
        title="Eine lange Überschrift для контекстной подсказки",
        body=body,
        start_label="Funktion starten",
        close_label="Hinweis schließen",
    )
    hint.resize(420, 320)
    hint.show()
    qt_app.processEvents()
    hint.layout().activate()
    qt_app.processEvents()

    assert hint.width() <= 420
    assert hint.body_label.text() == body
    assert hint.body_label.wordWrap()
    assert hint.body_scroll.isAncestorOf(hint.body_label)
    assert hint.body_scroll.widgetResizable()
    assert hint.body_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    scrollbar = hint.body_scroll.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    qt_app.processEvents()
    label_bottom = hint.body_label.mapTo(
        hint.body_scroll.viewport(), QPoint(0, hint.body_label.height() - 1)
    )
    assert hint.body_scroll.viewport().rect().contains(label_bottom)
    assert hint.body_scroll.horizontalScrollBar().maximum() == 0
    assert hint.start_button.isVisible()
    assert hint.close_button.isVisible()
    for button in (hint.start_button, hint.close_button):
        assert hint.rect().contains(button.geometry().topLeft())
        assert hint.rect().contains(button.geometry().bottomRight())

    hint.close()
    drain_deferred_deletes(qt_app)

@pytest.mark.parametrize("action", ["request_start", "dismiss"])
def test_business_methods_only_decide_a_visible_hint(qt_app, action):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    callback = getattr(hint, action)

    callback()
    hint.start_button.click()
    hint.close_button.click()
    assert not hint.decided
    assert len(started) == len(dismissed) == 0

    hint.show()
    qt_app.processEvents()
    hint.hide()
    callback()
    hint.start_button.click()
    hint.close_button.click()
    assert not hint.decided
    assert len(started) == len(dismissed) == 0

    hint.show()
    qt_app.processEvents()
    callback()
    assert hint.decided
    assert not hint.isVisible()
    assert list(started) == ([[]] if action == "request_start" else [])
    assert list(dismissed) == ([[]] if action == "dismiss" else [])

    callback()
    hint.request_start()
    hint.dismiss()
    hint.close()
    assert len(started) + len(dismissed) == 1
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)

    callback()
    hint.request_start()
    hint.dismiss()
    assert len(started) + len(dismissed) == 1


def test_window_close_while_hidden_retires_without_emitting_a_choice(qt_app):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    hint.show()
    qt_app.processEvents()
    hint.hide()

    hint.close()

    assert hint.decided
    assert len(started) == len(dismissed) == 0
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)


def test_old_business_callbacks_are_safe_after_undecided_hint_is_deleted(qt_app):
    hint = make_hint()
    request_start = hint.request_start
    dismiss = hint.dismiss
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    hint.show()
    qt_app.processEvents()

    sip.delete(hint)
    request_start()
    dismiss()

    assert sip.isdeleted(hint)
    assert len(started) == len(dismissed) == 0


@pytest.mark.parametrize("action", ["request_start", "dismiss", "close"])
def test_signal_callback_can_reenter_buttons_and_business_methods(qt_app, action):
    hint = make_hint()
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    observations = []
    assert callable(getattr(hint, "request_start", None))
    assert callable(getattr(hint, "dismiss", None))

    def reenter():
        observations.append(hint.decided)
        hint.start_button.click()
        hint.close_button.click()
        hint.request_start()
        hint.dismiss()
        hint.close()

    hint.start_requested.connect(reenter)
    hint.dismissed.connect(reenter)
    hint.show()
    qt_app.processEvents()

    getattr(hint, action)()

    assert observations == [True]
    assert list(started) == ([[]] if action == "request_start" else [])
    assert list(dismissed) == ([] if action == "request_start" else [[]])
    drain_deferred_deletes(qt_app)
    assert sip.isdeleted(hint)


@pytest.mark.parametrize("action", ["request_start", "dismiss", "close"])
@pytest.mark.parametrize("destroy", ["sip", "deferred", "parent"])
def test_terminal_callbacks_can_destroy_hint_synchronously(qt_app, action, destroy):
    parent = QWidget()
    hint = make_hint(parent=parent)
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)

    assert callable(getattr(hint, "request_start", None))
    assert callable(getattr(hint, "dismiss", None))

    def destroy_hint():
        if destroy == "sip":
            sip.delete(hint)
        elif destroy == "deferred":
            hint.close()
            hint.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        else:
            sip.delete(parent)

    hint.start_requested.connect(destroy_hint)
    hint.dismissed.connect(destroy_hint)
    hint.show()
    qt_app.processEvents()

    getattr(hint, action)()

    assert sip.isdeleted(hint)
    assert list(started) == ([[]] if action == "request_start" else [])
    assert list(dismissed) == ([] if action == "request_start" else [[]])
    if not sip.isdeleted(parent):
        parent.deleteLater()
    drain_deferred_deletes(qt_app)


@pytest.mark.parametrize("language,title,body,start_label,close_label", [
    ("zh", "如何使用这一功能的中文教学标题。", "中文正文很长，需要全部可达。",
     "开始了解并练习当前功能的完整操作流程", "暂时关闭这个教学提示并返回应用程序"),
    ("de", "Kontextbezogene Funktionen vollständig kennenlernen. ",
     "Längere deutsche Erläuterungen bleiben vollständig erreichbar. ",
     "Die ausgewählte Funktion kennenlernen und mit dem Üben beginnen",
     "Diesen Hinweis schließen und zur vorherigen Ansicht zurückkehren"),
    ("ru", "Обучение выбранной функции в текущем контексте. ",
     "Длинные русские пояснения должны оставаться доступными. ",
     "Изучить выбранную функцию и начать выполнение практического упражнения",
     "Закрыть эту подсказку и вернуться к предыдущему представлению"),
])
def test_long_text_stays_inside_work_area_with_complete_action_labels(
    qt_app, language, title, body, start_label, close_label
):
    hint = make_hint(
        title=title * 70, body=body * 150,
        start_label=start_label, close_label=close_label,
    )
    hint.resize(2000, 2000)
    hint.show()
    qt_app.processEvents()
    hint.layout().activate()
    qt_app.processEvents()

    work_area = hint.screen().availableGeometry()
    assert hint.width() <= 420
    assert work_area.contains(hint.frameGeometry())
    assert hint.title_label.text() == title * 70
    assert hint.body_label.text() == body * 150
    assert hint.title_label.textFormat() == Qt.TextFormat.PlainText
    assert hint.body_label.textFormat() == Qt.TextFormat.PlainText
    for button, text in ((hint.start_button, start_label), (hint.close_button, close_label)):
        assert button.text() == text
        assert button.isVisible()
        assert hint.rect().contains(button.geometry())
        assert button.heightForWidth(button.width()) <= button.height()

    assert hint.body_scroll.verticalScrollBar().maximum() > 0
    assert hint.body_scroll.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("text", [
    '<b>Text</b> <a href="https://example.invalid/">Link</a>',
    '<img src="missing.png"> &amp; <script>ignored()</script>',
    "中文 <i>Deutsch</i> & русский текст",
])
def test_markup_like_strings_stay_literal_and_inherit_qt_palette(qt_app, text):
    parent = QWidget()
    hint = make_hint(title=text, body=text, parent=parent)
    started = QSignalSpy(hint.start_requested)
    dismissed = QSignalSpy(hint.dismissed)
    hint.show()
    qt_app.processEvents()

    for label in (hint.title_label, hint.body_label):
        assert label.text() == text
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert label.wordWrap()
        assert not label.openExternalLinks()
    for widget in (hint, hint.title_label, hint.body_label, hint.start_button, hint.close_button):
        assert widget.styleSheet() == ""
        assert widget.palette() == parent.palette()
    assert not hint.start_button.autoDefault()
    assert not hint.start_button.isDefault()
    assert not hint.close_button.autoDefault()
    assert not hint.close_button.isDefault()
    assert len(started) == len(dismissed) == 0


@pytest.mark.parametrize("work_area", [
    QRect(100, 50, 320, 260),
    QRect(-900, 30, 280, 240),
])
def test_small_work_area_preserves_action_geometry(qt_app, monkeypatch, work_area):
    hint = make_hint(
        title="中文标题 Deutsche Überschrift Русский заголовок " * 20,
        body="中文正文 Deutsch Русский текст " * 100,
        start_label="Ausgewählte Funktion kennenlernen",
        close_label="Закрыть эту обучающую подсказку",
    )
    monkeypatch.setattr(
        hint, "screen", lambda: SimpleNamespace(availableGeometry=lambda: work_area)
    )
    hint.move(2000, 2000)
    hint.resize(2000, 2000)
    hint.show()
    qt_app.processEvents()
    hint.layout().activate()
    qt_app.processEvents()

    assert work_area.contains(hint.frameGeometry())
    for button in (hint.start_button, hint.close_button):
        assert hint.rect().contains(button.geometry())
        assert button.heightForWidth(button.width()) <= button.height()
    assert hint.body_scroll.verticalScrollBar().maximum() > 0
    assert hint.body_scroll.horizontalScrollBar().maximum() == 0


def test_long_unbroken_body_has_vertical_scroll_instead_of_clipping(qt_app):
    hint = make_hint(body="Donaudampfschifffahrtsgesellschaft" * 180)
    hint.show()
    qt_app.processEvents()

    assert hint.body_label.heightForWidth(hint.body_label.width()) > 300
    assert hint.body_scroll.verticalScrollBar().maximum() > 0
    assert hint.body_scroll.horizontalScrollBar().maximum() == 0
    scrollbar = hint.body_scroll.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    qt_app.processEvents()
    bottom = hint.body_label.mapTo(
        hint.body_scroll.viewport(), QPoint(0, hint.body_label.height() - 1)
    )
    assert hint.body_scroll.viewport().rect().contains(bottom)


def test_import_does_not_create_application_or_load_host_modules():
    code = """
import importlib
import sys
from PyQt6.QtWidgets import QApplication
assert QApplication.instance() is None
importlib.import_module("teaching.hint_widget")
assert QApplication.instance() is None
for name in ("main", "i18n", "teaching.application", "teaching.widgets",
             "teaching.context_hints", "teaching.catalog", "teaching.state",
             "keyboard", "pynput"):
    assert name not in sys.modules, name
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(), capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
