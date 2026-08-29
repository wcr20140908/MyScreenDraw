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
        # 保留真实的 settle 时间。5.4.0 之前这里被清成 0.0，于是
        # test_show_does_not_block_waiting_for_a_window 把自己要测的那个等待中和掉了，
        # 代码在 UI 线程上睡 0.6 秒它照样通过。要测「不阻塞」，就得让真实时长在场。
        touch_keyboard._forget_toggle()

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(touch_keyboard, name, value)
        touch_keyboard.LAUNCH_SETTLE_S = self._settle
        # 欠着的 toggle 是模块级状态，不清掉会漏进下一个用例。
        touch_keyboard._forget_toggle()

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
        # 5.4.0 起用 ShellExecuteExW 而不是 ShellExecuteW：同样走 UAC 提升那条路，
        # 但它能带回进程句柄，从而记下我们启动的 PID——退出时才知道该关掉谁。
        self.assertIn("ShellExecuteExW", attribute_calls,
                      "必须经 ShellExecuteEx 启动，它才会走 UAC 提升那条路")

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

    def test_tabtip_that_never_appears_is_replaced_only_on_escalation(self):
        """TabTip 报成功却永不出现时要能退到 osk——但那是升级步骤的事，不是 show()。

        5.3.2 在一次 show() 里就连开两个，于是屏幕上先后出现两个键盘。
        """
        saved = touch_keyboard.has_touch
        touch_keyboard.has_touch = lambda: True
        try:
            self.assertTrue(touch_keyboard.show())
            self.assertTrue(any("TabTip" in p for p in self.launched))
            self.assertFalse(any("osk" in p.lower() for p in self.launched),
                             "show() 阶段就启动了备用后端，两个键盘会同时出现")
            self.launched.clear()
            self.assertEqual(touch_keyboard.escalate(tried=("tabtip",)), "osk")
            self.assertTrue(any("osk" in p.lower() for p in self.launched),
                            f"升级后仍未回落到 osk：{self.launched}")
        finally:
            touch_keyboard.has_touch = saved

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


class SingleKeyboardTests(_LauncherHarness):
    """5.3.3: exactly one keyboard, ever.

    The reported symptom was TabTip appearing, vanishing, and osk arriving in its
    place. Cause: show() waited only 0.6s for a backend to draw itself and then
    launched the other one too. A cold-started osk needs about 1.0s, so the cutoff
    sat right at the real launch time -- warm it looked fine, cold two keyboards
    showed up.
    """

    def test_show_does_not_try_the_second_backend(self):
        """换后端是调用方在定时器上做的事，不能在一次 show() 里连开两个。"""
        touch_keyboard.show(prefer="tabtip")
        osk_launches = [p for p in self.launched if "osk" in p.lower()]
        self.assertEqual(osk_launches, [],
                         f"一次 show() 就启动了备用后端：{self.launched}")

    def test_show_does_not_block_waiting_for_a_window(self):
        """show() 不能在 UI 线程上干等键盘画出来。

        这个用例在 5.4.0 里是空的：它走的是 ``prefer="osk"``，而 osk 那条路本来就不等：
        阻塞发生在 show_tabtip() 里。名字对、断言对、测的分支不对，于是代码在文字编辑
        入口上冻 0.6 秒它一路绿灯。要测就必须让 tabtip 的冷启动分支真的执行——
        键盘没在跑（self.windows 为空），进程刚被启动，正是要等 ITipInvocation 的那一刻。
        """
        import time as _time

        touch_keyboard.LAUNCH_SETTLE_S = 5.0    # 若还在等，这里会明显超时
        start = _time.monotonic()
        touch_keyboard.show(prefer="tabtip")
        elapsed = _time.monotonic() - start
        self.assertTrue(any("TabTip" in p for p in self.launched),
                        f"没走到冷启动分支，等待根本没被测到：{self.launched}")
        self.assertLess(elapsed, 1.0, f"show() 在阻塞等待，耗了 {elapsed * 1000:.0f}ms")

    def test_a_cold_launch_leaves_the_toggle_owed_instead_of_waiting(self):
        """冷启动后 COM toggle 是「欠着」的，由调用方的定时器还，不是在这里睡出来。"""
        self.assertTrue(touch_keyboard.show_tabtip())
        self.assertEqual(self.com_calls, [], "进程刚起来，ITipInvocation 还没注册就 toggle 了")
        self.assertTrue(touch_keyboard.toggle_pending(), "toggle 既没发也没欠，键盘不会出现")

    def test_escalate_tries_the_other_backend(self):
        touch_keyboard.escalate(tried=("tabtip",))
        self.assertTrue(any("osk" in p.lower() for p in self.launched),
                        f"升级没有去试 osk：{self.launched}")

    def test_escalate_does_not_retry_what_already_failed(self):
        touch_keyboard.escalate(tried=("tabtip", "osk"))
        self.assertEqual(self.launched, [], "两个都试过了还在重试")

    def test_escalate_is_a_no_op_when_a_keyboard_is_up(self):
        self.raise_window("osk")
        self.assertIsNone(touch_keyboard.escalate(tried=("tabtip",)))
        self.assertEqual(self.launched, [])

    def test_enforce_single_closes_the_other_backend(self):
        import ctypes

        posted = []
        saved = ctypes.windll
        self.raise_window("osk")
        self.raise_window("tabtip")
        try:
            class _U:
                @staticmethod
                def PostMessageW(hwnd, msg, wparam, lparam):
                    posted.append(msg)
                    return 1

            class _W:
                user32 = _U()

            ctypes.windll = _W()
            closed = touch_keyboard.enforce_single("osk")
        finally:
            ctypes.windll = saved
        self.assertEqual(closed, ["tabtip"], "没有收掉另一个键盘")
        self.assertTrue(posted)

    def test_enforce_single_leaves_the_keeper_alone(self):
        import ctypes

        posted = []
        saved = ctypes.windll
        self.raise_window("osk")
        try:
            class _U:
                @staticmethod
                def PostMessageW(hwnd, msg, wparam, lparam):
                    posted.append(msg)
                    return 1

            class _W:
                user32 = _U()

            ctypes.windll = _W()
            closed = touch_keyboard.enforce_single("osk")
        finally:
            ctypes.windll = saved
        self.assertEqual(closed, [], "把要保留的那个也关了")
        self.assertEqual(posted, [])

    def test_a_touch_machine_prefers_tabtip(self):
        saved = touch_keyboard.has_touch
        touch_keyboard.has_touch = lambda: True
        try:
            self.assertEqual(touch_keyboard.preferred_backend(), "tabtip")
        finally:
            touch_keyboard.has_touch = saved

    def test_a_desktop_prefers_osk(self):
        """无数字化仪时 TabTip 永远不会出现，先等它就是纯粹的延迟。"""
        saved = touch_keyboard.has_touch
        touch_keyboard.has_touch = lambda: False
        try:
            self.assertEqual(touch_keyboard.preferred_backend(), "osk")
        finally:
            touch_keyboard.has_touch = saved


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

    def test_shutdown_survives_a_broken_win32_call(self):
        """退出路径上抛异常会把干净退出变成崩溃。"""
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            closed, terminated = touch_keyboard.shutdown()
            self.assertEqual((closed, terminated), ([], []))
        finally:
            ctypes.windll = original


