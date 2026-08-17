"""Unified File panel structure, layout, and Save As behavior regressions."""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FilePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas

    @classmethod
    def tearDownClass(cls):
        for timer in (cls.panel.listener, cls.panel.timer, cls.panel.autosave_timer):
            try:
                timer.stop()
            except Exception:
                pass
        cls.canvas.close()
        cls.panel.close()

    def setUp(self):
        self.panel.show_only_sub(None)
        self.panel.set_orientation("portrait")

    def test_main_toolbar_has_one_file_entry_and_no_legacy_project_row(self):
        self.assertEqual(self.panel.btn_file.text(), self.main.tr("file"))
        direct_buttons = [
            item.widget() for item in
            (self.panel.toolbar_layout.itemAt(i) for i in range(self.panel.toolbar_layout.count()))
            if item.widget() is not None
        ]
        self.assertEqual(direct_buttons.count(self.panel.btn_file), 1)
        self.assertNotIn(self.panel.btn_open_project, direct_buttons)
        self.assertNotIn(self.panel.btn_save_project, direct_buttons)

    def test_file_panel_contains_every_grouped_command(self):
        commands = (
            self.panel.btn_open_project, self.panel.btn_save_project,
            self.panel.btn_save_project_as, self.panel.btn_import_media,
            self.panel.btn_export_png, self.panel.btn_export_pdf,
            self.panel.btn_export_svg, self.panel.btn_export_eps,
        )
        self.assertEqual(len(set(commands)), 8)
        for button in commands:
            with self.subTest(button=button.text()):
                self.assertIs(self.panel.file_sub, button.parentWidget())
                self.assertTrue(button.text())

    def test_tools_panel_no_longer_duplicates_file_commands(self):
        button_texts = {
            button.text() for button in self.panel.tools_sub.findChildren(self.main.QPushButton)
        }
        self.assertNotIn(self.main.tr("import_media"), button_texts)
        self.assertNotIn(self.main.tr("export"), button_texts)

    def test_file_panel_is_anchored_and_does_not_change_tool(self):
        self.canvas.draw_state = "ERASER"
        self.panel.handle_file_click()
        self.assertTrue(self.panel.file_sub.isVisible())
        self.assertIs(self.panel.sub_anchor_button(self.panel.file_sub), self.panel.btn_file)
        self.assertEqual(self.canvas.draw_state, "ERASER")
        self.panel.handle_file_click()
        self.assertFalse(self.panel.file_sub.isVisible())

    def test_file_panel_fits_in_both_orientations(self):
        for orientation in ("portrait", "landscape"):
            with self.subTest(orientation=orientation):
                self.panel.set_orientation(orientation)
                self.panel.show_only_sub(self.panel.file_sub)
                self.assertGreater(self.panel.menu_panel.width(), 0)
                self.assertGreater(self.panel.menu_panel.height(), 0)
                screen = self.panel.screen_geometry(self.panel)
                self.assertLessEqual(self.panel.menu_panel.width(), screen.width())
                self.assertLessEqual(self.panel.menu_panel.height(), screen.height())

    def test_file_action_wrappers_close_panel_and_pass_no_boolean_path(self):
        calls = []
        panel = types.SimpleNamespace(
            show_only_sub=lambda target: calls.append(("close", target)),
            open_project=lambda: calls.append(("open",)) or True,
            save_project=lambda: calls.append(("save",)) or True,
            save_project_as=lambda: calls.append(("save_as",)) or True,
            import_media=lambda: calls.append(("import",)) or None,
        )
        self.main.ControlPanel.open_project_from_file_panel(panel)
        self.main.ControlPanel.save_project_from_file_panel(panel)
        self.main.ControlPanel.save_project_as_from_file_panel(panel)
        self.main.ControlPanel.import_media_from_file_panel(panel)
        self.assertEqual(
            calls,
            [("close", None), ("open",), ("close", None), ("save",),
             ("close", None), ("save_as",), ("close", None), ("import",)],
        )

    def test_save_as_cancel_preserves_current_path(self):
        panel = types.SimpleNamespace(project_path="existing.msd")
        with patch.object(self.main.QFileDialog, "getSaveFileName", return_value=("", "")):
            result = self.main.ControlPanel.save_project_as(panel)
        self.assertFalse(result)
        self.assertEqual(panel.project_path, "existing.msd")

    def test_save_as_uses_selected_path_and_existing_save_logic(self):
        calls = []
        panel = types.SimpleNamespace(
            project_path="existing.msd",
            save_project=lambda path=None: calls.append(path) or True,
        )
        with patch.object(
                self.main.QFileDialog, "getSaveFileName",
                return_value=("new-copy.msd", "MyScreenDraw project")):
            result = self.main.ControlPanel.save_project_as(panel)
        self.assertTrue(result)
        self.assertEqual(calls, ["new-copy.msd"])
        self.assertEqual(panel.project_path, "existing.msd")


if __name__ == "__main__":
    unittest.main()
