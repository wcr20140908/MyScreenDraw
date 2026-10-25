# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""A non-interactive Settings decoration for an available software update."""
from math import sin, tau

from PyQt6.QtCore import QElapsedTimer, QEvent, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QConicalGradient, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class UpdateIndicator(QWidget):
    badge_text = 'NEW！'

    def __init__(self, button):
        super().__init__(button)
        self.available = False
        self.setObjectName('SettingsUpdateIndicator')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet('background: transparent; border: none;')
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update)
        button.installEventFilter(self)
        self.hide()

    def set_available(self, available):
        available = bool(available)
        if available and not self.available:
            self.clock.start()
        self.available = available
        self.setGeometry(self.parentWidget().rect())
        self.setVisible(available)
        if available:
            self.raise_()
            self.update()
        self._sync_timer()

    def _sync_timer(self):
        if self.available and self.isVisible():
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
        return False

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        if not self.available:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        seconds = self.clock.elapsed() / 1000 if self.clock.isValid() else 0
        # Slow continuous breathing, with no flashing or changing button layout.
        pulse = 0.8 + 0.2 * sin(seconds * tau / 4)
        scale = max(0.75, min(self.width() / 56, self.height() / 44))
        inset = 3 * scale
        ring = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        gradient = QConicalGradient(ring.center(), seconds * 16)
        for offset, color in ((0,'#00efff'),(.28,'#a257ff'),(.53,'#ff42b8'),(.78,'#42bfff'),(1,'#00efff')):
            gradient.setColorAt(offset, QColor(color))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for width, opacity in ((7, .12), (4.5, .24), (2, 1)):
            painter.setOpacity(opacity * pulse)
            painter.setPen(QPen(QBrush(gradient), width * scale))
            painter.drawRoundedRect(ring, 7 * scale, 7 * scale)
        painter.setOpacity(1)
        height = min(18 * scale, self.height() * .26)
        width = min(34 * scale, self.width() - 8 * scale)
        badge = QRectF(self.width() - width - 3 * scale, 2 * scale, width, height)
        painter.setPen(QPen(QColor('#ff8795'), .7 * scale))
        painter.setBrush(QColor('#e71f3e'))
        painter.drawRoundedRect(badge, 3 * scale, 3 * scale)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(max(8, round(height * .76)))
        painter.setFont(font)
        painter.setPen(QColor('white'))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.badge_text)
