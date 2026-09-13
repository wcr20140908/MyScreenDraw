"""生命周期管理：后台驻留、托盘、退出保存测试"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class LifecycleBasicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import main
        cls.main = main
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.lifecycle = cls.panel.lifecycle

    @classmethod
    def tearDownClass(cls):
        for timer in (cls.panel.listener, cls.panel.timer, cls.panel.autosave_timer):
            try:
                timer.stop()
            except Exception:
                pass
        cls.canvas.close()
        cls.panel.close()

    def test_lifecycle_manager_exists(self):
        self.assertIsNotNone(self.lifecycle)
        self.assertIn(self.lifecycle.state, ["showing", "hidden"])

    def test_hide_to_background_changes_state(self):
        initial_state = self.lifecycle.state
        self.lifecycle.hide_to_background()
        self.assertEqual(self.lifecycle.state, "hidden")
        # 恢复原状态
        if initial_state == "showing":
            self.lifecycle.restore_from_background()

    def test_show_from_background_restores_visible_state(self):
        self.lifecycle.hide_to_background()
        self.assertEqual(self.lifecycle.state, "hidden")
        self.lifecycle.restore_from_background()
        self.assertEqual(self.lifecycle.state, "showing")

    def test_hide_sets_penetrable_mode(self):
        self.lifecycle.hide_to_background()
        # 画布应该进入穿透模式
        self.assertFalse(self.canvas.is_drawing_mode)
        self.lifecycle.restore_from_background()

    def test_tray_icon_exists(self):
        # offscreen环境托盘不可用，跳过托盘测试
        if not self.lifecycle.tray_icon:
            self.skipTest("System tray not available in offscreen mode")
        self.assertIsNotNone(self.lifecycle.tray_icon)
        self.assertTrue(self.lifecycle.tray_icon.isSystemTrayAvailable())

    def test_tray_menu_has_four_items(self):
        # offscreen环境托盘不可用，跳过托盘测试
        if not self.lifecycle.tray_icon:
            self.skipTest("System tray not available in offscreen mode")
        menu = self.lifecycle.tray_icon.contextMenu()
        actions = [a for a in menu.actions() if not a.isSeparator()]
        # 显示/隐藏、设置、重启、退出 = 4项（不含分隔线）
        self.assertEqual(len(actions), 4)

    def test_hide_commits_active_text_box(self):
        """隐藏时应该调用end_text_edit()结束活动的文本框编辑"""
        # 进入绘图模式并创建文本框
        self.panel.set_drawing_mode(True)
        self.canvas.current_tool = "text"

        # 创建文本框
        from PyQt6.QtCore import QRectF
        item = self.canvas.finish_text_box(QRectF(100, 100, 200, 80))
        self.canvas.begin_text_edit(item)

        # 验证文本框正在编辑
        self.assertIsNotNone(self.canvas.editing_text_item())

        # 隐藏到后台 - 应该调用end_text_edit()
        self.lifecycle.hide_to_background()

        # 验证文本框已经结束编辑
        self.assertIsNone(self.canvas.editing_text_item())

        # 恢复
        self.lifecycle.restore_from_background()


if __name__ == "__main__":
    unittest.main()
