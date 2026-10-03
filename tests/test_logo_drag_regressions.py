# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen LOGO regressions, without ControlPanel startup/hooks/settings I/O."""
import ast
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget
import toolbar_windows


def positioning_class():
    # Execute the actual production methods, not copies; avoid main's startup imports.
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
    panel = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ControlPanel")
    names = {"_on_logo_dragged", "_toolbar_slot_next_to_logo", "_reposition_toolbar_next_to_logo"}
    methods = [n for n in panel.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(methods) == len(names)
    cls = ast.ClassDef(name="Positioning", bases=[], keywords=[], body=methods, decorator_list=[])
    namespace = {"toolbar_windows": toolbar_windows}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "main.py", "exec"), namespace)
    return namespace["Positioning"]


class Toolbar(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)

    def clamp_into_screen(self):
        self.move(*toolbar_windows.clamp_point_into(self.x(), self.y(), self.width(), self.height(),
                                                   toolbar_windows._available_rect(self)))


class LogoDragRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.Positioning = positioning_class()

    def setUp(self):
        with patch.dict(sys.modules, {"main": types.SimpleNamespace(tr=lambda key: key)}):
            self.logo = toolbar_windows.LogoWindow()
        self.toolbar = Toolbar()
        self.panel = self.Positioning()
        self.panel.logo_window = self.logo
        self.panel.toolbar_window = self.toolbar
        self.panel._toolbar_detached = False
        self.panel._toolbar_saved_pos = None
        self.panel._schedule_split_save = lambda: None
        self.area = QRect(-200, -100, 800, 600)
        self.area_patch = patch.object(toolbar_windows, "_available_rect", return_value=self.area)
        self.area_patch.start()
        self.logo.show()
        self.toolbar.show()
        self.app.processEvents()
        self.clicks = []
        self.logo.clicked.connect(lambda: self.clicks.append(True))
        self.logo.position_changed.connect(self.panel._on_logo_dragged)
        self.configure("portrait")

    def tearDown(self):
        self.logo.close()
        self.toolbar.close()
        self.area_patch.stop()

    def configure(self, orientation):
        self.panel.orientation = orientation
        self.logo.set_size(*( (56, 40) if orientation == "portrait" else (40, 56)))
        self.toolbar.setFixedSize(*( (56, 400) if orientation == "portrait" else (400, 56)))
        self.logo.move(0, 0)

    def mouse(self, kind, global_pos, button, buttons):
        local = self.logo.logo_btn.mapFromGlobal(global_pos)
        event = QMouseEvent(kind, QPointF(local), QPointF(global_pos), button, buttons,
                            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.logo.logo_btn, event)

    def drag(self, target, release=True):
        start = self.logo.pos() + QPoint(10, 10)
        self.mouse(QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        self.assertTrue(self.logo.logo_btn.isDown())
        end = target + QPoint(10, 10)
        self.mouse(QEvent.Type.MouseMove, end, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        if release:
            self.mouse(QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)

    def assert_attached(self):
        gap = toolbar_windows.LOGO_GAP
        if self.panel.orientation == "portrait":
            self.assertEqual(self.toolbar.pos(), self.logo.pos() + QPoint(0, self.logo.height() + gap))
        else:
            self.assertEqual(self.toolbar.pos(), self.logo.pos() + QPoint(self.logo.width() + gap, 0))
        self.assertTrue(self.area.contains(self.logo.geometry()))
        self.assertTrue(self.area.contains(self.toolbar.geometry()))

    def test_drag_release_clears_pressed_without_click_and_next_click_works(self):
        self.drag(QPoint(80, 20))
        self.assertFalse(self.logo.logo_btn.isDown())
        self.assertEqual(self.clicks, [])
        self.assertIsNone(self.logo._drag_offset)
        self.assertIsNone(self.logo._press_pos)
        self.assertFalse(self.logo._dragging)
        QTest.mouseClick(self.logo.logo_btn, Qt.MouseButton.LeftButton)
        self.assertEqual(self.clicks, [True])

    def test_drag_clears_pressed_before_release(self):
        self.drag(QPoint(80, 20), release=False)
        self.assertFalse(self.logo.logo_btn.isDown())

    def test_normal_click_and_small_jitter_still_toggle(self):
        start = self.logo.pos() + QPoint(10, 10)
        self.mouse(QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        self.mouse(QEvent.Type.MouseMove, start + QPoint(2, 2), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        self.mouse(QEvent.Type.MouseButtonRelease, start + QPoint(2, 2), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        self.assertEqual(self.clicks, [True])
        self.assertFalse(self.logo.logo_btn.isDown())

    def test_attached_drag_clamps_group_at_every_edge(self):
        for orientation in ("portrait", "landscape"):
            for target in (QPoint(580, 480), QPoint(-400, -300), QPoint(150, 180), QPoint(900, 900)):
                with self.subTest(orientation=orientation, target=target):
                    self.configure(orientation)
                    self.drag(target)
                    self.assert_attached()
                    before = (self.logo.pos(), self.toolbar.pos())
                    self.panel._reposition_toolbar_next_to_logo()
                    self.assertEqual(before, (self.logo.pos(), self.toolbar.pos()))

    def test_detached_and_collapsed_drag_do_not_move_toolbar(self):
        for detached in (False, True):
            with self.subTest(detached=detached):
                self.panel._toolbar_detached = detached
                self.toolbar.setVisible(detached)
                self.toolbar.move(-100, -50)
                self.drag(QPoint(580, 480))
                self.assertEqual(self.toolbar.pos(), QPoint(-100, -50))
                self.assertEqual(self.logo.pos(), QPoint(544, 460))
                self.logo.move(0, 0)

    def test_continued_edge_drag_and_reverse_keep_pair_attached(self):
        for orientation in ("portrait", "landscape"):
            with self.subTest(orientation=orientation):
                self.configure(orientation)
                self.drag(QPoint(900, 900), release=False)
                stopped = (self.logo.pos(), self.toolbar.pos())
                self.mouse(QEvent.Type.MouseMove, QPoint(1100, 1100),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
                self.assertEqual(stopped, (self.logo.pos(), self.toolbar.pos()))
                self.assert_attached()
                self.mouse(QEvent.Type.MouseMove, QPoint(10, 10),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
                self.assertEqual(self.logo.pos(), QPoint(0, 0))
                self.assert_attached()
                self.mouse(QEvent.Type.MouseButtonRelease, QPoint(10, 10),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
                self.assertFalse(self.logo.logo_btn.isDown())
                self.assertEqual(self.clicks, [])

    def test_reposition_preserves_hidden_logo_and_detached_toolbar(self):
        self.toolbar.hide()
        self.logo.move(544, 460)
        self.panel._reposition_toolbar_next_to_logo()
        self.assertEqual(self.logo.pos(), QPoint(544, 460))
        self.toolbar.show()
        self.panel._toolbar_detached = True
        self.panel._toolbar_saved_pos = (-150, -80)
        self.panel._reposition_toolbar_next_to_logo()
        self.assertEqual(self.toolbar.pos(), QPoint(-150, -80))
        self.assertEqual(self.logo.pos(), QPoint(544, 460))

    def test_oversized_group_is_stable_and_does_not_overlap(self):
        for orientation in ("portrait", "landscape"):
            with self.subTest(orientation=orientation):
                self.configure(orientation)
                self.toolbar.setFixedSize(*( (56, 700) if orientation == "portrait" else (900, 56)))
                self.drag(QPoint(200, 200))
                before = (self.logo.pos(), self.toolbar.pos())
                for _ in range(3):
                    self.panel._reposition_toolbar_next_to_logo()
                    self.assertEqual(before, (self.logo.pos(), self.toolbar.pos()))
                self.assertFalse(self.logo.geometry().intersects(self.toolbar.geometry()))


if __name__ == "__main__":
    unittest.main()
