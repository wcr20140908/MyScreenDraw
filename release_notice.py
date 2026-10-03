# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure release-notice policy and a presentation-only settings card.

The parent calls ``begin_notice_session`` exactly once per normal startup,
then persists the returned state and keeps eligibility/dismissal for that
session. Opening settings, smoke runs and tests must not consume launches.
The widget knows nothing about startup, persistence, versions or i18n.
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QWidget


MAX_NOTICE_LAUNCHES = 2_147_483_647


def normalize_notice_state(raw: object) -> dict:
    """Return a fresh JSON-safe state, ignoring unknown or malformed fields.

    Only integer counts (not booleans, floats or numeric strings) are accepted;
    counts are clamped to [0, MAX_NOTICE_LAUNCHES]. Non-string versions become
    the empty string. The input and its nested values are never modified.
    """
    source = raw if isinstance(raw, dict) else {}
    launches = source.get("launches", 0)
    if not isinstance(launches, int) or isinstance(launches, bool):
        launches = 0
    last_version = source.get("last_version", "")
    return {
        "launches": max(0, min(launches, MAX_NOTICE_LAUNCHES)),
        "last_version": last_version if isinstance(last_version, str) else "",
    }


def begin_notice_session(raw: object, version: str) -> tuple[dict, bool]:
    """Advance one normal launch, returning (new_state, eligible).

    The count increments once per call, saturating at MAX_NOTICE_LAUNCHES.
    Eligibility is the first three launches OR a change from the preceding
    launch's version (including a downgrade or a previously unknown version).
    An empty/non-string current version retains the last known version.
    This function has no I/O, global counter or implicit session deduplication.
    """
    state = normalize_notice_state(raw)
    current_version = version if isinstance(version, str) and version else state["last_version"]
    version_changed = current_version != state["last_version"]
    state["launches"] = min(state["launches"] + 1, MAX_NOTICE_LAUNCHES)
    state["last_version"] = current_version
    return state, state["launches"] <= 3 or version_changed


class ReleaseNoticeCard(QWidget):
    """Compact amber notice using parent-supplied localized plain text.

    ``ReleaseNoticeCard(title, message, parent=None, *, theme_name="light",
    close_text="Close")`` creates the card. ``close_text`` supplies the close
    button's accessible name and tooltip; its visible glyph is language-neutral.
    ``set_theme(theme_name)`` accepts "light" or "dark" (unknown means light).
    Clicking/keyboard-activating close hides only this card, then emits the
    no-argument ``dismissed`` signal. The parent owns session dismissal state.

    ``title_label``, ``message_label`` and ``close_button`` are exposed for
    parent-driven text/accessibility updates. No links or markup are interpreted.
    """

    dismissed = pyqtSignal()

    def __init__(self, title: str, message: str, parent: QWidget | None = None,
                 *, theme_name: str = "light", close_text: str = "Close") -> None:
        super().__init__(parent)
        self.setObjectName("ReleaseNoticeCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

        self.title_label = self._make_label(title, "releaseNoticeTitle")
        self.message_label = self._make_label(message, "releaseNoticeMessage")
        self.close_button = QPushButton("\u00d7", self)
        self.close_button.setObjectName("releaseNoticeClose")
        self.close_button.setAccessibleName(close_text)
        self.close_button.setToolTip(close_text)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setAutoDefault(False)
        self.close_button.setDefault(False)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self._dismiss)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        layout.setColumnStretch(0, 1)
        layout.addWidget(self.title_label, 0, 0)
        layout.addWidget(self.close_button, 0, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.message_label, 1, 0, 1, 2)
        self.set_theme(theme_name)

    def _make_label(self, text: str, name: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # Ignore the longest word's minimum width, but retain height-for-width
        # so long translations/tokens grow vertically rather than clipping.
        policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        label.setSizePolicy(policy)
        label.setMinimumWidth(0)
        return label

    def sizeHint(self) -> QSize:
        # Ignored label widths otherwise give the grid a near-zero preferred
        # width and an excessively tall hint. This is a hint, not a width limit.
        width = 280
        return QSize(width, self.heightForWidth(width))

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def set_theme(self, theme_name: str) -> None:
        """Apply local amber/brown styling without changing card visibility."""
        if theme_name == "dark":
            background, text, title = "#3b2c16", "#ffe2a8", "#ffdb8a"
            border, hover, focus = "#95703a", "#594120", "#ffdb8a"
        else:
            background, text, title = "#fff4d6", "#58360d", "#663c0b"
            border, hover, focus = "#d6a64e", "#f4dfaf", "#663c0b"
        self.setStyleSheet(f"""
            QWidget#ReleaseNoticeCard {{
                background-color: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#releaseNoticeTitle, QLabel#releaseNoticeMessage {{
                background: transparent;
                color: {text};
                border: none;
                padding: 0;
                font-size: 13px;
            }}
            QLabel#releaseNoticeTitle {{
                color: {title};
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#releaseNoticeClose {{
                background: transparent;
                color: {text};
                border: 2px solid transparent;
                border-radius: 4px;
                padding: 0;
                font-size: 18px;
            }}
            QPushButton#releaseNoticeClose:hover,
            QPushButton#releaseNoticeClose:pressed {{
                background-color: {hover};
            }}
            QPushButton#releaseNoticeClose:focus {{
                border-color: {focus};
            }}
        """)
