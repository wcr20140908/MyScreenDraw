# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-table coverage for fixed software tutorial UI strings, without a GUI."""
from pathlib import Path
from string import Formatter
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import i18n
from i18n import TEXT as STRINGS

LANGUAGES = ("zh", "en", "fr", "es", "de", "ru", "ko", "ja")

# Fixed labels used by TeachingCenter and TeachingController, including the
# controller's generated button keys and the catalog's chapter status keys.
WIDGET_KEYS = frozenset({
    "teaching_center_title",
    "teaching_catalog",
    "teaching_status",
    "teaching_search",
    "teaching_filter_all",
    "teaching_filter_completed",
    "teaching_filter_unfinished",
    "teaching_course_progress",
    "teaching_context_hints",
    "teaching_chapter_switch_confirm",
    "teaching_context_hint_title",
    "teaching_context_hint_body",
    "teaching_context_hint_later",
    "teaching_reset_progress",
    "teaching_reset_confirm",
    "teaching_reset_welcome",
    "teaching_reset_accept",
    "teaching_cancel",
    "teaching_start",
    "teaching_replay",
    "teaching_resume",
    "teaching_close",
    "teaching_status_not_started",
    "teaching_status_in_progress",
    "teaching_status_completed",
    "teaching_status_skipped",
    "teaching_status_needs_review",
    "teaching_controller_title",
    "teaching_return_to_work",
    "teaching_previous",
    "teaching_next",
    "teaching_pause",
    "teaching_skip",
    "teaching_retry",
    "teaching_exit",
    "teaching_progress",
    "teaching_paused",
    "teaching_target_missing",
    "teaching_waiting_operation",
})

INTEGRATION_KEYS = frozenset({
    "teaching_entry",
    "teaching_welcome_title",
    "teaching_welcome_body",
    "teaching_welcome_start",
    "teaching_welcome_later",
    "teaching_practice_notice",
    "teaching_private_path_rejected",
    "teaching_unavailable",
    "teaching_progress_save_failed",
    "teaching_session_starting",
    "teaching_session_stopping",
    "teaching_session_start_failed",
    "teaching_session_connection_lost",
    "teaching_session_restore_failed",
})

FIXED_KEYS = WIDGET_KEYS | INTEGRATION_KEYS
FORMAT_VALUES = {"current": 2, "completed": 3, "total": 7, "chapter": "Practice chapter"}


