# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""独立的工具栏窗口：LOGO窗口和工具条窗口的分体设计"""

from PyQt6.QtWidgets import (QWidget, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QFrame, QLabel, QApplication)
from PyQt6.QtCore import Qt, QSize, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QFontMetrics, QIcon
import logging

logger = logging.getLogger(__name__)


# 按钮尺寸：图标 20px + 一行 10px 文字 + 上下留白。56×44 在触屏上仍够按，
# 又不会像 66×58 那样把竖版整栏顶出任务栏。
BUTTON_WIDTH = 56
BUTTON_HEIGHT = 44
BUTTON_HEIGHT_MIN = 28      # 再矮图标和文字就叠在一起了
BUTTON_WIDTH_MAX = 76       # 最长的文案（如 Durchsichtig）也不至于把栏撑得太宽
LOGO_THICKNESS = 40         # 竖版 LOGO 的高度 / 横版 LOGO 的宽度
LOGO_GAP = 2                # LOGO 与工具栏之间的缝


def _available_rect(widget):
    """widget 所在屏幕的可用区（不含任务栏）；屏幕拿不到时退回主屏。"""
    screen = None
    try:
        screen = widget.screen()
    except Exception:
        screen = None
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1040)
    return screen.availableGeometry()


def clamp_point_into(x, y, w, h, area):
    """把 (x, y, w, h) 的矩形收进 area；比 area 还大时贴左/上边。"""
    max_x = area.right() - w + 1
    max_y = area.bottom() - h + 1
    x = max(area.left(), min(x, max_x))
    y = max(area.top(), min(y, max_y))
    return int(x), int(y)


class LogoWindow(QWidget):
    """LOGO独立窗口：点击控制工具栏显示/隐藏，拖动移动位置"""

    clicked = pyqtSignal()  # LOGO被点击
    position_changed = pyqtSignal(QPoint)  # 位置改变，用于工具栏跟随

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tool：不上任务栏、不抢焦点；置顶归属由主面板的 bind_topmost_stack 统一挂到画布上。
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowIcon(QIcon())

        self._drag_offset = None
        self._dragging = False
        self._press_pos = None
        self._icon_size = 32

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 用QPushButton显示LOGO，确保能响应点击
        from main import tr
        self.logo_btn = QPushButton()
        self.logo_btn.setObjectName("LogoButton")
        self.logo_btn.setToolTip(tr("logo_hint"))
        self.logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo_btn.clicked.connect(self._on_logo_clicked)

        # 安装事件过滤器以处理拖动
        self.logo_btn.installEventFilter(self)

        layout.addWidget(self.logo_btn)
        self.set_size(LOGO_THICKNESS, LOGO_THICKNESS)

        logger.info("[LogoWindow] Initialized with QPushButton")

    def set_size(self, width, height):
        """LOGO 尺寸跟着工具栏走：竖版与工具栏同宽，横版与工具栏同高。

        两个窗口一宽一窄就是「宽度不一致、奇丑」的来源，所以尺寸不在这里自己决定，
        由主面板在工具栏每次重排后同步过来。图标按短边缩放并留出边框。
        """
        width = max(24, int(width))
        height = max(24, int(height))
        if (width, height) == (self.width(), self.height()) and self.logo_btn.width() == width:
            return
        self.setFixedSize(width, height)
        self.logo_btn.setFixedSize(width, height)
        self._icon_size = max(16, min(32, min(width, height) - 8))
        self.logo_btn.setIconSize(QSize(self._icon_size, self._icon_size))

    def icon_size(self):
        return self._icon_size

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
            elif event.type() == event.Type.MouseMove:
                if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
                    delta = event.globalPosition().toPoint() - self._press_pos
                    if not self._dragging and (abs(delta.x()) > 5 or abs(delta.y()) > 5):
                        self._dragging = True

                    if self._dragging:
                        new_pos = event.globalPosition().toPoint() - self._drag_offset
                        x, y = clamp_point_into(new_pos.x(), new_pos.y(), self.width(), self.height(),
                                                _available_rect(self))
                        new_pos = QPoint(x, y)
                        self.move(new_pos)
                        self.position_changed.emit(new_pos)
                        return True  # 拖动时阻止按钮处理事件
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
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
            self.logo_btn.setIconSize(QSize(self._icon_size, self._icon_size))


