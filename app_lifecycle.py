# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""应用生命周期管理：后台驻留、托盘、退出与重启。

生命周期状态：
- SHOWING: 完整显示（主面板+画布可见）
- COLLAPSED: LOGO折叠（只剩LOGO可见）
- HIDDEN: 后台隐藏（托盘图标可见，所有窗口隐藏）
- QUITTING: 退出中（防止重复退出弹窗）

后台隐藏时，所有会自动显示界面的回调（置顶心跳、定时器）必须暂停，
防止窗口自动重现。恢复时保持穿透模式，防止误画。
"""
import os
import sys
import json
import tempfile
import time
import weakref
from dataclasses import dataclass, replace
from pathlib import Path

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QWidgetAction, QLabel, QDialog, QWidget, QToolTip
from PyQt6.QtGui import QAction, QIcon, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, QRect, QAbstractEventDispatcher, QThread
from PyQt6 import sip


class LifecycleState:
    """生命周期状态枚举"""
    SHOWING = "showing"
    COLLAPSED = "collapsed"
    HIDDEN = "hidden"
    QUITTING = "quitting"


@dataclass(frozen=True)
class _TeachingWindowSnapshot:
    window: QWidget
    visible: bool
    geometry: QRect
    normal_geometry: QRect
    saved_geometry: object
    state: Qt.WindowState


@dataclass(frozen=True)
class _TeachingTimerSnapshot:
    timer: QTimer
    active: bool
    interval: int
    remaining: int
    single_shot: bool
    timer_type: Qt.TimerType


@dataclass(eq=False)
class _TeachingSuspension:
    manager_ref: object
    windows: tuple
    timers: tuple
    focus_ref: object
    restored: bool = False


class _TeachingTimerPhase(QObject):
    """Reset a resumed repeating timer's first (remaining) period, not its interval.

    QTimer.start(remaining) would change the nominal interval. Re-registering
    its existing dispatcher ID keeps QTimer's interval, activity, and genuine
    timeout delivery intact, including single-shot and stop/restart semantics.
    """

    def __init__(self, timer, dispatcher, timer_id, interval, timer_type):
        super().__init__(timer)
        self._timer_ref = weakref.ref(timer)
        self._dispatcher = dispatcher
        self._timer_id = timer_id
        self._interval = interval
        self._timer_type = timer_type
        timer.installEventFilter(self)

    def cancel(self):
        timer = self._timer_ref()
        if timer is not None and not sip.isdeleted(timer):
            timer.removeEventFilter(self)
        self.deleteLater()

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.Timer:
            return False
        if watched.timerId() != self._timer_id:
            # A callback or another owner explicitly stopped/restarted it.
            self.cancel()
            return False
        if event.timerId() != self._timer_id:
            return False
        try:
            if not watched.isSingleShot():
                if not self._dispatcher.unregisterTimer(self._timer_id):
                    raise RuntimeError("Cannot reset the teaching timer's repeating period")
                self._dispatcher.registerTimer(self._timer_id, self._interval,
                                               self._timer_type, watched)
        except Exception as error:
            # Never let an exception escape a Qt event filter (or spin a timer).
            watched.stop()
            self.cancel()
            print(f"Teaching timer resume failed: {error}", file=sys.stderr)
            return True
        self.cancel()
        return False


class _BackgroundWindowGuard(QObject):
    """Catch delayed/new tool windows without intercepting the tray menu."""

    def __init__(self, manager):
        super().__init__(manager.panel)
        self._manager_ref = weakref.ref(manager)

    def eventFilter(self, watched, event):
        # Qt may dispatch events while cyclic Python wrappers are being cleared.
        # Do not keep the panel/manager alive through a global application filter.
        manager_ref = getattr(self, "_manager_ref", None)
        manager = manager_ref() if manager_ref is not None else None
        if manager is None or not isinstance(watched, QWidget):
            return False
        suspended = getattr(manager.panel, "_teaching_suspended", False)
        context = getattr(manager.panel, "runtime_context", None)
        paths = getattr(context, "paths", None)
        inactive = context is not None and not context.ui_active
        if (event.type() == QEvent.Type.Show and watched.isWindow()
                and manager._owns_window(watched)):
            allowed_restore = watched in getattr(manager, "_teaching_restore_windows", ())
            allowed_recovery = (suspended and not inactive
                                and watched in getattr(manager, "_teaching_recovery_windows", ()))
            allowed_practice = (suspended and not inactive and context is not None
                                and getattr(paths, "practice", False) is True
                                and watched in manager._practice_teaching_windows)
            if not (allowed_restore or allowed_recovery or allowed_practice) and (suspended or inactive or (
                    manager.state == LifecycleState.HIDDEN
                    and not manager._allowed_in_background(watched))):
                watched.hide()
            elif watched.isVisible():
                manager._queue_teaching_raise(watched)
        elif manager.state == LifecycleState.HIDDEN and not suspended:
            if (event.type() == QEvent.Type.Close or (
                    event.type() == QEvent.Type.Hide
                    and watched in manager._background_allowed_windows)):
                manager._forget_closed_window(watched)
        return False


class AppLifecycleManager:
    """应用生命周期管理器：托盘图标、右键菜单、退出/重启对话框。

    托盘右键菜单固定四项，自定义颜色：
    1. 显示主界面 / 隐藏主界面（黑色）
    2. 打开设置（黑色）
    3. --- 分割线 ---
    4. 重启软件（蓝色 #0066cc）
    5. 退出软件（粗体红色 #cc0000）
    """

    def __init__(self, panel):
        """
        Args:
            panel: ControlPanel主面板
        """
        self.panel = panel
        self.state = LifecycleState.SHOWING
        self._state_before_hidden = self.state
        self.tray_icon = None
        self.tray_menu = None

        # 退出对话框防重入
        self._quit_dialog_showing = False

        # 从panel获取app和翻译函数
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance()

        self._restore_windows = []
        self._background_allowed_windows = weakref.WeakSet()
        self._tool_windows = weakref.WeakSet()
        self._teaching_token = None
        self._teaching_restoring = False
        self._teaching_restore_windows = weakref.WeakSet()
        self._teaching_recovery_windows = weakref.WeakSet()
        self._practice_teaching_windows = weakref.WeakSet()
        self._teaching_windows = []
        self._teaching_raise_pending = weakref.WeakSet()
        self._teaching_timer_phases = []
        self._window_guard = _BackgroundWindowGuard(self)
        self.app.installEventFilter(self._window_guard)
        self._setup_tray()

    def _setup_tray(self):
        """初始化托盘图标和菜单"""
        context = getattr(self.panel, "runtime_context", None)
        if context is not None and not context.tray:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("WARNING: System tray not available. Background mode disabled.",
                  file=sys.stderr)
            return

        # 托盘图标：使用主面板的LOGO生成方法，确保颜色一致
        logo_icon = self.panel._make_logo_icon(size=64)
        self.tray_icon = QSystemTrayIcon(logo_icon, self.app)

        # 左键单击：恢复完整主界面
        self.tray_icon.activated.connect(self._on_tray_activated)

        # 右键菜单
        self._build_tray_menu()

        self.tray_icon.show()

    def _build_tray_menu(self):
        """构建托盘右键菜单，自定义颜色"""
        self.tray_menu = QMenu()

        # 强制亮色背景，确保黑/蓝/红文字清晰可见
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
            QMenu::item {
                padding: 6px 32px 6px 12px;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
            QMenu::separator {
                height: 1px;
                background: #d0d0d0;
                margin: 4px 0px;
            }
        """)

        # 1. 显示/隐藏主界面（黑色）
        self.action_toggle_ui = QAction(self._tr("show_main_ui"), self.tray_menu)
        self.action_toggle_ui.triggered.connect(self._toggle_main_ui)
        self._style_action(self.action_toggle_ui, "#000000", bold=False)
        self.tray_menu.addAction(self.action_toggle_ui)

        # 2. 打开设置（黑色）
        self.action_settings = QAction(self._tr("settings"), self.tray_menu)
        self.action_settings.triggered.connect(self._open_settings_from_tray)
        self._style_action(self.action_settings, "#000000", bold=False)
        self.tray_menu.addAction(self.action_settings)

        # 3. 分割线
        self.tray_menu.addSeparator()

        # 4. 重启软件（蓝色）
        self.action_restart = QAction(self._tr("restart_app"), self.tray_menu)
        self.action_restart.triggered.connect(self._restart_app)
        self._style_action(self.action_restart, "#0066cc", bold=False)
        self.tray_menu.addAction(self.action_restart)

        # 5. 退出软件（粗体红色）
        self.action_quit = QAction(self._tr("quit_app"), self.tray_menu)
        self.action_quit.triggered.connect(self._quit_app)
        self._style_action(self.action_quit, "#cc0000", bold=True)
        self.tray_menu.addAction(self.action_quit)

        self.tray_icon.setContextMenu(self.tray_menu)

        # 应用样式：每个action单独设置颜色
        self._apply_menu_colors()

    def _tr(self, key):
        """翻译函数包装器"""
        from main import tr
        return tr(key)

    def _style_action(self, action, color, bold):
        """给菜单项设置颜色和粗体"""
        font = QFont()
        font.setBold(bold)
        action.setFont(font)

        # 存储颜色信息，稍后通过样式表统一设置
        action.setProperty("menu_color", color)
        action.setProperty("menu_bold", bold)

    def _apply_menu_colors(self):
        """应用菜单颜色：通过单独的样式表设置每个action"""
        self._menu_labels = {}
        # 为每个有颜色属性的action创建自定义widget
        for action in self.tray_menu.actions():
            if action.isSeparator():
                continue
            color = action.property("menu_color")
            if color:
                # 使用QWidgetAction包装，可以完全自定义样式
                text = action.text()
                bold = action.property("menu_bold")

                # 创建一个标签显示文本
                label = QLabel(text)
                label.setStyleSheet(f"""
                    QLabel {{
                        color: {color};
                        font-weight: {'bold' if bold else 'normal'};
                        padding: 4px 20px;
                        background: transparent;
                    }}
                    QLabel:hover {{
                        background: #e0e0e0;
                    }}
                """)
                label.setMinimumHeight(24)

                # 创建widget action替换原action
                widget_action = QWidgetAction(self.tray_menu)
                widget_action.setDefaultWidget(label)

                # 保持原来的triggered信号
                def make_trigger(orig_action):
                    def trigger():
                        orig_action.trigger()
                    return trigger

                def on_label_pressed(event, fn=make_trigger(action)):
                    # 先结束托盘菜单的嵌套事件循环，再排队打开退出确认框。
                    # 否则 QMessageBox.exec() 期间仍处于菜单事件循环，第二次点击
                    # 可能重入退出路径并绕过确认。
                    self.tray_menu.hide()
                    QTimer.singleShot(0, fn)

                label.mousePressEvent = on_label_pressed

                # 替换action
                self.tray_menu.insertAction(action, widget_action)
                self.tray_menu.removeAction(action)
                self._menu_labels[action] = label

    def _set_action_text(self, action, text):
        """改菜单项文字：原 action 已被 QWidgetAction 的标签顶替，只改 action 用户看不到。"""
        action.setText(text)
        label = getattr(self, "_menu_labels", {}).get(action)
        if label is not None:
            label.setText(text)

    def _teaching_coordinator(self):
        coordinator = getattr(self.panel, "teaching_coordinator", None)
        if isinstance(coordinator, QObject) and not sip.isdeleted(coordinator):
            return coordinator
        return None

    def _on_tray_activated(self, reason):
        """托盘图标激活：左键单击恢复完整主界面"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.restore_from_background()

    def _toggle_main_ui(self):
        """切换显示/隐藏主界面"""
        coordinator = self._teaching_coordinator()
        hidden = (coordinator.background_hidden if coordinator is not None and coordinator.active
                  else self.state == LifecycleState.HIDDEN)
        if hidden:
            self.restore_from_background()
        else:
            self.hide_to_background()

    def _open_settings_from_tray(self):
        """从托盘打开设置（后台也能打开）"""
        coordinator = self._teaching_coordinator()
        if getattr(self, "_teaching_token", None) is not None or coordinator is not None and coordinator.active:
            return
        if self.state == LifecycleState.HIDDEN:
            # 后台状态：设置页懒创建后再显示，不恢复主面板。
            if self.panel.settings_panel is None:
                self.panel.build_settings_panel()
            self._background_allowed_windows.add(self.panel.settings_panel)
            self.panel.open_settings_panel()
        else:
            # 前台状态：正常打开
            self.panel.open_settings_panel()

    def _route_teaching_action(self, action):
        coordinator = self._teaching_coordinator()
        if coordinator is not None and coordinator.request_lifecycle_action(action):
            return True
        # A lost coordinator cannot authorize mutation of a suspended original.
        return getattr(self, "_teaching_token", None) is not None

    def _restart_app(self):
        """重启软件：保留当前未保存工作"""
        context = getattr(self.panel, "runtime_context", None)
        if context is not None and not context.ordinary_recovery:
            return
        if self._route_teaching_action("restart"):
            return
        if self._quit_dialog_showing or self.state == LifecycleState.QUITTING:
            return
        import subprocess
        import sys
        import os
        import tempfile

        # 保存当前状态到临时恢复文件
        recovery_file = os.path.join(tempfile.gettempdir(),
                                     f'myscreendraw_restart_{os.getpid()}.msd')
        original_path = self.panel.project_path
        original_dirty = self.panel.project_dirty
        original_signature = getattr(self.panel, "_saved_document_signature", None)
        original_title = self.panel.windowTitle()
        try:
            success = self.panel.save_project(recovery_file)
        except Exception:
            success = False
        finally:
            # 临时快照不能改变用户当前文件的保存目标或未保存标记。
            self.panel.project_path = original_path
            self.panel.project_dirty = original_dirty
            self.panel._saved_document_signature = original_signature
            self.panel.setWindowTitle(original_title)
        if not success:
            # 保存失败时继续重启会丢掉所有未保存工作，必须留在当前进程。
            return

        # 构建启动命令
        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            launcher = sys.executable
            candidate = os.path.join(os.path.dirname(launcher), "pythonw.exe")
            if os.path.exists(candidate):
                launcher = candidate
            # 入口是 main.py，不是本文件：拉起 app_lifecycle.py 只会静默退出
            entry = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            cmd = [launcher, entry]

        if recovery_file:
            cmd.extend(['--restore', recovery_file])

        # 启动新进程
        try:
            subprocess.Popen(cmd,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        except Exception:
            # 启动失败：清理临时文件并留在程序里
            if recovery_file and os.path.exists(recovery_file):
                try:
                    os.remove(recovery_file)
                except Exception:
                    pass
            return

        # 新进程启动成功：退出旧进程（不保存，因为已经保存到临时文件）
        self._do_quit(save=False)

    def _quit_app(self):
        """退出软件：显示保存提示"""
        if self._route_teaching_action("quit"):
            return
        if self._quit_dialog_showing or self.state == LifecycleState.QUITTING:
            return

        self._quit_dialog_showing = True
        state_before_quit = self.state

        def stay_in_app():
            # 取消退出必须保持打开确认框前的真实状态；后台状态不能被取消操作唤回前台。
            self.state = state_before_quit

        try:
            # 暂停可能改动状态的回调
            self.panel.pause_callbacks()

            # 保存提示对话框
            dialog = QMessageBox(self.panel)
            dialog.setWindowTitle(self._tr("exit_title"))
            dialog.setText(self._tr("exit_prompt"))
            dialog.setIcon(QMessageBox.Icon.Question)
            # 主面板是置顶 Tool 窗口，对话框不置顶的话会开在全屏画布/工具栏底下
            dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

            # 三个按钮
            btn_cancel = dialog.addButton(self._tr("exit_cancel"),
                                         QMessageBox.ButtonRole.RejectRole)
            btn_quit_directly = dialog.addButton(self._tr("exit_no_save"),
                                                QMessageBox.ButtonRole.DestructiveRole)
            btn_save_and_quit = dialog.addButton(self._tr("exit_save"),
                                                QMessageBox.ButtonRole.AcceptRole)
            dialog.setDefaultButton(btn_save_and_quit)
            dialog.setEscapeButton(btn_cancel)

            # 直接退出是破坏性操作，单独标红；另外两个按钮保持普通样式。
            btn_quit_directly.setStyleSheet("color: #ffffff; background-color: #d64545; font-weight: bold;")
            result = dialog.exec()
            clicked = dialog.clickedButton()
            # 点右上角关闭按钮时 Qt 返回 Rejected 且 clickedButton() 为空。
            # 这种情况只表示取消退出，绝不能把整个程序一起关掉。
            if result == QDialog.DialogCode.Rejected or clicked is None or clicked == btn_cancel:

                stay_in_app()
            elif clicked == btn_quit_directly:
                # 直接退出：不保存
                self._do_quit(save=False)
            elif clicked == btn_save_and_quit:
                # 保存退出
                success = self.panel.save_project()
                if success:
                    self._do_quit(save=True)
                else:
                    # 保存失败：留在程序里
                    stay_in_app()
            else:
                stay_in_app()
        finally:
            self._quit_dialog_showing = False
            if not getattr(self, "_quit_done", False):
                if self.state == LifecycleState.QUITTING:
                    self.state = LifecycleState.SHOWING
                self.panel.resume_callbacks()

    def _do_quit(self, save):
        """执行退出清理"""
        if self._route_teaching_action("quit"):
            return
        if getattr(self, "_quit_done", False):
            return
        self._quit_done = True
        self.state = LifecycleState.QUITTING
        # 停止所有定时器和监听器
        try:
            self.panel.listener.stop()
        except Exception:
            pass
        try:
            self.panel.timer.stop()
        except Exception:
            pass
        try:
            self.panel.autosave_timer.stop()
        except Exception:
            pass
        # 所有独立顶层浮窗必须在 QApplication.quit() 前收走；否则 Windows 上
        # 它们可能在退出过渡期继续显示，尤其是页面预览窗口。
        try:
            self.panel.close_thumbnail_panel()
        except Exception:
            pass
        for name in (
            "page_rail", "menu_panel", "select_panel", "settings_panel",
            "text_panel", "calc_panel", "roster_panel", "mini_timer",
            "toolbar_window", "logo_window", "canvas", "panel",
        ):
            try:
                window = self.panel if name == "panel" else getattr(self.panel, name, None)
                if window is not None:
                    window.hide()
            except Exception:
                pass

        # Let already-started atomic autosaves finish before files/process exit.
        shutdown_autosave = getattr(self.panel, "shutdown_autosave", None)
        if shutdown_autosave is not None:
            shutdown_autosave()

        # 清理托盘图标
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()

        # 退出应用
        self.app.quit()

    def register_tool_window(self, window):
        """Track ownership without Qt parenting (native stacking owns the tools)."""
        self._tool_windows.add(window)

    def teaching_windows(self):
        windows = [ref() for ref in self._teaching_windows]
        windows = [window for window in windows if window is not None and not sip.isdeleted(window)]
        self._teaching_windows = [weakref.ref(window) for window in windows]
        # Recent dialogs go first; input-transparent highlights cannot cover controls.
        newest = list(reversed(windows))
        return tuple(window for window in newest
                     if not window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)) + tuple(
                     window for window in newest
                     if window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def register_teaching_window(self, window):
        if (not isinstance(window, QWidget) or sip.isdeleted(window) or not window.isWindow()
                or QThread.currentThread() != self.panel.thread()):
            raise ValueError("Teaching layer requires a live top-level window on the GUI thread")
        self.register_tool_window(window)
        if not any(existing is window for existing in self.teaching_windows()):
            self._teaching_windows.append(weakref.ref(window))
            self.panel._bound_key = None
        if window.isVisible():
            self._queue_teaching_raise(window)

    def _queue_teaching_raise(self, window):
        if (window not in self.teaching_windows() or window in self._teaching_raise_pending):
            return
        self._teaching_raise_pending.add(window)
        manager_ref, window_ref = weakref.ref(self), weakref.ref(window)
        def raise_later():
            manager = manager_ref()
            if manager is None:
                return
            current = window_ref()
            if current is not None:
                manager._teaching_raise_pending.discard(current)
                manager._raise_teaching_window(current)
        QTimer.singleShot(0, raise_later)

    def _raise_teaching_window(self, window):
        if (sip.isdeleted(self.panel) or window is None or sip.isdeleted(window)
                or window not in self.teaching_windows() or not window.isVisible()
                or self.state in (LifecycleState.HIDDEN, LifecycleState.QUITTING)):
            return False
        context = getattr(self.panel, "runtime_context", None)
        if context is not None and not context.ui_active:
            return False
        if (getattr(self.panel, "_teaching_suspended", False)
                and window not in self._practice_teaching_windows
                and window not in self._teaching_recovery_windows):
            return False
        raise_window = getattr(self.panel, "raise_floating", None)
        if not callable(raise_window):
            return False
        try:
            raise_window(window)
        except Exception:
            return False
        return True

    def unregister_tool_window(self, window):
        """Release explicit ownership/allowance, without touching other windows."""
        self._tool_windows.discard(window)
        self._background_allowed_windows.discard(window)
        self._teaching_recovery_windows.discard(window)
        self._practice_teaching_windows.discard(window)
        self._teaching_windows = [ref for ref in self._teaching_windows if ref() is not None and ref() is not window]
        self._teaching_raise_pending.discard(window)
        self.panel._bound_key = None

    def allow_practice_teaching_window(self, window):
        """Trusted active child views only; original parent UI cannot use this exemption."""
        context = getattr(self.panel, "runtime_context", None)
        paths = getattr(context, "paths", None)
        if (context is None or getattr(paths, "practice", False) is not True or not context.ui_active
                or QThread.currentThread() != self.panel.thread()
                or not isinstance(window, QWidget) or sip.isdeleted(window)
                or not window.isWindow() or not self._owns_window(window)):
            raise ValueError("An active owned practice teaching window is required")
        self.register_teaching_window(window)
        self._practice_teaching_windows.add(window)

    def allow_teaching_recovery_window(self, window):
        """Trusted parent UI only: broker must already confirm child NotRunning.

        This is not a course/IPC capability. Only this exact owned top-level
        prompt is exempted while suspended; inactive practice UI stays blocked.
        """
        if QThread.currentThread() != self.panel.thread():
            raise RuntimeError("Teaching recovery UI must run on the panel's Qt thread")
        if not isinstance(window, QWidget) or sip.isdeleted(window) or not window.isWindow():
            raise ValueError("Teaching recovery prompt must be a live top-level QWidget")
        self.register_teaching_window(window)
        self._teaching_recovery_windows.add(window)

    def disallow_teaching_recovery_window(self, window):
        """Revoke just this prompt's bypass; keep ownership until explicit teardown.

        Keeping ownership prevents a parentless prompt from evading the guard
        as a foreign window. The caller can unregister it after hiding/deleting.
        """
        if QThread.currentThread() != self.panel.thread():
            raise RuntimeError("Teaching recovery UI must run on the panel's Qt thread")
        self._teaching_recovery_windows.discard(window)
        if (isinstance(window, QWidget) and not sip.isdeleted(window)
                and self._owns_window(window) and getattr(self.panel, "_teaching_suspended", False)):
            window.hide()

    def _owns_window(self, window):
        # Tool windows historically have no Qt parent; discover those through
        # their owning panel as well as normal parent chains (dialogs/popups).
        if not isinstance(self.panel, QWidget) or sip.isdeleted(self.panel):
            return False
        roots = [self.panel] + [value for value in vars(self.panel).values()
                               if isinstance(value, QWidget) and not sip.isdeleted(value)]
        roots.extend(tool for tool in self._tool_windows if not sip.isdeleted(tool))
        current = window
        while current is not None:
            if current is self.tray_menu:
                return False
            if current in roots:
                return True
            current = current.parentWidget()
        return False

    def _forget_closed_window(self, closed):
        def belongs(window):
            return (window is not None and not sip.isdeleted(window)
                    and (window is closed or closed.isAncestorOf(window)))
        self._restore_windows = [ref for ref in self._restore_windows if not belongs(ref())]
        for window in list(self._background_allowed_windows):
            if belongs(window):
                self._background_allowed_windows.discard(window)

    def _allowed_in_background(self, window):
        # Only explicit tray actions may open UI while hidden. In particular,
        # quit/save confirmation dialogs must not become invisible modal loops.
        current = window
        while current is not None:
            if current in self._background_allowed_windows:
                return True
            if self._quit_dialog_showing and isinstance(current, QDialog):
                return True
            current = current.parentWidget()
        return False

    def _owned_windows(self):
        return [window for window in self.app.topLevelWidgets()
                if not sip.isdeleted(window) and self._owns_window(window)]

    def _owned_timers(self, windows=None):
        """Only this panel's QObject trees and explicitly held parentless timers."""
        roots = [self.panel] + list(self._owned_windows() if windows is None else windows)
        coordinator = getattr(self.panel, "teaching_coordinator", None)
        if not isinstance(coordinator, QObject) or sip.isdeleted(coordinator):
            coordinator = None

        def teaching_transport_timer(timer):
            # This explicit trusted parent owns broker/transport deadlines, not
            # the business UI. They must run through suspension and session
            # cleanup, and must never become part of a restoration token.
            parent = timer
            while parent is not None:
                if parent is coordinator:
                    return True
                parent = parent.parent()
            return False

        timers = {}
        for root in roots:
            if sip.isdeleted(root):
                continue
            for timer in root.findChildren(QTimer):
                if not sip.isdeleted(timer) and not teaching_transport_timer(timer):
                    timers[id(timer)] = timer
            for value in vars(root).values():
                if (not isinstance(value, QTimer) or sip.isdeleted(value)
                        or teaching_transport_timer(value)):
                    continue
                parent = value.parent()
                while parent is not None and parent not in roots:
                    parent = parent.parent()
                if parent in roots or value.parent() is None:
                    timers[id(value)] = value
        return list(timers.values())

    def _cancel_teaching_timer_phases(self):
        phases, self._teaching_timer_phases = self._teaching_timer_phases, []
        for phase in phases:
            if not sip.isdeleted(phase):
                phase.cancel()

    def suspend_for_teaching(self):
        """Hide owned UI and pause QTimers without editing the document/state.

        The opaque token belongs to this manager. Repeated suspension raises
        RuntimeError instead of replacing the original snapshot. Use on the Qt
        GUI thread, just like the normal lifecycle's hide/show operations.
        """
        if self._teaching_token is not None or getattr(self.panel, "_teaching_suspended", False):
            raise RuntimeError("This panel is already suspended for teaching")
        if QThread.currentThread() != self.panel.thread():
            raise RuntimeError("Teaching suspension must run on the panel's Qt thread")
        windows = self._owned_windows()
        timers = self._owned_timers(windows)
        if any(timer.thread() != QThread.currentThread() for timer in timers):
            raise RuntimeError("Owned teaching timers must run on the panel's Qt thread")
        focus = self.app.focusWidget()
        token = _TeachingSuspension(
            weakref.ref(self),
            tuple(_TeachingWindowSnapshot(window, window.isVisible(), QRect(window.geometry()),
                                          QRect(window.normalGeometry()), window.saveGeometry(),
                                          window.windowState()) for window in windows),
            tuple(_TeachingTimerSnapshot(timer, timer.isActive(), timer.interval(),
                                         timer.remainingTime(), timer.isSingleShot(), timer.timerType())
                  for timer in timers),
            weakref.ref(focus) if focus is not None and self._owns_window(focus) else None,
        )
        self._teaching_token = token
        self.panel._teaching_suspended = True
        try:
            self._cancel_teaching_timer_phases()
            for timer in timers:
                timer.stop()
            for window in windows:
                window.hide()
            # hideEvent callbacks can create/restart timers; leave them stopped.
            for timer in self._owned_timers():
                timer.stop()
        except Exception as error:
            for rollback_error in self._teaching_fail_closed(token):
                error.add_note(f"Teaching suspension cleanup failed: {rollback_error}")
            raise
        return token

    def _teaching_fail_closed(self, token):
        """Best-effort rollback; do not let one broken widget leave others live."""
        self.panel._teaching_suspended = True
        self._teaching_restore_windows.clear()
        errors = []
        try:
            self._cancel_teaching_timer_phases()
        except Exception as error:
            errors.append(error)
        windows = {id(snapshot.window): snapshot.window for snapshot in token.windows}
        timers = {id(snapshot.timer): snapshot.timer for snapshot in token.timers}
        try:
            windows.update((id(window), window) for window in self._owned_windows())
            timers.update((id(timer), timer) for timer in self._owned_timers())
        except Exception as error:
            errors.append(error)
        for timer in timers.values():
            if not sip.isdeleted(timer):
                try:
                    timer.stop()
                except Exception as error:
                    errors.append(error)
        for window in windows.values():
            if not sip.isdeleted(window):
                try:
                    window.hide()
                except Exception as error:
                    errors.append(error)
        # Hide handlers may create as well as restart timers during rollback.
        try:
            timers.update((id(timer), timer) for timer in self._owned_timers())
        except Exception as error:
            errors.append(error)
        for timer in timers.values():
            if not sip.isdeleted(timer):
                try:
                    timer.stop()
                except Exception as error:
                    errors.append(error)
        return errors

    def _restore_teaching_windows(self, token):
        def depth(snapshot):
            count, parent = 0, snapshot.window.parentWidget()
            while parent is not None:
                count += 1
                parent = parent.parentWidget()
            return count
        for snapshot in sorted(token.windows, key=depth):
            window = snapshot.window
            unchanged_stateful = (
                snapshot.state != Qt.WindowState.WindowNoState
                and window.windowState() == snapshot.state
                and window.geometry() == snapshot.geometry
                and window.normalGeometry() == snapshot.normal_geometry)
            # hide() retains these properties. Reconstructing an already exact
            # fullscreen/no-focus window can instead make Qt restore its normal
            # geometry or clear fullscreen; leave that state untouched.
            if not unchanged_stateful:
                window.setWindowState(Qt.WindowState.WindowNoState)
                window.setGeometry(snapshot.normal_geometry if snapshot.normal_geometry.isValid()
                                   else snapshot.geometry)
                if not window.restoreGeometry(snapshot.saved_geometry):
                    raise RuntimeError("Cannot restore an owned teaching window's geometry")
                window.setWindowState(snapshot.state)
                if snapshot.state == Qt.WindowState.WindowNoState and window.geometry() != snapshot.geometry:
                    window.setGeometry(snapshot.geometry)
            if snapshot.visible:
                window.show()
            else:
                window.hide()
            if (window.isVisible() != snapshot.visible or window.windowState() != snapshot.state
                    or window.geometry() != snapshot.geometry):
                raise RuntimeError(
                    "Cannot restore an owned teaching window's visibility/state/geometry: "
                    f"{type(window).__name__}, expected "
                    f"{snapshot.visible}/{snapshot.state}/{snapshot.geometry}, got "
                    f"{window.isVisible()}/{window.windowState()}/{window.geometry()}")

    def _restore_teaching_timer(self, snapshot):
        timer = snapshot.timer
        timer.stop()
        timer.setInterval(snapshot.interval)
        timer.setSingleShot(snapshot.single_shot)
        timer.setTimerType(snapshot.timer_type)
        if (timer.interval() != snapshot.interval or timer.isSingleShot() != snapshot.single_shot
                or timer.timerType() != snapshot.timer_type):
            raise RuntimeError("Cannot restore an owned teaching timer's configuration")
        if not snapshot.active:
            return
        timer.start()
        if not timer.isActive():
            raise RuntimeError("Cannot restart an owned teaching timer")
        if snapshot.remaining < 0 or snapshot.remaining == snapshot.interval:
            return
        dispatcher = QAbstractEventDispatcher.instance(timer.thread())
        timer_id = timer.timerId()
        if dispatcher is None or not dispatcher.unregisterTimer(timer_id):
            raise RuntimeError("Cannot restore an owned teaching timer's remaining deadline")
        dispatcher.registerTimer(timer_id, snapshot.remaining, snapshot.timer_type, timer)
        if timer.remainingTime() < 0:
            raise RuntimeError("Cannot register an owned teaching timer's remaining deadline")
        if not snapshot.single_shot:
            self._teaching_timer_phases.append(_TeachingTimerPhase(
                timer, dispatcher, timer_id, snapshot.interval, snapshot.timer_type))

    def restore_practice_after_chapter_change(self, token):
        """Rebuild this child's UI sizes; original-work restoration remains exact."""
        context = getattr(self.panel, "runtime_context", None)
        paths = getattr(context, "paths", None)
        if (context is None or not context.ui_active or getattr(paths, "practice", False) is not True):
            raise ValueError("Chapter layout rebuilding requires an active private practice")
        if (not isinstance(token, _TeachingSuspension) or token.manager_ref() is not self
                or not token.restored and self._teaching_token is not token):
            raise ValueError("Private chapter token belongs to this manager only")
        if QThread.currentThread() != self.panel.thread() or self._teaching_restoring:
            raise RuntimeError("Private chapter rebuilding requires the idle GUI thread")
        if token.restored:
            return
        snapshots = []
        canvas = getattr(self.panel, "canvas", None)
        for snapshot in token.windows:
            window = snapshot.window
            if sip.isdeleted(window):
                raise RuntimeError("A private chapter window was destroyed")
            if window is not canvas and snapshot.state == Qt.WindowState.WindowNoState:
                geometry = QRect(snapshot.geometry.topLeft(), window.size())
                normal = QRect(snapshot.normal_geometry)
                if normal.isValid():
                    normal.setSize(window.size())
                snapshot = replace(snapshot, geometry=geometry, normal_geometry=normal)
            snapshots.append(snapshot)
        token.windows = tuple(snapshots)
        self.restore_after_teaching(token)

    def restore_after_teaching(self, token):
        """Restore this manager's snapshot, or raise and keep it retryable/hidden.

        Successful tokens are idempotent, even if a later suspension is active.
        Invalid/foreign tokens raise ValueError; reentrant restoration raises
        RuntimeError. No document editing, normal background restore, or listener
        shutdown occurs here. The input barrier stays up until every step succeeds.
        """
        if not isinstance(token, _TeachingSuspension) or token.manager_ref() is not self:
            raise ValueError("Teaching token belongs to a different lifecycle manager")
        if token.restored:
            return
        if self._teaching_token is not token:
            raise ValueError("Teaching token is not this manager's active suspension")
        if self._teaching_restoring:
            raise RuntimeError("Teaching restoration is already in progress")
        if QThread.currentThread() != self.panel.thread():
            raise RuntimeError("Teaching restoration must run on the panel's Qt thread")
        current_focus = self.app.focusWidget()
        foreign_focus = (current_focus is not None and current_focus.isVisible()
                         and not self._owns_window(current_focus))
        self.panel._teaching_suspended = True
        self._teaching_restoring = True
        self._teaching_restore_windows = weakref.WeakSet(
            snapshot.window for snapshot in token.windows if snapshot.visible)
        try:
            if any(sip.isdeleted(snapshot.window) for snapshot in token.windows):
                raise RuntimeError("An owned teaching window was destroyed while suspended")
            if any(sip.isdeleted(snapshot.timer) for snapshot in token.timers):
                raise RuntimeError("An owned teaching timer was destroyed while suspended")
            self._cancel_teaching_timer_phases()
            for timer in self._owned_timers():
                timer.stop()
            self._restore_teaching_windows(token)
            bind = getattr(self.panel, "bind_topmost_stack", None)
            if bind is not None:
                self.panel._bound_key = None
                result = bind()
                # The existing binding method catches its own native errors.
                if result is False or getattr(self.panel, "_topmost_error", False):
                    raise RuntimeError("Cannot rebind the restored teaching window stack")
            self._restore_teaching_windows(token)
            for timer in self._owned_timers():
                timer.stop()
            focus = token.focus_ref() if token.focus_ref is not None else None
            if (not foreign_focus and focus is not None and not sip.isdeleted(focus)
                    and self._owns_window(focus) and focus.isVisible() and focus.isEnabled()
                    and focus.window() in self._teaching_restore_windows):
                focus.window().activateWindow()
                focus.setFocus(Qt.FocusReason.OtherFocusReason)
            # Focus/activation handlers can run nested event loops. Only restart
            # the original timers once all such UI work has finished.
            for snapshot in token.timers:
                self._restore_teaching_timer(snapshot)
            if hasattr(self.panel, "_timer_last"):
                self.panel._timer_last = time.monotonic()
        except Exception as error:
            for rollback_error in self._teaching_fail_closed(token):
                error.add_note(f"Teaching restoration cleanup failed: {rollback_error}")
            raise
        else:
            token.restored = True
            self._teaching_token = None
            self.panel._teaching_suspended = False
        finally:
            self._teaching_restore_windows.clear()
            self._teaching_restoring = False

    def _remember_tool_windows(self):
        # Selection, text editing, menus and thumbnail previews are transient:
        # switching to safe mouse mode intentionally ends those interactions.
        managed = [self.panel] + [getattr(self.panel, name, None) for name in (
            "canvas", "logo_window", "toolbar_window", "page_rail", "menu_panel",
            "select_panel", "text_panel", "thumbnail_panel", "_name_projection")]
        self._restore_windows = [weakref.ref(window) for window in self._owned_windows()
                                 if window.isVisible() and window not in managed
                                 and window.windowType() not in (Qt.WindowType.Popup, Qt.WindowType.ToolTip)]

    def hide_to_background(self):
        """转入后台：隐藏所有窗口，保持托盘图标"""
        coordinator = self._teaching_coordinator()
        if coordinator is not None and coordinator.hide_to_background():
            return
        if getattr(self, "_teaching_token", None) is not None:
            return
        if self._quit_dialog_showing or self.state in (LifecycleState.HIDDEN, LifecycleState.QUITTING):
            return

        self._state_before_hidden = self.state
        self._background_allowed_windows.clear()
        self._remember_tool_windows()
        if hasattr(self.panel, 'canvas') and self.panel.canvas and self.panel.canvas.editing_text_item():
            self.panel.canvas.end_text_edit(discard_empty=True)

        # 在任何延迟心跳/重排回调运行前先建立 HIDDEN 状态，回调即可安全早退。
        self.state = LifecycleState.HIDDEN

        # 进入穿透模式
        self.panel.set_drawing_mode(False)

        # 隐藏所有窗口（包括分体窗口）
        self.panel.close_thumbnail_panel()
        self.panel._close_name_projection()
        if self.panel.canvas:
            self.panel.canvas.hide()
        self.panel.hide()
        if hasattr(self.panel, 'logo_window') and self.panel.logo_window:
            self.panel.logo_window.hide()
        if hasattr(self.panel, 'toolbar_window') and self.panel.toolbar_window:
            self.panel.toolbar_window.hide()
        if hasattr(self.panel, 'page_rail') and self.panel.page_rail:
            self.panel.page_rail.hide()
        if hasattr(self.panel, 'settings_panel') and self.panel.settings_panel:
            self.panel.settings_panel.hide()
        # 隐藏所有子菜单
        self.panel.show_only_sub(None)

        # Cover every owned top-level window, including dialogs and tools added
        # later. The event filter prevents timer callbacks from showing them again.
        for window in self._owned_windows():
            window.hide()
        QToolTip.hideText()

        # 隐藏软键盘
        if hasattr(self.panel, '_keyboard_process') and self.panel._keyboard_process:
            try:
                self.panel._keyboard_process.terminate()
                self.panel._keyboard_process = None
            except Exception:
                pass

        # 更新托盘菜单文字
        if hasattr(self, 'action_toggle_ui') and self.action_toggle_ui:
            self._set_action_text(self.action_toggle_ui, self._tr("show_main_ui"))

        # 暂停心跳和定时器
        self.panel.pause_callbacks()

    def restore_from_background(self):
        """从后台恢复完整主界面"""
        coordinator = self._teaching_coordinator()
        if coordinator is not None and coordinator.restore_from_background():
            return
        if getattr(self, "_teaching_token", None) is not None:
            return
        if self._quit_dialog_showing or self.state in (LifecycleState.SHOWING, LifecycleState.QUITTING):
            return

        was_collapsed = (self.state == LifecycleState.HIDDEN
                         and self._state_before_hidden == LifecycleState.COLLAPSED)
        self._background_allowed_windows.clear()
        # Lift the background guard before showing any window or syncing geometry.
        self.state = LifecycleState.COLLAPSED if was_collapsed else LifecycleState.SHOWING

        # 画布也要回来：进后台时把它藏了，不重新显示的话已有批注全部不见，用户要再
        # 点一次绘图模式才「找回」墨迹。此时仍是穿透模式，显示出来不拦点击。
        if hasattr(self.panel, 'canvas') and self.panel.canvas:
            self.panel.canvas.show()
        self.panel.show()
        # 恢复 LOGO；只有进入后台前是完整显示时才恢复工具栏。
        if hasattr(self.panel, 'logo_window') and self.panel.logo_window:
            self.panel.logo_window.show()
        if hasattr(self.panel, 'toolbar_window') and self.panel.toolbar_window:
            if was_collapsed:
                self.panel.toolbar_window.hide()
            else:
                self.panel.toolbar_window.show()
        if hasattr(self.panel, '_sync_split_geometry'):
            self.panel._sync_split_geometry()
        if getattr(self.panel, "page_rail", None) is not None:
            if self.panel.canvas and self.panel.canvas.whiteboard_mode:
                self.panel.page_rail.show()
                self.panel._position_page_rail()
            else:
                self.panel.page_rail.hide()

        # 保持穿透模式，直到用户主动选择绘图工具
        # （防止恢复时误画）

        saved_windows, self._restore_windows = self._restore_windows, []
        # Parents first, then modal/child tool windows, without reopening closed tools.
        windows = [ref() for ref in saved_windows]
        windows = [window for window in windows if window is not None and not sip.isdeleted(window)]
        def depth(window):
            count = 0
            while window.parentWidget() is not None:
                count += 1
                window = window.parentWidget()
            return count
        for window in sorted(windows, key=depth):
            window.show()
        # hide()/show() 后 Qt 可能把 GWLP_HWNDPARENT 重置，整组窗口重新挂回画布之上
        self.panel._bound_key = None
        if hasattr(self.panel, 'bind_topmost_stack'):
            self.panel.bind_topmost_stack()
        self.panel.resume_callbacks()

        # 更新托盘菜单文字
        if hasattr(self, 'action_toggle_ui') and self.action_toggle_ui:
            self._set_action_text(self.action_toggle_ui, self._tr("hide_main_ui"))

    def is_exiting(self):
        """是否正在退出中"""
        return self.state == LifecycleState.QUITTING

    def is_background(self):
        """是否在后台隐藏状态"""
        return self.state == LifecycleState.HIDDEN

    def pause_callbacks(self):
        """暂停会自动显示界面的回调（退出对话框期间调用）"""
        # 由 ControlPanel.pause_callbacks() 实现
        pass

    def resume_callbacks(self):
        """恢复回调（退出对话框关闭后调用）"""
        # 由 ControlPanel.resume_callbacks() 实现
        pass
