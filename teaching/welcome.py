# SPDX-License-Identifier: GPL-3.0-or-later
"""Nonmodal first-use welcome. All choices are requests to the host policy."""
from __future__ import annotations

from collections.abc import Callable

from PyQt6 import sip
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


from .onboarding import TeachingReadiness, WelcomePolicy


class TeachingWelcome(QDialog):
    decision_made = pyqtSignal(str)

    def __init__(self, translate: Callable[[str], str], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setModal(False)
        self.setWindowTitle(translate('teaching_welcome_title'))
        self._decision: str | None = None
        self.body_label = QLabel(translate('teaching_welcome_body'), self)
        self.body_label.setTextFormat(Qt.TextFormat.PlainText)
        self.body_label.setWordWrap(True)
        self.start_button = QPushButton(translate('teaching_welcome_start'), self)
        self.later_button = QPushButton(translate('teaching_welcome_later'), self)
        actions = QHBoxLayout()
        for button in (self.start_button, self.later_button):
            button.setAutoDefault(False)
            button.setDefault(False)
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.body_label, 1)
        layout.addLayout(actions)
        self.resize(480, 240)
        self.start_button.clicked.connect(lambda: self._choose('accepted'))
        self.later_button.clicked.connect(lambda: self._choose('skipped'))

    def _record_choice(self, decision: str) -> None:
        if self._decision is None:
            self._decision = decision
            self.hide()
            self.decision_made.emit(decision)

    def _choose(self, decision: str) -> None:
        self._record_choice(decision)
        if not sip.isdeleted(self):
            self.close()

    def reject(self) -> None:
        self._choose('dismissed')

    def closeEvent(self, event: QCloseEvent) -> None:
        self._record_choice('dismissed')
        event.accept()


class WelcomeCoordinator(QObject):
    """Host-driven bridge: safe snapshot -> one welcome -> persisted choice.

    The application calls maybe_show() only after building a trusted readiness
    snapshot. No timer, application launch or edit commit is hidden here; the
    explicit Start choice invokes the supplied trusted start_core callback.
    """

    failed = pyqtSignal(str)

    def __init__(self, policy: WelcomePolicy, *, translate: Callable[[str], str],
                 start_core: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.policy, self._translate, self._start_core = policy, translate, start_core
        self._window_parent = parent
        self._dialog: TeachingWelcome | None = None
        self._closed = False

    @property
    def dialog(self) -> TeachingWelcome | None:
        value = self._dialog
        return value if value is not None and not sip.isdeleted(value) else None

    def maybe_show(self, readiness: TeachingReadiness) -> bool:
        if self._closed or self.dialog is not None or not self.policy.claim_welcome(readiness):
            return False
        try:
            dialog = TeachingWelcome(self._translate, self._window_parent)
            self._dialog = dialog
            dialog.decision_made.connect(self._decide)
            dialog.destroyed.connect(lambda: self._forget(dialog))
            dialog.show()  # WA_ShowWithoutActivating; never activateWindow/raise_.
        except Exception:
            self.failed.emit('teaching_unavailable')
            return False
        return True

    def _decide(self, decision: str) -> None:
        try:
            self.policy.decide(decision, start_core=self._start_core)
        except Exception:
            # A failing launcher must not escape a Qt signal and terminate the app.
            self.failed.emit('teaching_session_start_failed')

    def _forget(self, dialog: TeachingWelcome) -> None:
        if self._dialog is dialog:
            self._dialog = None

    def close(self) -> None:
        if self._closed:
            return
        dialog = self.dialog
        if dialog is not None:
            dialog.close()  # A visible welcome is explicitly dismissed on close.
        self._closed = True
