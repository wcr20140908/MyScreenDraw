"""Thumbnail panel vs submenus: only one floating window at a time.

The thumbnail panel is an independent floating window, not a member of all_subs(),
so show_only_sub() never touched it. Both it and the submenu panel call
raise_floating, and HWND_TOPMOST cannot order two siblings inside the topmost
band -- whichever loses ends up under the other and its clicks land on the
fullscreen canvas instead (in eraser mode that silently wipes content).
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ThumbnailZOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        try:
            cls.panel = main.ControlPanel()
        except Exception as exc:      # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas

    @classmethod
    def tearDownClass(cls):
        for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
            try:
                getattr(getattr(cls, "panel", None), name).stop()
            except Exception:
                pass

    def setUp(self):
        # 缩略图只在白板模式下开得起来，走正式入口以建立页面模型
        if not self.canvas.whiteboard_mode:
            self.canvas.enter_whiteboard()
        self.panel.show_only_sub(None)
        self.panel.close_thumbnail_panel()

    def open_thumbnail(self):
        self.panel.toggle_thumbnail_panel()
        return self.panel.thumbnail_panel.isVisible()

    def test_opening_a_submenu_closes_the_thumbnail(self):
        self.assertTrue(self.open_thumbnail(), "缩略图应打开")
        self.panel.show_only_sub(self.panel.draw_sub)
        self.assertFalse(self.panel.thumbnail_panel.isVisible(),
                         "打开子菜单时缩略图必须让位，否则两个浮窗抢置顶")

    def test_opening_the_thumbnail_closes_a_submenu(self):
        """反向也要成立：只做单向的话，关掉再开缩略图时子菜单还在，争抢原样复现。"""
        self.panel.show_only_sub(self.panel.draw_sub)
        self.assertTrue(self.panel.menu_panel.isVisible())
        self.open_thumbnail()
        self.assertFalse(self.panel.menu_panel.isVisible(),
                         "打开缩略图时子菜单必须收起")

    def test_closing_the_thumbnail_stops_live_rendering(self):
        """只 hide() 不停计时器的话，它仍以 150ms 节拍把整本白板逐页渲染成 pixmap，
        白占主线程拖慢正在书写的笔迹。"""
        self.open_thumbnail()
        self.panel.show_only_sub(self.panel.draw_sub)
        self.assertFalse(self.panel._thumbnail_live_timer.isActive(),
                         "缩略图关闭后实时渲染必须停")

    def test_toggle_closes_when_already_open(self):
        self.assertTrue(self.open_thumbnail())
        self.panel.toggle_thumbnail_panel()
        self.assertFalse(self.panel.thumbnail_panel.isVisible())
        self.assertFalse(self.panel._thumbnail_live_timer.isActive())

    def test_close_reports_whether_it_did_anything(self):
        """toggle 靠这个返回值区分「刚关掉」和「本来就没开」。"""
        self.open_thumbnail()
        self.assertTrue(self.panel.close_thumbnail_panel())
        self.assertFalse(self.panel.close_thumbnail_panel())

    def test_the_timer_stops_even_if_the_panel_was_hidden_elsewhere(self):
        """面板被别的路径 hide() 之后，计时器仍必须能停。

        实测过的 bug：close_thumbnail_panel 原先先判断 isVisible()，面板已隐藏时
        直接 return，_thumbnail_live_timer 就再也停不下来，一直以 150ms 节拍渲染
        整本白板。
        """
        self.open_thumbnail()
        self.panel.thumbnail_panel.hide()          # 绕过正式入口
        self.assertTrue(self.panel._thumbnail_live_timer.isActive())
        self.panel.close_thumbnail_panel()
        self.assertFalse(self.panel._thumbnail_live_timer.isActive(),
                         "面板已隐藏也必须把实时渲染停掉")

    def test_collapsing_everything_leaves_the_thumbnail_alone(self):
        """show_only_sub(None) 是「全部收起」，缩略图是独立浮窗，不该被它带走。"""
        self.panel.show_only_sub(None)
        self.assertTrue(self.open_thumbnail())
        self.panel.show_only_sub(None)
        self.assertTrue(self.panel.thumbnail_panel.isVisible(),
                        "收起子菜单不应关掉缩略图")

    def test_thumbnail_is_not_a_submenu(self):
        self.assertNotIn(self.panel.thumbnail_panel, self.panel.all_subs(),
                         "缩略图不在 all_subs() 里——这正是原先漏管它的原因")


if __name__ == "__main__":
    unittest.main(verbosity=2)
