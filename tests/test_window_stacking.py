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
class Win32WindowCase(unittest.TestCase):
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
        self.created = getattr(self, "created", set()) | {hwnd}
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


class ForceAboveTests(Win32WindowCase):
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


@unittest.skipUnless(sys.platform == "win32", "Win32 z-order helpers")
class TopmostOrderTests(Win32WindowCase):
    """5.5.1: the heartbeat reads the real topmost band and only rewrites it when wrong.

    Desired order, top to bottom: ClassIsland's windows > our floating chain > canvas >
    every other topmost window (sprite balls, floating launchers, the taskbar). Two things
    the old heartbeat got wrong: it shoved the canvas to the *front* of the band every
    500 ms (covering ClassIsland and, in whiteboard mode, recompositing the opaque
    fullscreen canvas twice a second -- the "main panel flickers" report), and it never
    checked whether anything needed moving at all.

    Windows are real STATIC windows parked off-screen; ownership mirrors the app
    (panel owned by canvas, tool owned by panel). Process-based predicates are replaced
    by explicit sets: only windows this test created can be "foreign" or "privileged".
    Everything else in the real topmost band (the user's actual ClassIsland, which
    re-asserts itself while the suite runs, the taskbar, IME helpers) is desktop noise
    and is treated as harmless, otherwise the verdict depends on what happens to be open.
    """

    def setUp(self):
        self.foreign = self._window("foreign-floater")           # a "sprite ball"
        self.island = self._window("classisland")                 # stands in for ClassIsland
        self.canvas = self._window("canvas", WS_EX_NOACTIVATE)
        self.panel = self._window("panel")
        self.tool = self._window("text-panel")
        self.main.set_window_owner(self.panel, self.canvas)
        self.main.set_window_owner(self.tool, self.panel)
        self.chain = [self.tool, self.panel, self.canvas]
        self.ignore = set()

    def _enforce(self, privileged=()):
        ours = set(self.chain)
        return self.main.enforce_topmost_order(
            self.chain,
            is_ours=lambda h: h in ours or h not in self.created,
            is_privileged=lambda h: h in privileged,
            ignore=self.ignore)

    def _z(self, *handles):
        zs = [self._z_index(h) for h in handles]
        self.assertNotIn(None, zs, "窗口不在 Z 序里")
        return zs

    def _assert_chain_order(self):
        tool_z, panel_z, canvas_z = self._z(self.tool, self.panel, self.canvas)
        self.assertLess(tool_z, panel_z, "文字面板没压在主面板之上")
        self.assertLess(panel_z, canvas_z, "主面板没压在画布之上")

    def test_a_foreign_topmost_window_gets_covered(self):
        self.main.force_topmost(self.foreign)          # the floater re-asserts itself
        self.assertLess(self._z(self.foreign)[0], self._z(self.canvas)[0])
        changed, ceiling, unreachable = self._enforce()
        self.assertTrue(changed)
        self.assertIsNone(ceiling)
        self.assertEqual(unreachable, [])
        self._assert_chain_order()
        self.assertLess(self._z(self.canvas)[0], self._z(self.foreign)[0],
                        "画布没有压过悬浮窗：置顶不够靠上")

    def _above(self, target):
        """Every *visible* window stacked above target, top to bottom.

        Hidden ones are excluded on purpose: each thread's invisible "Default IME" /
        "MSCTFIME UI" helper windows ride along with the thread's active window.
        """
        out = []
        hwnd = self.u32.GetTopWindow(None)
        while hwnd and hwnd != target:
            if self.u32.IsWindowVisible(ctypes.c_void_p(hwnd)):
                out.append(hwnd)
            hwnd = self.u32.GetWindow(ctypes.c_void_p(hwnd), GW_HWNDNEXT)
        return out

    def test_the_privileged_window_stays_above_the_whole_chain(self):
        self.main.force_topmost(self.canvas)           # what the old heartbeat did
        self.assertLess(self._z(self.canvas)[0], self._z(self.island)[0])
        # Only the windows this test owns: the user's real ClassIsland may re-assert
        # itself between the two walks, which is exactly the noise this must ignore.
        others_before = [h for h in self._above(self.island) if h in self.created - set(self.chain)]
        changed, ceiling, _ = self._enforce(privileged={self.island})
        self.assertTrue(changed)
        self.assertEqual(ceiling, self.island)
        island_z, tool_z, canvas_z = self._z(self.island, self.tool, self.canvas)
        self.assertLess(island_z, tool_z, "ClassIsland 被我们的浮窗压住了")
        self.assertLess(island_z, canvas_z, "ClassIsland 被画布压住了")
        self._assert_chain_order()
        others_after = [h for h in self._above(self.island) if h in self.created - set(self.chain)]
        self.assertEqual(others_after, others_before, "重排动了 ClassIsland 自己（或它上面别人的）窗口")

    def test_a_floater_between_classisland_and_the_canvas_is_pushed_below(self):
        self.main.force_topmost(self.foreign)
        self.main.force_topmost(self.island)           # band: island, foreign, ..., canvas
        changed, _, _ = self._enforce(privileged={self.island})
        self.assertTrue(changed)
        island_z, tool_z, canvas_z, foreign_z = self._z(self.island, self.tool, self.canvas, self.foreign)
        self.assertLess(island_z, tool_z)
        self.assertLess(canvas_z, foreign_z, "悬浮窗仍插在 ClassIsland 和画布之间")

    def test_a_floater_above_classisland_is_not_our_fight(self):
        """Covering it would mean climbing over ClassIsland. Leave both alone."""
        self._enforce(privileged={self.island})       # settle into the right order first
        self.main.force_topmost(self.island)
        self.main.force_topmost(self.foreign)          # band: foreign, island, chain
        changed, _, _ = self._enforce(privileged={self.island})
        self.assertFalse(changed, "为了压一个在 ClassIsland 之上的悬浮窗去重排，会越过 ClassIsland")
        self.assertLess(self._z(self.foreign)[0], self._z(self.island)[0])
        self.assertLess(self._z(self.island)[0], self._z(self.tool)[0])

    def test_nothing_is_touched_when_the_order_is_already_right(self):
        changed, _, _ = self._enforce(privileged={self.island})
        self.assertTrue(changed)                       # first pass may legitimately fix things
        calls = []
        original = self.main.apply_topmost_order
        self.main.apply_topmost_order = lambda chain, ceiling: calls.append((list(chain), ceiling))
        try:
            for _ in range(3):
                changed, _, _ = self._enforce(privileged={self.island})
                self.assertFalse(changed)
        finally:
            self.main.apply_topmost_order = original
        self.assertEqual(calls, [], "顺序已经对了还在 SetWindowPos：白板模式下这就是每 500ms 闪一次")

    def test_a_disordered_chain_is_repaired(self):
        """Qt may reset GWLP_HWNDPARENT on show(); without the owner link a click can
        re-stack the main panel over the text panel. The audit must notice and repair."""
        self._enforce()
        self.main.set_window_owner(self.tool, self.canvas)   # owner link to the panel lost
        self.main.force_topmost(self.panel)                  # a click raised the panel
        self.assertLess(self._z(self.panel)[0], self._z(self.tool)[0])
        changed, _, _ = self._enforce()
        self.assertTrue(changed, "链序错了却没有重排")
        self._assert_chain_order()

    def test_a_window_that_cannot_be_beaten_is_remembered(self):
        """UIAccess windows (touch keyboard, magnifier) live in a band we cannot reach.

        Simulated by making the rewrite a no-op: the floater stays on top after our
        attempt, so it must be recorded and ignored -- not fought again every heartbeat.
        """
        self.main.force_topmost(self.foreign)
        original = self.main.apply_topmost_order
        self.main.apply_topmost_order = lambda chain, ceiling: None
        try:
            changed, _, unreachable = self._enforce()
        finally:
            self.main.apply_topmost_order = original
        self.assertTrue(changed)
        self.assertEqual(unreachable, [self.foreign])
        self.assertIn(self.foreign, self.ignore)
        calls = []
        self.main.apply_topmost_order = lambda chain, ceiling: calls.append(1)
        try:
            changed, _, _ = self._enforce()
        finally:
            self.main.apply_topmost_order = original
        self.assertFalse(changed, "压不过的窗口每拍都在重排")
        self.assertEqual(calls, [])

    def test_a_remembered_window_is_forgotten_once_it_drops_below_us(self):
        self.ignore.add(self.foreign)
        self._enforce()                                # foreign is below the canvas here
        self.assertNotIn(self.foreign, self.ignore, "掉到我们下面的窗口仍被记为压不过")
        self.main.force_topmost(self.foreign)          # it comes back: fight again
        changed, _, _ = self._enforce()
        self.assertTrue(changed)
        self.assertLess(self._z(self.canvas)[0], self._z(self.foreign)[0])

    def test_hidden_or_empty_windows_do_not_trigger_a_rewrite(self):
        self._enforce()
        ghost = self._window("zero-size")
        self.main._user32.SetWindowPos(ctypes.c_void_p(ghost), self.main.HWND_TOPMOST, 0, 0, 0, 0,
                                       self.main.SWP_NOMOVE | self.main.SWP_NOACTIVATE)  # 0x0, on top
        self.assertFalse(self.main.window_covers_anything(ghost))
        self.assertIn(ghost, self.main.topmost_band())
        changed, _, _ = self._enforce()
        self.assertFalse(changed, "零面积窗口盖不住任何东西，不该为它重排")

    def test_the_band_walk_stops_at_the_first_non_topmost_window(self):
        plain = self.u32.CreateWindowExW(WS_EX_TOOLWINDOW, "STATIC", "plain", WS_POPUP | WS_VISIBLE,
                                         -3000, -3000, 120, 120, None, None, None, None)
        self.addCleanup(self.u32.DestroyWindow, ctypes.c_void_p(plain))
        band = self.main.topmost_band()
        self.assertNotIn(plain, band)
        for hwnd in self.chain:
            self.assertIn(hwnd, band)

    def test_plan_treats_our_own_extra_windows_as_harmless(self):
        """Tooltips and the settings page are ours but not in the chain; they may sit above."""
        band = [self.island, self.foreign, self.tool, self.panel, self.canvas]
        need, ceiling, foreign = self.main.plan_topmost_order(
            band, self.chain, is_ours=lambda h: h == self.foreign, is_privileged=lambda h: h == self.island)
        self.assertFalse(need)
        self.assertEqual(ceiling, self.island)
        self.assertEqual(foreign, [])

    def test_plan_flags_a_foreign_window_inside_our_zone(self):
        band = [self.island, self.foreign, self.tool, self.panel, self.canvas]
        need, ceiling, foreign = self.main.plan_topmost_order(
            band, self.chain, is_ours=lambda h: False, is_privileged=lambda h: h == self.island)
        self.assertTrue(need)
        self.assertEqual(foreign, [self.foreign])

    def test_plan_wants_the_canvas_below_the_lowest_privileged_window(self):
        second_island = self._window("classisland-notify")
        band = [self.island, self.tool, self.panel, self.canvas, second_island]
        need, ceiling, _ = self.main.plan_topmost_order(
            band, self.chain, is_ours=lambda h: False,
            is_privileged=lambda h: h in (self.island, second_island))
        self.assertTrue(need, "ClassIsland 的第二扇窗在画布之下，没有被要求让位")
        self.assertEqual(ceiling, second_island)

    def test_process_name_lookup_identifies_classisland_by_prefix(self):
        self.assertEqual(self.main.process_image_name(os.getpid()),
                         os.path.basename(sys.executable).lower())
        self.assertFalse(self.main.is_privileged_window(self.canvas))
        self.assertTrue(self.main.is_own_window(self.canvas))
        self.assertTrue("classisland.desktop.exe".startswith(self.main.PRIVILEGED_PROCESS_PREFIXES))
        self.assertTrue("classisland.exe".startswith(self.main.PRIVILEGED_PROCESS_PREFIXES))
        self.assertFalse("explorer.exe".startswith(self.main.PRIVILEGED_PROCESS_PREFIXES))


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