class TeachingI18nTests(unittest.TestCase):
    def test_all_fixed_keys_exist_in_all_eight_languages(self):
        self.assertEqual(len(FIXED_KEYS), 53)
        self.assertEqual(i18n._LANGS, LANGUAGES)
        self.assertEqual(set(STRINGS), set(LANGUAGES))
        for language in LANGUAGES:
            with self.subTest(language=language):
                missing = FIXED_KEYS.difference(STRINGS[language])
                self.assertFalse(missing, f"{language}: missing {sorted(missing)}")

    def test_settings_entries_keep_approved_chinese_copy(self):
        expected = {
            "teaching_context_hints": "首次使用功能时显示教学提示",
            "teaching_reset_progress": "清除学习进度",
            "teaching_reset_confirm": (
                "清除所有章节进度和已显示的功能提示记录。"
                "此操作不会修改你的板书、文件或软件设置。"
            ),
            "teaching_reset_welcome": "下次启动时再次显示欢迎教学",
            "teaching_reset_accept": "确认清除",
            "teaching_cancel": "取消",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertIn(key, WIDGET_KEYS)
                self.assertIn(key, STRINGS["zh"])
                self.assertEqual(STRINGS["zh"][key], value)

    def test_fixed_entries_keep_eight_tuple_order_and_non_empty_values(self):
        for key in sorted(FIXED_KEYS):
            with self.subTest(key=key):
                self.assertIn(key, i18n._BASE)
                values = i18n._BASE[key]
                self.assertIsInstance(values, tuple)
                self.assertEqual(len(values), len(LANGUAGES))
                for index, language in enumerate(LANGUAGES):
                    with self.subTest(language=language):
                        value = STRINGS[language][key]
                        self.assertIsInstance(value, str)
                        self.assertTrue(value.strip(), f"{language}.{key} is empty")
                        self.assertEqual(value, values[index])

    def test_fixed_templates_have_matching_placeholders_and_format(self):
        formatter = Formatter()
        for language in LANGUAGES:
            for key in sorted(FIXED_KEYS):
                with self.subTest(language=language, key=key):
                    self.assertIn(key, STRINGS[language])
                    template = STRINGS[language][key]
                    fields = {
                        field for _, field, _, _ in formatter.parse(template)
                        if field is not None
                    }
                    english_fields = {
                        field for _, field, _, _ in formatter.parse(STRINGS["en"][key])
                        if field is not None
                    }
                    expected = {
                        "teaching_progress": {"current", "total"},
                        "teaching_course_progress": {"completed", "total"},
                        "teaching_context_hint_body": {"chapter"},
                    }.get(key, set())
                    self.assertEqual(fields, english_fields)
                    self.assertEqual(fields, expected)
                    rendered = template.format(**FORMAT_VALUES)
                    self.assertTrue(rendered.strip())
                    if key == "teaching_progress":
                        self.assertIn("2/7", rendered)
                    elif key == "teaching_course_progress":
                        self.assertIn("3/7", rendered)

    def test_tr_reads_current_language_for_every_fixed_key(self):
        for language in LANGUAGES:
            with mock.patch.object(i18n, "CURRENT", language):
                for key in sorted(FIXED_KEYS):
                    with self.subTest(language=language, key=key):
                        self.assertIn(key, STRINGS[language])
                        self.assertEqual(i18n.tr(key), STRINGS[language][key])
                        self.assertNotEqual(i18n.tr(key), key)

    def test_set_language_selects_fixed_translations(self):
        self.addCleanup(setattr, i18n, "CURRENT", i18n.CURRENT)
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(i18n.set_language(language), language)
                self.assertEqual(i18n.CURRENT, language)
                for key in sorted(FIXED_KEYS):
                    self.assertIn(key, STRINGS[language])
                    self.assertEqual(i18n.tr(key), STRINGS[language][key])

    def test_trf_formats_fixed_translations_in_current_language(self):
        for language in LANGUAGES:
            with mock.patch.object(i18n, "CURRENT", language):
                for key in sorted(FIXED_KEYS):
                    with self.subTest(language=language, key=key):
                        self.assertIn(key, STRINGS[language])
                        expected = STRINGS[language][key].format(**FORMAT_VALUES)
                        self.assertEqual(i18n.trf(key, **FORMAT_VALUES), expected)

    def test_progress_missing_parameters_fall_back_to_template(self):
        for language in LANGUAGES:
            with mock.patch.object(i18n, "CURRENT", language):
                for key, partial in (
                    ("teaching_progress", {"current": 2}),
                    ("teaching_course_progress", {"completed": 3}),
                ):
                    with self.subTest(language=language, key=key):
                        self.assertIn(key, STRINGS[language])
                        template = STRINGS[language][key]
                        self.assertEqual(i18n.trf(key), template)
                        self.assertEqual(i18n.trf(key, **partial), template)

    def test_localized_guidance_is_not_an_english_placeholder(self):
        for language in LANGUAGES:
            if language == "en":
                continue
            for key in (
                "teaching_entry", "teaching_welcome_body", "teaching_practice_notice",
                "teaching_search", "teaching_filter_all", "teaching_filter_completed",
                "teaching_filter_unfinished", "teaching_course_progress",
                "teaching_context_hints", "teaching_reset_progress",
                "teaching_reset_confirm", "teaching_reset_welcome",
                "teaching_reset_accept", "teaching_cancel",
            ):
                with self.subTest(language=language, key=key):
                    self.assertIn(key, STRINGS[language])
                    self.assertNotEqual(STRINGS[language][key], STRINGS["en"][key])


if __name__ == "__main__":
    unittest.main()
