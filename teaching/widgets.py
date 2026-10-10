# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone teaching views. No engine, document, process or desktop-hook access.

The host translates teaching_* keys and connects request signals to its session.
Closing disposes view windows; hiding is presentation-only. InputBarrier must be
closed by its host and suspended around native dialogs. All geometry is in Qt
logical/global coordinates, using the explicitly supplied screen work area.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
import weakref

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QRect, QSize, QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCloseEvent, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout,
    QMenu, QPushButton, QScrollArea, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .models import TutorialCatalog, TutorialCourse, TutorialStep
from .state import TutorialStateStore

Translate = Callable[[str], str]
_CHAPTER_ROLE = Qt.ItemDataRole.UserRole


class TeachingCenter(QDialog):
    """Read-only catalog/progress browser; all launches are requests to the host.

    search_edit matches localized titles and stable IDs; filter_combo carries
    all/completed/unfinished, independent of its translated labels.
    start_requested carries (course_id, chapter_id), also for replay/resume.
    Resume reveals last_started only if that pair still exists in this catalog.
    refresh() preserves filters/visible selection without writing the store.
    """

    start_requested = pyqtSignal(str, str)

    def __init__(self, catalog: TutorialCatalog, state_store: TutorialStateStore,
                 translate: Translate, parent: QWidget | None = None) -> None:
        from PyQt6.QtWidgets import QLineEdit

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(translate('teaching_center_title'))
        self._catalog = catalog
        self._store = state_store
        self._translate = translate
        self._items: dict[tuple[str, str], QTreeWidgetItem] = {}
        self._course_items: dict[str, QTreeWidgetItem] = {}
        self._completed: set[tuple[str, str]] = set()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(translate('teaching_search'))
        self.search_edit.setClearButtonEnabled(True)
        self.filter_combo = QComboBox(self)
        for status in ('all', 'completed', 'unfinished'):
            self.filter_combo.addItem(translate(f'teaching_filter_{status}'), status)
        filters = QHBoxLayout()
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.filter_combo)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([translate('teaching_catalog'), translate('teaching_status')])
        self.warning_label = QLabel(translate('teaching_progress_save_failed'), self)
        self.warning_label.setTextFormat(Qt.TextFormat.PlainText)
        self.warning_label.setWordWrap(True)
        self.start_button = QPushButton(translate('teaching_start'), self)
        self.replay_button = QPushButton(translate('teaching_replay'), self)
        self.resume_button = QPushButton(translate('teaching_resume'), self)
        self.close_button = QPushButton(translate('teaching_close'), self)
        buttons = QHBoxLayout()
        for button in (self.start_button, self.replay_button, self.resume_button, self.close_button):
            button.setAutoDefault(False)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.warning_label)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)
        self.search_edit.textChanged.connect(self._apply_filters)
        self.filter_combo.currentIndexChanged.connect(self._apply_filters)
        self.tree.currentItemChanged.connect(self._update_actions)
        self.tree.itemActivated.connect(self._request_selected)
        self.start_button.clicked.connect(self._request_selected)
        self.replay_button.clicked.connect(self._request_selected)
        self.resume_button.clicked.connect(self._request_resume)
        self.close_button.clicked.connect(self.reject)
        self.resize(640, 480)
        self.refresh()
        pair = self._last_started()
        if pair is not None:
            self.select_chapter(*pair)

    @staticmethod
    def _item_visible(item: QTreeWidgetItem | None) -> bool:
        if item is None:
            return False
        while item is not None:
            if item.isHidden():
                return False
            item = item.parent()
        return True

    @property
    def selected_chapter(self) -> tuple[str, str] | None:
        item = self.tree.currentItem()
        if not self._item_visible(item):
            return None
        value = item.data(0, _CHAPTER_ROLE)
        return tuple(value) if value is not None else None

    def select_chapter(self, course_id: str, chapter_id: str) -> bool:
        item = self._items.get((course_id, chapter_id))
        if not self._item_visible(item):
            item = None
            self.tree.clearSelection()
        self.tree.setCurrentItem(item)
        if item is not None:
            parent = item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
            self.tree.scrollToItem(item)
        self._update_actions()
        return item is not None

    def _last_started(self) -> tuple[str, str] | None:
        last = self._store.last_started
        if last is None:
            return None
        pair = (last['course_id'], last['chapter_id'])
        return pair if pair in self._items else None

    def refresh(self) -> None:
        self.warning_label.setVisible(self._store.read_only)
        selected = self.selected_chapter
        blocker = QSignalBlocker(self.tree)
        self._items.clear()
        self._course_items.clear()
        self._completed.clear()
        self.tree.clear()
        grouped: set[str] = set()
        courses = {course.id: course for course in self._catalog.courses}
        for group in self._catalog.groups:
            group_item = QTreeWidgetItem(self.tree, [self._translate(group.title_key)])
            for course_id in group.courses:
                self._add_course(courses[course_id], group_item)
                grouped.add(course_id)
        for course in self._catalog.courses:
            if course.id not in grouped:
                self._add_course(course, self.tree)
        self.tree.expandAll()
        self._apply_filters()
        self.tree.resizeColumnToContents(0)
        if selected is not None:
            self.select_chapter(*selected)
        del blocker
        self._update_actions()

    def _add_course(self, course: TutorialCourse, parent: QTreeWidget | QTreeWidgetItem) -> None:
        course_item = QTreeWidgetItem(parent, [self._translate(course.title_key)])
        self._course_items[course.id] = course_item
        completed = 0
        for chapter in course.chapters:
            record = self._store.chapter_record(chapter.id)
            needs_review = record['needs_review'] or (
                record['completed_revision'] is not None
                and record['completed_revision'] != course.compat_revision)
            status = self._translate(f"teaching_status_{record['status']}")
            if needs_review:
                status += ' · ' + self._translate('teaching_status_needs_review')
            item = QTreeWidgetItem(course_item, [self._translate(chapter.title_key), status])
            pair = (course.id, chapter.id)
            item.setData(0, _CHAPTER_ROLE, pair)
            self._items[pair] = item
            if record['status'] == 'completed' and not needs_review:
                self._completed.add(pair)
                completed += 1
        course_item.setText(1, self._translate('teaching_course_progress').format(
            completed=completed, total=len(course.chapters)))

    def _apply_filters(self, *_args: object) -> None:
        current = self.tree.currentItem()
        blocker = QSignalBlocker(self.tree)
        query = self.search_edit.text().strip().casefold()
        status = self.filter_combo.currentData()
        for course in self._catalog.courses:
            course_item = self._course_items[course.id]
            course_match = query in course.id.casefold() or query in course_item.text(0).casefold()
            visible = False
            for chapter in course.chapters:
                pair = (course.id, chapter.id)
                item = self._items[pair]
                matches = (course_match or query in chapter.id.casefold()
                           or query in item.text(0).casefold())
                completed = pair in self._completed
                matches_status = (status == 'all' or status == 'completed' and completed
                                  or status == 'unfinished' and not completed)
                shown = matches and matches_status
                item.setHidden(not shown)
                visible = visible or shown
            course_item.setHidden(not visible)
        for index in range(len(self._catalog.groups)):
            group_item = self.tree.topLevelItem(index)
            group_item.setHidden(all(group_item.child(child).isHidden()
                                     for child in range(group_item.childCount())))
        if not self._item_visible(current):
            self.tree.clearSelection()
            current = None
        self.tree.setCurrentItem(current)
        del blocker
        self._update_actions()

    def _update_actions(self, *_args: object) -> None:
        selected = self.selected_chapter is not None
        self.start_button.setEnabled(selected)
        self.replay_button.setEnabled(selected)
        self.resume_button.setEnabled(self._last_started() is not None)

    def _request_selected(self, *_args: object) -> None:
        if (_args and isinstance(_args[0], QTreeWidgetItem)
                and _args[0] is not self.tree.currentItem()):
            return
        pair = self.selected_chapter
        if pair is not None:
            self.start_requested.emit(*pair)

    def _request_resume(self) -> None:
        pair = self._last_started()
        if pair is None:
            return
        if not self._item_visible(self._items[pair]):
            search_blocker = QSignalBlocker(self.search_edit)
            filter_blocker = QSignalBlocker(self.filter_combo)
            self.search_edit.clear()
            self.filter_combo.setCurrentIndex(self.filter_combo.findData('all'))
            del search_blocker, filter_blocker
            self._apply_filters()
        if self.select_chapter(*pair):
            self.start_requested.emit(*pair)


