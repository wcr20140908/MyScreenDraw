"""测试所有UI图标的生成"""
import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from ui_icons import make_ui_pixmap


class IconGenerationTests(unittest.TestCase):
    """验证所有图标都能正确生成"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建QApplication"""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
    """验证所有图标都能正确生成"""

    def test_all_icons_generate_valid_pixmaps(self):
        """所有图标名称都应该生成有效的QPixmap"""
        icon_names = [
            "mouse", "pen", "eraser", "select", "text", "shape", "tools",
            "folder", "undo", "redo", "clear", "whiteboard", "settings", "close",
            "line", "rect", "ellipse", "arrow", "number",
            "ruler", "protractor", "calculator", "dice", "timer", "nametag",
            "screenshot", "magnifier", "keyboard", "logo",
        ]

        for name in icon_names:
            with self.subTest(icon=name):
                pixmap = make_ui_pixmap(name, "#5b8def", 32)
                self.assertIsInstance(pixmap, QPixmap)
                self.assertFalse(pixmap.isNull())
                self.assertEqual(pixmap.width(), 32)
                self.assertEqual(pixmap.height(), 32)

    def test_icon_color_customization(self):
        """图标应该使用指定的颜色"""
        # 测试不同颜色的图标生成
        colors = ["#ff0000", "#00ff00", "#0000ff", "#ffffff", "#000000"]
        for color in colors:
            with self.subTest(color=color):
                pixmap = make_ui_pixmap("pen", color, 24)
                self.assertIsInstance(pixmap, QPixmap)
                self.assertFalse(pixmap.isNull())

    def test_icon_size_scaling(self):
        """图标应该支持不同的尺寸"""
        sizes = [16, 20, 24, 32, 40, 48]
        for size in sizes:
            with self.subTest(size=size):
                pixmap = make_ui_pixmap("pen", "#5b8def", size)
                self.assertEqual(pixmap.width(), size)
                self.assertEqual(pixmap.height(), size)


if __name__ == "__main__":
    unittest.main()
