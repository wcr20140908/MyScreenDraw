# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""独立的工具栏窗口：LOGO窗口和工具条窗口的分体设计"""

from PyQt6.QtWidgets import QWidget, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor
import logging

logger = logging.getLogger(__name__)


class LogoWindow(QWidget):
    """LOGO独立窗口：点击控制工具栏显示/隐藏，拖动移动位置"""

    clicked = pyqtSignal()  # LOGO被点击
    position_changed = pyqtSignal(QPoint)  # 位置改变，用于工具栏跟随

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
            # 暂时移除Tool标志测试
            # | Qt.WindowType.Tool
        )
        # 不使用WA_TranslucentBackground，而是给窗口一个实际背景
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_offset = None
        self._dragging = False
        self._press_pos = None

        # 设置固定大小 - 与工具按钮一致（40x40）
        self.setFixedSize(40, 40)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 用QPushButton显示LOGO，确保能响应点击
        from main import tr
        self.logo_btn = QPushButton()
        self.logo_btn.setObjectName("LogoButton")
        self.logo_btn.setFixedSize(40, 40)
        self.logo_btn.setToolTip(tr("logo_hint"))
        self.logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo_btn.clicked.connect(self._on_logo_clicked)

        # 安装事件过滤器以处理拖动
        self.logo_btn.installEventFilter(self)

        layout.addWidget(self.logo_btn)

        logger.info("[LogoWindow] Initialized with QPushButton")

    def _on_logo_clicked(self):
        """LOGO按钮被点击"""
        logger.info("[LogoWindow] Logo button clicked, emitting signal")
        self.clicked.emit()

    def eventFilter(self, obj, event):
        """事件过滤器：在按钮上处理拖动，不影响点击"""
        if obj == self.logo_btn:
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._press_pos = event.globalPosition().toPoint()
                    self._drag_offset = self._press_pos - self.pos()
                    self._dragging = False
                    logger.info(f"[LogoWindow] Press recorded at {self._press_pos}")
            elif event.type() == event.Type.MouseMove:
                if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
                    delta = event.globalPosition().toPoint() - self._press_pos
                    if not self._dragging and (abs(delta.x()) > 5 or abs(delta.y()) > 5):
                        self._dragging = True
                        logger.info(f"[LogoWindow] Dragging started, delta={delta}")

                    if self._dragging:
                        new_pos = event.globalPosition().toPoint() - self._drag_offset
                        self.move(new_pos)
                        self.position_changed.emit(new_pos)
                        return True  # 拖动时阻止按钮处理事件
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    logger.info(f"[LogoWindow] mouseReleaseEvent: dragging={self._dragging}")
                    was_dragging = self._dragging
                    self._drag_offset = None
                    self._dragging = False
                    self._press_pos = None

                    # 如果在拖动，阻止按钮的点击事件
                    if was_dragging:
                        return True

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """窗口级鼠标事件（已由eventFilter处理，这里仅保留以防万一）"""
        event.ignore()

    def mouseMoveEvent(self, event):
        """窗口级鼠标移动（已由eventFilter处理）"""
        event.ignore()

    def mouseReleaseEvent(self, event):
        """窗口级鼠标释放（已由eventFilter处理）"""
        event.ignore()

    def apply_theme(self, theme, radius, opacity, logo_icon=None):
        """应用主题样式

        Args:
            theme: 主题颜色字典
            radius: 圆角半径
            opacity: 不透明度
            logo_icon: 可选的LOGO图标（QIcon），如果提供则更新按钮图标
        """
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            QPushButton#LogoButton {{
                background-color: {theme['button']};
                border: 2px solid {theme['accent']};
                border-radius: {radius}px;
                padding: 0px;
                margin: 0px;
            }}
            QPushButton#LogoButton:hover {{
                background-color: {theme['button_hover']};
            }}
            QPushButton#LogoButton:pressed {{
                background-color: {theme['accent']};
            }}
        """)
        self.setWindowOpacity(opacity / 100.0)

        # 更新按钮图标
        if logo_icon is not None and hasattr(self, 'logo_btn'):
            self.logo_btn.setIcon(logo_icon)
            self.logo_btn.setIconSize(QSize(32, 32))  # 图标32x32，按钮40x40（含4px留白）


class ToolbarWindow(QWidget):
    """工具栏独立窗口：显示所有工具按钮，可独立拖动"""

    position_changed = pyqtSignal(QPoint)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_offset = None
        self.orientation = "portrait"
        self.icon_buttons = {}
        self._button_width = 66
        self._button_height = 58

        # 主布局框架
        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.main_frame)

        # 内部布局（会根据方向动态切换）
        self.toolbar_layout = QVBoxLayout(self.main_frame)
        self.toolbar_layout.setContentsMargins(6, 6, 6, 6)
        self.toolbar_layout.setSpacing(2)
        self.toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 工具按钮网格
        self.icon_grid = QGridLayout()
        self.icon_grid.setContentsMargins(0, 0, 0, 0)
        self.icon_grid.setSpacing(2)
        self.toolbar_layout.addLayout(self.icon_grid)

        # 白板控制区
        self.icon_wb_box = QWidget()
        self.icon_wb_grid = QGridLayout(self.icon_wb_box)
        self.icon_wb_grid.setContentsMargins(0, 0, 0, 0)
        self.icon_wb_grid.setSpacing(2)
        self.icon_wb_box.setVisible(False)
        self.toolbar_layout.addWidget(self.icon_wb_box)

    def mousePressEvent(self, event):
        """鼠标按下：记录拖动起始点"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动：拖动窗口"""
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.position_changed.emit(self.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放：结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def set_orientation(self, orientation):
        """切换横版/竖版布局"""
        if self.orientation == orientation:
            return
        self.orientation = orientation

        # 重建布局
        items = []
        while self.toolbar_layout.count():
            item = self.toolbar_layout.takeAt(0)
            widget, sub = item.widget(), item.layout()
            if widget is not None:
                items.append(("widget", widget))
            elif sub is not None:
                items.append(("layout", sub))

        # 临时widget接管旧布局
        QWidget().setLayout(self.toolbar_layout)

        # 创建新布局
        if orientation == "landscape":
            new_layout = QHBoxLayout(self.main_frame)
            new_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        else:
            new_layout = QVBoxLayout(self.main_frame)
            new_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        new_layout.setContentsMargins(6, 6, 6, 6)
        new_layout.setSpacing(2)

        for kind, obj in items:
            if kind == "widget":
                new_layout.addWidget(obj)
            else:
                new_layout.addLayout(obj)

        self.toolbar_layout = new_layout
        self._relayout_buttons()

    def _relayout_buttons(self):
        """根据方向重排按钮：横版单行，竖版单列"""
        # 清空网格
        for grid in (self.icon_grid, self.icon_wb_grid):
            while grid.count():
                grid.takeAt(0)

        # 白板控制按钮的key
        wb_keys = {'prev_page', 'pages', 'next_page', 'new_page', 'board_style'}

        # 重新排列
        main_buttons = [btn for key, btn in self.icon_buttons.items()
                       if key not in wb_keys]
        wb_buttons = [btn for key, btn in self.icon_buttons.items()
                     if key in wb_keys]

        if self.orientation == "landscape":
            # 横版：单行
            for i, btn in enumerate(main_buttons):
                self.icon_grid.addWidget(btn, 0, i)
            for i, btn in enumerate(wb_buttons):
                self.icon_wb_grid.addWidget(btn, 0, i)
        else:
            # 竖版：单列
            for i, btn in enumerate(main_buttons):
                self.icon_grid.addWidget(btn, i, 0)
            for i, btn in enumerate(wb_buttons):
                self.icon_wb_grid.addWidget(btn, i, 0)

        for btn in main_buttons + wb_buttons:
            btn.setVisible(True)

        self.adjustSize()

    def apply_theme(self, theme, radius, opacity):
        """应用主题样式"""
        # 按钮尺寸：使用TOUCH_MIN_BUTTON与主面板IconBtn保持一致
        from main import TOUCH_MIN_BUTTON
        btn_size = TOUCH_MIN_BUTTON  # 32px，与主面板样式统一
        self.setStyleSheet(f"""
            QFrame#MainFrame {{
                background-color: {theme['frame']};
                border-radius: {radius}px;
                border: 2px solid {theme['accent']};
            }}
            QPushButton, QToolButton {{
                background-color: {theme['button']};
                color: {theme['text']};
                border-radius: 6px;
                border: none;
                padding: 2px;
                margin: 1px;
                min-width: {self._button_width}px;
                max-width: {self._button_width}px;
                min-height: {self._button_height}px;
                max-height: {self._button_height}px;
                font-size: 10px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background-color: {theme['button_hover']};
            }}
            QPushButton:pressed, QToolButton:pressed {{
                background-color: {theme['accent']};
            }}
            QToolButton#IconBtn {{
                background-color: {theme['button']};
            }}
            QToolButton#IconBtnActive {{
                background-color: {theme['accent']};
                color: {theme['active_text']};
            }}
        """)
        self.setWindowOpacity(opacity / 100.0)