class ShutdownTests(unittest.TestCase):
    """5.4.0 request: "关闭软件后，无论是tabtip还是osk键盘，都应该顺带完成关闭".

    Closing the window is not enough. TabTip normally answers SC_CLOSE by re-cloaking
    itself and keeps running, so the user is left with a keyboard that pops back up on
    the next text field, with our app gone and nothing to dismiss it. And before this
    release nothing called any teardown at all: F12 goes exit_requested ->
    QApplication.quit, and main.py has no closeEvent.
    """

    def setUp(self):
        self.closed = []
        self.alive = set()
        self.killed = []
        self._saved = {name: getattr(touch_keyboard, name) for name in
                       ("_close_all_windows", "_process_alive", "_terminate")}
        self._grace = touch_keyboard.SHUTDOWN_GRACE_S
        touch_keyboard.SHUTDOWN_GRACE_S = 0.0
        touch_keyboard._close_all_windows = self._fake_close
        touch_keyboard._process_alive = lambda pid: pid in self.alive
        touch_keyboard._terminate = self._fake_terminate
        self._pids = set(touch_keyboard._OUR_PIDS)
        touch_keyboard._OUR_PIDS.clear()

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(touch_keyboard, name, value)
        touch_keyboard.SHUTDOWN_GRACE_S = self._grace
        touch_keyboard._OUR_PIDS.clear()
        touch_keyboard._OUR_PIDS.update(self._pids)

    def _fake_close(self):
        self.closed.append(True)
        return ["tabtip"]

    def _fake_terminate(self, pid):
        self.killed.append(pid)
        self.alive.discard(pid)
        return True

    def test_shutdown_closes_the_windows(self):
        touch_keyboard.shutdown()
        self.assertTrue(self.closed, "退出时没有关闭键盘窗口")

    def test_a_keyboard_that_ignores_the_close_is_terminated(self):
        """TabTip 对 SC_CLOSE 通常只是重新 cloak，进程还在跑。"""
        touch_keyboard._OUR_PIDS.add(4321)
        self.alive.add(4321)
        _closed, terminated = touch_keyboard.shutdown()
        self.assertEqual(self.killed, [4321])
        self.assertEqual(terminated, [4321])

    def test_a_keyboard_that_exits_on_its_own_is_not_terminated(self):
        touch_keyboard._OUR_PIDS.add(4321)      # 不在 alive 里＝已经自己退了
        _closed, terminated = touch_keyboard.shutdown()
        self.assertEqual(self.killed, [])
        self.assertEqual(terminated, [])

    def test_a_keyboard_we_did_not_start_is_left_alone(self):
        """用户自己开着的键盘不是我们的，杀掉它比留着更糟。"""
        self.alive.add(9999)                    # 活着，但不是我们启动的
        touch_keyboard.shutdown()
        self.assertEqual(self.killed, [])

    def test_shutdown_forgets_the_pids_afterwards(self):
        """留着已处理的 PID，下一次 shutdown 就会去杀一个被系统复用的 PID。"""
        touch_keyboard._OUR_PIDS.add(4321)
        self.alive.add(4321)
        touch_keyboard.shutdown()
        self.assertEqual(touch_keyboard.launched_pids(), set())

    def test_shutdown_is_safe_with_nothing_launched(self):
        closed, terminated = touch_keyboard.shutdown()
        self.assertEqual(terminated, [])
        self.assertIsInstance(closed, list)

    def test_shutdown_clears_the_pids_even_if_closing_raises(self):
        touch_keyboard._close_all_windows = lambda: (_ for _ in ()).throw(OSError("boom"))
        touch_keyboard._OUR_PIDS.add(4321)
        touch_keyboard.shutdown()
        self.assertEqual(touch_keyboard.launched_pids(), set())

    def test_launched_pids_is_a_copy(self):
        touch_keyboard._OUR_PIDS.add(7)
        touch_keyboard.launched_pids().clear()
        self.assertIn(7, touch_keyboard._OUR_PIDS)


