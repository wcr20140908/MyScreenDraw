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
        # 每个用例从经典 UI、不透明、默认圆角开始，避免用例间互相污染
        self.panel.set_ui_mode("classic", persist=False)
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


class IconUiTests(_PanelCase):
    def test_switching_modes_shows_exactly_one_tree(self):
        self.panel.set_ui_mode("icon", persist=False)
        self.assertTrue(self.panel.icon_frame.isVisible())
        self.assertFalse(self.panel.main_frame.isVisible())
        self.panel.set_ui_mode("classic", persist=False)
        self.assertTrue(self.panel.main_frame.isVisible())
        self.assertFalse(self.panel.icon_frame.isVisible())

    def test_every_icon_button_has_a_drawn_icon(self):
        empty = [key for key, btn in self.panel.icon_buttons.items() if btn.icon().isNull()]
        self.assertEqual(empty, [], f"这些图标画不出来: {empty}")

    def test_icon_buttons_keep_the_touch_target_size(self):
        """换 UI 不能让触控命中面积缩水。"""
        small = [(key, btn.minimumWidth(), btn.minimumHeight())
                 for key, btn in self.panel.icon_buttons.items()
                 if btn.minimumWidth() < self.main.TOUCH_MIN_BUTTON
                 or btn.minimumHeight() < self.main.TOUCH_MIN_BUTTON]
        self.assertEqual(small, [])

    def test_highlight_is_projected_from_the_classic_button(self):
        self.panel.set_ui_mode("icon", persist=False)
        self.panel.handle_eraser_click()
        self.assertEqual(self.panel.btn_eraser.objectName(), "ActiveTool")
        self.assertEqual(self.panel.icon_buttons["eraser"].objectName(), "IconBtnActive")
        self.panel.handle_annotate_click()
        self.assertEqual(self.panel.icon_buttons["eraser"].objectName(), "IconBtn")
        self.assertEqual(self.panel.icon_buttons["pen"].objectName(), "IconBtnActive")

    def test_enabled_state_is_projected(self):
        self.panel.set_ui_mode("icon", persist=False)
        self.panel.update_history_ui()
        for key, classic in (("undo", self.panel.btn_undo), ("redo", self.panel.btn_redo)):
            self.assertEqual(self.panel.icon_buttons[key].isEnabled(), classic.isEnabled(),
                             f"{key} 的可用性没跟上经典按钮")

    def test_tooltips_follow_the_live_button_text(self):
        """模式键在「穿透/绘图」之间来回，提示不能停在旧文案上。"""
        self.panel.set_ui_mode("icon", persist=False)
        before = self.panel.icon_buttons["mode"].toolTip()
        self.assertEqual(before, self.panel.btn_mode.text())
        self.panel.toggle_mode()
        self.panel.sync_icon_buttons()
        after = self.panel.icon_buttons["mode"].toolTip()
        self.assertEqual(after, self.panel.btn_mode.text())
        self.assertNotEqual(after, before, "切换模式后提示没变")
        self.panel.toggle_mode()

    def test_whiteboard_bar_appears_in_icon_mode(self):
        """回归：祖先隐藏使 isVisible() 恒 False，用它投影会让翻页栏永不出现。"""
        self.panel.set_ui_mode("icon", persist=False)
        self.panel.toggle_whiteboard()
        self.assertTrue(self.canvas.whiteboard_mode)
        self.assertFalse(self.panel.wb_box.isHidden(), "经典白板栏的显示意图没写上")
        self.assertFalse(self.panel.icon_wb_box.isHidden(), "图标白板栏没跟上")
        self.assertTrue(self.panel.icon_wb_box.isVisible(), "图标模式下翻页栏应当真的可见")
        self.panel.toggle_whiteboard()
        self.assertTrue(self.panel.icon_wb_box.isHidden())

    def test_orientation_keeps_the_icon_tree_intact(self):
        self.panel.set_ui_mode("icon", persist=False)
        self.panel.set_orientation("landscape")
        self.assertEqual(self.panel.icon_layout.__class__.__name__, "QHBoxLayout")
        self.assertTrue(all(btn.parent() is not None
                            for btn in self.panel.icon_buttons.values()))
        self.panel.set_orientation("portrait")
        self.assertEqual(self.panel.icon_layout.__class__.__name__, "QVBoxLayout")
        self.assertTrue(all(btn.parent() is not None
                            for btn in self.panel.icon_buttons.values()))

    def test_submenu_anchors_move_to_the_icon_buttons(self):
        """子菜单要贴着当前那棵树的按钮弹，否则在图标模式下会飘到别处。"""
        self.panel.set_ui_mode("icon", persist=False)
        anchor = self.panel.sub_anchor_button(self.panel.annotate_sub)
        self.assertIn(anchor, list(self.panel.icon_buttons.values()))
        self.panel.set_ui_mode("classic", persist=False)
        anchor = self.panel.sub_anchor_button(self.panel.annotate_sub)
        self.assertNotIn(anchor, list(self.panel.icon_buttons.values()))


