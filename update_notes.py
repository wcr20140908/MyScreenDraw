# SPDX-License-Identifier: GPL-3.0-or-later
"""Local installed-version history and presentation of GitHub Release notes.

History is separate from settings and never infers installations from downloads.
Network access is injected by the application; widgets do not fetch or own threads.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from PyQt6.QtCore import QByteArray, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QTextDocument, QTextOption
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from i18n import tr, trf
from persistence import atomic_write_json

MAX_NOTES_BYTES = 128 * 1024
MAX_HISTORY_BYTES = 16 * 1024 * 1024
MAX_VERSIONS = 100
_VERSION = re.compile(r"[vV]?((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-(?:beta|rc)\.(?:0|[1-9]\d*))?)\Z")


def version_tag(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    match = _VERSION.fullmatch(value.strip())
    return "v" + match[1] if match else None


def release_body(release):
    """Return (body, error); absent/malformed is different from a published empty body."""
    if not isinstance(release, dict) or "body" not in release:
        return None, "bad_release_notes"
    body = release["body"]
    if body is None:
        body = ""
    if not isinstance(body, str):
        return None, "bad_release_notes"
    try:
        size = len(body.encode("utf-8"))
    except UnicodeError:
        return None, "bad_release_notes"
    if size > MAX_NOTES_BYTES:
        return None, "notes_too_large"
    return body, None


class UpdateHistory:
    """Lazy, bounded local record. Read errors never overwrite the damaged file."""

    def __init__(self, path):
        self.path = Path(path)
        self.installed = []
        self.notes = {}
        self.read_error = None
        self.write_error = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_HISTORY_BYTES + 1)
            if len(raw) > MAX_HISTORY_BYTES:
                raise ValueError("history_too_large")
            data = json.loads(raw.decode("utf-8"))
            if (not isinstance(data, dict) or data.get("schema") != 1
                    or not isinstance(data.get("installed"), list)
                    or not isinstance(data.get("notes"), dict)):
                raise ValueError("invalid_history")
            seen = set()
            for entry in data["installed"][:MAX_VERSIONS]:
                if not isinstance(entry, dict):
                    continue
                tag = version_tag(entry.get("tag"))
                when = entry.get("first_seen")
                if tag and tag not in seen and isinstance(when, str) and len(when) <= 64:
                    self.installed.append({"tag": tag, "first_seen": when})
                    seen.add(tag)
            for tag, body in list(data["notes"].items())[:MAX_VERSIONS + 1]:
                key = version_tag(tag)
                text, error = release_body({"body": body})
                if key and error is None:
                    self.notes[key] = text
        except FileNotFoundError:
            pass
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            self.read_error = f"{type(exc).__name__}: {exc}"

    def _save(self):
        if self.read_error:
            return
        try:
            # JSON escapes can occupy six bytes per source character. Bound the
            # serialized cache too, reserving room for the installed-version list.
            sizes = [(tag, len(json.dumps(body, ensure_ascii=False).encode("utf-8")) + len(tag) + 16)
                     for tag, body in self.notes.items()]
            total = sum(size for _, size in sizes)
            for tag, size in sizes:
                if total <= MAX_HISTORY_BYTES - 64 * 1024:
                    break
                self.notes.pop(tag)
                total -= size
            self.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(str(self.path), {
                "schema": 1, "installed": self.installed, "notes": self.notes,
            })
            self.write_error = None
        except (OSError, ValueError) as exc:
            self.write_error = f"{type(exc).__name__}: {exc}"

    def record_running(self, version):
        self.load()
        tag = version_tag(version)
        if not tag or self.read_error:
            return
        if any(item["tag"] == tag for item in self.installed):
            if self.write_error:
                self._save()
            return
        self.installed.insert(0, {"tag": tag, "first_seen": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        self.installed = self.installed[:MAX_VERSIONS]
        self._prune_notes(tag)
        self._save()

    def _prune_notes(self, candidate):
        keep = {item["tag"] for item in self.installed} | {candidate}
        self.notes = {tag: body for tag, body in self.notes.items() if tag in keep}

    def remember_notes(self, tag, body):
        self.load()
        tag = version_tag(tag)
        body, error = release_body({"body": body})
        if not tag or error or self.read_error:
            return
        if self.notes.get(tag) == body and tag in self.notes and not self.write_error:
            return
        if not any(item["tag"] == tag for item in self.installed):
            self._prune_notes(tag)
        self.notes[tag] = body
        self._save()


class NotesWorker(QThread):
    result = pyqtSignal(str, object, object)

    def __init__(self, tag, fetch, parent):
        super().__init__(parent)
        self.tag, self.fetch = tag, fetch

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            body, error = self.fetch(self.tag)
        except Exception as exc:
            body, error = None, f"error_{type(exc).__name__}"
        if not self.isInterruptionRequested():
            self.result.emit(self.tag, body, error)


class NotesController(QObject):
    """One bounded worker, latest requested version wins the waiting slot."""

    changed = pyqtSignal(str)

    def __init__(self, path, fetch, allowed, parent=None):
        super().__init__(parent)
        self.history = UpdateHistory(path)
        self.fetch, self.allowed = fetch, allowed
        self.states = {}
        self._worker = None
        self._wanted = None
        self._stopping = False

    def state(self, tag):
        tag = version_tag(tag)
        if tag in self.states:
            return self.states[tag]
        self.history.load()
        return (self.history.notes[tag], None) if tag in self.history.notes else (None, None)

    def prime(self, tag, body, error):
        tag = version_tag(tag)
        if not tag or self._stopping:
            return
        if error is None and body is not None:
            body, error = release_body({"body": body})
        self.states[tag] = (body, error)
        if error is None and body is not None:
            self.history.remember_notes(tag, body)
        self.changed.emit(tag)

    def request(self, tag, *, force=False):
        tag = version_tag(tag)
        if not tag or self._stopping:
            return
        self._wanted = None
        body, error = self.state(tag)
        if not force and (body is not None or error is not None):
            self.changed.emit(tag)
            return
        if not self.allowed():
            self.prime(tag, None, "notes_unavailable")
            return
        self.states[tag] = (None, None)
        self.changed.emit(tag)
        if self._worker is not None:
            # Switching the selector does not spawn unbounded requests. The active
            # response is still cached under its own tag, never under the new one.
            self._wanted = tag if self._worker.tag != tag else None
            return
        self._start(tag)

    def _start(self, tag):
        worker = NotesWorker(tag, self.fetch, self)
        worker.result.connect(self._received)
        worker.finished.connect(self._finished)
        self._worker = worker
        worker.start()

    def _received(self, tag, body, error):
        if self._stopping:
            return
        if not self.allowed():
            body, error = None, "notes_unavailable"
        self.prime(tag, body, error)

    def _finished(self):
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        wanted, self._wanted = self._wanted, None
        if wanted and not self._stopping:
            self.request(wanted)

    def stop(self):
        self._stopping = True
        self._wanted = None
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait()


def notes_error_text(error):
    keys = {
        "http_404": "update_notes_not_found", "rate_limited": "update_rate_limited",
        "bad_release_notes": "update_notes_bad_response", "bad_json": "update_notes_bad_response",
        "notes_too_large": "update_notes_too_large", "notes_unavailable": "update_notes_unavailable",
    }
    if str(error).startswith("net_") or "Timeout" in str(error):
        detail = tr("update_notes_network")
    else:
        detail = tr(keys[error]) if error in keys else str(error)
    return trf("update_notes_failed", detail=detail)


class NotesBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReleaseNotesBrowser")
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

    def loadResource(self, resource_type, name):
        # Release Markdown is untrusted. Never load remote tracking images or
        # local files, even when the user only expands a section offline.
        return QByteArray()

    def _open_link(self, url):
        if url.scheme().lower() in ("https", "http") and url.host():
            QDesktopServices.openUrl(url)


class NotesView(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.tag = None
        self._rendered = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.browser = NotesBrowser()
        self.browser.setMinimumWidth(0)
        self.browser.setMinimumHeight(160)
        layout.addWidget(self.browser, 1)
        self.retry = QPushButton(tr("update_notes_retry"))
        self.retry.clicked.connect(self._retry)
        layout.addWidget(self.retry)
        controller.changed.connect(self._refresh)

    def select(self, tag):
        self.tag = version_tag(tag)
        self._refresh(self.tag)
        self.controller.request(self.tag)

    def _retry(self):
        self.controller.request(self.tag, force=True)

    def _refresh(self, tag):
        if tag != self.tag or not tag:
            return
        body, error = self.controller.state(tag)
        state = (tag, body, error)
        if state == self._rendered:
            return
        self._rendered = state
        self.status.setVisible(error is not None or body is None or not body.strip())
        self.browser.setVisible(error is None and body is not None and bool(body.strip()))
        self.retry.setVisible(error is not None or body is not None)
        if error is not None:
            self.status.setText(notes_error_text(error))
            self.browser.clear()
        elif body is None:
            self.status.setText(tr("update_notes_loading"))
            self.browser.clear()
        elif not body.strip():
            self.status.setText(tr("update_notes_empty"))
            self.browser.clear()
        else:
            self.status.clear()
            self.browser.document().setMarkdown(body, QTextDocument.MarkdownFeature.MarkdownNoHTML)
            self.browser.moveCursor(self.browser.textCursor().MoveOperation.Start)


class ReleaseNotesSection(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.tag = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QToolButton()
        self.toggle.setObjectName("ReleaseNotesToggle")
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.toggle)
        self.view = NotesView(controller)
        self.view.setMaximumHeight(300)
        layout.addWidget(self.view)
        self.view.hide()
        self.toggle.toggled.connect(self._toggle)
        self.hide()

    def set_tag(self, tag):
        tag = version_tag(tag)
        if tag != self.tag:
            self.toggle.setChecked(False)
        self.tag = tag
        self.toggle.setText(trf("update_notes_title", value=tag or ""))
        self.setVisible(tag is not None)
        if self.toggle.isChecked():
            self.view.select(tag)

    def _toggle(self, expanded):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.view.setVisible(expanded)
        if expanded and self.tag:
            self.view.select(self.tag)


class UpdateHistoryDialog(QDialog):
    def __init__(self, controller, current_version, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdateHistory")
        self.setWindowTitle(tr("update_history"))
        self.controller = controller
        history = controller.history
        history.load()
        layout = QVBoxLayout(self)
        hint = QLabel(tr("update_history_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.storage_status = QLabel()
        self.storage_status.setTextFormat(Qt.TextFormat.PlainText)
        self.storage_status.setWordWrap(True)
        layout.addWidget(self.storage_status)
        self.versions = QComboBox()
        current = version_tag(current_version)
        if current:
            self.versions.addItem(trf("update_history_current", value=current), current)
        for entry in history.installed:
            if entry["tag"] != current:
                self.versions.addItem(entry["tag"], entry["tag"])
        layout.addWidget(self.versions)
        self.seen = QLabel()
        self.seen.setTextFormat(Qt.TextFormat.PlainText)
        self.seen.setWordWrap(True)
        layout.addWidget(self.seen)
        self.view = NotesView(controller)
        layout.addWidget(self.view, 1)
        close = QPushButton(tr("teaching_close"))
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)
        self.versions.currentIndexChanged.connect(self._select)
        controller.changed.connect(self._storage_status)
        self.resize(640, 520)
        if self.screen():
            available = self.screen().availableGeometry()
            self.resize(min(self.width(), int(available.width() * .9)),
                        min(self.height(), int(available.height() * .85)))
        self._select()

    def _storage_status(self, *_):
        history = self.controller.history
        error = history.read_error or history.write_error
        self.storage_status.setVisible(bool(error))
        self.storage_status.setText(trf("update_history_read_failed" if history.read_error else
                                       "update_history_write_failed", detail=error) if error else "")

    def _select(self, *_):
        tag = self.versions.currentData()
        entry = next((entry for entry in self.controller.history.installed if entry["tag"] == tag), None)
        self.seen.setText(trf("update_history_seen", value=entry["first_seen"]) if entry else tr("update_history_empty"))
        self._storage_status()
        self.view.select(tag)
