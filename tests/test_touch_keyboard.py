# SPDX-License-Identifier: GPL-3.0-or-later
"""The on-screen keyboard wrapper.

These tests must not pop a keyboard onto the user's screen, so they exercise the
pure/observational parts, stub the launcher when they need to watch dispatch, and
check that every entry point is total -- a classroom PC may have the tablet input
service disabled by policy, and the app must degrade to "no keyboard" rather than
raise.

The 5.3.2 additions are regression tests for a bug that survived two releases
because nothing here watched *how* the process gets launched: TabTip.exe and
osk.exe both require elevation, so CreateProcess (subprocess.Popen) can never
start them, and ITipInvocation only exists once TabTip is already running. The
combination meant the keyboard button worked or failed depending on whether
something else had started TabTip earlier in the login session -- identical code,
different behaviour after a reboot.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import touch_keyboard


class AvailabilityTests(unittest.TestCase):
    def test_available_returns_a_bool(self):
        self.assertIsInstance(touch_keyboard.available(), bool)

    def test_is_visible_returns_a_bool(self):
        self.assertIsInstance(touch_keyboard.is_visible(), bool)

    def test_has_touch_returns_a_bool(self):
        self.assertIsInstance(touch_keyboard.has_touch(), bool)

    def test_backend_is_none_or_a_known_name(self):
        self.assertIn(touch_keyboard.backend(), (None, "tabtip", "osk"))

    def test_keyboard_rect_is_none_or_a_four_tuple(self):
        rect = touch_keyboard.keyboard_rect()
        if rect is not None:
            self.assertEqual(len(rect), 4)
            for value in rect:
                self.assertIsInstance(value, int)

    def test_hide_is_safe_when_nothing_is_up(self):
        """没弹键盘时调 hide 不能抛异常。"""
        if not touch_keyboard.is_visible():
            self.assertFalse(touch_keyboard.hide())

    def test_paths_are_absolute(self):
        for path in touch_keyboard.TABTIP_PATHS + touch_keyboard.OSK_PATHS:
            self.assertTrue(path[1:3] == ":\\", f"{path} 应是绝对路径")

    def test_osk_is_reachable_from_a_32_bit_process(self):
        """32 位进程看到的 System32 被重定向到 SysWOW64（那里没有 osk.exe）。

        Sysnative 是绕回真 System32 的门；少了它，32 位打包的版本会认为没有键盘。
        """
        self.assertTrue(any("Sysnative" in p for p in touch_keyboard.OSK_PATHS))


class LaunchGuardTests(unittest.TestCase):
    """The keyboard is a system-wide window, so headless runs must not spawn it."""

    def test_offscreen_runs_may_not_launch(self):
        original = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            self.assertFalse(touch_keyboard.launch_allowed())
            self.assertFalse(touch_keyboard.show(),
                             "离屏运行绝不能把键盘弹到用户真实屏幕上")
        finally:
            if original is None:
                os.environ.pop("QT_QPA_PLATFORM", None)
            else:
                os.environ["QT_QPA_PLATFORM"] = original

    def test_the_explicit_override_blocks_launching(self):
        original = os.environ.get("MYSCREENDRAW_NO_KEYBOARD")
        os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
        try:
            self.assertFalse(touch_keyboard.launch_allowed())
        finally:
            if original is None:
                os.environ.pop("MYSCREENDRAW_NO_KEYBOARD", None)
            else:
                os.environ["MYSCREENDRAW_NO_KEYBOARD"] = original


class _LauncherHarness(unittest.TestCase):
    """Stub out the two things that touch the OS: launching and window lookup."""

    def setUp(self):
        self.launched = []
        self.com_calls = []
        self.windows = {}           # (class, title) -> showing?
        self._saved = {name: getattr(touch_keyboard, name) for name in
                       ("_shell_execute", "_invoke_com", "_find", "_showing",
                        "launch_allowed", "_window_rect")}
        touch_keyboard._shell_execute = self._fake_launch
        touch_keyboard._invoke_com = self._fake_com
        touch_keyboard._find = self._fake_find
        touch_keyboard._showing = self._fake_showing
        touch_keyboard.launch_allowed = lambda: True
        touch_keyboard._window_rect = lambda hwnd: (0, 500, 1200, 300)
        self._settle = touch_keyboard.LAUNCH_SETTLE_S
        touch_keyboard.LAUNCH_SETTLE_S = 0.0

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(touch_keyboard, name, value)
        touch_keyboard.LAUNCH_SETTLE_S = self._settle

    # --- fakes ---
    def _fake_launch(self, path):
        self.launched.append(path)
        return True

    def _fake_com(self):
        self.com_calls.append(True)
        return True

    def _fake_find(self, window_class, title=None):
        return 1 if (window_class, title) in self.windows else 0

    def _fake_showing(self, hwnd):
        if not hwnd:
            return False
        return any(self.windows.values())

    def raise_window(self, which):
        if which == "osk":
            self.windows[(touch_keyboard.OSK_WINDOW_CLASS, None)] = True
        else:
            self.windows[(touch_keyboard.TABTIP_CORE_CLASS,
                          touch_keyboard.TABTIP_CORE_TITLE)] = True


class LaunchMechanismTests(_LauncherHarness):
    def test_launching_never_uses_create_process(self):
        """TabTip/osk 都要求提升，CreateProcess 必然 WinError 740。

        这是 5.3.0/5.3.1 那个 bug 的本体：subprocess.Popen 起不来，异常被吞掉。
        """
        # 查语法树而不是文本：模块文档里解释「为什么不能用 subprocess」的那段话
        # 不该算违规，按行过滤注释挡不住多行字符串。
        import ast

        source = Path(touch_keyboard.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        attribute_calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Attribute):
                attribute_calls.add(node.attr)
        self.assertNotIn("subprocess", imported,
                         "不能用 subprocess 起键盘——CreateProcess 无法提升，永远 WinError 740")
        self.assertNotIn("CreateProcessW", attribute_calls)
        self.assertIn("ShellExecuteW", attribute_calls,
                      "必须经 ShellExecuteW 启动，它才会走 UAC 提升那条路")

    def test_a_cold_machine_starts_the_process_before_toggling_com(self):
        """ITipInvocation 只在 TabTip 已经在跑时才注册，所以顺序不能反。"""
        touch_keyboard.show_tabtip()
        self.assertTrue(self.launched, "TabTip 没被启动，COM 就无从注册")
        self.assertTrue(any("TabTip" in p for p in self.launched))

    def test_a_visible_keyboard_is_not_toggled_off(self):
        """Toggle 是切换：对已弹出的键盘再调一次会把它收起来。"""
        self.raise_window("tabtip")
        self.assertTrue(touch_keyboard.show_tabtip())
        self.assertEqual(self.com_calls, [], "键盘已在屏幕上，不该再 toggle")
        self.assertEqual(self.launched, [], "键盘已在屏幕上，不该再启动进程")

    def test_show_falls_back_to_osk_when_tabtip_never_appears(self):
        """没有数字化仪的台式机上 TabTip 报成功却永不出现，必须退到 osk。"""
        touch_keyboard.has_touch = lambda: True
        try:
            result = touch_keyboard.show()
        finally:
            del touch_keyboard.has_touch
        self.assertTrue(result)
        self.assertTrue(any("osk" in p.lower() for p in self.launched),
                        f"未回落到 osk，只启动了 {self.launched}")

    def test_a_desktop_without_touch_reaches_for_osk_first(self):
        saved = touch_keyboard.has_touch
        touch_keyboard.has_touch = lambda: False
        try:
            touch_keyboard.show()
        finally:
            touch_keyboard.has_touch = saved
        self.assertTrue(self.launched)
        self.assertIn("osk", self.launched[0].lower(),
                      "无触摸机器应先试 osk，TabTip 在那里不会出现")

    def test_show_reports_true_once_a_keyboard_is_actually_up(self):
        self.raise_window("osk")
        self.assertTrue(touch_keyboard.show())
        self.assertEqual(self.launched, [], "已经有键盘了，不该再启动")


class VisibilityTests(_LauncherHarness):
    def test_nothing_showing_means_no_backend(self):
        self.assertIsNone(touch_keyboard.backend())
        self.assertFalse(touch_keyboard.is_visible())
        self.assertIsNone(touch_keyboard.keyboard_rect())

    def test_a_showing_window_yields_a_rect(self):
        self.raise_window("osk")
        self.assertEqual(touch_keyboard.backend(), "osk")
        self.assertEqual(touch_keyboard.keyboard_rect(), (0, 500, 1200, 300))

    def test_hide_closes_whatever_is_up(self):
        self.raise_window("osk")
        import ctypes

        posted = []
        saved = ctypes.windll
        try:
            class _U:
                @staticmethod
                def PostMessageW(hwnd, msg, wparam, lparam):
                    posted.append((msg, wparam))
                    return 1

            class _W:
                user32 = _U()

            ctypes.windll = _W()
            self.assertTrue(touch_keyboard.hide())
        finally:
            ctypes.windll = saved
        self.assertIn((touch_keyboard.WM_SYSCOMMAND, touch_keyboard.SC_CLOSE), posted)


class CloakTests(unittest.TestCase):
    """On Win10 1809+ the keyboard is DWM-cloaked rather than hidden when down."""

    def test_a_zero_area_window_is_not_showing(self):
        """IPTip_Main_Window 是个 0x0 的占位窗口，IsWindowVisible 恒为真。

        只看 IsWindowVisible 会把它当成「键盘在屏幕上」，面板的避让逻辑因此从未触发。
        """
        saved_rect = touch_keyboard._window_rect
        saved_cloak = touch_keyboard._is_cloaked
        import ctypes

        saved_windll = ctypes.windll
        try:
            class _U:
                @staticmethod
                def IsWindowVisible(hwnd):
                    return 1

            class _W:
                user32 = _U()

            ctypes.windll = _W()
            touch_keyboard._is_cloaked = lambda hwnd: False
            touch_keyboard._window_rect = lambda hwnd: (0, 0, 0, 0)
            self.assertFalse(touch_keyboard._showing(1))
            touch_keyboard._window_rect = lambda hwnd: (0, 500, 1200, 300)
            self.assertTrue(touch_keyboard._showing(1))
            touch_keyboard._is_cloaked = lambda hwnd: True
            self.assertFalse(touch_keyboard._showing(1),
                             "cloaked 的窗口不占屏幕空间，不算可见")
        finally:
            ctypes.windll = saved_windll
            touch_keyboard._window_rect = saved_rect
            touch_keyboard._is_cloaked = saved_cloak

    def test_the_modern_core_window_is_among_the_candidates(self):
        """真正画键盘的是 TextInputHost 的 CoreWindow，不是那个占位窗口。"""
        self.assertEqual(touch_keyboard.TABTIP_CORE_CLASS, "Windows.UI.Core.CoreWindow")
        self.assertEqual(touch_keyboard.TABTIP_CORE_TITLE, "Microsoft Text Input Application")


class DegradationTests(unittest.TestCase):
    """Every entry point must be total, even with the platform pulled out."""

    def test_show_reports_false_when_unavailable(self):
        saved_tabtip = touch_keyboard.TABTIP_PATHS
        saved_osk = touch_keyboard.OSK_PATHS
        touch_keyboard.TABTIP_PATHS = ()
        touch_keyboard.OSK_PATHS = ()
        try:
            self.assertFalse(touch_keyboard.show(),
                             "找不到任何键盘时应返回 False 而不是抛异常")
        finally:
            touch_keyboard.TABTIP_PATHS = saved_tabtip
            touch_keyboard.OSK_PATHS = saved_osk

    def test_is_visible_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None            # 模拟调用失败
            self.assertFalse(touch_keyboard.is_visible())
        finally:
            ctypes.windll = original

    def test_keyboard_rect_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertIsNone(touch_keyboard.keyboard_rect())
        finally:
            ctypes.windll = original

    def test_hide_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertFalse(touch_keyboard.hide())
        finally:
            ctypes.windll = original

    def test_has_touch_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertFalse(touch_keyboard.has_touch())
        finally:
            ctypes.windll = original

    def test_backend_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertIsNone(touch_keyboard.backend())
        finally:
            ctypes.windll = original

    def test_show_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertIsInstance(touch_keyboard.show(), bool)
        finally:
            ctypes.windll = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