class SmartShapesDualEntryTests(_PanelCase):
    def _pin(self, enabled):
        """直接把两边落到 enabled，不经过 set_smart_shapes——它正是被测对象。

        变异测试里踩到过：拿 set_smart_shapes 铺场地时，前一个用例失败后留下
        canvas=True / 按钮未勾选，本用例翻一次刚好两边都变成 False，断言凑巧
        通过，漏抓了「不同步 checked」这个变异。场地必须由构造保证一致。
        """
        self.canvas.smart_shapes_enabled = enabled
        self.panel.btn_smart_toggle.blockSignals(True)
        self.panel.btn_smart_toggle.setChecked(enabled)
        self.panel.btn_smart_toggle.blockSignals(False)

    def test_settings_toggle_syncs_the_checkable_button(self):
        """只改文案不改 checked，会让批注面板那颗按钮下一次点击「没反应」。"""
        for start in (False, True):
            with self.subTest(start=start):
                self._pin(start)
                self.panel.toggle_smart_shapes()
                self.assertEqual(self.canvas.smart_shapes_enabled, not start)
                self.assertEqual(self.panel.btn_smart_toggle.isChecked(),
                                 self.canvas.smart_shapes_enabled)
                # 现在从批注面板那颗点回去，必须真的切回来
                self.panel.btn_smart_toggle.setChecked(start)
                self.panel.on_smart_toggle()
                self.assertEqual(self.canvas.smart_shapes_enabled, start)

    def test_both_buttons_show_the_same_state(self):
        self.panel.open_settings_panel()
        for want in (True, False):
            self.panel.set_smart_shapes(want)
            self.assertEqual(self.panel.btn_smart_toggle.isChecked(), want)
            expect = self.main.tr("smart_shapes_on") if want else self.main.tr("smart_shapes_off")
            self.assertEqual(self.panel.btn_smart_toggle.text(), expect)
            self.assertEqual(self.panel.btn_settings_smart.text(), expect)

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
        self.panel.set_ui_mode("icon", persist=False)
        self.panel.set_ui_radius(21, persist=False)
        self.panel.set_ui_opacity(58, persist=False)
        self.panel.update_check_enabled = True
        settings = self.panel.collect_settings()
        self.assertEqual(settings["ui_mode"], "icon")
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
            self.panel.set_ui_mode("classic", persist=False)
            self.panel.set_ui_radius(10, persist=False)
            self.panel.set_ui_opacity(90, persist=False)
            baseline = {"ui_mode": self.panel.ui_mode,
                        "ui_radius": self.panel.ui_radius,
                        "ui_opacity": self.panel.ui_opacity}
            for bad in ({"ui_mode": "nonsense"}, {"ui_mode": 7},
                        {"ui_radius": "big"}, {"ui_radius": None},
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
        block = source[start:source.index("# --- 手动检查更新", start)]
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
    def test_disabled_by_default(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("self.update_check_enabled = False", source,
                      "不联网必须仍然是默认状态")

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

    def test_nothing_checks_on_startup(self):
        """启动时不能有任何自动检查——包括延时的、包括心跳里的。"""
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        for hook in ("singleShot", "heartbeat_refresh", "aboutToQuit"):
            index = 0
            while True:
                index = source.find(hook, index + 1)
                if index < 0:
                    break
                window = source[index:index + 200]
                self.assertNotIn("check_for_updates", window,
                                 f"{hook} 附近出现了自动检查更新")

    def test_version_parsing(self):
        parse = self.main.parse_version
        self.assertEqual(parse("v5.5.0"), (5, 5, 0))
        self.assertEqual(parse("5.5.0"), (5, 5, 0))
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
            self.assertEqual(offered, ["v99.0.0"])
            self.assertIn("99.0.0", self.panel.update_status_label.text())
            self.panel._on_update_result("v0.0.1", None)
            self.assertEqual(offered, ["v99.0.0"], "旧版本不该弹框")
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

    def test_never_downloads_or_executes(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        start = source.index("# --- 手动检查更新")
        block = source[start:source.index("class UpdateCheckWorker") + 400]
        for forbidden in ("urlretrieve", "subprocess", "os.system", "os.startfile",
                          "ShellExecute", "extractall"):
            self.assertNotIn(forbidden, block,
                             f"检查更新的代码里出现了 {forbidden}；它只该读版本号")

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
        original = self.main.fetch_latest_version
        # 回一个远低于当前版本的号，_on_update_result 就走「已是最新」那支，
        # 不会弹出模态的 _offer_update_page 把测试挂住。
        self.main.fetch_latest_version = lambda *a, **k: (
            seen.append(QThread.currentThread()), ("v0.0.1", None))[1]
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
            self.main.fetch_latest_version = original
            self.panel.update_check_enabled = was_enabled
            self.panel.stop_update_worker()
            self.panel.sync_settings_panel()
            self.panel.settings_panel.hide()

    def test_stop_worker_is_safe_without_one(self):
        self.panel._update_worker = None
        self.panel.stop_update_worker()      # 不该抛

    def test_quit_stops_the_worker(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("aboutToQuit.connect(pnl.stop_update_worker)", source,
                      "QThread 还在跑就退出会崩在析构里")


if __name__ == "__main__":
    unittest.main(verbosity=2)
