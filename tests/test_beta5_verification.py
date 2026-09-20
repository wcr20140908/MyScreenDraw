# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""6.0.0-beta.5 回归：beta.4 报告的分体界面问题。

- 竖版工具栏必须落在可用屏幕内（不压任务栏），LOGO 与工具栏同宽/同高
- 工具栏、LOGO 在浮窗链里（否则绘图模式下被全屏画布盖住，点不动）
- 换主题重绘后每个按钮仍有图标（旧图标表缺 mouse/folder/close，穿透/文件/关闭变空白）
- F12 从 pynput 线程进后台必须经队列信号回主线程（killTimer 跨线程警告）
- 后台状态下 bind_topmost_stack 不许把主面板拉回来
- 主面板空壳不许缩成 0×0（UpdateLayeredWindowIndirect 报错）
- 工具栏拖动时保存配置要防抖
"""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402
import toolbar_windows  # noqa: E402
from app_lifecycle import LifecycleState  # noqa: E402


def pump(app, ms):
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


class Beta5SplitUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.panel.apply_theme()
        cls.panel.update_whiteboard_ui()
        cls.panel.update_history_ui()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        for t in (cls.panel.listener, cls.panel.timer, cls.panel.autosave_timer):
            try:
                t.stop()
            except Exception:
                pass
        cls.canvas.close()
        cls.panel.close()

    def setUp(self):
        self.panel.set_orientation("portrait")
        if self.canvas.whiteboard_mode:
            self.panel.toggle_whiteboard()
        self.panel._toolbar_detached = False
        self.app.processEvents()

    # ---- 几何 ----
    def _avail(self):
        return toolbar_windows._available_rect(self.panel.toolbar_window)

    def test_portrait_toolbar_fits_available_height(self):
        tb, logo = self.panel.toolbar_window, self.panel.logo_window
        avail = self._avail()
        self.assertLessEqual(tb.height(), avail.height() - toolbar_windows.LOGO_THICKNESS - toolbar_windows.LOGO_GAP,
                             f"toolbar {tb.height()} tall on {avail}")
        self.assertTrue(avail.contains(tb.frameGeometry()), (tb.frameGeometry(), avail))
        self.assertEqual(logo.width(), tb.width())
        self.assertEqual(logo.height(), toolbar_windows.LOGO_THICKNESS)

    def test_portrait_whiteboard_box_still_fits(self):
        tb, logo = self.panel.toolbar_window, self.panel.logo_window
        self.panel.toggle_whiteboard()
        self.app.processEvents()
        try:
            self.assertTrue(tb.icon_wb_box.isVisible())
            avail = self._avail()
            self.assertTrue(avail.contains(tb.frameGeometry()), (tb.frameGeometry(), avail))
            self.assertEqual(logo.width(), tb.width())
            for key in tb.WB_KEYS:
                self.assertTrue(tb.icon_buttons[key].isVisible(), key)
        finally:
            self.panel.toggle_whiteboard()
            self.app.processEvents()
        self.assertFalse(tb.icon_wb_box.isVisible())
        self.assertEqual(logo.width(), tb.width())

    def test_buttons_are_wider_than_tall(self):
        tb = self.panel.toolbar_window
        self.assertGreaterEqual(tb._button_width, tb._button_height)
        self.assertLessEqual(tb._button_height, toolbar_windows.BUTTON_HEIGHT)
        self.assertGreaterEqual(tb._button_height, toolbar_windows.BUTTON_HEIGHT_MIN)
        for key, btn in tb.icon_buttons.items():
            if btn.isVisible():
                self.assertEqual(btn.width(), tb._button_width + 2, key)
                self.assertEqual(btn.height(), tb._button_height + 2, key)

    def test_landscape_logo_matches_toolbar_height(self):
        tb, logo = self.panel.toolbar_window, self.panel.logo_window
        self.panel.set_orientation("landscape")
        self.app.processEvents()
        avail = self._avail()
        self.assertTrue(avail.contains(tb.frameGeometry()), (tb.frameGeometry(), avail))
        if avail.width() < 900:
            # 离屏 800px 宽：一行 14 个按钮放不下，必须折成两行而不是被 clamp 到 x=0
            self.assertEqual(tb._main_rows, 2)
        self.assertEqual(logo.height(), tb.height())
        self.assertEqual(logo.width(), toolbar_windows.LOGO_THICKNESS)
        self.assertEqual(tb.y(), logo.y())
        self.assertEqual(tb.x(), logo.x() + logo.width() + toolbar_windows.LOGO_GAP)

    def test_toolbar_flips_above_logo_near_bottom(self):
        tb, logo = self.panel.toolbar_window, self.panel.logo_window
        avail = self._avail()
        logo.move(logo.x(), avail.bottom() - logo.height() - 5)
        self.panel._on_logo_dragged(logo.pos())
        self.app.processEvents()
        try:
            self.assertTrue(avail.contains(tb.frameGeometry()), (tb.frameGeometry(), avail))
            self.assertLess(tb.frameGeometry().bottom(), logo.y())
        finally:
            logo.move(20, 20)
            self.panel._on_logo_dragged(logo.pos())
            self.app.processEvents()

    def test_clamp_point_into(self):
        area = QRect(0, 0, 100, 50)
        self.assertEqual(toolbar_windows.clamp_point_into(90, 45, 20, 10, area), (80, 40))
        self.assertEqual(toolbar_windows.clamp_point_into(-5, -5, 20, 10, area), (0, 0))
        # 比区域还大：贴左上
        self.assertEqual(toolbar_windows.clamp_point_into(30, 30, 200, 200, area), (0, 0))

    # ---- 层级 ----
    def test_split_windows_in_floating_stack(self):
        stack = self.panel.floating_stack()
        self.assertIn(self.panel.toolbar_window, stack)
        self.assertIn(self.panel.logo_window, stack)
        # 主面板垫底，分体窗口在它之上
        self.assertLess(stack.index(self.panel.toolbar_window), stack.index(self.panel))
        self.assertLess(stack.index(self.panel.logo_window), stack.index(self.panel))

    def test_split_windows_follow_opacity(self):
        targets = list(self.panel.opacity_targets())
        self.assertIn(self.panel.toolbar_window, targets)
        self.assertIn(self.panel.logo_window, targets)

    # ---- 图标 ----
    def test_every_button_keeps_icon_after_theme_repaint(self):
        self.panel.repaint_ui_icons()
        for key, btn in self.panel.toolbar_window.icon_buttons.items():
            self.assertFalse(btn.icon().isNull(), key)
            self.assertFalse(btn.icon().pixmap(20, 20).isNull(), key)

    def test_file_anchor_uses_folder_icon_name(self):
        self.assertEqual(self.panel.ICON_ANCHOR_KEYS["btn_file"], "folder")
        from ui_icons import make_ui_icon
        for key, icon_name, *_ in self.panel.ICON_ACTIONS + self.panel.ICON_WB_ACTIONS:
            self.assertFalse(make_ui_icon(icon_name, "#ffffff", 20).pixmap(20, 20).isNull(), (key, icon_name))

    def test_legacy_icon_factory_falls_back_to_ui_icons(self):
        for name in ("mouse", "folder", "close"):
            self.assertFalse(main.make_ui_icon(name, "#ffffff", 20).isNull(), name)

    # ---- 生命周期 ----
    def test_f12_hides_via_queued_signal(self):
        from pynput import keyboard
        lc = self.panel.lifecycle
        self.assertNotEqual(lc.state, LifecycleState.HIDDEN)
        self.panel.on_global_key_press(keyboard.Key.f12)
        # 队列连接：热键线程只投递，不直接动窗口/定时器
        self.assertNotEqual(lc.state, LifecycleState.HIDDEN)
        pump(self.app, 50)
        self.assertEqual(lc.state, LifecycleState.HIDDEN)
        lc.restore_from_background()
        self.app.processEvents()
        self.assertEqual(lc.state, LifecycleState.SHOWING)

    def test_bind_topmost_stack_does_not_reshow_panel_while_hidden(self):
        lc = self.panel.lifecycle
        lc.hide_to_background()
        try:
            self.assertFalse(self.panel.isVisible())
            # 进后台前 set_drawing_mode(False) 排的延迟重绑会在 hide 之后才到
            self.panel.bind_topmost_stack()
            pump(self.app, 600)
            self.assertFalse(self.panel.isVisible())
            self.assertFalse(self.panel.toolbar_window.isVisible())
            self.assertFalse(self.panel.logo_window.isVisible())
            self.assertFalse(self.canvas.isVisible())
        finally:
            lc.restore_from_background()
            self.app.processEvents()

    def test_restore_from_background_shows_canvas_and_split_windows(self):
        lc = self.panel.lifecycle
        lc.hide_to_background()
        self.assertFalse(self.canvas.isVisible())
        lc.restore_from_background()
        self.app.processEvents()
        self.assertTrue(self.canvas.isVisible())
        self.assertTrue(self.panel.toolbar_window.isVisible())
        self.assertTrue(self.panel.logo_window.isVisible())
        self.assertEqual(self.panel.logo_window.width(), self.panel.toolbar_window.width())

    def test_restore_keeps_collapsed_toolbar_collapsed(self):
        lc = self.panel.lifecycle
        self.panel.toggle_toolbar_collapsed()
        self.assertFalse(self.panel.toolbar_window.isVisible())
        lc.hide_to_background()
        lc.restore_from_background()
        self.app.processEvents()
        try:
            self.assertEqual(lc.state, LifecycleState.COLLAPSED)
            self.assertTrue(self.panel.logo_window.isVisible())
            self.assertFalse(self.panel.toolbar_window.isVisible())
        finally:
            self.panel.toggle_toolbar_collapsed()
            self.app.processEvents()
        self.assertTrue(self.panel.toolbar_window.isVisible())

    def test_tray_label_follows_action_text(self):
        lc = self.panel.lifecycle
        if not lc.tray_icon:
            self.skipTest("offscreen 无托盘")
        label = lc._menu_labels.get(lc.action_toggle_ui)
        self.assertIsNotNone(label)
        lc.hide_to_background()
        self.assertEqual(label.text(), main.tr("show_main_ui"))
        lc.restore_from_background()
        self.assertEqual(label.text(), main.tr("hide_main_ui"))

    # ---- 主面板空壳 ----
    def test_panel_shell_never_zero_sized(self):
        self.panel._resize_to_content()
        self.assertGreaterEqual(self.panel.width(), 1)
        self.assertGreaterEqual(self.panel.height(), 1)

    def test_canvas_is_fullscreen_without_activation(self):
        self.assertTrue(self.canvas.isFullScreen())

    # ---- 托盘「重启软件」----
    def test_restart_command_launches_main_entry_with_restore_file(self):
        lc = self.panel.lifecycle
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            return object()

        with patch("subprocess.Popen", side_effect=fake_popen), \
                patch.object(lc, "_do_quit") as do_quit:
            lc._restart_app()
        self.assertTrue(do_quit.called)
        cmd = captured["cmd"]
        # 开发态：入口必须是 main.py（原来拉起的是 app_lifecycle.py，新进程静默退出）
        self.assertTrue(cmd[1].lower().endswith("main.py"), cmd)
        self.assertIn("--restore", cmd)
        recovery = cmd[cmd.index("--restore") + 1]
        self.assertTrue(os.path.isfile(recovery), recovery)
        os.remove(recovery)

    def test_restore_from_restart_reloads_work_and_cleans_up(self):
        import tempfile
        from PyQt6.QtCore import QLine
        from PyQt6.QtGui import QPen, QColor

        cv = self.canvas
        self.panel.set_drawing_mode(True)
        cv.all_segments = [{
            "line": QLine(10, 20, 30, 40),
            "pen": QPen(QColor("#ff4757"), 4),
            "id": "restart-me",
            "marker": False,
        }]
        cv.text_items = []
        cv.shape_items = []
        cv.image_items = []
        fd, path = tempfile.mkstemp(suffix=".msd")
        os.close(fd)
        try:
            self.assertTrue(self.panel.save_project(path))
            saved_as = self.panel.project_path
            cv.all_segments = []
            self.assertTrue(self.panel.restore_from_restart(path))
            self.assertEqual([s["id"] for s in cv.all_segments], ["restart-me"])
            self.assertIsNone(self.panel.project_path)
            self.assertTrue(self.panel.project_dirty)
            self.assertFalse(os.path.exists(path))
            self.assertNotEqual(saved_as, None)
        finally:
            if os.path.exists(path):
                os.remove(path)
            self.panel.project_path = None
            self.panel.project_dirty = False
            cv.all_segments = []
        self.assertFalse(self.panel.restore_from_restart(path))
        self.assertFalse(self.panel.restore_from_restart(None))

    # ---- 拖动保存防抖 ----
    def test_toolbar_drag_save_is_debounced(self):
        from PyQt6.QtCore import QPoint
        with patch.object(self.panel, "save_settings") as save:
            timer = getattr(self.panel, "_split_save_timer", None)
            if timer is not None:
                timer.timeout.disconnect()
                timer.timeout.connect(self.panel.save_settings)
            for i in range(50):
                self.panel._on_toolbar_dragged(QPoint(100 + i, 100))
            self.assertEqual(save.call_count, 0)
            pump(self.app, 700)
            self.assertEqual(save.call_count, 1)
        self.panel._toolbar_detached = False
        self.panel._toolbar_saved_pos = None
        timer = getattr(self.panel, "_split_save_timer", None)
        if timer is not None:
            timer.timeout.disconnect()
            timer.timeout.connect(self.panel.save_settings)


if __name__ == "__main__":
    unittest.main()
