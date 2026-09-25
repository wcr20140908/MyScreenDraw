# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""原创 UI 图标绘制：所有功能图标的统一视觉风格。

设计原则：
- 一眼可辨：优先用该功能最通用的意象（笔就是笔、垃圾桶就是清空、工具箱就是工具），
  而不是抽象几何。小尺寸下实心块比细线轮廓好认，所以箭头、笔尖这类靠外形识别的
  部件一律填充。
- 统一风格：同一套线宽比例、圆头圆角、0..1 归一化坐标。
- 适配主题：颜色由调用方按主题传入，这里不写死任何色值。
- 无外部依赖：纯 QPainter 绘制，不用图标字体也不用图片资源。

坐标约定：绘制函数收到 (painter, color, size)，用 s = size 把 0..1 的比例换算成
像素。同一份路径因此在 16px 托盘图标和 256px EXE 图标上都成立。
"""
import math

from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QIcon, QPainterPath, QBrush
from PyQt6.QtCore import Qt, QRectF, QPointF


def _pen(p, color, s, ratio=1.0):
    """标准描边画笔：线宽随尺寸等比缩放，圆头圆角。

    下限 1.2px 是为了 16px 托盘图标——再细会被抗锯齿抹成一团灰雾，
    图标看着像脏了一块而不是一个形状。
    """
    stroke = QPen(QColor(color))
    stroke.setWidthF(max(1.2, s * 0.075 * ratio))
    stroke.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(stroke)
    p.setBrush(Qt.BrushStyle.NoBrush)
    return stroke


def _solid(p, color):
    """实心填充、不描边：用于箭头、笔尖这类靠外形识别的部件。"""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))


def _poly(p, *points):
    """按给定顶点画一个闭合多边形（配合 _pen / _solid 决定描边还是填充）。"""
    path = QPainterPath()
    path.moveTo(points[0][0], points[0][1])
    for x, y in points[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)


def _draw_logo(p, color, s):
    """LOGO：一块屏幕 + 一道笔迹。程序做的就是「在屏幕上写字」。"""
    _pen(p, color, s, 1.0)
    # 屏幕：圆角矩形 + 底座，一眼是显示器而不是普通方框
    p.drawRoundedRect(QRectF(s * 0.13, s * 0.20, s * 0.74, s * 0.48), s * 0.07, s * 0.07)
    p.drawLine(QPointF(s * 0.38, s * 0.80), QPointF(s * 0.62, s * 0.80))
    p.drawLine(QPointF(s * 0.50, s * 0.68), QPointF(s * 0.50, s * 0.80))
    # 笔迹：屏幕里一道手写曲线
    path = QPainterPath()
    path.moveTo(s * 0.25, s * 0.52)
    path.cubicTo(QPointF(s * 0.36, s * 0.26), QPointF(s * 0.46, s * 0.58),
                 QPointF(s * 0.57, s * 0.42))
    path.cubicTo(QPointF(s * 0.65, s * 0.31), QPointF(s * 0.70, s * 0.38),
                 QPointF(s * 0.76, s * 0.34))
    _pen(p, color, s, 0.85)
    p.drawPath(path)


def _draw_mouse_pointer(p, color, s):
    """鼠标模式：标准鼠标箭头。实心——空心箭头在 22px 下根本看不出是箭头。"""
    _solid(p, color)
    _poly(p, (s * 0.28, s * 0.14), (s * 0.28, s * 0.76), (s * 0.43, s * 0.61),
          (s * 0.53, s * 0.84), (s * 0.63, s * 0.79), (s * 0.53, s * 0.57),
          (s * 0.72, s * 0.55))


def _draw_pen(p, color, s):
    """普通笔：45° 斜握的笔，右上是笔杆、左下是实心笔尖。"""
    # 笔杆
    _pen(p, color, s, 0.9)
    _poly(p, (s * 0.52, s * 0.14), (s * 0.86, s * 0.30), (s * 0.44, s * 0.66),
          (s * 0.30, s * 0.58))
    # 笔箍：一道横线，把笔杆和笔尖分开
    p.drawLine(QPointF(s * 0.40, s * 0.44), QPointF(s * 0.66, s * 0.58))
    # 笔尖：实心三角，指向左下
    _solid(p, color)
    _poly(p, (s * 0.30, s * 0.58), (s * 0.44, s * 0.66), (s * 0.16, s * 0.84))


def _draw_highlighter(p, color, s):
    """荧光笔：扁头马克笔 + 下方一道宽色带。"""
    _pen(p, color, s, 0.9)
    # 笔身
    _poly(p, (s * 0.46, s * 0.12), (s * 0.82, s * 0.30), (s * 0.60, s * 0.52),
          (s * 0.28, s * 0.36))
    # 扁笔头：实心梯形（荧光笔的识别点就是这个宽头）
    _solid(p, color)
    _poly(p, (s * 0.28, s * 0.36), (s * 0.60, s * 0.52), (s * 0.50, s * 0.64),
          (s * 0.20, s * 0.48))
    # 涂痕：一道粗色带
    band = QPen(QColor(color))
    band.setWidthF(max(2.0, s * 0.14))
    band.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(band)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(s * 0.16, s * 0.80), QPointF(s * 0.84, s * 0.80))


def _draw_laser(p, color, s):
    """激光笔：笔身 + 射出的光束和光点。"""
    _pen(p, color, s, 0.9)
    p.drawRoundedRect(QRectF(s * 0.30, s * 0.12, s * 0.40, s * 0.34), s * 0.06, s * 0.06)
    # 光束：从笔口向下发散的三道线
    _pen(p, color, s, 0.7)
    p.drawLine(QPointF(s * 0.50, s * 0.46), QPointF(s * 0.50, s * 0.66))
    p.drawLine(QPointF(s * 0.36, s * 0.52), QPointF(s * 0.30, s * 0.64))
    p.drawLine(QPointF(s * 0.64, s * 0.52), QPointF(s * 0.70, s * 0.64))
    # 光点：实心圆
    _solid(p, color)
    p.drawEllipse(QRectF(s * 0.40, s * 0.72, s * 0.20, s * 0.20))


def _draw_eraser(p, color, s):
    """橡皮：斜放的橡皮块 + 擦过的碎屑。"""
    _pen(p, color, s, 0.9)
    _poly(p, (s * 0.22, s * 0.46), (s * 0.54, s * 0.16), (s * 0.82, s * 0.42),
          (s * 0.50, s * 0.72))
    # 分界线：把橡皮分成「胶头」和「套」两段，才像橡皮不像纸片
    p.drawLine(QPointF(s * 0.36, s * 0.32), QPointF(s * 0.66, s * 0.58))
    # 碎屑
    _solid(p, color)
    for cx, cy, r in ((0.24, 0.80, 0.045), (0.40, 0.88, 0.035), (0.60, 0.84, 0.030)):
        p.drawEllipse(QRectF(s * (cx - r), s * (cy - r), s * r * 2, s * r * 2))


def _draw_select(p, color, s):
    """框选：虚线选框 + 四角实心把手。"""
    stroke = _pen(p, color, s, 0.7)
    stroke.setStyle(Qt.PenStyle.DashLine)
    p.setPen(stroke)
    p.drawRect(QRectF(s * 0.20, s * 0.24, s * 0.60, s * 0.52))
    # 把手：实心小方块。空心圆点在小尺寸下会糊成一团，方块边缘清楚。
    _solid(p, color)
    h = s * 0.075
    for x, y in ((0.20, 0.24), (0.80, 0.24), (0.20, 0.76), (0.80, 0.76)):
        p.drawRect(QRectF(s * x - h / 2, s * y - h / 2, h, h))


def _draw_text(p, color, s):
    """文本框：一个衬线大写 T。带脚的 T 不会被误读成加号。"""
    _solid(p, color)
    bar = s * 0.115           # 横画粗细
    stem = s * 0.115          # 竖画粗细
    p.drawRect(QRectF(s * 0.20, s * 0.20, s * 0.60, bar))
    p.drawRect(QRectF(s * 0.50 - stem / 2, s * 0.20, stem, s * 0.56))
    # 底部衬线：一小段横画，让它明确是字母而不是十字
    p.drawRect(QRectF(s * 0.33, s * 0.76 - bar * 0.75, s * 0.34, bar * 0.75))


def _draw_formula(p, color, s):
    """公式：求和符号 Σ。数学意象里它最不容易和别的图标撞。"""
    _pen(p, color, s, 1.0)
    path = QPainterPath()
    path.moveTo(s * 0.72, s * 0.20)
    path.lineTo(s * 0.28, s * 0.20)
    path.lineTo(s * 0.52, s * 0.50)
    path.lineTo(s * 0.28, s * 0.80)
    path.lineTo(s * 0.72, s * 0.80)
    p.drawPath(path)


def _draw_shape(p, color, s):
    """图形：一个方形和一个圆相交。「若干基本图形」的通用画法。"""
    _pen(p, color, s, 0.85)
    p.drawRect(QRectF(s * 0.16, s * 0.16, s * 0.44, s * 0.44))
    p.drawEllipse(QRectF(s * 0.40, s * 0.40, s * 0.44, s * 0.44))


def _draw_line(p, color, s):
    """直线：一条斜线 + 两端的实心端点（端点表明它是「两点确定的线段」）。"""
    _pen(p, color, s, 0.9)
    p.drawLine(QPointF(s * 0.22, s * 0.76), QPointF(s * 0.78, s * 0.24))
    _solid(p, color)
    r = s * 0.075
    for x, y in ((0.22, 0.76), (0.78, 0.24)):
        p.drawEllipse(QRectF(s * x - r, s * y - r, r * 2, r * 2))


def _draw_tools(p, color, s):
    """工具：工具箱。扳手在 22px 下太细碎，箱子的外形轮廓更稳。"""
    _pen(p, color, s, 0.9)
    # 提手
    path = QPainterPath()
    path.moveTo(s * 0.36, s * 0.34)
    path.lineTo(s * 0.36, s * 0.24)
    path.lineTo(s * 0.64, s * 0.24)
    path.lineTo(s * 0.64, s * 0.34)
    p.drawPath(path)
    # 箱体
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.34, s * 0.72, s * 0.44), s * 0.06, s * 0.06)
    # 箱体中缝 + 锁扣
    p.drawLine(QPointF(s * 0.14, s * 0.50), QPointF(s * 0.86, s * 0.50))
    _solid(p, color)
    p.drawRect(QRectF(s * 0.44, s * 0.44, s * 0.12, s * 0.12))


def _draw_folder(p, color, s):
    """文件：带标签页的文件夹。"""
    _pen(p, color, s, 0.9)
    path = QPainterPath()
    path.moveTo(s * 0.14, s * 0.74)
    path.lineTo(s * 0.14, s * 0.26)
    path.lineTo(s * 0.42, s * 0.26)
    path.lineTo(s * 0.50, s * 0.38)
    path.lineTo(s * 0.86, s * 0.38)
    path.lineTo(s * 0.86, s * 0.74)
    path.closeSubpath()
    p.drawPath(path)


def _arc_arrow(p, color, s, mirror):
    """撤销 / 重做共用：一段回转弧 + 弧头的实心三角箭头。

    mirror=False 是撤销（弧向左回、箭头指左），True 是重做（整体水平镜像）。
    两个方向共用一份路径，避免两套坐标各写一遍后画得不对称。
    """
    if mirror:
        p.save()
        p.translate(s, 0)
        p.scale(-1, 1)
    _pen(p, color, s, 0.9)
    # 弧：上半圈，左端断开留给箭头
    p.drawArc(QRectF(s * 0.20, s * 0.28, s * 0.60, s * 0.48), 30 * 16, 165 * 16)
    # 箭头：实心三角，压在弧的左端点上，指向左下
    _solid(p, color)
    _poly(p, (s * 0.10, s * 0.36), (s * 0.36, s * 0.34), (s * 0.22, s * 0.60))
    if mirror:
        p.restore()


def _draw_undo(p, color, s):
    """撤销：向左回转的箭头。"""
    _arc_arrow(p, color, s, mirror=False)


def _draw_redo(p, color, s):
    """重做：向右回转的箭头（撤销的镜像）。"""
    _arc_arrow(p, color, s, mirror=True)


def _draw_clear(p, color, s):
    """清屏：垃圾桶。带盖和提手，且桶身有竖纹——不然只是个方块。"""
    _pen(p, color, s, 0.85)
    # 提手 + 盖
    p.drawLine(QPointF(s * 0.40, s * 0.20), QPointF(s * 0.60, s * 0.20))
    p.drawLine(QPointF(s * 0.40, s * 0.20), QPointF(s * 0.40, s * 0.28))
    p.drawLine(QPointF(s * 0.60, s * 0.20), QPointF(s * 0.60, s * 0.28))
    p.drawLine(QPointF(s * 0.16, s * 0.30), QPointF(s * 0.84, s * 0.30))
    # 桶身：下方略收，像个桶
    path = QPainterPath()
    path.moveTo(s * 0.24, s * 0.30)
    path.lineTo(s * 0.30, s * 0.84)
    path.lineTo(s * 0.70, s * 0.84)
    path.lineTo(s * 0.76, s * 0.30)
    p.drawPath(path)
    # 竖纹
    _pen(p, color, s, 0.6)
    p.drawLine(QPointF(s * 0.41, s * 0.42), QPointF(s * 0.43, s * 0.74))
    p.drawLine(QPointF(s * 0.57, s * 0.42), QPointF(s * 0.59, s * 0.74))


def _draw_whiteboard(p, color, s):
    """白板：带支架的书写板。有腿，才不会和 LOGO 的屏幕、文件夹混。"""
    _pen(p, color, s, 0.9)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.18, s * 0.76, s * 0.50), s * 0.05, s * 0.05)
    # 支架：两条斜腿
    p.drawLine(QPointF(s * 0.30, s * 0.68), QPointF(s * 0.24, s * 0.86))
    p.drawLine(QPointF(s * 0.70, s * 0.68), QPointF(s * 0.76, s * 0.86))
    # 板面上两道书写示意线
    _pen(p, color, s, 0.55)
    p.drawLine(QPointF(s * 0.24, s * 0.36), QPointF(s * 0.70, s * 0.36))
    p.drawLine(QPointF(s * 0.24, s * 0.52), QPointF(s * 0.56, s * 0.52))


def _chevron(p, color, s, forward):
    """翻页共用：一个粗尖角。forward=True 指右（下一页），False 指左。"""
    _pen(p, color, s, 1.3)
    x1, x2 = (s * 0.40, s * 0.64) if forward else (s * 0.60, s * 0.36)
    path = QPainterPath()
    path.moveTo(x1, s * 0.22)
    path.lineTo(x2, s * 0.50)
    path.lineTo(x1, s * 0.78)
    p.drawPath(path)


def _draw_page_prev(p, color, s):
    """上一页：左尖角。"""
    _chevron(p, color, s, forward=False)


def _draw_page_next(p, color, s):
    """下一页：右尖角。"""
    _chevron(p, color, s, forward=True)


def _draw_close(p, color, s):
    """关闭软件：向下收进托盘。

    不用 × 也不用电源符号——这颗键不结束进程，它把界面收到通知区域。
    「箭头压向一条底线」是最贴近这个动作的通用意象。
    """
    _pen(p, color, s, 0.9)
    p.drawLine(QPointF(s * 0.50, s * 0.16), QPointF(s * 0.50, s * 0.58))
    p.drawLine(QPointF(s * 0.22, s * 0.84), QPointF(s * 0.78, s * 0.84))
    _solid(p, color)
    _poly(p, (s * 0.30, s * 0.50), (s * 0.70, s * 0.50), (s * 0.50, s * 0.72))


def _draw_settings(p, color, s):
    """设置：齿轮。按要求这一颗保持原样，不参与本次重绘。"""
    _pen(p, color, s, 0.8)
    center_r = s * 0.12
    p.drawEllipse(QRectF(s * 0.50 - center_r, s * 0.50 - center_r,
                         center_r * 2, center_r * 2))
    for i in range(6):
        angle = i * 60 * math.pi / 180
        x1 = s * 0.50 + math.cos(angle) * s * 0.20
        y1 = s * 0.50 + math.sin(angle) * s * 0.20
        x2 = s * 0.50 + math.cos(angle) * s * 0.35
        y2 = s * 0.50 + math.sin(angle) * s * 0.35
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


# 图标名 → 绘制函数。main.py / app_lifecycle.py 只通过名字引用，改图形不影响调用方。
# 未知名字会回退到「设置」图标：宁可显示一个已知形状，也不让按钮空白。
_DRAWERS = {
    "logo": _draw_logo,
    "mouse": _draw_mouse_pointer,
    "pen": _draw_pen,
    "highlighter": _draw_highlighter,
    "laser": _draw_laser,
    "eraser": _draw_eraser,
    "select": _draw_select,
    "text": _draw_text,
    "formula": _draw_formula,
    "shape": _draw_shape,
    "line": _draw_line,
    "tools": _draw_tools,
    "folder": _draw_folder,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "clear": _draw_clear,
    "whiteboard": _draw_whiteboard,
    "page_prev": _draw_page_prev,
    "page_next": _draw_page_next,
    "settings": _draw_settings,
    "close": _draw_close,
}


def _draw(name, painter, color, size):
    drawer = _DRAWERS.get(name) or _draw_settings
    drawer(painter, color, size)


def make_ui_pixmap(name, color, size, dpr=1.0):
    """按设备像素比绘制一张 pixmap。托盘/EXE 图标用这个；按钮走 make_ui_icon。"""
    px = max(1, round(size * dpr))
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(dpr)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _draw(name, painter, color, size)
    painter.end()
    return pixmap


def make_ui_icon(name, color, size=24, dpr=1.0):
    """生成一张功能图标。颜色由调用方按当前主题传入。"""
    return QIcon(make_ui_pixmap(name, color, size, dpr))


def make_app_icon():
    """程序标识：同一份 LOGO 按多尺寸打包成一个 QIcon。

    Windows 任务栏/标题栏/托盘/资源管理器各取不同尺寸。只给 32px 一张的话，
    任务栏会把那张图放大成糊的。
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = make_ui_pixmap("logo", "#5b8def", size)
        icon.addPixmap(pixmap)
    return icon
