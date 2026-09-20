"""v6.0.0-beta.3 关键功能验证"""
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import ControlPanel
from ui_icons import make_ui_pixmap


class IconGenerationTests(unittest.TestCase):
    """验证所有图标能正常生成"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_all_toolbar_icons_generate(self):
        """所有工具栏图标都能生成非空 pixmap"""
        icons = ['mouse', 'pen', 'eraser', 'select', 'text', 'shape', 'tools',
                 'folder', 'undo', 'redo', 'clear', 'whiteboard', 'settings', 'close']

        for name in icons:
            with self.subTest(icon=name):
                pix = make_ui_pixmap(name, '#5b8def', 20)
                self.assertFalse(pix.isNull(), f"{name} icon is null")
                self.assertEqual(pix.width(), 20)
                self.assertEqual(pix.height(), 20)


class LogoWindowTests(unittest.TestCase):
    """验证 LOGO 窗口的点击和拖动功能"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = ControlPanel()
        self.panel.offscreen_mode = True

    def tearDown(self):
        try:
            self.panel.close()
            self.panel.canvas.close()
            if self.panel.logo_window:
                self.panel.logo_window.close()
            if self.panel.toolbar_window:
                self.panel.toolbar_window.close()
        except Exception:
            pass

    def test_logo_uses_theme_colors(self):
        """LOGO 图标使用主题颜色而非硬编码颜色"""
        # 读取 _make_logo_icon 源码，确认使用 self.theme
        import inspect
        source = inspect.getsource(self.panel._make_logo_icon)

        self.assertIn('self.theme["accent"]', source)
        self.assertIn('self.theme["button"]', source)
        # theme["text"] 不是必需的，LOGO 只需要 accent 和 button
        self.assertNotIn('#5b8def', source, "LOGO should not use hardcoded colors")

    def test_logo_window_exists(self):
        """LOGO 窗口已创建"""
        self.assertIsNotNone(self.panel.logo_window)

    def test_toolbar_window_exists(self):
        """工具栏窗口已创建"""
        self.assertIsNotNone(self.panel.toolbar_window)

    def test_toolbar_collapse_hides_toolbar(self):
        """折叠功能隐藏工具栏但保留 LOGO"""
        # offscreen 模式下先显示窗口
        self.panel.logo_window.show()
        self.panel.toolbar_window.show()

        self.assertTrue(self.panel.toolbar_window.isVisible())

        # 调用折叠
        self.panel.toggle_toolbar_collapsed()

        # 工具栏应该隐藏
        self.assertFalse(self.panel.toolbar_window.isVisible())
        # LOGO 应该保持可见
        self.assertTrue(self.panel.logo_window.isVisible())

    def test_toolbar_expand_shows_toolbar(self):
        """展开功能显示工具栏"""
        # offscreen 模式下先显示窗口
        self.panel.logo_window.show()
        self.panel.toolbar_window.show()

        # 先折叠
        self.panel.toggle_toolbar_collapsed()
        self.assertFalse(self.panel.toolbar_window.isVisible())

        # 再展开
        self.panel.toggle_toolbar_collapsed()

        # 工具栏应该重新显示
        self.assertTrue(self.panel.toolbar_window.isVisible())
        self.assertTrue(self.panel.logo_window.isVisible())


class LifecycleTests(unittest.TestCase):
    """验证生命周期管理（后台隐藏、恢复）"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = ControlPanel()
        self.panel.offscreen_mode = True

    def tearDown(self):
        try:
            if hasattr(self.panel, 'lifecycle') and self.panel.lifecycle:
                self.panel.lifecycle.state = "showing"  # 重置状态以便正常关闭
            self.panel.close()
            self.panel.canvas.close()
            if self.panel.logo_window:
                self.panel.logo_window.close()
            if self.panel.toolbar_window:
                self.panel.toolbar_window.close()
        except Exception:
            pass

    def test_close_button_hides_to_background(self):
        """关闭按钮转入后台而非退出"""
        # offscreen 模式下先显示窗口
        self.panel.logo_window.show()
        self.panel.toolbar_window.show()
        if self.panel.canvas:
            self.panel.canvas.show()

        self.assertTrue(self.panel.logo_window.isVisible())
        self.assertTrue(self.panel.toolbar_window.isVisible())

        # 调用关闭
        self.panel.close_to_background()

        # 所有窗口应该隐藏
        self.assertFalse(self.panel.logo_window.isVisible())
        self.assertFalse(self.panel.toolbar_window.isVisible())
        if self.panel.canvas:
            self.assertFalse(self.panel.canvas.isVisible())

        # 生命周期状态应该是 HIDDEN
        from app_lifecycle import LifecycleState
        self.assertEqual(self.panel.lifecycle.state, LifecycleState.HIDDEN)

    def test_restore_from_background_shows_windows(self):
        """从后台恢复显示所有窗口"""
        # offscreen 模式下先显示窗口
        self.panel.logo_window.show()
        self.panel.toolbar_window.show()
        if self.panel.canvas:
            self.panel.canvas.show()

        # 先隐藏
        self.panel.close_to_background()
        self.assertFalse(self.panel.logo_window.isVisible())

        # 恢复
        self.panel.lifecycle.restore_from_background()

        # 窗口应该重新显示
        self.assertTrue(self.panel.logo_window.isVisible())
        self.assertTrue(self.panel.toolbar_window.isVisible())
        if self.panel.canvas:
            self.assertTrue(self.panel.canvas.isVisible())


if __name__ == "__main__":
    unittest.main()