def controller_geometry(anchor: QRect, size: QSize, available: QRect, *, gap: int = 12) -> QRect:
    """Place beside the anchor, clamping size/position to this screen's work area.

    No primary-screen lookup or zero-origin assumption. Oversized controllers
    shrink to available; callers must pass QScreen.availableGeometry(), not its
    full geometry, to respect the taskbar/dock.
    """
    if available.isEmpty() or size.isEmpty() or gap < 0:
        raise ValueError('positive size/work area and nonnegative gap required')
    width = min(size.width(), available.width())
    height = min(size.height(), available.height())
    x = anchor.right() + 1 + gap
    if x + width > available.right() + 1:
        x = anchor.left() - gap - width
    x = max(available.left(), min(x, available.right() + 1 - width))
    y = max(available.top(), min(anchor.top(), available.bottom() + 1 - height))
    return QRect(x, y, width, height)


class TutorialController(QWidget):
    """Independent tool window; zero-based present() never executes a step.

    Operation steps cannot emit next_requested through the Next button, even
    when can_next=True. Pause is a toggle *request*: the host calls set_paused()
    to acknowledge it. Target availability is likewise supplied by the host.
    """

    previous_requested = pyqtSignal()
    next_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    skip_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    def __init__(self, translate: Translate, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(translate('teaching_controller_title'))
        self._translate = translate
        self._step: TutorialStep | None = None
        self._finished: str | None = None
        self._can_previous = self._can_next = False
        self._paused = self._missing = self._exit_emitted = False
        self.title_label = QLabel(self)
        self.body_label = QLabel(self)
        self.progress_label = QLabel(self)
        self.status_label = QLabel(self)
        self.warning_label = QLabel(self)
        self.warning_label.hide()
        for label in (self.title_label, self.body_label, self.progress_label, self.status_label, self.warning_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body_scroll = self.body_scroll = QScrollArea(self)
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_scroll.setWidget(self.body_label)
        body_scroll.setMinimumSize(0, 60)
        actions = QGridLayout()
        for index, name in enumerate(('previous', 'next', 'pause', 'skip', 'retry', 'exit')):
            button = QPushButton(translate(f'teaching_{name}'), self)
            setattr(self, f'{name}_button', button)
            actions.addWidget(button, index // 2, index % 2)
            if name == 'exit':
                button.clicked.connect(self.close)
            else:
                button.clicked.connect(getattr(self, f'{name}_requested').emit)
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(body_scroll, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.warning_label)
        layout.addLayout(actions)
        self.resize(420, 300)
        self._update_actions()

    def present(self, step: TutorialStep, index: int, total: int,
                can_previous: bool, can_next: bool) -> None:
        if not isinstance(step, TutorialStep):
            raise ValueError('a tutorial step is required')
        if type(index) is not int or type(total) is not int or not 0 <= index < total:
            raise ValueError('invalid step progress')
        title = self._translate(step.title_key)
        body = self._translate(step.body_key)
        progress = self._translate('teaching_progress').format(current=index + 1, total=total)
        self._step, self._finished = step, None
        self._can_previous, self._can_next = bool(can_previous), bool(can_next)
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.progress_label.setText(progress)
        self._update_actions()

    @property
    def chapter_finished(self) -> bool:
        return self._finished is not None

    def set_finished(self, status: str) -> None:
        if status not in ('completed', 'skipped'):
            raise ValueError('invalid chapter summary status')
        self._step, self._finished = None, status
        self._paused = self._missing = False
        self.title_label.setText(self._translate('teaching_status_' + status))
        self.body_label.setText(self._translate('teaching_return_to_work'))
        self.title_label.show()
        self.body_scroll.show()
        self._update_actions()

    def set_persistence_warning(self) -> None:
        self.warning_label.setText(self._translate('teaching_progress_save_failed'))
        self.warning_label.show()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self.title_label.setVisible(not self._paused)
        self.body_scroll.setVisible(not self._paused)
        self._update_actions()

    def set_target_missing(self, missing: bool) -> None:
        self._missing = bool(missing)
        self._update_actions()

    def _update_actions(self) -> None:
        ready = self._step is not None and not self._paused and not self._missing
        self.previous_button.setEnabled(ready and self._can_previous)
        self.next_button.setEnabled(ready and self._can_next and self._step.kind == 'information')
        self.pause_button.setEnabled(self._step is not None)
        self.pause_button.setText(self._translate('teaching_resume' if self._paused else 'teaching_pause'))
        self.skip_button.setEnabled(self._step is not None)
        self.retry_button.setEnabled(self._missing and not self._paused)
        self.exit_button.setEnabled(True)
        if self._finished is not None:
            key = 'teaching_status_' + self._finished
        elif self._paused:
            key = 'teaching_paused'
        elif self._missing:
            key = 'teaching_target_missing'
        elif self._step is not None and self._step.kind == 'operation':
            key = 'teaching_waiting_operation'
        else:
            key = None
        self.status_label.setText(self._translate(key) if key else '')

    def place(self, anchor: QRect, available: QRect) -> QRect:
        geometry = controller_geometry(anchor, self.size(), available)
        self.setGeometry(geometry)
        return geometry

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._exit_emitted:
            self._exit_emitted = True
            self.exit_requested.emit()
        event.accept()


class HighlightOverlay(QWidget):
    """Border-only tool window, transparent to OS input and unable to take focus."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        for attribute in (Qt.WidgetAttribute.WA_DeleteOnClose,
                          Qt.WidgetAttribute.WA_TranslucentBackground,
                          Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                          Qt.WidgetAttribute.WA_ShowWithoutActivating):
            self.setAttribute(attribute)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def highlight(self, global_rect: QRect | None) -> None:
        if global_rect is None or global_rect.isEmpty():
            self.hide()
            return
        self.setGeometry(QRect(global_rect))
        self.show()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#f5b700'), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))


_INPUT_EVENTS = frozenset({
    QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
    QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseMove,
    QEvent.Type.NonClientAreaMouseButtonPress, QEvent.Type.NonClientAreaMouseButtonRelease,
    QEvent.Type.NonClientAreaMouseButtonDblClick, QEvent.Type.NonClientAreaMouseMove,
    QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.Shortcut,
    QEvent.Type.ShortcutOverride, QEvent.Type.InputMethod, QEvent.Type.Wheel,
    QEvent.Type.TabletPress, QEvent.Type.TabletMove, QEvent.Type.TabletRelease,
    QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel,
    QEvent.Type.Gesture, QEvent.Type.GestureOverride, QEvent.Type.NativeGesture,
    QEvent.Type.ContextMenu, QEvent.Type.DragEnter, QEvent.Type.DragMove,
    QEvent.Type.DragLeave, QEvent.Type.Drop,
})


def _live(reference):
    value = reference() if reference is not None else None
    return value if value is not None and not sip.isdeleted(value) else None


def _associated_popups(root: QWidget) -> Iterable[QWidget]:
    """Resolve the current actual menu tree at input time, never a stale snapshot."""
    menu = root if isinstance(root, QMenu) else (
        root.menu() if isinstance(root, (QPushButton, QToolButton)) else None)
    pending, visited = ([menu] if menu is not None else []), set()
    while pending:
        current = pending.pop()
        if sip.isdeleted(current) or current in visited:
            continue
        visited.add(current)
        yield current
        pending.extend(action.menu() for action in current.actions() if action.menu() is not None)
    if isinstance(root, QComboBox):
        yield root.view().window()


class InputBarrier(QObject):
    """Application-local, explicitly-owned-window input filter; never an OS hook.

    owns() is called with the receiving widget's top-level window. Allowed roots
    include their child widgets in the same window and their actual, dynamically
    resolved Qt popup/menu trees. Unrelated owned menus are not allowed.
    QShortcut/QAction receivers
    are checked through their QWidget parent. Unowned or unidentifiable receivers
    pass untouched. Canvas grants all canvas-subtree gestures, not the toolbar.

    activate(policy, targets=(), canvas=None, controller=None) replaces the allow
    list. free/deactivate/suspend remove the filter, nested resume reinstalls it.
    close() removes it permanently and releases callbacks. Widget roots are weak.
    """

    def __init__(self, owns: Callable[[QWidget], bool], parent: QObject | None = None) -> None:
        super().__init__(parent)
        app = QApplication.instance()
        if app is None:
            raise RuntimeError('InputBarrier requires a QApplication')
        self._app = weakref.ref(app)
        self._owns = owns
        self._targets: tuple[weakref.ReferenceType[QWidget], ...] = ()
        self._canvas = self._controller = None
        self._policy = 'free'
        self._active = self._installed = self._closed = False
        self._suspensions = 0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def installed(self) -> bool:
        return self._installed

    def activate(self, policy: str, *, targets: Iterable[QWidget] = (),
                 canvas: QWidget | None = None, controller: QWidget | None = None) -> None:
        if self._closed:
            raise RuntimeError('InputBarrier is closed')
        if policy not in ('free', 'canvas', 'target_only'):
            raise ValueError('invalid input policy')
        targets = tuple(targets)
        if any(not isinstance(widget, QWidget) for widget in (*targets, canvas, controller)
               if widget is not None):
            raise TypeError('input roots must be widgets')
        self._targets = tuple(weakref.ref(widget) for widget in targets)
        self._canvas = weakref.ref(canvas) if canvas is not None else None
        self._controller = weakref.ref(controller) if controller is not None else None
        self._policy, self._active = policy, True
        self._sync_filter()

    def deactivate(self) -> None:
        self._active = False
        self._targets = ()
        self._canvas = self._controller = None
        self._sync_filter()

    def suspend(self) -> None:
        if not self._closed:
            self._suspensions += 1
            self._sync_filter()

    def resume(self) -> None:
        if self._suspensions:
            self._suspensions -= 1
            self._sync_filter()

    def close(self) -> None:
        self._closed = True
        self.deactivate()
        self._suspensions = 0
        self._owns = None

    def _sync_filter(self) -> None:
        app = _live(self._app)
        needed = self._active and not self._closed and not self._suspensions and self._policy != 'free'
        if app is not None:
            if needed and not self._installed:
                app.installEventFilter(self)
            elif not needed and self._installed:
                app.removeEventFilter(self)
        self._installed = bool(needed and app is not None)

    def eventFilter(self, receiver: QObject, event: QEvent) -> bool:
        if event.type() not in _INPUT_EVENTS or not self._installed:
            return False
        widget = receiver
        while widget is not None and not isinstance(widget, QWidget):
            widget = widget.parent()
        if widget is None or sip.isdeleted(widget):
            return False
        window = widget.window()
        try:
            owned = self._owns is not None and self._owns(window)
        except Exception:
            # Unknown ownership must never block another window during shutdown.
            return False
        if not owned:
            return False
        roots = (*self._targets, self._controller)
        if self._policy == 'canvas':
            roots += (self._canvas,)
        for reference in roots:
            root = _live(reference)
            if root is None:
                continue
            if root.window() is window and (root is widget or root.isAncestorOf(widget)):
                return False
            for popup in _associated_popups(root):
                if popup.window() is window and (popup is widget or popup.isAncestorOf(widget)):
                    return False
        event.accept()  # In particular, stop shortcut lookup after ShortcutOverride.
        return True