class ToolbarWindow(QWidget):
    """工具栏独立窗口：显示所有工具按钮，可独立拖动"""

    position_changed = pyqtSignal(QPoint)
    # 白板控制按钮的key。翻页条已经挪到右下角的跑道控件，主栏只留白/黑板切换。
    WB_KEYS = frozenset({'board_style'})

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowIcon(QIcon())

        self._drag_offset = None
        self.orientation = "portrait"
        self.icon_buttons = {}
        self._button_width = BUTTON_WIDTH
        self._button_height = BUTTON_HEIGHT
        self._wb_columns = 1
        self._main_rows = 1
        self._theme_args = None

        # 主布局框架
        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self.main_frame)

        # 内部布局（会根据方向动态切换）
        self.toolbar_layout = QVBoxLayout(self.main_frame)
        self.toolbar_layout.setContentsMargins(6, 6, 6, 6)
        self.toolbar_layout.setSpacing(2)
        self.toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 工具按钮网格（白板入口之前的按钮）
        self.icon_grid = QGridLayout()
        self.icon_grid.setContentsMargins(0, 0, 0, 0)
        self.icon_grid.setSpacing(2)
        self.toolbar_layout.addLayout(self.icon_grid)

        # 白板控制区：插在「进入/退出白板」按钮正下方，关闭按钮之前
        self.icon_wb_box = QWidget()
        self.icon_wb_grid = QGridLayout(self.icon_wb_box)
        self.icon_wb_grid.setContentsMargins(0, 0, 0, 0)
        self.icon_wb_grid.setSpacing(2)
        self.icon_wb_box.setVisible(False)
        self.toolbar_layout.addWidget(self.icon_wb_box)

        # 白板入口之后的按钮（设置、关闭）：关闭始终在最下方
        self.icon_grid_tail = QGridLayout()
        self.icon_grid_tail.setContentsMargins(0, 0, 0, 0)
        self.icon_grid_tail.setSpacing(2)
        self.toolbar_layout.addLayout(self.icon_grid_tail)

    # --- 拖动 ---
    def mousePressEvent(self, event):
        """鼠标按下：记录拖动起始点"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动：拖动窗口"""
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            target = event.globalPosition().toPoint() - self._drag_offset
            x, y = clamp_point_into(target.x(), target.y(), self.width(), self.height(),
                                    _available_rect(self))
            self.move(x, y)
            self.position_changed.emit(self.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放：结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    # --- 布局 ---
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

    def _main_buttons(self):
        # 白板入口按钮排在主区末尾：白板控制区紧跟在它下方，关闭按钮再排在最底。
        buttons = [btn for key, btn in self.icon_buttons.items() if key not in self.WB_KEYS]
        entry = self.icon_buttons.get("whiteboard")
        close = self.icon_buttons.get("close")
        if entry is not None and entry in buttons:
            buttons.remove(entry)
            if close is not None and close in buttons:
                buttons.insert(buttons.index(close), entry)
            else:
                buttons.append(entry)
        return buttons

    def _wb_buttons(self):
        return [btn for key, btn in self.icon_buttons.items() if key in self.WB_KEYS]

    def _relayout_buttons(self):
        """根据方向重排按钮：横版单行，竖版单列，然后按内容收紧并收进屏幕。"""
        self._place_buttons()
        self._button_width = self._measure_button_width()
        # 先按标准高度排一次，量到的才是真实高度；超高再压矮重排。
        # 白板翻页不在主栏里，主栏不再为它折列。
        self._button_height = BUTTON_HEIGHT
        self._wb_columns = 1
        self._main_rows = 1
        self._reapply_button_size()
        self._place_buttons()
        self._fit_to_content()
        avail = _available_rect(self)
        if self.orientation == "portrait":
            # LOGO 固定在工具栏上方，所以工具栏自己只能用掉「屏幕高度减去 LOGO」的部分。
            # 放不下就按颗数把按钮压矮，压到能整栏放下为止；不能靠把 LOGO 挪到下面来腾地方。
            limit = avail.height() - LOGO_THICKNESS - LOGO_GAP
            count = max(1, sum(1 for btn in self.icon_buttons.values() if not btn.isHidden()))
            while self.height() > limit and self._button_height > BUTTON_HEIGHT_MIN:
                overflow = self.height() - limit
                shrink = max(2, -(-overflow // count))
                self._button_height = max(BUTTON_HEIGHT_MIN, self._button_height - shrink)
                self._reapply_button_size()
                self._place_buttons()
                self._fit_to_content()
        else:
            # 横版一行 14 个按钮约 850px，窄屏（200% 缩放的 1080p 只有 960 逻辑像素）
            # 放不下就折成两行，比让整栏伸出屏幕右边被 clamp 到 x=0 好。
            limit = avail.width() - LOGO_THICKNESS - LOGO_GAP
            if self.width() > limit:
                self._main_rows = 2
                self._place_buttons()
                self._fit_to_content()
        self.clamp_into_screen()

    def _place_buttons(self):
        for grid in (self.icon_grid, self.icon_grid_tail, self.icon_wb_grid):
            while grid.count():
                grid.takeAt(0)
        main_buttons = self._main_buttons()
        wb_buttons = self._wb_buttons()
        # 白/黑板切换紧跟在「进入/退出白板」按钮后面：竖版在它下方，横版在它右侧。
        entry = self.icon_buttons.get("whiteboard")
        split_at = main_buttons.index(entry) + 1 if entry in main_buttons else len(main_buttons)
        head, tail = main_buttons[:split_at], main_buttons[split_at:]
        if self.orientation == "landscape":
            rows = max(1, self._main_rows)
            per_row = max(1, -(-len(main_buttons) // rows))
            for i, btn in enumerate(head):
                self.icon_grid.addWidget(btn, i // per_row, i % per_row)
            wb_per_row = max(1, -(-len(wb_buttons) // rows))
            for i, btn in enumerate(wb_buttons):
                self.icon_wb_grid.addWidget(btn, i // wb_per_row, i % wb_per_row)
            start = len(head)
            for i, btn in enumerate(tail):
                pos = start + i
                self.icon_grid_tail.addWidget(btn, pos // per_row, pos % per_row)
        else:
            for i, btn in enumerate(head):
                self.icon_grid.addWidget(btn, i, 0)
            cols = max(1, self._wb_columns)
            for i, btn in enumerate(wb_buttons):
                self.icon_wb_grid.addWidget(btn, i // cols, i % cols)
            for i, btn in enumerate(tail):
                self.icon_grid_tail.addWidget(btn, i, 0)
        # Button visibility is owned by sync_icon_buttons(); relayout must not
        # resurrect controls hidden by mouse mode.

    def _measure_button_width(self):
        """按钮宽度由最长文案决定：英文的 "Whiteboard" 比中文长得多，56px 会把字截掉。

        白板入口的文案在「进入白板/退出白板」之间切换，退出文案更长，
        把它算进去会让进白板时整栏变宽。入口按钮单独放宽，其它按钮保持原宽。
        """
        widest = 0
        for key, btn in self.icon_buttons.items():
            if key == "whiteboard":
                continue
            text = btn.text()
            if not text:
                continue
            font = btn.font()
            font.setPixelSize(10)
            widest = max(widest, QFontMetrics(font).horizontalAdvance(text))
        return max(BUTTON_WIDTH, min(BUTTON_WIDTH_MAX, widest + 8))

    def _reapply_button_size(self):
        if self._theme_args is not None:
            self.apply_theme(*self._theme_args)

    def _fit_to_content(self):
        """按内容定死窗口尺寸。

        半透明无边框窗口只 adjustSize() 不够：嵌套布局的 sizeHint 有缓存，白板区
        显隐或按钮改尺寸后窗口只会变大不会缩回，底部留一截透明却仍拦点击的空白。
        """
        for nested in (self.icon_grid, self.icon_grid_tail, self.icon_wb_grid, self.toolbar_layout, self.layout()):
            if nested is not None:
                nested.invalidate()
                nested.activate()
        hint = self.layout().sizeHint()
        if hint.isValid() and hint.width() > 0 and hint.height() > 0:
            self.setFixedSize(hint)
        else:
            self.adjustSize()
        self.update()

    def refresh_layout(self):
        """白板控制区显隐后重新收紧并收进屏幕（主面板 sync_icon_buttons 调用）。"""
        self._relayout_buttons()

    def clamp_into_screen(self):
        """整栏收进当前屏幕可用区：竖版不许伸到任务栏下面，横版不许伸出右边。"""
        area = _available_rect(self)
        x, y = clamp_point_into(self.x(), self.y(), self.width(), self.height(), area)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
            return True
        return False

    def logo_size_for(self):
        """与本栏匹配的 LOGO 尺寸：竖版同宽、横版同高。"""
        if self.orientation == "portrait":
            return self.width(), LOGO_THICKNESS
        return LOGO_THICKNESS, self.height()

    def apply_theme(self, theme, radius, opacity):
        """应用主题样式"""
        self._theme_args = (theme, radius, opacity)
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
                padding: 1px;
                margin: 0px;
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
