# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent, host-driven context teaching hint view."""
from __future__ import annotations

from typing import Literal

from PyQt6 import sip
from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QPaintEvent, QPalette, QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)


Decision = Literal["started", "dismissed"]


class _HintLabel(QLabel):
    """Plain text that can wrap even when the host text has no word breaks."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setText(text)

    def _text_flags(self) -> int:
        return (
            int(self.alignment())
            | int(Qt.TextFlag.TextWordWrap)
            | int(Qt.TextFlag.TextWrapAnywhere)
        )

    def heightForWidth(self, width: int) -> int:
        text_rect = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, width), 16777215), self._text_flags(), self.text()
        )
        return text_rect.height()

    def sizeHint(self) -> QSize:
        return QSize(360, self.heightForWidth(360))

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height())

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QStylePainter(self)
        painter.drawItemText(
            self.contentsRect(), self._text_flags(), self.palette(),
            self.isEnabled(), self.text(), self.foregroundRole(),
        )


class _HintButton(QPushButton):
    """Wrap host text while retaining QPushButton behavior and Qt styling."""

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(text, parent)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAutoDefault(False)
        self.setDefault(False)

    def _text_flags(self) -> int:
        return (
            int(Qt.AlignmentFlag.AlignCenter)
            | int(Qt.TextFlag.TextWordWrap)
            | int(Qt.TextFlag.TextWrapAnywhere)
            | int(Qt.TextFlag.TextShowMnemonic)
        )

    def heightForWidth(self, width: int) -> int:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        base_height = super().sizeHint().height()
        option.rect = QRect(0, 0, max(1, width), base_height)
        contents = self.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, self
        )
        text_rect = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, contents.width()), 16777215),
            self._text_flags(),
            self.text(),
        )
        return max(base_height, text_rect.height() + base_height - contents.height())

    def sizeHint(self) -> QSize:
        width = min(380, super().sizeHint().width())
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().sizeHint().height())

    def paintEvent(self, event: QPaintEvent) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        contents = self.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, self
        )
        painter.drawItemText(
            contents, self._text_flags(), option.palette,
            self.isEnabled(), text, QPalette.ColorRole.ButtonText,
        )


class ContextTeachingHint(QFrame):
    """Nonmodal, one-shot requests for the host's ContextHintPolicy.

    All four strings are already translated by the host. Showing this view has
    no teaching, persistence, translation, or application-start side effects.
    Public label/button fields are available for host wiring and inspection.
    """

    start_requested = pyqtSignal()
    dismissed = pyqtSignal()

    _MAX_WIDTH = 420
    _MAX_HEIGHT = 480
    _WORK_AREA_MARGIN = 8

    def __init__(
        self,
        title: str,
        body: str,
        start_label: str,
        close_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(title)
        self.setMaximumSize(self._MAX_WIDTH, self._MAX_HEIGHT)
        self._decision: Decision | None = None

        self.title_label = _HintLabel(title)
        self.body_label = _HintLabel(body)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.body_label)
        content_layout.addStretch()

        self.body_scroll = QScrollArea(self)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body_scroll.setMinimumSize(0, 0)
        self.body_scroll.setWidget(content)

        self.start_button = _HintButton(start_label, self)
        self.close_button = _HintButton(close_label, self)
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.addWidget(self.body_scroll, 1)
        layout.addWidget(self.start_button)
        layout.addWidget(self.close_button)
        self.resize(self._MAX_WIDTH, 300)

        self.start_button.clicked.connect(self.request_start)
        self.close_button.clicked.connect(self.dismiss)

    @property
    def decided(self) -> bool:
        """Whether this hint has already made its one terminal decision."""
        return self._decision is not None

    def request_start(self) -> None:
        """Request teaching once, only while the undecided hint is visible."""
        self._choose("started")

    def dismiss(self) -> None:
        """Dismiss once, only while the undecided hint is visible."""
        self._choose("dismissed")

    def _choose(self, decision: Decision) -> None:
        if sip.isdeleted(self) or self.decided or not self.isVisible():
            return
        self._decision = decision
        signal = self.start_requested if decision == "started" else self.dismissed
        self.close()
        # Close schedules deletion. Emitting last lets a synchronous slot
        # destroy the hint without any follow-up access to its SIP.
        if not sip.isdeleted(self):
            signal.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
        if sip.isdeleted(self):
            return
        should_dismiss = not self.decided and self.isVisible()
        if not self.decided:
            self._decision = "dismissed"
        if should_dismiss:
            # Settle the decision and event before a slot can delete us.
            self.dismissed.emit()

    def showEvent(self, event: QShowEvent) -> None:
        self._fit_work_area()
        super().showEvent(event)

    def _fit_work_area(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        margin = self._WORK_AREA_MARGIN
        inset = available.adjusted(margin, margin, -margin, -margin)
        if not inset.isEmpty():
            available = inset
        frame = self.frameGeometry()
        frame_width = max(0, frame.width() - self.width())
        frame_height = max(0, frame.height() - self.height())
        max_width = max(1, min(self._MAX_WIDTH, available.width() - frame_width))
        max_height = max(1, min(self._MAX_HEIGHT, available.height() - frame_height))
        self.setMaximumSize(max_width, max_height)
        self.resize(min(self.width(), max_width), min(self.height(), max_height))
        frame = self.frameGeometry()
        x = max(available.left(), min(frame.x(), available.right() + 1 - frame.width()))
        y = max(available.top(), min(frame.y(), available.bottom() + 1 - frame.height()))
        self.move(x, y)
