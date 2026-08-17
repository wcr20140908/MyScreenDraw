"""Tool-state invariants for the control panel.

The eraser-to-other-tool defects all came from one broken invariant: a click handler
moved the main-bar highlight without changing ``canvas.draw_state``. The canvas then
kept erasing, kept painting its eraser cursor, and clicking the eraser button again
only toggled its settings panel, so the mismatch never healed.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_panel():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import main

    panel = main.ControlPanel()
    canvas = main.DrawingCanvas(panel)
    panel.canvas = canvas
    return app, main, panel, canvas


class ToolHighlightInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app, cls.main, cls.panel, cls.canvas = _build_panel()
        except Exception as exc:  # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")

    @classmethod
    def tearDownClass(cls):
        for stopper in (getattr(getattr(cls, "panel", None), "listener", None),
                        getattr(getattr(cls, "panel", None), "timer", None),
                        getattr(getattr(cls, "panel", None), "autosave_timer", None)):
            try:
                stopper.stop()
            except Exception:
                pass

    def highlighted(self):
        buttons = {
            "btn_pen": self.panel.btn_pen, "btn_eraser": self.panel.btn_eraser,
            "btn_select": self.panel.btn_select, "btn_text": self.panel.btn_text,
            "btn_shape": self.panel.btn_shape, "btn_tools": self.panel.btn_tools,
        }
        return {name for name, btn in buttons.items() if btn.objectName() == "ActiveTool"}

    def assert_highlight_matches_state(self):
        expected = self.panel.TOOL_HIGHLIGHT.get(self.canvas.draw_state)
        self.assertIsNotNone(expected, f"unmapped draw_state {self.canvas.draw_state}")
        self.assertEqual(self.highlighted(), {expected},
                         f"draw_state={self.canvas.draw_state} 高亮={self.highlighted()}")

    def test_highlight_tracks_draw_state_across_every_tool_switch(self):
        steps = [
            self.panel.handle_eraser_click,
            self.panel.handle_annotate_click,
            self.panel.handle_eraser_click,
            self.panel.handle_select_click,
            self.panel.handle_eraser_click,
            self.panel.handle_shape_click,
            self.panel.handle_eraser_click,
            self.panel.handle_text_click,
            self.panel.handle_eraser_click,
            self.panel.handle_spotlight_click,
            self.panel.handle_eraser_click,
            self.panel.choose_marker_tool,
            self.panel.handle_eraser_click,
            self.panel.choose_laser_tool,
        ]
        for step in steps:
            with self.subTest(step=step.__name__):
                step()
                self.assert_highlight_matches_state()

    def test_annotate_button_leaves_the_eraser_instead_of_only_moving_the_highlight(self):
        self.panel.handle_eraser_click()
        self.assertEqual(self.canvas.draw_state, "ERASER")
        self.panel.handle_annotate_click()
        self.assertIn(self.canvas.draw_state, ("PEN", "MARKER", "LASER"))
        self.assert_highlight_matches_state()

    def test_annotate_button_returns_to_the_last_used_annotate_tool(self):
        self.panel.choose_marker_tool()
        self.panel.handle_eraser_click()
        self.panel.handle_annotate_click()
        self.assertEqual(self.canvas.draw_state, "MARKER")

        self.panel.choose_pen_tool()
        self.panel.handle_eraser_click()
        self.panel.handle_annotate_click()
        self.assertEqual(self.canvas.draw_state, "PEN")

    def test_leaving_the_eraser_parks_its_cursor_off_screen(self):
        from PyQt6.QtCore import QPoint

        self.panel.handle_eraser_click()
        self.canvas.mouse_pos = QPoint(600, 400)
        self.panel.handle_annotate_click()
        self.assertNotEqual(self.canvas.draw_state, "ERASER")
        self.assertLess(self.canvas.mouse_pos.x(), 0, "橡皮光标圈会残留在画布上")

    def test_placing_an_aid_keeps_the_real_tool_highlighted(self):
        self.panel.handle_eraser_click()
        self.panel.spawn_aid("ruler")
        # 教具在任意绘图态下都可拖动，因此 draw_state 不变；高亮也不能改口说是「工具」。
        self.assertEqual(self.canvas.draw_state, "ERASER")
        self.assert_highlight_matches_state()
        self.canvas.clear_aids()


if __name__ == "__main__":
    unittest.main()
