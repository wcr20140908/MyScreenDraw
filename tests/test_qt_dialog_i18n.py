"""Qt standard-dialog localization for every supported application language."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class QtDialogTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main

    def tearDown(self):
        translator = getattr(self.app, "qtbase_translator", None)
        if translator is not None:
            self.app.removeTranslator(translator)
            del self.app.qtbase_translator

    def _install(self, language):
        with patch.object(self.main, "CURRENT", language):
            self.main.install_qt_translations(self.app)
        self.assertTrue(hasattr(self.app, "qtbase_translator"))

    def test_all_eight_languages_have_packaged_qtbase_catalogs(self):
        from PyQt6.QtCore import QLibraryInfo
        from pathlib import Path

        root = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        for language in ("zh", "en", "fr", "es", "de", "ru", "ko", "ja"):
            with self.subTest(language=language):
                code = "zh_CN" if language == "zh" else language
                self.assertTrue((root / f"qtbase_{code}.qm").is_file())

    def test_chinese_file_dialog_and_color_dialog_controls_are_localized(self):
        from PyQt6.QtWidgets import QColorDialog, QFileDialog, QLabel, QPushButton

        self._install("zh")
        file_dialog = QFileDialog()
        file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        file_text = [w.text() for w in file_dialog.findChildren(QLabel)] + [
            w.text() for w in file_dialog.findChildren(QPushButton)
        ]
        self.assertIn("文件名称(&N)：", file_text)
        self.assertIn("打开(&O)", file_text)
        self.assertIn("取消", file_text)

        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        color_text = [w.text() for w in color_dialog.findChildren(QLabel)] + [
            w.text() for w in color_dialog.findChildren(QPushButton)
        ]
        self.assertIn("基本颜色(&B)", color_text)
        self.assertIn("拾取屏幕颜色(&P)", color_text)
        self.assertIn("添加到自定义颜色(&A)", color_text)
        self.assertIn("确定", color_text)

    def test_each_language_changes_standard_dialog_open_button(self):
        from PyQt6.QtWidgets import QFileDialog, QPushButton

        expected = {
            "zh": "打开(&O)", "en": "&Open", "fr": "&Ouvrir", "es": "&Abrir",
            "de": "&Öffnen", "ru": "&Открыть", "ko": "열기(&O)", "ja": "開く(&O)",
        }
        for language, text in expected.items():
            with self.subTest(language=language):
                self._install(language)
                dialog = QFileDialog()
                dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
                self.assertIn(text, [w.text() for w in dialog.findChildren(QPushButton)])
                self.tearDown()


if __name__ == "__main__":
    unittest.main()
