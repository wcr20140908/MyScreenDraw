# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone, read-only autosave recovery picker.

The host supplies a safe, validating loader and a page-to-pixmap renderer. Neither
callback is used on unselected older versions; this module never writes autosaves.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QVBoxLayout, QWidget)

from i18n import tr, trf


_PREVIEW_SIZE = QSize(360, 220)


def _label(key: str, **values: object) -> str:
    return trf(key, **values) if values else tr(key)


class RecoveryDialog(QDialog):
    """Choose one validated recovery document without applying it to the canvas.

    ``selected_data`` and ``selected_path`` are set only for a successfully loaded
    selection. A caller must check ``exec() == QDialog.DialogCode.Accepted`` before
    applying either; rejecting the dialog also clears both attributes.
    """

    def __init__(self, candidates: Sequence[str | Path],
                 load_data: Callable[[str | Path], dict],
                 render_preview: Callable[[dict, QSize], QPixmap], parent=None):
        super().__init__(parent)
        self._candidates = tuple(candidates)  # Already newest-first; no filesystem scan.
        self._load_data = load_data
        self._render_preview = render_preview
        self.selected_data: dict | None = None
        self.selected_path: str | Path | None = None
        self.setWindowTitle(_label("recovery_title"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_label("recovery_intro")))
        self.details = QLabel(_label("recovery_no_valid"))
        layout.addWidget(self.details)
        self.page_selector = QComboBox()
        self.page_selector.setAccessibleName(_label("recovery_page", number=""))
        self.page_selector.hide()
        layout.addWidget(self.page_selector)
        self.preview = QLabel(_label("recovery_preview_unavailable"))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(_PREVIEW_SIZE)
        layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.advanced_toggle = QPushButton(_label("recovery_advanced"))
        self.advanced_toggle.setCheckable(True)
        layout.addWidget(self.advanced_toggle)
        self.advanced_options = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_options)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.version_list = QListWidget()
        for path in self._candidates:
            self.version_list.addItem(Path(path).name)
        advanced_layout.addWidget(self.version_list)
        self.advanced_options.hide()
        layout.addWidget(self.advanced_options)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.not_now_button = QPushButton(_label("recovery_not_now"))
        self.restore_button = QPushButton(_label("recovery_restore"))
        self.restore_button.setEnabled(False)
        self.not_now_button.setDefault(True)
        buttons.addWidget(self.not_now_button)
        buttons.addWidget(self.restore_button)
        layout.addLayout(buttons)

        self.advanced_toggle.toggled.connect(self.advanced_options.setVisible)
        self.version_list.currentRowChanged.connect(self._select_index)
        self.page_selector.currentIndexChanged.connect(self._show_preview)
        self.not_now_button.clicked.connect(self.reject)
        self.restore_button.clicked.connect(self.accept)

        # Only decode as far as the newest valid candidate. Older entries remain lazy.
        for index in range(len(self._candidates)):
            if self._select_index(index):
                self.version_list.blockSignals(True)
                self.version_list.setCurrentRow(index)
                self.version_list.blockSignals(False)
                break
        if self.selected_data is None:
            self.details.setText(_label("recovery_no_valid"))

    def _clear_selection(self) -> None:
        self.selected_data = None
        self.selected_path = None
        self.restore_button.setEnabled(False)
        self.preview.clear()  # Never show a pixmap from the previous document.
        self.preview.setText(_label("recovery_preview_unavailable"))
        self.page_selector.blockSignals(True)
        self.page_selector.clear()
        self.page_selector.blockSignals(False)
        self.page_selector.hide()

    def _select_index(self, index: int) -> bool:
        self._clear_selection()
        if index < 0 or index >= len(self._candidates):
            self.details.setText(_label("recovery_no_valid"))
            return False
        path = self._candidates[index]
        try:
            data = self._load_data(path)
            # The loader is expected to validate the entire document; these basic
            # checks also prevent a broken callback result reaching the renderer.
            if not isinstance(data, dict) or not isinstance(data.get("pages"), list) or not data["pages"]:
                raise ValueError("invalid recovery document")
            if not all(isinstance(page, dict) for page in data["pages"]):
                raise ValueError("invalid recovery page")
        except Exception:
            self.details.setText(_label("recovery_invalid_version"))
            return False

        self.selected_path = path
        self.selected_data = data
        pages = data["pages"]
        timestamp = data.get("saved_at") or data.get("timestamp") or Path(path).name
        self.details.setText(_label("recovery_saved_pages", timestamp=timestamp, count=len(pages)))
        self.page_selector.blockSignals(True)
        for number in range(1, len(pages) + 1):
            self.page_selector.addItem(_label("recovery_page", number=number))
        current = data.get("current_page", 0)
        if not isinstance(current, int) or isinstance(current, bool):
            current = 0
        self.page_selector.setCurrentIndex(max(0, min(current, len(pages) - 1)))
        self.page_selector.blockSignals(False)
        self.page_selector.setVisible(len(pages) > 1)
        self.restore_button.setEnabled(True)
        self._show_preview()
        return True

    def _show_preview(self, _index: int = -1) -> None:
        self.preview.clear()
        self.preview.setText(_label("recovery_preview_unavailable"))
        if self.selected_data is None:
            return
        page = self.selected_data["pages"][self.page_selector.currentIndex()]
        try:
            pixmap = self._render_preview(page, QSize(_PREVIEW_SIZE))
            if not isinstance(pixmap, QPixmap) or pixmap.isNull():
                return
            bounded = pixmap.scaled(_PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            if not bounded.isNull():
                self.preview.setPixmap(bounded)
        except Exception:
            # A failed preview does not invalidate successfully loaded document data.
            pass

    def accept(self) -> None:
        if self.selected_data is not None and self.selected_path is not None:
            super().accept()

    def reject(self) -> None:
        self._clear_selection()
        super().reject()
