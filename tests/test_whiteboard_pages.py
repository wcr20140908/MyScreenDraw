"""Offscreen whiteboard page controls and safe deletion regressions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QLine, QRect
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QApplication, QMessageBox
import main


class WhiteboardPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.panel.pause_callbacks()

    @classmethod
    def tearDownClass(cls):
        cls.panel.pause_callbacks()
        if getattr(cls.panel, "listener", None):
            cls.panel.listener.stop()
        for widget in cls.app.topLevelWidgets():
            widget.hide()

    def setUp(self):
        self.panel.close_thumbnail_panel()
        self.canvas._cancel_all_pointers()
        self.canvas.whiteboard_mode = True
        self.canvas.pages = [{"segments": [], "texts": [], "shapes": [], "images": []}]
        self.canvas.current_page = 0
        self.canvas.load_page(self.canvas.pages[0])
        self.canvas.reset_history()
        self.panel.project_dirty = False
        self.panel.update_whiteboard_ui()

    def ink(self, name):
        self.canvas.all_segments.append({"line": QLine(1, 2, 30, 40), "pen": QPen(), "id": name})

    def test_delete_survivor_preserves_live_snapshot(self):
        self.canvas.new_page()
        self.ink("live")
        self.canvas.schedule_page_snapshot()
        self.assertTrue(self.canvas.delete_page(0))
        self.assertEqual(self.canvas.current_page, 0)
        self.assertEqual(self.canvas.pages[0]["segments"][0]["id"], "live")
        self.assertFalse(self.canvas._page_snapshot_timer.isActive())
        self.assertTrue(self.panel.project_dirty)

    def test_delete_current_loads_neighbor_and_clears_history_and_stroke(self):
        self.ink("survivor")
        self.canvas.new_page()
        self.ink("deleted")
        self.canvas.push_undo()
        self.canvas.redo_stack.append(self.canvas.capture_page())
        self.canvas.current_stroke_id = "deleted"
        self.canvas.current_stroke_points = [main.QPointF(1, 1)]
        with patch.object(self.canvas, "_cancel_all_pointers", wraps=self.canvas._cancel_all_pointers) as cancel:
            self.assertTrue(self.canvas.delete_page())
            cancel.assert_called_once()
        self.assertEqual(self.canvas.all_segments[0]["id"], "survivor")
        self.assertFalse(self.canvas.undo_stack)
        self.assertFalse(self.canvas.redo_stack)
        self.assertIsNone(self.canvas.current_stroke_id)
        self.assertFalse(self.canvas.current_stroke_points)

    def test_delete_only_page_keeps_blank_page(self):
        self.ink("deleted")
        self.canvas.delete_page()
        self.assertEqual(len(self.canvas.pages), 1)
        self.assertEqual(self.canvas.current_page, 0)
        self.assertFalse(main.page_has_content(self.canvas.capture_page()))
        self.assertFalse(main.page_has_content(self.canvas.pages[0]))

    def test_invalid_delete_does_not_change_document(self):
        self.ink("retained")
        self.assertFalse(self.canvas.delete_page(-1))
        self.assertFalse(self.canvas.delete_page(1))
        self.assertEqual(self.canvas.all_segments[0]["id"], "retained")
        self.assertFalse(self.panel.project_dirty)

    def test_boundary_arrows_remain_enabled_grey_and_notify(self):
        with patch.object(main, "tr", side_effect=lambda key: key), patch.object(main, "notify_user") as notify:
            for button, message in ((self.panel.rail_prev, "first_page"), (self.panel.rail_next, "last_page")):
                self.assertTrue(button.isEnabled())
                self.assertIn("#919991", button.styleSheet())
                button.click()
                notify.assert_called_with(self.panel, "page_list", message, level="information")
        self.canvas.new_page()
        self.panel.update_whiteboard_ui()
        self.assertIn("#1c2420", self.panel.rail_prev.styleSheet())
        self.panel.rail_prev.click()
        self.assertEqual(self.canvas.current_page, 0)
        self.assertIn("#1c2420", self.panel.rail_next.styleSheet())

    def run_confirmation(self, result):
        self.panel.toggle_thumbnail_panel()
        original_pause = self.panel.pause_callbacks
        def exec_box(box):
            self.assertEqual(box.defaultButton(), box.button(QMessageBox.StandardButton.Cancel))
            self.assertEqual(box.escapeButton(), box.button(QMessageBox.StandardButton.Cancel))
            self.assertTrue(box.windowFlags() & main.Qt.WindowType.WindowStaysOnTopHint)
            self.assertFalse(self.panel._thumbnail_live_timer.isActive())
            return result
        with patch.object(QMessageBox, "exec", exec_box), patch.object(self.panel, "pause_callbacks", wraps=original_pause) as pause, patch.object(self.panel, "resume_callbacks") as resume, patch.object(self.panel, "raise_floating") as raise_window:
            self.panel.btn_delete_page.click()
            pause.assert_called_once()
            resume.assert_called_once()
            self.assertFalse(raise_window.call_args_list[0].kwargs["bind_owner"])
        self.assertTrue(self.panel._thumbnail_live_timer.isActive())

    def test_cancel_confirmation_leaves_content_and_history_unchanged(self):
        self.ink("retained")
        self.canvas.push_undo()
        self.run_confirmation(QMessageBox.StandardButton.Cancel)
        self.assertEqual(self.canvas.all_segments[0]["id"], "retained")
        self.assertEqual(len(self.canvas.undo_stack), 1)
        self.assertFalse(self.panel.project_dirty)

    def test_confirm_deletes_and_refreshes_list(self):
        self.canvas.new_page()
        self.run_confirmation(QMessageBox.StandardButton.Yes)
        self.assertEqual(len(self.canvas.pages), 1)
        self.assertEqual(self.panel.thumbnail_list.count(), 1)
        self.assertEqual(self.panel.rail_count.text(), "1/1")
        self.assertTrue(self.panel.project_dirty)

    def test_compact_placement_tracks_rail_and_clamps_to_screen(self):
        self.assertLess(self.panel.thumbnail_list.minimumWidth(), 580)
        with patch.object(main.toolbar_windows, "_available_rect", return_value=QRect(-800, 20, 800, 600)), patch.object(self.panel, "_floating_anchor", side_effect=AssertionError("must not anchor to toolbar")):
            self.panel._position_page_rail()
            self.panel.toggle_thumbnail_panel()
            rect = self.panel.thumbnail_panel.geometry()
            rail = self.panel.page_rail.geometry()
            self.assertLessEqual(rect.width(), 320)
            self.assertLessEqual(rect.height(), 300)
            self.assertEqual(rect.right(), rail.right())
            self.assertLess(rect.bottom(), rail.top())
            self.assertTrue(QRect(-800, 20, 800, 600).contains(rect))
        with patch.object(main.toolbar_windows, "_available_rect", return_value=QRect(0, 0, 300, 250)):
            self.panel._position_page_rail()
            rect = self.panel.thumbnail_panel.geometry()
            self.assertTrue(QRect(0, 0, 300, 250).contains(rect), str(rect))
            self.assertLess(rect.bottom(), self.panel.page_rail.geometry().top())


if __name__ == "__main__":
    unittest.main()
