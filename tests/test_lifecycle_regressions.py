"""退出确认与独立浮窗回归；不退出测试进程，不注入桌面输入。"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from app_lifecycle import AppLifecycleManager, LifecycleState


class QuitRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def manager(self, state="showing"):
        manager = AppLifecycleManager.__new__(AppLifecycleManager)
        manager.panel = Mock()
        manager.state = state
        manager._state_before_hidden = state
        manager._quit_dialog_showing = False
        manager.tray_icon = None
        manager.app = Mock()
        manager._tr = lambda key: key
        return manager

    def run_dialog(self, manager, choice):
        # 真正执行 QMessageBox.exec：保留 Qt 对关闭、Esc 和按钮返回码的语义。
        dialog = QMessageBox()
        def choose():
            if choice == "close":
                dialog.close()
            elif choice == "escape":
                from PyQt6.QtTest import QTest
                QTest.keyClick(dialog, Qt.Key.Key_Escape)
            else:
                next(b for b in dialog.buttons() if b.text() == choice).click()
        with patch("app_lifecycle.QMessageBox", wraps=QMessageBox) as constructor:
            constructor.return_value = dialog
            constructor.Icon = QMessageBox.Icon
            constructor.ButtonRole = QMessageBox.ButtonRole
            QTimer.singleShot(0, choose)
            manager._quit_app()
        dialog.deleteLater()

    def test_close_escape_cancel_and_save_failure_preserve_each_state(self):
        for state in ("showing", "collapsed", "hidden"):
            for choice in ("close", "escape", "exit_cancel", "exit_save"):
                with self.subTest(state=state, choice=choice):
                    manager = self.manager(state)
                    manager.panel.save_project.return_value = False
                    manager.restore_from_background = Mock()
                    self.run_dialog(manager, choice)
                    self.assertEqual(manager.state, state)
                    manager.restore_from_background.assert_not_called()
                    manager.app.quit.assert_not_called()
                    self.assertFalse(manager._quit_dialog_showing)

    def test_repeated_close_requires_another_confirmation(self):
        manager = self.manager("hidden")
        self.run_dialog(manager, "close")
        self.run_dialog(manager, "close")
        manager.app.quit.assert_not_called()
        self.run_dialog(manager, "exit_no_save")
        manager.app.quit.assert_called_once()
        manager.panel.save_project.assert_not_called()

    def test_tray_label_defers_confirmation_until_menu_hidden(self):
        from PyQt6.QtTest import QTest
        manager = self.manager("hidden")
        manager.tray_icon = Mock()
        manager._build_tray_menu()
        label = manager._menu_labels[manager.action_quit]
        opened = []
        try:
            for _ in range(2):
                dialog = QMessageBox()
                real_exec = dialog.exec

                def exec_and_close():
                    opened.append(manager.tray_menu.isVisible())
                    QTimer.singleShot(0, dialog.close)
                    return real_exec()

                with patch("app_lifecycle.QMessageBox", wraps=QMessageBox) as constructor:
                    constructor.return_value = dialog
                    constructor.Icon = QMessageBox.Icon
                    constructor.ButtonRole = QMessageBox.ButtonRole
                    with patch.object(dialog, "exec", side_effect=exec_and_close):
                        manager.tray_menu.show()
                        self.assertTrue(manager.tray_menu.isVisible())
                        before = len(opened)
                        QTest.mousePress(label, Qt.MouseButton.LeftButton)
                        self.assertFalse(manager.tray_menu.isVisible())
                        self.assertEqual(len(opened), before)
                        self.app.processEvents()
                        self.assertEqual(len(opened), before + 1)
                dialog.deleteLater()
                self.assertEqual(manager.state, "hidden")
                manager.app.quit.assert_not_called()
                self.assertFalse(manager._quit_dialog_showing)
            self.assertEqual(opened, [False, False])
        finally:
            manager.tray_menu.hide()
            manager.tray_menu.deleteLater()

    def test_successful_save_is_required_for_save_exit(self):
        manager = self.manager()
        manager.panel.save_project.return_value = True
        self.run_dialog(manager, "exit_save")
        manager.panel.save_project.assert_called_once()
        manager.app.quit.assert_called_once()

    def test_quitting_is_idempotent_and_cannot_restore_or_hide(self):
        manager = self.manager()
        manager._do_quit(False)
        manager._do_quit(False)
        manager.restore_from_background()
        manager.hide_to_background()
        self.assertEqual(manager.state, LifecycleState.QUITTING)
        manager.app.quit.assert_called_once()
        manager.panel.show.assert_not_called()
        manager.panel.close_thumbnail_panel.assert_called_once()
        for name in ("page_rail", "toolbar_window", "logo_window", "canvas", "settings_panel"):
            getattr(manager.panel, name).hide.assert_called_once()

    def test_restart_save_failure_never_starts_or_quits(self):
        manager = self.manager()
        manager.panel.project_path = "original.msd"
        manager.panel.project_dirty = True
        manager.panel.save_project.return_value = False
        with patch("subprocess.Popen") as spawn:
            manager._restart_app()
        spawn.assert_not_called()
        manager.app.quit.assert_not_called()
        self.assertEqual(manager.panel.project_path, "original.msd")
        self.assertTrue(manager.panel.project_dirty)

    def test_failed_restart_restore_keeps_recovery_file(self):
        import tempfile
        import main
        panel = Mock()
        panel.project_path = "existing.msd"
        panel.project_dirty = True
        panel.open_project_from_path.return_value = False
        with tempfile.TemporaryDirectory() as root:
            recovery = Path(root) / "recovery.msd"
            recovery.write_text('{"recovery": true}', encoding="utf-8")
            self.assertFalse(main.ControlPanel.restore_from_restart(panel, str(recovery)))
            self.assertTrue(recovery.exists())
            self.assertEqual(panel.project_path, "existing.msd")
            self.assertTrue(panel.project_dirty)

    def test_confirmation_blocks_visibility_and_restart_reentry(self):
        manager = self.manager("hidden")
        manager._quit_dialog_showing = True
        with patch("subprocess.Popen") as spawn:
            manager.restore_from_background()
            manager.hide_to_background()
            manager._restart_app()
            manager._quit_app()
        spawn.assert_not_called()
        manager.panel.show.assert_not_called()
        manager.panel.save_project.assert_not_called()
        self.assertEqual(manager.state, "hidden")


class FloatingLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        import main
        cls.main = main
        cls.app = QApplication.instance() or QApplication([])
        cls.root = tempfile.TemporaryDirectory()
        cls.config = patch.object(main, "CONFIG_FILE", str(Path(cls.root.name) / "config.json"))
        cls.config.start()
        cls.updates = patch.object(main.ControlPanel, "check_for_updates", lambda *a, **k: None)
        cls.updates.start()
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.panel.load_settings()
        cls.panel.show()

    @classmethod
    def tearDownClass(cls):
        cls.panel.pause_callbacks()
        cls.panel.update_check_timer.stop()
        cls.panel.listener.stop()
        for widget in cls.app.topLevelWidgets():
            widget.hide()
        cls.updates.stop()
        cls.config.stop()
        cls.root.cleanup()

    def test_portrait_group_near_bottom_does_not_cover_logo(self):
        from PyQt6.QtCore import QRect
        import toolbar_windows
        panel = self.panel
        panel.set_orientation("portrait")
        panel._toolbar_detached = False
        panel.toolbar_window.show()
        panel.logo_window.move(300, 600)
        with patch.object(toolbar_windows, "_available_rect", return_value=QRect(0, 0, 1200, 800)):
            panel._sync_split_geometry()
        self.assertFalse(panel.logo_window.frameGeometry().intersects(panel.toolbar_window.frameGeometry()))
        self.assertLess(panel.logo_window.frameGeometry().bottom(), panel.toolbar_window.y())
        self.assertLessEqual(panel.toolbar_window.frameGeometry().bottom(), 799)

    def test_preview_hide_stops_timer_and_restore_does_not_reopen(self):
        panel = self.panel
        panel.canvas.enter_whiteboard()
        panel.update_whiteboard_ui()
        panel.toggle_thumbnail_panel()
        self.assertTrue(panel.thumbnail_panel.isVisible())
        self.assertTrue(panel._thumbnail_live_timer.isActive())
        panel.lifecycle.hide_to_background()
        self.assertFalse(panel.thumbnail_panel.isVisible())
        self.assertFalse(panel._thumbnail_live_timer.isActive())
        # 后台仍可更新页面模型，但不能因此重新显示轨道或恢复心跳。
        panel.update_whiteboard_ui()
        panel.resume_callbacks()
        self.assertFalse(panel.page_rail.isVisible())
        self.assertFalse(panel.timer.isActive())
        panel.lifecycle.restore_from_background()
        self.assertTrue(panel.logo_window.isVisible())
        self.assertTrue(panel.page_rail.isVisible())
        self.assertFalse(panel.thumbnail_panel.isVisible())
        self.assertIn(panel.logo_window, panel.floating_stack())
        self.assertIn(panel.page_rail, panel.floating_stack())


if __name__ == "__main__":
    unittest.main()
