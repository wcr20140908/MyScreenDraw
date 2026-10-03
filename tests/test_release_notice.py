# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Launch-policy and offscreen-only presentation tests; never import main."""

import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from release_notice import (
    MAX_NOTICE_LAUNCHES,
    ReleaseNoticeCard,
    begin_notice_session,
    normalize_notice_state,
)


class NoticeStateTests(unittest.TestCase):
    def test_non_objects_fall_back_to_empty_state(self):
        for raw in (None, False, 8, 1.5, "state", [], [1], ()):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_notice_state(raw),
                                 {"launches": 0, "last_version": ""})

    def test_missing_fields_are_independent(self):
        for raw, expected in (
            ({}, {"launches": 0, "last_version": ""}),
            ({"launches": 2}, {"launches": 2, "last_version": ""}),
            ({"last_version": "6.0.0"}, {"launches": 0, "last_version": "6.0.0"}),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_notice_state(raw), expected)

    def test_malformed_counts_are_not_coerced(self):
        for count in (None, True, False, "2", "oops", 2.0, 2.8,
                      float("nan"), float("inf"), [], {}):
            with self.subTest(count=count):
                state = normalize_notice_state({"launches": count, "last_version": "v1"})
                self.assertEqual(state, {"launches": 0, "last_version": "v1"})
                self.assertIs(type(state["launches"]), int)

    def test_integer_counts_are_clamped(self):
        for count, expected in ((-10, 0), (0, 0), (3, 3),
                                (MAX_NOTICE_LAUNCHES, MAX_NOTICE_LAUNCHES),
                                (10 ** 100, MAX_NOTICE_LAUNCHES)):
            with self.subTest(count=count):
                self.assertEqual(normalize_notice_state({"launches": count})["launches"],
                                 expected)

    def test_malformed_versions_are_not_stringified(self):
        for version in (None, True, 6, 6.0, [], {}, b"6.0"):
            with self.subTest(version=version):
                self.assertEqual(normalize_notice_state(
                    {"launches": 4, "last_version": version}),
                    {"launches": 4, "last_version": ""})

    def test_string_versions_are_preserved(self):
        for version in ("", "6.0.0-beta.8", "版本 6.0.0"):
            with self.subTest(version=version):
                self.assertEqual(normalize_notice_state({"last_version": version})[
                    "last_version"], version)

    def test_normalization_is_fresh_idempotent_and_does_not_mutate_input(self):
        raw = {"launches": 2, "last_version": "v1", "other": {"nested": [1]}}
        before = copy.deepcopy(raw)
        state = normalize_notice_state(raw)
        self.assertEqual(raw, before)
        self.assertIsNot(state, raw)
        self.assertEqual(state, {"launches": 2, "last_version": "v1"})
        again = normalize_notice_state(state)
        self.assertEqual(again, state)
        self.assertIsNot(again, state)

    def test_only_first_three_launches_are_eligible_at_same_version(self):
        state = None
        for launch in range(1, 8):
            with self.subTest(launch=launch):
                state, eligible = begin_notice_session(state, "6.0.0")
                self.assertEqual(state, {"launches": launch, "last_version": "6.0.0"})
                self.assertIs(eligible, launch <= 3)

    def test_version_changes_are_eligible_once_including_downgrades(self):
        state = {"launches": 20, "last_version": "6.0.0"}
        for version, expected in (("6.0.1", True), ("6.0.1", False),
                                  ("6.0.0", True), ("6.0.0", False)):
            with self.subTest(version=version, expected=expected):
                old_count = state["launches"]
                state, eligible = begin_notice_session(state, version)
                self.assertIs(eligible, expected)
                self.assertEqual(state, {"launches": old_count + 1, "last_version": version})

    def test_unknown_previous_version_is_eligible_and_recorded(self):
        state, eligible = begin_notice_session({"launches": 50, "last_version": []}, "v2")
        self.assertEqual(state, {"launches": 51, "last_version": "v2"})
        self.assertTrue(eligible)
        self.assertFalse(begin_notice_session(state, "v2")[1])

    def test_session_normalizes_malformed_input(self):
        for raw in (None, [], {"launches": "bad", "last_version": False}):
            with self.subTest(raw=raw):
                self.assertEqual(begin_notice_session(raw, "v1"),
                                 ({"launches": 1, "last_version": "v1"}, True))

    def test_session_does_not_mutate_input_or_use_hidden_global_counter(self):
        raw = {"launches": 2, "last_version": "v1", "other": [1, 2]}
        before = copy.deepcopy(raw)
        first = begin_notice_session(raw, "v1")
        self.assertEqual(begin_notice_session(raw, "v1"), first)
        self.assertEqual(raw, before)
        self.assertIsNot(first[0], raw)
        self.assertEqual(first, ({"launches": 3, "last_version": "v1"}, True))

    def test_counter_saturates_without_reenabling_first_launch_notice(self):
        state = {"launches": MAX_NOTICE_LAUNCHES - 1, "last_version": "v1"}
        for version, expected in (("v1", False), ("v1", False), ("v2", True), ("v2", False)):
            state, eligible = begin_notice_session(state, version)
            self.assertEqual(state["launches"], MAX_NOTICE_LAUNCHES)
            self.assertIs(eligible, expected)


class ReleaseNoticeCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Run these tests with QT_QPA_PLATFORM=offscreen")

    def setUp(self):
        self.app_style = self.app.styleSheet()
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.card = ReleaseNoticeCard("开源软件", "感谢使用这个开源项目。", self.host,
                                      close_text="关闭提示")
        self.layout.addWidget(self.card)

    def tearDown(self):
        self.host.close()
        self.host.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def show_at_width(self, width=300):
        self.host.setFixedWidth(width)
        self.layout.activate()
        height = self.layout.totalHeightForWidth(width)
        self.host.resize(width, height if height >= 0 else self.host.sizeHint().height())
        self.host.show()
        self.app.processEvents()

    def test_parent_text_is_wrapped_plain_text_not_executable_markup(self):
        text = '<a href="https://untrusted.invalid">localized text</a>'
        card = ReleaseNoticeCard(text, text, self.host)
        for label in (card.title_label, card.message_label):
            self.assertEqual(label.text(), text)
            self.assertTrue(label.wordWrap())
            self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
            self.assertFalse(label.openExternalLinks())

    def test_mouse_dismissal_emits_once_after_hiding_only_the_card(self):
        self.show_at_width()
        spy = QSignalSpy(self.card.dismissed)
        hidden_when_emitted = []
        self.card.dismissed.connect(lambda: hidden_when_emitted.append(self.card.isHidden()))
        QTest.mouseClick(self.card.close_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(spy), 1)
        self.assertEqual(list(spy[0]), [])
        self.assertEqual(hidden_when_emitted, [True])
        self.assertTrue(self.card.isHidden())
        self.assertTrue(self.host.isVisible())

    def test_close_button_is_keyboard_accessible_and_localized(self):
        before = QPushButton("Before", self.host)
        after = QPushButton("After", self.host)
        self.layout.insertWidget(0, before)
        self.layout.addWidget(after)
        QWidget.setTabOrder(before, self.card.close_button)
        QWidget.setTabOrder(self.card.close_button, after)
        self.show_at_width()
        button = self.card.close_button
        self.assertEqual(button.accessibleName(), "关闭提示")
        self.assertEqual(button.toolTip(), "关闭提示")
        self.assertEqual(button.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        before.setFocus()
        QTest.keyClick(before, Qt.Key.Key_Tab)
        self.assertTrue(button.hasFocus())
        QTest.keyClick(button, Qt.Key.Key_Tab)
        self.assertTrue(after.hasFocus())
        QTest.keyClick(after, Qt.Key.Key_Backtab)
        self.assertTrue(button.hasFocus())
        spy = QSignalSpy(self.card.dismissed)
        QTest.keyClick(button, Qt.Key.Key_Space)
        self.assertEqual(len(spy), 1)
        self.assertTrue(self.card.isHidden())
        self.assertTrue(self.host.isVisible())

    def test_dismissal_does_not_accept_or_close_parent_dialog(self):
        from PyQt6.QtWidgets import QDialog
        dialog = QDialog(self.host)
        layout = QVBoxLayout(dialog)
        card = ReleaseNoticeCard("Title", "Message", dialog)
        layout.addWidget(card)
        finished = QSignalSpy(dialog.finished)
        dialog.show()
        self.app.processEvents()
        card.close_button.click()
        self.assertEqual(len(finished), 0)
        self.assertTrue(dialog.isVisible())
        self.assertFalse(card.close_button.autoDefault())
        dialog.close()

    def test_widget_never_calls_state_helpers_and_does_not_persist_dismissal(self):
        with patch("release_notice.begin_notice_session", side_effect=AssertionError("startup only")), \
             patch("release_notice.normalize_notice_state", side_effect=AssertionError("parent only")):
            self.show_at_width()
            self.card.close_button.click()
            self.host.hide()
            self.host.show()
            self.assertTrue(self.card.isHidden())
            replacement = ReleaseNoticeCard("Title", "Message", self.host)
            self.layout.addWidget(replacement)
            replacement.show()
            self.assertTrue(replacement.isVisible())
            self.card.show()
            self.assertTrue(self.card.isVisible())

    def assert_content_fits(self):
        button_rect = self.card.close_button.geometry()
        self.assertTrue(self.card.rect().contains(button_rect))
        self.assertLessEqual(self.card.width(), self.host.width())
        for label in (self.card.title_label, self.card.message_label):
            self.assertTrue(self.card.rect().contains(label.geometry()))
            self.assertFalse(label.geometry().intersects(button_rect))
            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
        self.assertFalse(self.card.title_label.geometry().intersects(
            self.card.message_label.geometry()))

    def test_long_localized_text_fits_narrow_settings_in_both_themes(self):
        samples = (
            ("An open-source classroom annotation application " * 4,
             "This software is free and open source. Thank you for using it. " * 8),
            ("这是开源项目的重要提示" * 10, "感谢支持开源软件，欢迎反馈问题和提出建议。" * 16),
            ("إشعار برنامج مفتوح المصدر " * 8, "شكرا لاستخدام هذا البرنامج. " * 16),
            ("VeryLongTitle" * 24, "UnbrokenMessage" * 40),
        )
        for theme in ("light", "dark"):
            self.card.set_theme(theme)
            for title, message in samples:
                for width in (300, 260):
                    with self.subTest(theme=theme, width=width, title=title[:20]):
                        self.card.title_label.setText(title)
                        self.card.message_label.setText(message)
                        self.show_at_width(width)
                        self.assertEqual(self.host.width(), width)
                        self.assert_content_fits()

    def test_wrapping_increases_height_instead_of_overlapping(self):
        self.card.title_label.setText("Open-source software " * 3)
        self.card.message_label.setText("A localized notice message with wrapping. " * 8)
        self.show_at_width(600)
        wide_height = self.card.height()
        self.show_at_width(300)
        self.assertGreater(self.card.height(), wide_height)
        self.assert_content_fits()

    def test_natural_parent_size_hint_keeps_short_notice_compact(self):
        self.host.setFixedWidth(300)
        self.host.adjustSize()
        self.host.show()
        self.app.processEvents()
        self.assertLess(self.card.height(), 150)
        self.assert_content_fits()

    def test_short_notice_stays_compact(self):
        self.show_at_width()
        self.assertLess(self.card.height(), 150)
        self.assert_content_fits()

    def test_amber_themes_render_offscreen_with_readable_text(self):
        def luminance(color):
            channels = [color.redF(), color.greenF(), color.blueF()]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                      for c in channels]
            return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        backgrounds = {}
        for theme, expected in (("light", "#fff4d6"), ("dark", "#3b2c16")):
            with self.subTest(theme=theme):
                self.card.set_theme(theme)
                self.show_at_width()
                image = self.card.grab().toImage()
                background = image.pixelColor(5, image.height() // 2)
                self.assertEqual(background, QColor(expected))
                backgrounds[theme] = luminance(background)
                for label in (self.card.title_label, self.card.message_label):
                    foreground = label.palette().color(QPalette.ColorRole.WindowText)
                    levels = sorted((luminance(foreground), luminance(background)))
                    self.assertGreaterEqual((levels[1] + 0.05) / (levels[0] + 0.05), 4.5)
                self.assert_content_fits()
        self.assertGreater(backgrounds["light"], backgrounds["dark"])
        self.assertEqual(self.host.styleSheet(), "")
        self.assertEqual(self.app.styleSheet(), self.app_style)
        self.assertIn(":focus", self.card.styleSheet())

    def test_unknown_theme_falls_back_to_light_without_reshowing_dismissed_card(self):
        self.card.set_theme("light")
        light_style = self.card.styleSheet()
        self.show_at_width()
        self.card.close_button.click()
        for theme in ("dark", "light", "unknown", None):
            self.card.set_theme(theme)
            self.assertTrue(self.card.isHidden())
        self.assertEqual(self.card.styleSheet(), light_style)

    def test_constructor_accepts_theme_and_optional_parent(self):
        card = ReleaseNoticeCard("Title", "Message", theme_name="dark")
        try:
            self.assertIsNone(card.parent())
            self.assertIn("#3b2c16", card.styleSheet())
            self.assertEqual(card.close_button.accessibleName(), "Close")
        finally:
            card.close()
            card.deleteLater()


if __name__ == "__main__":
    unittest.main()
