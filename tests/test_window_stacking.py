"""Win32 stacking invariants for the floating panels.

The fullscreen canvas and every floating panel are all WS_EX_TOPMOST, so HWND_TOPMOST
alone does not decide which of two siblings wins. force_above() must genuinely place
the panel above the canvas even when the GWLP_HWNDPARENT owner binding is missing —
otherwise a shown submenu can land under the canvas and every click on it is swallowed
by the canvas instead.
"""
import ctypes
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000008, 0x00000080, 0x08000000
GW_HWNDNEXT = 2


@unittest.skipUnless(sys.platform == "win32", "Win32 z-order helpers")
class ForceAboveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main
        cls.u32 = ctypes.windll.user32
        cls.u32.CreateWindowExW.restype = ctypes.c_void_p
        cls.u32.GetTopWindow.restype = ctypes.c_void_p
        cls.u32.GetTopWindow.argtypes = [ctypes.c_void_p]
        cls.u32.GetWindow.restype = ctypes.c_void_p
        cls.u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.u32.DestroyWindow.argtypes = [ctypes.c_void_p]

    def _window(self, title, ex_style=0):
        # Parked far off-screen so the test never flashes anything at the user.
        hwnd = self.u32.CreateWindowExW(
            ex_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW, "STATIC", title,
            WS_POPUP | WS_VISIBLE, -3000, -3000, 120, 120, None, None, None, None)
        self.assertTrue(hwnd, "CreateWindowExW failed")
        self.addCleanup(self.u32.DestroyWindow, ctypes.c_void_p(hwnd))
        return hwnd

    def _z_index(self, target):
        """0 == frontmost, walking the real top-to-bottom z order."""
        hwnd = self.u32.GetTopWindow(None)
        index = 0
        while hwnd:
            if hwnd == target:
                return index
            hwnd = self.u32.GetWindow(ctypes.c_void_p(hwnd), GW_HWNDNEXT)
            index += 1
        return None

    def _stack(self, bind_owner):
        canvas = self._window("canvas", WS_EX_NOACTIVATE)
        panel = self._window("panel")
        if bind_owner:
            self.main.set_window_owner(panel, canvas)
        self.main.force_topmost(canvas)
        self.main.force_topmost(panel)
        self.main.force_above(panel, canvas)
        return self._z_index(canvas), self._z_index(panel)

    def test_panel_wins_even_without_the_owner_binding(self):
        canvas_z, panel_z = self._stack(bind_owner=False)
        self.assertIsNotNone(canvas_z)
        self.assertIsNotNone(panel_z)
        self.assertLess(panel_z, canvas_z,
                        "浮窗被全屏画布压住：点击会穿到画布上，子菜单点不动")

    def test_panel_wins_with_the_owner_binding(self):
        canvas_z, panel_z = self._stack(bind_owner=True)
        self.assertLess(panel_z, canvas_z)

    def test_force_above_is_a_noop_for_falsy_handles(self):
        self.main.force_above(0, 0)
        self.main.force_above(None, None)
        self.main.force_topmost(0)


class MoreMenuStackingTests(unittest.TestCase):
    """The "⋯" geometry menu is a parentless QMenu, so no owner keeps it above the canvas.

    The topmost heartbeat calls force_topmost(canvas), which lifts the fullscreen canvas
    to the front of the topmost band. If it keeps ticking while the menu is open, within
    500 ms the canvas covers the menu: strokes paint over the menu text and clicks fall
    through to the canvas. Every other modal (colour picker, calibration, roster import)
    already stops the heartbeat for its duration.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication

            cls.app = QApplication.instance() or QApplication([])
            import main

            cls.main = main
            cls.panel = main.ControlPanel()
            cls.canvas = main.DrawingCanvas(cls.panel)
            cls.panel.canvas = cls.canvas
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")

    @classmethod
    def tearDownClass(cls):
        for attr in ("listener", "timer", "autosave_timer"):
            try:
                getattr(cls.panel, attr).stop()
            except Exception:
                pass

    def _select_a_line(self):
        from PyQt6.QtCore import QPointF

        self.canvas.shape_items.clear()
        item = self.canvas.build_point_shape("LINE", [QPointF(10, 10), QPointF(120, 90)])
        self.canvas.shape_items.append(item)
        self.canvas.selected_ids = {item["id"]}
        self.assertIsNotNone(self.canvas.single_flat_shape())

    def test_heartbeat_is_paused_while_the_more_menu_is_open(self):
        from PyQt6.QtWidgets import QMenu

        self._select_a_line()
        self.panel.timer.start(self.panel.HEARTBEAT_MS)
        seen = {}
        original = QMenu.exec

        def fake_exec(menu, *args, **kwargs):
            seen["heartbeat_active"] = self.panel.timer.isActive()
            seen["actions"] = [a.text() for a in menu.actions() if a.text()]
            return None

        QMenu.exec = fake_exec
        try:
            self.panel.open_more_menu()
        finally:
            QMenu.exec = original

        self.assertIn("heartbeat_active", seen, "open_more_menu 没有弹出菜单")
        self.assertTrue(seen["actions"], "菜单没有任何条目")
        self.assertFalse(seen["heartbeat_active"],
                         "菜单弹出期间心跳仍在跑：force_topmost(画布) 会把画布盖到菜单上")
        self.assertTrue(self.panel.timer.isActive(), "菜单关闭后心跳必须恢复")

    def test_heartbeat_is_restored_even_if_the_menu_raises(self):
        from PyQt6.QtWidgets import QMenu

        self._select_a_line()
        self.panel.timer.start(self.panel.HEARTBEAT_MS)
        original = QMenu.exec

        def boom(menu, *args, **kwargs):
            raise RuntimeError("popup failed")

        QMenu.exec = boom
        try:
            with self.assertRaises(RuntimeError):
                self.panel.open_more_menu()
        finally:
            QMenu.exec = original
        self.assertTrue(self.panel.timer.isActive())


if __name__ == "__main__":
    unittest.main()
