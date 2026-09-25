"""v5.5.0 的设置页、图标 UI、透明度、圆角、自启与检查更新。

这些测试盯的是几个具体踩过的坑，不是泛泛的「功能能跑」：

1. **祖先可见性**。图标模式下 ``main_frame`` 整个隐藏，其子控件的 ``isVisible()``
   恒为 False。第一版 ``sync_icon_buttons`` 用 ``isVisible()`` 投影白板栏显隐，
   结果图标模式下进白板永远看不到翻页栏。正确的读法是 ``isHidden()``。
2. **画布不能跟着淡**。``setWindowOpacity`` 作用到 ``DrawingCanvas`` 上会把用户
   画的墨迹一起淡掉——那不是界面半透明，那是墨水变淡。
3. **checkable 按钮的双入口**。智能识别图形在批注子面板和设置页各有一颗按钮，
   前者是 checkable 的；只改文案不改 checked 会让它下一次点击「没反应」。
4. **透明度下限**。允许调到 0 意味着用户能把面板调成完全看不见，又因为看不见
   而找不到设置页调回来——不可逆自锁。
5. **自启的真相在注册表**，不在配置文件里；两处都存就会出现「该信谁」。
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
    panel.apply_theme()
    panel.update_whiteboard_ui()
    panel.update_history_ui()
    return app, main, panel, canvas


class _PanelCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app, cls.main, cls.panel, cls.canvas = _build_panel()
        except Exception as exc:  # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")

    @classmethod
    def tearDownClass(cls):
        panel = getattr(cls, "panel", None)
        for stopper in (getattr(panel, "listener", None),
                        getattr(panel, "timer", None),
                        getattr(panel, "autosave_timer", None)):
            try:
                stopper.stop()
            except Exception:
                pass

    def setUp(self):
        # 每个用例从不透明、默认圆角开始，避免用例间互相污染
        self.panel.set_ui_opacity(100, persist=False)
        self.panel.set_ui_radius(self.panel.RADIUS_DEFAULT, persist=False)
        if self.canvas.whiteboard_mode:
            self.panel.toggle_whiteboard()


class SettingsPanelTests(_PanelCase):
    def test_panel_builds_and_owns_the_theme_button(self):
        self.panel.open_settings_panel()
        self.assertIsNotNone(self.panel.settings_panel)
        # 主题按钮从主栏搬进了设置页；它仍然是同一颗按钮，只是换了父级
        self.assertIs(self.panel.btn_theme.window(), self.panel.settings_panel)
        in_toolbar = [self.panel.toolbar_layout.itemAt(i).widget()
                      for i in range(self.panel.toolbar_layout.count())]
        self.assertNotIn(self.panel.btn_theme, in_toolbar)

    def test_opening_twice_reuses_one_panel(self):
        self.panel.open_settings_panel()
        first = self.panel.settings_panel
        self.panel.open_settings_panel()
        self.assertIs(self.panel.settings_panel, first)

    def test_settings_panel_reflects_live_state_not_its_own_copy(self):
        self.panel.open_settings_panel()
        self.panel.set_ui_radius(19, persist=False)
        self.panel.set_ui_opacity(64, persist=False)
        self.assertEqual(self.panel.ui_radius_slider.value(), 19)
        self.assertEqual(self.panel.ui_opacity_slider.value(), 64)
        self.assertIn("19", self.panel.radius_value_label.text())
        self.assertIn("64", self.panel.opacity_value_label.text())

    def test_orientation_buttons_highlight_the_active_one(self):
        self.panel.open_settings_panel()
        self.panel._set_orientation_from_settings("landscape")
        self.assertEqual(self.panel.orientation, "landscape")
        self.assertEqual(self.panel.btn_orient_landscape.objectName(), "ActiveTool")
        self.assertEqual(self.panel.btn_orient_portrait.objectName(), "")
        self.panel._set_orientation_from_settings("portrait")
        self.assertEqual(self.panel.btn_orient_portrait.objectName(), "ActiveTool")
        self.assertEqual(self.panel.btn_orient_landscape.objectName(), "")


class OpacityTests(_PanelCase):
    def test_canvas_is_never_faded(self):
        """墨迹载体必须排除在透明度之外。"""
        self.panel.set_ui_opacity(40, persist=False)
        self.assertNotIn(self.canvas, self.panel.opacity_targets())
        self.assertAlmostEqual(self.canvas.windowOpacity(), 1.0, places=3)
        self.assertAlmostEqual(self.panel.windowOpacity(), 0.40, places=2)

    def test_floor_prevents_an_invisible_panel(self):
        self.panel.set_ui_opacity(0, persist=False)
        self.assertEqual(self.panel.ui_opacity, self.panel.OPACITY_MIN)
        self.assertGreaterEqual(self.panel.OPACITY_MIN, 20,
                                "下限太低，用户会把面板调到看不见又找不回来")
        self.assertGreater(self.panel.windowOpacity(), 0.0)

    def test_ceiling_is_fully_opaque(self):
        self.panel.set_ui_opacity(400, persist=False)
        self.assertEqual(self.panel.ui_opacity, self.panel.OPACITY_MAX)
        self.assertAlmostEqual(self.panel.windowOpacity(), 1.0, places=3)

    def test_hidden_panels_are_included(self):
        """隐藏的浮窗也要设：否则它下次显示出来是不透明的，跟其余界面不一致。"""
        self.panel.open_settings_panel()
        self.panel.settings_panel.hide()
        self.panel.set_ui_opacity(55, persist=False)
        self.assertIn(self.panel.settings_panel, self.panel.opacity_targets())
        self.assertAlmostEqual(self.panel.settings_panel.windowOpacity(), 0.55, places=2)

    def test_heartbeat_does_not_thrash_the_value(self):
        """Qt 把 alpha 量化成 8bit，读回有误差；比较不做取整会导致每次心跳都重设。"""
        self.panel.set_ui_opacity(73, persist=False)
        before = self.panel.windowOpacity()
        for _ in range(5):
            self.panel.apply_window_opacity()
        self.assertAlmostEqual(self.panel.windowOpacity(), before, places=6)


class RadiusTests(_PanelCase):
    def test_default_matches_the_pre_5_5_hardcoded_value(self):
        """默认必须仍是 12，否则老用户升级后界面莫名变形。"""
        self.assertEqual(self.panel.RADIUS_DEFAULT, 12)

    def test_radius_reaches_the_stylesheet(self):
        for value in (0, 7, 24):
            self.panel.set_ui_radius(value, persist=False)
            token = self.panel.radius_tokens()["frame"]
            self.assertEqual(token, value)
            self.assertIn(f"border-radius: {token}px", self.panel.styleSheet())

    def test_radius_is_clamped(self):
        self.panel.set_ui_radius(9999, persist=False)
        self.assertEqual(self.panel.ui_radius, self.panel.RADIUS_MAX)
        self.panel.set_ui_radius(-9999, persist=False)
        self.assertEqual(self.panel.ui_radius, self.panel.RADIUS_MIN)

    def test_zero_radius_leaves_no_rounded_leftovers(self):
        """圆角调到 0 时不能有硬编码的残留值，否则界面一半方一半圆。"""
        self.panel.set_ui_radius(0, persist=False)
        tokens = self.panel.radius_tokens()
        for name, value in tokens.items():
            if name == "handle":
                continue          # 滑块把手是圆的，与外框圆角无关
            self.assertEqual(value, 0, f"{name} 在圆角为 0 时仍是 {value}")


class SmartShapesDualEntryTests(_PanelCase):
    def test_multitouch_and_speed_width_have_ui_entries(self):
        self.panel.open_settings_panel()
        for toggle, attr in ((self.panel.toggle_multitouch, "smart_multitouch_enabled"),
                             (self.panel.toggle_speed_width, "speed_width_enabled")):
            start = getattr(self.canvas, attr)
            toggle()
            self.assertEqual(getattr(self.canvas, attr), not start)
            toggle()
            self.assertEqual(getattr(self.canvas, attr), start)


class PersistenceTests(_PanelCase):
    def test_new_keys_round_trip(self):
        self.panel.set_ui_radius(21, persist=False)
        self.panel.set_ui_opacity(58, persist=False)
        self.panel.update_check_enabled = True
        settings = self.panel.collect_settings()
        self.assertEqual(settings["ui_radius"], 21)
        self.assertEqual(settings["ui_opacity"], 58)
        self.assertIs(settings["update_check_enabled"], True)

    def test_theme_round_trips(self):
        before = self.panel.theme_name
        self.panel.toggle_theme()
        self.assertNotEqual(self.panel.theme_name, before)
        self.assertEqual(self.panel.collect_settings()["theme"], self.panel.theme_name)
        self.panel.toggle_theme()

    def test_autostart_is_not_stored_in_the_config_file(self):
        """注册表是自启的唯一真相；配置里再存一份就会出现「该信谁」。"""
        settings = self.panel.collect_settings()
        for key in settings:
            self.assertNotIn("autostart", key)

    def test_garbage_values_are_rejected(self):
        """配置文件可能被手改坏；坏值应当被忽略而不是让程序带着坏状态跑。

        走真实的 load_settings()，不走「我以为它长这样」的替身。用完把配置文件还原，
        测试不该改掉用户的真实配置。
        """
        import json
        import shutil

        config = Path(self.main.CONFIG_FILE)
        backup = config.with_suffix(".test-backup")
        had_config = config.exists()
        if had_config:
            shutil.copy2(config, backup)
        try:
            self.panel.set_ui_radius(10, persist=False)
            self.panel.set_ui_opacity(90, persist=False)
            baseline = {"ui_radius": self.panel.ui_radius,
                        "ui_opacity": self.panel.ui_opacity}
            for bad in ({"ui_radius": "big"}, {"ui_radius": None},
                        {"ui_opacity": None}, {"ui_opacity": "half"},
                        {"ui_opacity": True}):     # True 是 int 的子类，必须挡住
                key = next(iter(bad))
                merged = dict(self.panel.collect_settings())
                merged.update(bad)
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
                self.panel.load_settings()
                self.assertEqual(getattr(self.panel, key), baseline[key],
                                 f"坏值 {bad} 被接受了")
        finally:
            if had_config:
                shutil.move(str(backup), str(config))
            elif config.exists():
                config.unlink()


class AutostartTests(unittest.TestCase):
    """只读注册表，不写。写注册表的路径留给实屏验证。"""

    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def test_command_is_quoted(self):
        command = self.main.autostart_command()
        self.assertTrue(command.startswith('"'),
                        "路径不加引号时，装在 Program Files 下会静默失效")
        self.assertIn('"', command[1:])

    def test_source_run_uses_pythonw(self):
        """python.exe 会在开机时挂一个黑控制台窗口，用户以为中了病毒。"""
        if getattr(sys, "frozen", False):
            self.skipTest("frozen build points at the exe")
        command = self.main.autostart_command()
        self.assertIn("pythonw", command.lower())

    def test_frozen_command_is_quoted_too(self):
        """打包版走的是另一条分支，而用户拿到的正是打包版。

        测试永远在源码模式下跑，autostart_command 的 frozen 分支平时一次都不会
        被执行到。变异测试里把 frozen 分支的引号去掉，全套测试依然是绿的——所以
        这里假装自己是打包版，把那条分支也钉住。装在 Program Files 下时，不加
        引号 Windows 会把路径按空格拆成两个参数，自启静默失效。
        """
        had = hasattr(sys, "frozen")
        previous = getattr(sys, "frozen", None)
        sys.frozen = True
        try:
            command = self.main.autostart_command()
        finally:
            if had:
                sys.frozen = previous
            else:
                del sys.frozen
        self.assertTrue(command.startswith('"'), "打包版的自启路径没加引号")
        self.assertTrue(command.rstrip().endswith('"'), "打包版的自启路径右引号缺失")

    def test_only_touches_the_current_user(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        start = source.index("AUTOSTART_ROOT")
        block = source[start:source.index("UPDATE_API_URL", start)]
        self.assertNotIn("HKEY_LOCAL_MACHINE", block,
                         "写 HKLM 需要管理员权限，还会给所有账户装上自启")
        self.assertIn("HKEY_CURRENT_USER", block)

    def test_reading_state_never_raises(self):
        self.assertIsInstance(self.main.autostart_enabled(), bool)
        self.assertIsInstance(self.main.autostart_stored_command(), str)

    def test_heal_is_a_noop_when_disabled(self):
        if self.main.autostart_enabled():
            self.skipTest("autostart is on for this account")
        self.assertFalse(self.main.heal_autostart())


class UpdateCheckTests(_PanelCase):
    def setUp(self):
        super().setUp()
        self.panel._updates_stopping = False

    def test_default_check_only_notifies(self):
        from unittest.mock import patch
        with patch.object(self.panel, '_offer_update_page') as offer:
            self.panel._on_update_result({'tag': 'v99.0.0'}, None)
            offer.assert_not_called()
            self.assertEqual(self.panel._pending_update_release['tag'], 'v99.0.0')

    def test_no_request_while_disabled(self):
        """关着的时候，check_for_updates 必须在建线程之前就掉头。

        只断言「fetch 没被调用」是有竞态的：worker 是另一条线程，守卫被拿掉时
        它可能还没跑到 fetch，断言就凑巧过了，然后线程在测试拆完补丁之后才发出
        真实网络请求。所以这里断言的是「worker 根本没被建出来」——那是同步可见的。
        """
        calls = []
        original = self.main.fetch_latest_version
        self.main.fetch_latest_version = lambda *a, **k: (calls.append(1), (None, "x"))[1]
        self.panel.open_settings_panel()
        self.panel._update_worker = None
        try:
            self.panel.update_check_enabled = False
            self.panel.sync_settings_panel()
            self.panel.check_for_updates()
            self.assertIsNone(self.panel._update_worker, "关着的时候不该建检查线程")
            self.assertNotEqual(self.panel.update_status_label.text(),
                                self.main.tr("update_checking"),
                                "关着的时候不该进入「正在检查」")
            self.assertEqual(calls, [], "关着的时候不该发请求")
            self.assertFalse(self.panel.btn_check_update.isEnabled())
        finally:
            self.panel.stop_update_worker()
            self.main.fetch_latest_version = original
            self.panel.settings_panel.hide()

    def test_manual_download_is_separate_from_check(self):
        from unittest.mock import patch
        with patch.object(self.panel, '_offer_update_page') as offer:
            self.panel._on_update_result({'tag': 'v99.0.0'}, None)
            offer.assert_not_called()
            self.panel.download_pending_update()
            offer.assert_called_once_with({'tag': 'v99.0.0'})

    def test_version_parsing(self):
        parse = self.main.parse_version
        self.assertEqual(parse("v5.5.0"), (5, 5, 0, 2, 0))
        self.assertEqual(parse("5.5.0"), (5, 5, 0, 2, 0))
        self.assertIsNone(parse("nonsense"))
        self.assertIsNone(parse(None))
        self.assertGreater(parse("v5.6.0"), parse("v5.5.0"))
        self.assertGreater(parse("v5.10.0"), parse("v5.9.0"),
                           "字符串比较会把 5.10 判成小于 5.9")

    def test_newer_version_offers_the_page_but_downloads_nothing(self):
        offered = []
        original = self.panel._offer_update_page
        self.panel._offer_update_page = lambda tag: offered.append(tag)
        try:
            self.panel.open_settings_panel()
            self.panel._on_update_result("v99.0.0", None)
            self.assertEqual(offered, [])
            self.assertIn("99.0.0", self.panel.update_status_label.text())
            self.panel._on_update_result("v0.0.1", None)
            self.assertEqual(offered, [], "旧版本不该弹框")
            self.assertEqual(self.panel.update_status_label.text(),
                             self.main.tr("update_current"))
        finally:
            self.panel._offer_update_page = original

    def test_failure_is_reported_not_swallowed(self):
        self.panel.open_settings_panel()
        self.panel._on_update_result(None, "timed out")
        self.assertIn("timed out", self.panel.update_status_label.text())

    def _http_error(self, code, remaining):
        """造一个 urllib 的 HTTPError，headers 里带（或不带）限流余量。"""
        import urllib.error
        from email.message import Message
        headers = Message()
        if remaining is not None:
            headers["X-RateLimit-Remaining"] = remaining
        return urllib.error.HTTPError("https://example.invalid", code,
                                      "Forbidden", headers, None)

    def _fetch_raising(self, exc):
        """让 urlopen 抛出指定异常，其余照原样走 fetch_latest_version。"""
        import urllib.request

        class _Ctx:
            def __enter__(self_inner):
                raise exc
            def __exit__(self_inner, *a):
                return False

        original = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: _Ctx()
        try:
            return self.main.fetch_latest_version(url="https://example.invalid/x")
        finally:
            urllib.request.urlopen = original

    def test_rate_limit_is_told_apart_from_a_real_failure(self):
        """403 + X-RateLimit-Remaining: 0 是限流，不是「检查失败」。

        这条是在打包好的 exe 上实测时撞出来的：GitHub 未认证接口每 IP 每小时 60 次，
        而本程序的场景是一间教室几十台机器共用一个出口 IP，配额按出口 IP 算，所以撞
        限流是常态。原来的代码把它报成「检查失败：http_403」——用户既看不懂，也会
        以为是自己网络坏了而去翻网络设置，而实际上什么都不用改，等一会儿就行。
        """
        for code in (403, 429):
            tag, error = self._fetch_raising(self._http_error(code, "0"))
            self.assertIsNone(tag)
            self.assertEqual(error, "rate_limited", f"{code} + 余量0 应判为限流")

    def test_a_real_403_is_not_disguised_as_rate_limiting(self):
        """余量没耗尽的 403 是真的被拒，不能报成「过会儿再试」——等下去不会好。"""
        tag, error = self._fetch_raising(self._http_error(403, "57"))
        self.assertIsNone(tag)
        self.assertEqual(error, "http_403")

    def test_other_http_errors_keep_their_code(self):
        tag, error = self._fetch_raising(self._http_error(500, None))
        self.assertIsNone(tag)
        self.assertEqual(error, "http_500")

    def test_rate_limit_message_says_wait_not_failed(self):
        """界面上给的话必须是「过会儿再试」，不能是「检查失败」。"""
        self.panel.open_settings_panel()
        self.panel._on_update_result(None, "rate_limited")
        shown = self.panel.update_status_label.text()
        self.assertEqual(shown, self.main.tr("update_rate_limited"))
        self.assertNotIn("rate_limited", shown, "不该把内部错误码抛给用户")
        self.assertNotEqual(shown, self.main.trf("update_failed", detail="rate_limited"))

    def test_rate_limit_message_exists_in_every_language(self):
        import i18n
        entry = i18n._BASE["update_rate_limited"]
        self.assertEqual(len(entry), len(i18n._LANGS))
        for index, text in enumerate(entry):
            self.assertTrue(text.strip(), f"第 {index} 种语言缺文案")
            self.assertNotIn("{", text, "这句不需要占位符")

    def test_check_does_not_download_or_execute(self):
        from unittest.mock import patch
        with patch.object(self.main, 'UpdateDownloadWorker') as download, \
                patch.object(self.main.subprocess, 'Popen') as launch:
            self.panel._on_update_result({'tag': 'v99.0.0', 'download_url': 'https://example.invalid/u.zip'}, None)
            download.assert_not_called()
            launch.assert_not_called()

    def test_worker_runs_off_the_ui_thread(self):
        from PyQt6.QtCore import QThread
        self.assertTrue(issubclass(self.main.UpdateCheckWorker, QThread),
                        "6 秒超时放在 UI 线程上会把界面卡死")

    def test_the_request_really_leaves_the_ui_thread(self):
        """继承 QThread 还不够：把 start() 写成 run() 也照样卡死 UI。

        上一个用例只看类型，只有真跑一次才知道请求落在哪条线程上。
        """
        from PyQt6.QtCore import QThread

        ui_thread = QThread.currentThread()
        seen = []
        original = self.main.fetch_release
        self.main.fetch_release = lambda *a, **k: (
            seen.append(QThread.currentThread()), ({"tag": "v0.0.1", "download_url": "https://example.invalid/update.zip"}, None))[1]
        self.panel.open_settings_panel()
        was_enabled = self.panel.update_check_enabled
        self.panel.update_check_enabled = True
        try:
            self.panel.check_for_updates()
            worker = self.panel._update_worker
            self.assertIsNotNone(worker, "worker 没建起来")
            self.assertTrue(worker.wait(5000), "worker 5 秒没跑完")
            self.app.processEvents()          # 把跨线程信号派发到主线程
            self.assertEqual(len(seen), 1, f"请求发了 {len(seen)} 次")
            self.assertIsNot(seen[0], ui_thread, "请求是在 UI 线程上发的，界面会卡住")
            self.assertEqual(self.panel.update_status_label.text(),
                             self.main.tr("update_current"),
                             "比当前版本旧的号应当报「已是最新」")
        finally:
            self.main.fetch_release = original
            self.panel.update_check_enabled = was_enabled
            self.panel.stop_update_worker()
            self.panel.sync_settings_panel()
            self.panel.settings_panel.hide()

    def test_install_confirmation_save_gate_and_powershell_handoff(self):
        import tempfile
        import zipfile
        from unittest.mock import patch
        panel = self.panel
        yes = self.main.QMessageBox.StandardButton.Yes
        cancel = self.main.QMessageBox.StandardButton.Cancel
        for choice, saved, launched in ((cancel, True, False), (yes, False, False), (yes, True, True)):
            with self.subTest(choice=choice, saved=saved), tempfile.TemporaryDirectory() as root:
                folder = Path(root) / 'download'
                folder.mkdir()
                archive = folder / 'update.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('MyScreenDraw.exe', b'fake')
                panel.project_dirty = True
                panel._update_install_handoff = False
                with patch.object(self.main.QMessageBox, 'exec', return_value=choice), \
                        patch.object(panel, 'save_project', return_value=saved) as save, \
                        patch.object(panel, 'save_settings'), \
                        patch.object(self.main, 'make_update_batch', return_value=str(Path(root) / 'apply.ps1')), \
                        patch.object(self.main.subprocess, 'Popen') as popen, \
                        patch.object(panel.lifecycle, '_do_quit') as quit_app:
                    panel._on_update_downloaded(str(archive), None)
                    self.assertEqual(popen.called, launched)
                    self.assertEqual(quit_app.called, launched)
                    self.assertEqual(save.called, choice == yes)
                    if launched:
                        command = popen.call_args.args[0]
                        self.assertEqual(command[0], 'powershell.exe')
                        self.assertIn('-File', command)
                    else:
                        self.assertFalse(folder.exists())
        panel.project_dirty = False
        panel._update_install_handoff = False

    def test_download_cancel_and_hidden_do_not_restart_heartbeat(self):
        from unittest.mock import patch
        panel = self.panel
        previous = panel.lifecycle.state
        panel.lifecycle.state = self.main.LifecycleState.HIDDEN
        panel.timer.stop()
        try:
            with patch.object(self.main.QMessageBox, 'exec', return_value=self.main.QMessageBox.StandardButton.Cancel), \
                    patch.object(self.main, 'UpdateDownloadWorker') as worker:
                panel._offer_update_page({'tag': 'v99.0.0', 'download_url': 'https://example.invalid/u.zip'})
                worker.assert_not_called()
                self.assertFalse(panel.timer.isActive())
        finally:
            panel.lifecycle.state = previous

    def test_update_ui_regressions_kill_known_bad_methods(self):
        import inspect
        import textwrap
        from unittest.mock import patch
        cases = [
            ('_on_update_result', 'self._pending_update_release = release',
             'self._pending_update_release = release; self._offer_update_page(release)',
             self.test_default_check_only_notifies),
            ('download_pending_update', 'self._offer_update_page(release)', 'pass',
             self.test_manual_download_is_separate_from_check),
            ('_on_update_downloaded', 'if self.project_dirty and not self.save_project():', 'if False:',
             self.test_install_confirmation_save_gate_and_powershell_handoff),
            ('_on_update_downloaded', '"powershell.exe"', '"cmd.exe"',
             self.test_install_confirmation_save_gate_and_powershell_handoff),
            ('_offer_update_page', 'self.resume_callbacks()', 'self.timer.start(self.HEARTBEAT_MS)',
             self.test_download_cancel_and_hidden_do_not_restart_heartbeat),
        ]
        # unittest subTest normally records rather than raises failures; a plain
        # assertion context is needed when deliberately running a broken method.
        import contextlib
        for method, old, new, check in cases:
            source = textwrap.dedent(inspect.getsource(getattr(self.main.ControlPanel, method)))
            self.assertIn(old, source)
            namespace = dict(self.main.__dict__)
            exec(source.replace(old, new), namespace)
            import types
            with patch.object(self.panel, method, types.MethodType(namespace[method], self.panel)), \
                    patch.object(self, 'subTest', side_effect=lambda **kw: contextlib.nullcontext()):
                with self.assertRaises(AssertionError, msg=method + ' / ' + old):
                    check()
            self.panel._update_flow_busy = False
            self.panel._update_install_handoff = False
            self.panel.project_dirty = False

    def test_stop_worker_is_safe_without_one(self):
        self.panel._update_worker = None
        self.panel.stop_update_worker()      # 不该抛

    def test_quit_stops_the_worker(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("aboutToQuit.connect(pnl.stop_update_worker)", source,
                      "QThread 还在跑就退出会崩在析构里")


class SettingsAppearanceTests(_PanelCase):
    """设置页自己长什么样——两条都是实屏上被用户看出来的，纯逻辑测试测不到。

    1. **背景色**。``QScrollArea.setWidget()`` 会把内容 widget 的 autoFillBackground
       打开，它于是拿调色板默认灰（#efefef）铺满滚动区，盖掉 MainFrame 的主题底色。
       暗色主题下这块浅灰非常刺眼；亮色主题下 #efefef 和 #f7f9fb 只差一点，所以
       这个 bug 长期只在暗色下被看见。断言必须落在【像素】上：objectName、
       stylesheet 字符串都是「设置对了」的证据，不是「画出来对了」的证据。
    2. **二选一按钮的高亮**。``set_ui_mode`` 原来不通知设置页，于是界面真的换了、
       高亮却钉在左边那颗上，看起来就是「不管选哪个都高亮左边」。
    """

    def setUp(self):
        super().setUp()
        self._theme_before = self.panel.theme_name
        self.panel.open_settings_panel()

    def tearDown(self):
        if self.panel.theme_name != self._theme_before:
            self.panel.toggle_theme()

    def _use_theme(self, name):
        if self.panel.theme_name != name:
            self.panel.toggle_theme()
        self.assertEqual(self.panel.theme_name, name)
        self.app.processEvents()

    def _panel_pixel(self, point):
        from PyQt6.QtGui import QImage
        shot = self.panel.settings_panel.grab().toImage()
        self.assertFalse(shot.isNull(), "抓不到设置页")
        self.assertGreater(shot.width(), 8, "抓下来的图不成形，量什么都不算数")
        self.assertTrue(shot.rect().contains(point),
                        f"采样点 {point.x()},{point.y()} 落在图({shot.width()}x"
                        f"{shot.height()})外面——量的是空气")
        del QImage
        return shot.pixelColor(point).name().lower()

    def _gap_point(self):
        """取设置页中间靠上的背景区域——避开按钮和边框。

        不取窗口角落：MainFrame 有 2px 描边加圆角，角落像素合法地是边框色或
        透明，拿它当背景量会得出一个「看着不对但其实没错」的颜色。
        """
        from PyQt6.QtCore import QPoint
        host = self.panel.settings_panel
        # 取中间偏上的位置，避开所有按钮
        return QPoint(host.width() // 2, 30)

    def test_settings_background_follows_the_theme(self):
        """暗色主题下设置页背景必须是主题的 frame 色，不能是调色板默认灰。"""
        self._use_theme("dark")
        want = self.main.ControlPanel.THEMES["dark"]["frame"].lower()
        got = self._panel_pixel(self._gap_point())
        self.assertEqual(got, want,
                         f"暗色下设置页背景是 {got}，应为主题 frame {want}")
        self.assertNotEqual(got, "#efefef", "又变回 Qt 调色板默认灰了")

    def test_light_theme_background_also_follows_the_theme(self):
        """亮色下也得对。这条容易漏：#efefef 和 #f7f9fb 肉眼几乎分不出。"""
        self._use_theme("light")
        want = self.main.ControlPanel.THEMES["light"]["frame"].lower()
        got = self._panel_pixel(self._gap_point())
        self.assertEqual(got, want,
                         f"亮色下设置页背景是 {got}，应为主题 frame {want}")

    def test_background_survives_a_theme_switch(self):
        """换主题会重新下发样式表。修复不能只在「刚建好」那一刻成立。"""
        self._use_theme("dark")
        self._use_theme("light")
        self._use_theme("dark")
        want = self.main.ControlPanel.THEMES["dark"]["frame"].lower()
        self.assertEqual(self._panel_pixel(self._gap_point()), want,
                         "来回换过主题之后背景又跑了")

    def test_background_survives_a_radius_change(self):
        """拖圆角滑块也会重新下发样式表，同上。"""
        self._use_theme("dark")
        self.panel.set_ui_radius(self.panel.RADIUS_MAX, persist=False)
        self.app.processEvents()
        want = self.main.ControlPanel.THEMES["dark"]["frame"].lower()
        self.assertEqual(self._panel_pixel(self._gap_point()), want,
                         "调过圆角之后背景又跑了")

    def test_the_transparent_rule_does_not_flatten_the_buttons(self):
        """让内容区透明的那条规则不能把按钮底色一起弄透明。

        这是给「让滚动区里一切都透明」的几种顺手写法留的绊子。实测 `QScrollArea *`、
        `QScrollArea QWidget`、全局 `QWidget` 都会把【非高亮】按钮打成 frame 色，而
        高亮那颗带 `#ActiveTool`、objectName 特异性更高反倒顶住了——于是界面看起来
        变成「所有按钮都高亮」。关键是：打穿之后，上面那几条背景断言【照样全绿】，
        所以必须单独盯按钮底色。
        （`QScrollArea > QWidget > QWidget` 在 Qt6 下实测不打穿，精确类匹配优先于
        基类匹配；但那依赖优先级规则，所以正式代码仍按 objectName 点名。）
        """
        from PyQt6.QtCore import QPoint
        self._use_theme("dark")
        theme = self.main.ControlPanel.THEMES["dark"]
        # 在设置页内部找一颗按钮，量它的底色
        self.panel.open_settings_panel()
        self.panel.settings_panel.show()
        self.panel.settings_panel.repaint()
        self.app.processEvents()
        button = self.panel.btn_check_update  # 设置页内部的按钮
        host = self.panel.settings_panel
        # 贴着左内边取点：按钮正中是字形，量到的会是文字色而不是底色
        point = button.mapTo(host, QPoint(4, button.height() // 2))
        got = self._panel_pixel(point)
        self.assertEqual(got, theme["button"].lower(),
                         f"按钮底色是 {got}，应为 {theme['button']}；"
                         f"要是等于 frame {theme['frame']} 就是被那条透明规则打穿了")


class SettingsPlacementTests(_PanelCase):
    """设置页要避着主面板弹，跟子菜单一个规矩。

    这条缺陷是实屏量出来的，代码审查看不见：设置页原先是屏幕居中弹出，而主面板常
    停在屏幕中间偏左，两者大面积相交。被压住的那半边点下去是主面板在收事件，用户
    看到的是「点不动」。

    为什么不是靠窗口层级解决：设置页和主面板都是置顶 Tool 窗口，把设置页挂进
    owner 链去争高低，实测会被心跳里的 owner 重绑带着一起隐藏（Hide 事件里一个
    Python 栈帧都没有，是原生侧动作）——那比原来的毛病严重得多。摆开就不必争。

    让位允许把设置页压矮，不是只挑方向：横版主面板宽到溢出屏幕，左右无地，停在
    屏幕中间高度时上下也塞不下整页。矮一点只是多滚两下，压住则是点不动。
    """

    def _open(self):
        self.panel.open_settings_panel()
        self.app.processEvents()
        return self.panel.settings_panel

    def _overlap(self):
        sp = self.panel.settings_panel.geometry()
        return self.panel.frameGeometry().intersected(sp)

    def test_settings_panel_does_not_overlap_the_main_panel(self):
        sp = self._open()
        ov = self._overlap()
        self.assertTrue(ov.isEmpty(),
                        f"设置页和主面板重叠 {ov.width()}x{ov.height()}，"
                        f"重叠区里的按钮点下去会被主面板收走。"
                        f"设置页 {sp.geometry()} 主面板 {self.panel.frameGeometry()}")

    def test_it_dodges_wherever_the_main_panel_sits(self):
        """主面板挪到屏幕各处都不能被压住——包括正中间那个最坏位置。"""
        from PyQt6.QtWidgets import QApplication
        screen = self.panel.screen_geometry(self.panel) or \
            QApplication.primaryScreen().availableGeometry()
        spots = {
            "左上": (screen.left() + 4, screen.top() + 4),
            "正中": (screen.center().x() - self.panel.width() // 2,
                     screen.center().y() - self.panel.height() // 2),
            "右上": (screen.right() - self.panel.width() - 4, screen.top() + 4),
            "左下": (screen.left() + 4, screen.bottom() - self.panel.height() - 4),
        }
        for name, (x, y) in spots.items():
            with self.subTest(主面板位置=name):
                self.panel.move(x, y)
                self.app.processEvents()
                self._open()
                ov = self._overlap()
                self.assertTrue(ov.isEmpty(),
                                f"主面板在{name}时重叠 {ov.width()}x{ov.height()}")

    def test_it_stays_inside_the_screen(self):
        """避让不能把设置页甩到屏幕外——那是彻底点不到，比压住更糟。

        必须把主面板挪遍四角再各查一次，只查正中间是不够的：主面板贴在右上角时，
        右侧空地只剩几 px，如果少了「空地够不够宽」那道判断，设置页会被塞进那条
        窄缝、整块甩到屏幕右外侧。那种情况下它和主面板并不相交，查重叠的那几条
        测试一条都不会红（变异实测：丙-3 全绿），只有查屏幕边界才抓得住。
        """
        from PyQt6.QtWidgets import QApplication
        screen = self.panel.screen_geometry(self.panel) or \
            QApplication.primaryScreen().availableGeometry()
        w, h = self.panel.width(), self.panel.height()
        spots = {
            "正中": (screen.center().x() - w // 2, screen.center().y() - h // 2),
            "右上": (screen.right() - w - 4, screen.top() + 4),
            "右下": (screen.right() - w - 4, screen.bottom() - h - 4),
            "左上": (screen.left() + 4, screen.top() + 4),
            "左下": (screen.left() + 4, screen.bottom() - h - 4),
            "贴右边": (screen.right() - w, screen.center().y() - h // 2),
        }
        for name, (x, y) in spots.items():
            with self.subTest(主面板位置=name):
                self.panel.move(x, y)
                self.app.processEvents()
                geo = self._open().geometry()
                self.assertGreaterEqual(geo.left(), screen.left(),
                                        f"主面板在{name}时设置页左边越出屏幕 {geo}")
                self.assertGreaterEqual(geo.top(), screen.top(),
                                        f"主面板在{name}时设置页上边越出屏幕 {geo}")
                self.assertLessEqual(geo.right(), screen.right(),
                                     f"主面板在{name}时设置页右边越出屏幕 {geo}")
                self.assertLessEqual(geo.bottom(), screen.bottom(),
                                     f"主面板在{name}时设置页下边越出屏幕 {geo}")

    def test_landscape_orientation_also_dodges(self):
        """横版是最坏的场景：让位必须允许把设置页压矮，光挑方向不够。

        实测横版主面板宽 885，比 800 宽的屏还宽（它本身就左右溢出），所以左右两侧
        一寸空地都没有。主面板又常被拖到屏幕中间高度，上下各剩三百来 px，也塞不下
        686 高的设置页——四个方向全军覆没，只挑方向的话必然退回 clamp，也就是压在
        主面板身上（这一版最早就是这么失败的，重叠 300x54）。

        所以判据是「不重叠 + 不出屏 + 高度还够用」，而不是「高度保持不变」。设置页
        内部是 QScrollArea，矮一点只是多滚两下。
        """
        from PyQt6.QtWidgets import QApplication
        screen = self.panel.screen_geometry(self.panel) or \
            QApplication.primaryScreen().availableGeometry()
        self.panel.set_orientation("landscape")
        self.app.processEvents()
        try:
            # 挪到屏幕中间高度，逼出「上下都不宽裕」的那一档
            self.panel.move(screen.center().x() - self.panel.width() // 2,
                            screen.center().y() - self.panel.height() // 2)
            self.app.processEvents()
            sp = self._open()
            ov = self._overlap()
            geo = sp.geometry()
            self.assertTrue(ov.isEmpty(),
                            f"横版下重叠 {ov.width()}x{ov.height()}，"
                            f"设置页 {geo} 主面板 {self.panel.frameGeometry()}")
            self.assertGreaterEqual(geo.top(), screen.top(), f"越出屏幕上边 {geo}")
            self.assertLessEqual(geo.bottom(), screen.bottom(), f"越出屏幕下边 {geo}")
            self.assertGreaterEqual(geo.height(), self.panel.DODGE_MIN_HEIGHT,
                                    f"为了让位把设置页压到 {geo.height()}px，没法用了")
        finally:
            self.panel.set_orientation("portrait")
            self.app.processEvents()

    def test_shrinking_to_fit_keeps_the_content_reachable(self):
        """压矮之后内容不能就此丢掉——得靠滚动条还能滚到底部那几颗键。"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        screen = self.panel.screen_geometry(self.panel) or \
            QApplication.primaryScreen().availableGeometry()
        self.panel.set_orientation("landscape")
        self.app.processEvents()
        try:
            self.panel.move(screen.center().x() - self.panel.width() // 2,
                            screen.center().y() - self.panel.height() // 2)
            self.app.processEvents()
            sp = self._open()
            scroll = self.panel.settings_scroll
            bar = scroll.verticalScrollBar()
            content = scroll.widget().sizeHint().height()
            if content > scroll.viewport().height():
                # 光看 bar.maximum() 抓不住毛病：把竖向滚动条设成 ScrollBarAlwaysOff，
                # Qt 照样维护 maximum、setValue 照样能滚——代码滚得动，手滚不动。
                # 变异实测（丙-8）这条全绿。所以判据得是「这根条子用户看得见」。
                self.assertGreater(bar.maximum(), 0,
                                   "窗口被压矮、内容装不下，滚动条却滚不动，"
                                   "底部的设置项就永远点不到")
                self.assertNotEqual(
                    scroll.verticalScrollBarPolicy(),
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
                    "内容装不下却把竖向滚动条关了，用户没有任何办法滚到底部")
                self.assertTrue(bar.isVisible(),
                                "内容装不下，竖向滚动条却不出现，用户滚不动")
            # 无论压没压矮，底部那颗键都得能滚进视野
            bar.setValue(bar.maximum())
            self.app.processEvents()
            btn = self.panel.btn_check_update
            top_in_view = btn.mapTo(scroll.viewport(), btn.rect().topLeft()).y()
            self.assertLess(top_in_view, scroll.viewport().height(),
                            f"滚到底了「立即检查」还在视野外（y={top_in_view}，"
                            f"视野高 {scroll.viewport().height()}），设置页 {sp.geometry()}")
        finally:
            self.panel.set_orientation("portrait")
            self.app.processEvents()

    def test_it_never_shrinks_below_the_usable_floor(self):
        """空地只剩一条缝时宁可退回原高度，也不能摆出一个几十 px 高的窗口。

        这一条必须自己伪造一块小屏幕。离屏跑的是 800x800，而竖版主面板 394 高、
        横版 54 高——上下两侧总是有一侧剩 240px 以上，下限根本触发不到（变异实测：
        把 DODGE_MIN_HEIGHT 改成 1，在真实屏幕尺寸下一条测试都不红）。下限真正管
        的是矮屏：把屏幕缩到 400x400、主面板 394 高，上下就都只剩十几 px 了。
        """
        from PyQt6.QtCore import QRect
        # 这个 200 是写死的，不能读 self.panel.DODGE_MIN_HEIGHT：那样把常量改小，
        # 判据会跟着一起松掉，变异照样全绿（丙-4 第一版就是这么漏的）。这里问的是
        # 「摆出来的窗口还能用吗」，那是产品判据，不该由被测代码自己定义。
        usable = 200
        fake = QRect(0, 0, 400, 400)
        real_geo = self.panel.screen_geometry
        real_rect = self.panel.geometry()
        # 主面板 150x394 摆在 y=20：上方空地 13px（正数但远不够用），下方是负数，
        # 左右两侧都不到 300 宽——四块空地全废，只能退回原高度。
        fake = QRect(0, 0, 400, 400)
        fake_panel_geo = QRect(100, 20, 150, 394)
        real_geo = self.panel.screen_geometry
        real_panel_geo = self.panel.geometry
        real_frame_geo = self.panel.frameGeometry
        # 在offscreen模式下setGeometry不生效，直接mock geometry()和frameGeometry()
        self.panel.geometry = lambda: fake_panel_geo
        self.panel.frameGeometry = lambda: fake_panel_geo
        self.panel.screen_geometry = lambda *_a, **_k: fake
        try:
            x, y, height = self.panel._dodge_main_panel(300, 600, gap=8)
            self.assertGreaterEqual(
                height, usable,
                f"让位让出了一条 {height}px 高的缝，那还不如不让。"
                f"落点 ({x},{y}) 主面板 {self.panel.frameGeometry()} 屏幕 {fake}")
            # 这块屏幕上四个方向都不够，唯一正确的答案是原样退回
            self.assertEqual(height, 600,
                             f"四块空地都不够用，却还是压矮到 {height}px 摆了出去")
        finally:
            self.panel.screen_geometry = real_geo
            self.panel.geometry = real_panel_geo
            self.panel.frameGeometry = real_frame_geo
            self.app.processEvents()


    def test_submenu_anchoring_still_works(self):
        """抽出 anchor_for 之后，子菜单的锚点解析不能跟着坏掉。

        icon模式下返回icon_buttons["pen"]，classic模式下返回btn_pen。
        """
        target = self.panel.draw_sub
        result = self.panel.sub_anchor_button(target)
        # 在icon模式下应该返回图标按钮，而不是经典按钮
        if self.panel.ui_mode == "icon":
            expected = self.panel.icon_buttons.get("pen")
            self.assertIs(result, expected,
                          f"icon模式下应返回icon_buttons['pen']，实际返回{result}")
        else:
            self.assertIs(result, self.panel.btn_pen,
                          f"classic模式下应返回btn_pen，实际返回{result}")

    def test_reopening_keeps_it_clear(self):
        """关掉再开、以及主面板挪过位置之后再开，都要重新避让。"""
        self._open()
        self.panel.settings_panel.hide()
        self.app.processEvents()
        moved = self.panel.settings_panel.pos()
        self.panel.move(self.panel.x() + 120, self.panel.y() + 60)
        self.app.processEvents()
        self._open()
        self.assertTrue(self._overlap().isEmpty(), "主面板挪过之后再开又压上了")
        self.assertNotEqual(self.panel.settings_panel.pos(), moved,
                            "主面板都挪了 120px，设置页却停在老位置，说明落点没重算")


    def test_switching_orientation_re_dodges(self):
        """换方向的尺寸变化比换 UI 模式更大（竖版 150 宽 ↔ 横版几百宽）。

        主面板必须先挪离 y=0：贴顶时竖版让位把设置页开在 y≈190，而横版主面板只有
        54px 高、占 y=0..53，两者本来就错开，压不上——这条测试的第一版就停在 @0,0，
        变异（删掉换方向后的重新让位）照样全绿。挪到竖直居中之后，横版那道横条正好
        扫过设置页所在的高度，不重新让位就是 300x54 的重叠（实测）。
        """
        screen = self.panel.screen_geometry(self.panel)
        self.panel.set_orientation("portrait")
        self.app.processEvents()
        self.panel.move(screen.left(), screen.center().y() - 200)
        self.app.processEvents()
        self._open()
        self.assertTrue(self._overlap().isEmpty(), "竖版下开就压上了")
        self.panel.set_orientation("landscape")
        self.app.processEvents()
        ov = self._overlap()
        self.assertTrue(ov.isEmpty(),
                        f"转横版之后重叠 {ov.width()}x{ov.height()}；"
                        f"设置页 {self.panel.settings_panel.geometry()}，"
                        f"主面板 {self.panel.frameGeometry()}")
        self.panel.set_orientation("portrait")
        self.app.processEvents()
        self.assertTrue(self._overlap().isEmpty(), "转回竖版之后又压上了")

    def test_dragging_the_main_panel_takes_the_settings_page_along(self):
        """拖动主面板时设置页要跟着让位，跟子菜单同一个规矩（用户原话）。

        走 mouseMoveEvent 真事件，不直接调 reposition_settings_panel——后者是实现
        细节，测它等于测「我调了我自己」。这里问的是「拖的时候会不会跟」。
        """
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        self.panel.set_orientation("portrait")
        self.app.processEvents()
        self._open()
        start = self.panel.pos()
        self.panel._drag_offset = QPoint(10, 10)
        before = self.panel.settings_panel.pos()
        target = QPointF(start.x() + 260 + 10, start.y() + 40 + 10)
        ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(10, 10), target,
                         Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        self.panel.mouseMoveEvent(ev)
        self.app.processEvents()
        self.panel._drag_offset = None
        self.assertNotEqual(self.panel.pos(), start, "主面板没被拖动，前提不成立")
        ov = self._overlap()
        self.assertTrue(ov.isEmpty(),
                        f"拖完之后重叠 {ov.width()}x{ov.height()}；设置页停在老位置了")
        self.assertNotEqual(self.panel.settings_panel.pos(), before,
                            "主面板拖走了，设置页一动不动——它没跟着让位")

    def test_re_dodging_can_grow_back(self):
        """让位压矮过之后，挪到宽裕的地方要能长回去，不能越摆越矮。

        这一条防的是「拿 panel.height() 再算一遍想要多高」：那时窗口已经被上一次
        让位压矮了，再算只会更矮，反复摆位就单调递减收不回来。所以想要的高度必须
        在打开时记下来，之后每次让位都拿那个原始值去要。
        """
        from PyQt6.QtCore import QRect
        from unittest import mock
        self.panel.set_orientation("landscape")
        self.app.processEvents()
        # 先制造一次「被压矮」：横版主面板停在屏幕中间高度，上下都塞不下整页
        screen = self.panel.screen_geometry(self.panel)
        self.panel.move(screen.left(), screen.center().y() - self.panel.height() // 2)
        self.app.processEvents()
        self._open()
        squeezed = self.panel.settings_panel.height()
        # 再挪到贴顶：下方一整片空地，页面应该长回去
        self.panel.move(screen.left(), screen.top())
        self.app.processEvents()
        self.panel.reposition_settings_panel()
        self.app.processEvents()
        grown = self.panel.settings_panel.height()
        self.assertGreater(grown, squeezed,
                           f"压矮到 {squeezed}px 之后挪到宽裕处仍是 {grown}px，长不回来")


if __name__ == "__main__":
    unittest.main(verbosity=2)