class ShutdownWindowScopeTests(_LauncherHarness):
    """Which windows shutdown targets, versus which hide() targets."""

    def setUp(self):
        super().setUp()
        self.posted = []
        import ctypes

        self._user32 = ctypes.windll.user32.PostMessageW
        ctypes.windll.user32.PostMessageW = lambda *a: self.posted.append(a) or 1

    def tearDown(self):
        import ctypes

        ctypes.windll.user32.PostMessageW = self._user32
        super().tearDown()

    def test_a_cloaked_keyboard_is_still_closed_on_shutdown(self):
        """hide() 跳过 not showing 的窗口——被 cloak 的 TabTip 正是这样躲过关闭的。"""
        self.windows[(touch_keyboard.TABTIP_CORE_CLASS,
                      touch_keyboard.TABTIP_CORE_TITLE)] = False    # 存在但被 cloak
        self.assertEqual(touch_keyboard.hide(), False,
                         "这个用例假设 hide() 会跳过被 cloak 的窗口")
        self.assertTrue(touch_keyboard._close_all_windows(),
                        "shutdown 必须连被 cloak 的窗口一起关")


class OwedToggleTests(_LauncherHarness):
    """5.4.1: settle 时间是「欠着的」而不是「睡出来的」。

    5.4.0 在 show_tabtip() 里用 time.sleep 轮询等 TabTip 注册 ITipInvocation，位置是
    UI 线程、文字编辑入口内，于是每次进入编辑都冻住最多 LAUNCH_SETTLE_S。现在改成记一个
    单调截止时间，由调用方本来就有的定时器调 pump() 来还。

    这样做多出三条必须堵上的失败路径，每条都对应一个用例：面板已经关了（补上就等于
    自己把键盘弹到没有输入框的界面上）、升级去了 osk（不清就是 5.3.3 的两个键盘）、
    以及程序退出。
    """

    def test_pump_is_a_cheap_no_op_when_nothing_is_owed(self):
        """它挂在 150ms 的定时器上，空转必须不碰 COM。"""
        self.assertFalse(touch_keyboard.pump())
        self.assertEqual(self.com_calls, [])

    def test_pump_issues_the_toggle_once_the_process_is_up(self):
        touch_keyboard.show_tabtip()
        self.assertEqual(self.com_calls, [])
        # 进程起来了：窗口类找得到，但还没显示出来。
        self.windows[(touch_keyboard.TABTIP_CORE_CLASS,
                      touch_keyboard.TABTIP_CORE_TITLE)] = False
        self.assertTrue(touch_keyboard.pump(), "进程已就绪，pump 却没把欠的 toggle 发出去")
        self.assertEqual(len(self.com_calls), 1)

    def test_the_toggle_is_issued_only_once(self):
        touch_keyboard.show_tabtip()
        self.windows[(touch_keyboard.TABTIP_CORE_CLASS,
                      touch_keyboard.TABTIP_CORE_TITLE)] = False
        touch_keyboard.pump()
        self.assertFalse(touch_keyboard.pump(), "同一笔欠账被还了两次，第二次会把键盘收起来")
        self.assertEqual(len(self.com_calls), 1)
        self.assertFalse(touch_keyboard.toggle_pending())

    def test_pump_waits_for_the_process_but_not_past_the_deadline(self):
        """进程一直起不来也不能永远欠着：到点就试一次，失败可恢复，永欠不可。"""
        touch_keyboard.LAUNCH_SETTLE_S = 5.0
        touch_keyboard.show_tabtip()
        self.assertFalse(touch_keyboard.pump(), "进程还没起来就 toggle，ITipInvocation 还没注册")
        touch_keyboard.LAUNCH_SETTLE_S = 0.0
        touch_keyboard._owe_toggle()            # 截止时间就是现在
        self.assertTrue(touch_keyboard.pump(), "到了截止时间还在等，键盘永远不会出现")

    def test_a_keyboard_that_arrived_on_its_own_cancels_the_toggle(self):
        """toggle 是切换：键盘已经在屏幕上时再发一次等于把它收起来。"""
        touch_keyboard.show_tabtip()
        self.raise_window("tabtip")
        self.assertFalse(touch_keyboard.pump(), "键盘已经出来了还 toggle，等于自己把它关掉")
        self.assertEqual(self.com_calls, [])
        self.assertFalse(touch_keyboard.toggle_pending())

    def test_cancel_pending_drops_the_toggle_without_touching_windows(self):
        """面板关了就得撤销欠账，否则键盘会自己弹到一个没有输入框的界面上。"""
        touch_keyboard.show_tabtip()
        self.assertTrue(touch_keyboard.cancel_pending())
        self.assertFalse(touch_keyboard.pump())
        self.assertEqual(self.com_calls, [], "撤销后仍然发了 toggle")

    def test_hide_drops_an_owed_toggle(self):
        """收起键盘后欠账不能存活，否则它稍后触发又把键盘放回屏幕。"""
        touch_keyboard.show_tabtip()
        touch_keyboard.hide()
        self.assertFalse(touch_keyboard.toggle_pending())
        self.assertFalse(touch_keyboard.pump())
        self.assertEqual(self.com_calls, [])

    def test_escalating_to_osk_drops_the_toggle_owed_to_tabtip(self):
        """5.3.3 的两个键盘会以另一种方式回来：欠给 TabTip 的 toggle 在 osk 起来后触发。"""
        touch_keyboard.show_tabtip()
        self.assertTrue(touch_keyboard.toggle_pending())
        self.assertEqual(touch_keyboard.escalate(tried=("tabtip",)), "osk")
        self.assertFalse(touch_keyboard.toggle_pending(),
                         "已经换到 osk 了还欠着 TabTip 的 toggle，两个键盘会同时出现")

    def test_shutdown_drops_an_owed_toggle(self):
        touch_keyboard.show_tabtip()
        touch_keyboard.shutdown()
        self.assertFalse(touch_keyboard.toggle_pending())

    def test_no_blocking_sleep_remains_in_the_launch_path(self):
        """按语法树查：启动路径上不能再有 sleep。

        LAUNCH_SETTLE_S 现在只该被 _owe_toggle 当算术用。shutdown() 里那个 sleep 是
        拆卸时的宽限轮询，不在 UI 交互路径上，所以按函数名白名单放过。
        """
        import ast

        source = Path(touch_keyboard.__file__).read_text(encoding="utf-8")
        allowed = {"shutdown", "_terminate"}
        offenders = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef) or node.name in allowed:
                continue
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "sleep"):
                    offenders.append(f"{node.name}():{inner.lineno}")
        self.assertEqual(offenders, [],
                         f"启动路径上还有阻塞睡眠，文字编辑入口会被冻住：{offenders}")


class ExitWiringTests(unittest.TestCase):
    """shutdown() 得真的被退出路径调用。5.3.x 这个函数就算存在也没人调。"""

    def test_shutdown_is_wired_to_about_to_quit(self):
        """挂 aboutToQuit 而不是 closeEvent：F12 那条路（exit_requested →
        QApplication.quit）根本不经过任何窗口的 closeEvent，而 main.py 里也没有
        closeEvent。aboutToQuit 是所有退出路径唯一的共同出口。"""
        import ast

        source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wired = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "connect"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "aboutToQuit"):
                if "shutdown" in ast.dump(node):
                    wired = True
        self.assertTrue(wired, "退出时没有调用 touch_keyboard.shutdown()，键盘会留在桌面上")


if __name__ == "__main__":
    unittest.main(verbosity=2)
