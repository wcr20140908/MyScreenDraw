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
from pathlib import Path

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QWidgetAction, QLabel
from PyQt6.QtGui import QAction, QIcon, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer


class LifecycleState:
    """生命周期状态枚举"""
    SHOWING = "showing"
    COLLAPSED = "collapsed"
    HIDDEN = "hidden"
    QUITTING = "quitting"


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

        self._setup_tray()

    def _setup_tray(self):
        """初始化托盘图标和菜单"""
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

                label.mousePressEvent = lambda e, fn=make_trigger(action): (fn(), self.tray_menu.hide())

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

    def _on_tray_activated(self, reason):
        """托盘图标激活：左键单击恢复完整主界面"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.restore_from_background()

    def _toggle_main_ui(self):
        """切换显示/隐藏主界面"""
        if self.state == LifecycleState.HIDDEN:
            self.restore_from_background()
        else:
            self.hide_to_background()

    def _open_settings_from_tray(self):
        """从托盘打开设置（后台也能打开）"""
        if self.state == LifecycleState.HIDDEN:
            # 后台状态：设置页懒创建后再显示，不恢复主面板。
            if self.panel.settings_panel is None:
                self.panel.build_settings_panel()
            self.panel.open_settings_panel()
        else:
            # 前台状态：正常打开
            self.panel.open_settings_panel()

    def _restart_app(self):
        """重启软件：保留当前未保存工作"""
        import subprocess
        import sys
        import os
        import tempfile

        # 保存当前状态到临时恢复文件
        recovery_file = os.path.join(tempfile.gettempdir(),
                                     f'myscreendraw_restart_{os.getpid()}.msd')
        try:
            success = self.panel.save_project(recovery_file)
            if not success:
                recovery_file = None
        except Exception:
            # 保存失败也继续重启，只是不恢复数据
            recovery_file = None

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
        if self._quit_dialog_showing or self.state == LifecycleState.QUITTING:
            return

        self._quit_dialog_showing = True
        state_before_quit = self.state
        self.state = LifecycleState.QUITTING

        def stay_in_app():
            # 「不再退出」：后台状态就恢复主界面；本来就显示着的保持原样（折叠的仍折叠）
            if state_before_quit == LifecycleState.HIDDEN:
                self.restore_from_background()
            else:
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

            dialog.exec()
            clicked = dialog.clickedButton()

            if clicked == btn_quit_directly:
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
                # 不再退出（含按 Esc / 关闭对话框）
                stay_in_app()
        finally:
            self._quit_dialog_showing = False
            if not getattr(self, "_quit_done", False):
                if self.state == LifecycleState.QUITTING:
                    self.state = LifecycleState.SHOWING
                self.panel.resume_callbacks()

    def _do_quit(self, save):
        """执行退出清理"""
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

        # 清理托盘图标
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()

        # 退出应用
        self.app.quit()

    def hide_to_background(self):
        """转入后台：隐藏所有窗口，保持托盘图标"""
        if self.state == LifecycleState.HIDDEN:
            return

        self._state_before_hidden = self.state
        if hasattr(self.panel, 'canvas') and self.panel.canvas and self.panel.canvas.editing_text_item():
            self.panel.canvas.end_text_edit(discard_empty=True)

        # 进入穿透模式
        self.panel.set_drawing_mode(False)

        # 隐藏所有窗口（包括分体窗口）
        if self.panel.canvas:
            self.panel.canvas.hide()
        self.panel.hide()
        if hasattr(self.panel, 'logo_window') and self.panel.logo_window:
            self.panel.logo_window.hide()
        if hasattr(self.panel, 'toolbar_window') and self.panel.toolbar_window:
            self.panel.toolbar_window.hide()
        if hasattr(self.panel, 'settings_panel') and self.panel.settings_panel:
            self.panel.settings_panel.hide()
        # 隐藏所有子菜单
        self.panel.show_only_sub(None)

        # 隐藏软键盘
        if hasattr(self.panel, '_keyboard_process') and self.panel._keyboard_process:
            try:
                self.panel._keyboard_process.terminate()
                self.panel._keyboard_process = None
            except Exception:
                pass

        self.state = LifecycleState.HIDDEN

        # 更新托盘菜单文字
        if hasattr(self, 'action_toggle_ui') and self.action_toggle_ui:
            self._set_action_text(self.action_toggle_ui, self._tr("show_main_ui"))

        # 暂停心跳和定时器
        self.panel.pause_callbacks()

    def restore_from_background(self):
        """从后台恢复完整主界面"""
        if self.state == LifecycleState.SHOWING:
            return

        # 画布也要回来：进后台时把它藏了，不重新显示的话已有批注全部不见，用户要再
        # 点一次绘图模式才「找回」墨迹。此时仍是穿透模式，显示出来不拦点击。
        if hasattr(self.panel, 'canvas') and self.panel.canvas:
            self.panel.canvas.show()
        self.panel.show()
        # 恢复 LOGO；只有进入后台前是完整显示时才恢复工具栏。
        if hasattr(self.panel, 'logo_window') and self.panel.logo_window:
            self.panel.logo_window.show()
        was_collapsed = self._state_before_hidden == LifecycleState.COLLAPSED
        if hasattr(self.panel, 'toolbar_window') and self.panel.toolbar_window:
            if was_collapsed:
                self.panel.toolbar_window.hide()
            else:
                self.panel.toolbar_window.show()
        if hasattr(self.panel, '_sync_split_geometry'):
            self.panel._sync_split_geometry()

        # 保持穿透模式，直到用户主动选择绘图工具
        # （防止恢复时误画）

        self.state = LifecycleState.COLLAPSED if was_collapsed else LifecycleState.SHOWING
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
