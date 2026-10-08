# SPDX-License-Identifier: GPL-3.0-or-later
"""Lazy semantic Qt targets with session-scoped, event-driven geometry watches."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from weakref import ReferenceType, ref

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QMetaObject, QObject, QPoint, QRect, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QScreen, QWindow
from PyQt6.QtWidgets import QAbstractScrollArea, QScrollArea, QScrollBar, QWidget

from .models import require_id

Resolver = Callable[[], QWidget | None]
Reveal = Callable[[], object]

_EVENTS = frozenset({
    QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide,
    QEvent.Type.ShowToParent, QEvent.Type.HideToParent, QEvent.Type.LayoutRequest,
    QEvent.Type.ParentChange, QEvent.Type.ChildAdded, QEvent.Type.ChildRemoved,
    QEvent.Type.ChildPolished, QEvent.Type.WinIdChange, QEvent.Type.WindowStateChange,
    QEvent.Type.PlatformSurface, QEvent.Type.DevicePixelRatioChange,
    QEvent.Type.Scroll, QEvent.Type.ScrollPrepare, QEvent.Type.EnabledChange,
})
_SCREEN_SIGNALS = ('geometryChanged', 'availableGeometryChanged', 'virtualGeometryChanged',
                   'logicalDotsPerInchChanged', 'physicalDotsPerInchChanged', 'orientationChanged')
_WINDOW_SIGNALS = ('screenChanged', 'xChanged', 'yChanged', 'widthChanged', 'heightChanged',
                   'visibleChanged', 'visibilityChanged')


def _alive(obj: QObject | None) -> bool:
    return obj is not None and not sip.isdeleted(obj)


@dataclass
class _Watch:
    reference: ReferenceType[QObject]
    owner: ReferenceType[QWidget] | None = None
    accessor: str | None = None
    connections: list[QMetaObject.Connection] = field(default_factory=list)

    def object(self) -> QObject | None:
        obj = self.reference()
        if _alive(obj):
            return obj
        owner = self.owner() if self.owner is not None else None
        if _alive(owner) and self.accessor is not None:
            # Native Qt-owned wrappers may be collected before the C++ object.
            return getattr(owner, self.accessor)()
        return None


class TargetRegistry(QObject):
    """Resolvers choose semantic controls; hidden controls are never fallbacks.

    ``watch`` defers one initial, zero-argument notification, then follows only
    active targets and their Qt surfaces. A surviving host remains watched while
    its target is absent, allowing a later rebuild without desktop polling.
    ``unwatch`` preserves registrations; ``close`` releases them permanently.
    """

    failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: dict[str, tuple[Resolver, Reveal | None]] = {}
        self._ids: tuple[str, ...] = ()
        self._extra_resolvers: tuple[Resolver, ...] = ()
        self._watch_generation = 0
        self._on_change: Callable[[], None] | None = None
        self._hosts: dict[str | int, tuple[ReferenceType[QWidget], ...]] = {}
        self._watched: dict[int, _Watch] = {}
        self._timer: QTimer | None = None
        self._closed = False
        self._settling = False

    def register(self, target_id: str, resolver: Resolver, reveal: Reveal | None = None) -> None:
        target_id = require_id(target_id, 'target id')
        self._require_open()
        if target_id in self._entries:
            raise ValueError(f'duplicate target id: {target_id}')
        if not callable(resolver) or (reveal is not None and not callable(reveal)):
            raise TypeError('target resolver and reveal must be callable')
        self._entries[target_id] = (resolver, reveal)
        if target_id in self._ids:
            self._schedule()

    def resolve(self, target_id: str) -> QWidget | None:
        widget = self._candidate(require_id(target_id, 'target id'))
        return widget if widget is not None and widget.isVisible() else None

    def reveal(self, target_id: str) -> bool:
        target_id = require_id(target_id, 'target id')
        entry = self._entries.get(target_id)
        if entry is None or self._closed:
            return False
        try:
            if entry[1] is not None:
                entry[1]()
            widget = self.resolve(target_id)
            if widget is None:
                return False
            ancestors = list(self._ancestors(widget))
            for ancestor in ancestors:
                if isinstance(ancestor, QScrollArea) and _alive(ancestor) and _alive(widget):
                    ancestor.ensureWidgetVisible(widget)
            return self.resolve(target_id) is not None
        except (RuntimeError, ReferenceError):
            return False
        finally:
            self._schedule()

    def global_rect(self, target_id: str) -> QRect | None:
        widget = self.resolve(target_id)
        if widget is None:
            return None
        return QRect(widget.mapToGlobal(QPoint()), widget.size())

    def watch(self, target_ids: Iterable[str], on_change: Callable[[], None], *,
              extra_resolvers: Iterable[Resolver] = ()) -> None:
        self._require_open()
        ids = tuple(dict.fromkeys(require_id(value, 'target id') for value in target_ids))
        if not callable(on_change):
            raise TypeError('on_change must be callable')
        extra = tuple(extra_resolvers)
        if any(not callable(resolver) for resolver in extra):
            raise TypeError('extra surface resolvers must be callable')
        self.unwatch()
        if not ids and not extra:
            return
        self._ids, self._on_change, self._extra_resolvers = ids, on_change, extra
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._notify)
        try:
            self._refresh()
        except Exception:
            self.unwatch()
            raise
        self._schedule()

    def unwatch(self) -> None:
        self._watch_generation += 1
        self._ids, self._on_change, self._extra_resolvers = (), None, ()
        self._settling = False
        if self._timer is not None:
            self._timer.stop()
            self._timer.timeout.disconnect(self._notify)
            self._timer.deleteLater()
            self._timer = None
        for key, watched in tuple(self._watched.items()):
            self._detach(key, watched)
        self._watched.clear()
        self._hosts.clear()

    def close(self) -> None:
        self.unwatch()
        self._closed = True
        self._entries.clear()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in _EVENTS:
            self._schedule()
        return False

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError('target registry is closed')

    def _candidate(self, target_id: str) -> QWidget | None:
        entry = self._entries.get(target_id)
        if self._closed or entry is None:
            return None
        return self._resolve_widget(entry[0])

    @staticmethod
    def _resolve_widget(resolver: Resolver) -> QWidget | None:
        try:
            widget = resolver()
        except (RuntimeError, ReferenceError):
            return None
        return widget if isinstance(widget, QWidget) and _alive(widget) else None

    @staticmethod
    def _ancestors(widget: QWidget) -> Iterable[QWidget]:
        while _alive(widget):
            yield widget
            widget = widget.parentWidget()

    @pyqtSlot()
    def _schedule(self) -> None:
        if self._on_change is not None and _alive(self._timer):
            self._settling = True
            if not self._timer.isActive():
                self._timer.start(0)

    @pyqtSlot()
    def _notify(self) -> None:
        if self._on_change is None:
            return
        generation = self._watch_generation
        try:
            self._refresh()
            if generation != self._watch_generation or self._on_change is None:
                return
            if self._settling:
                # Allow a quiet turn for native window/layout echoes to settle.
                self._settling = False
                self._timer.start(0)
                return
            self._on_change()
        except Exception:
            # Deferred resolver/callback failures must never escape a Qt slot.
            self.unwatch()
            self.failed.emit('target_resolution_failed')

    @pyqtSlot()
    def _destroyed(self) -> None:
        # Only inspect the address, never widget methods on the dying tree.
        sender = self.sender()
        if sender is not None:
            self._watched.pop(sip.unwrapinstance(sender), None)
        self._schedule()

    def _refresh(self) -> None:
        generation = self._watch_generation
        surfaces: dict[int, tuple[QObject, QWidget | None, str | None]] = {}

        def add(obj: QObject | None, owner: QWidget | None = None,
                accessor: str | None = None) -> None:
            if _alive(obj):
                key = sip.unwrapinstance(obj)
                # Preserve accessor recovery when an ancestor is added again.
                if key not in surfaces or owner is not None:
                    surfaces[key] = (obj, owner, accessor)

        resolvers = [(target_id, lambda target_id=target_id: self._candidate(target_id))
                     for target_id in self._ids]
        resolvers.extend((index, resolver) for index, resolver in enumerate(self._extra_resolvers))
        for target_id, resolver in resolvers:
            widget = self._resolve_widget(resolver)
            if self._closed or generation != self._watch_generation:
                return
            if widget is not None:
                self._hosts[target_id] = tuple(ref(host) for host in self._ancestors(widget))
            for host_ref in self._hosts.get(target_id, ()):
                host = host_ref()
                if not _alive(host):
                    continue
                add(host)
                add(host.layout(), host, 'layout')
                if isinstance(host, QAbstractScrollArea):
                    add(host.viewport(), host, 'viewport')
                    add(host.horizontalScrollBar(), host, 'horizontalScrollBar')
                    add(host.verticalScrollBar(), host, 'verticalScrollBar')
                if host.isWindow():
                    add(host.windowHandle(), host, 'windowHandle')
                    add(host.screen(), host, 'screen')

        for key in self._watched.keys() - surfaces.keys():
            self._detach(key, self._watched.pop(key))
        for key, (obj, owner, accessor) in surfaces.items():
            if key in self._watched:
                watched = self._watched[key]
                watched.reference = ref(obj)
                continue
            watched = _Watch(ref(obj), ref(owner) if owner is not None else None, accessor)
            self._watched[key] = watched
            if not isinstance(obj, QScreen):
                obj.installEventFilter(self)
            watched.connections.append(obj.destroyed.connect(self._destroyed))
            if isinstance(obj, QScrollBar):
                signals = ('valueChanged', 'rangeChanged')
            elif isinstance(obj, QWindow):
                signals = _WINDOW_SIGNALS
            elif isinstance(obj, QScreen):
                signals = _SCREEN_SIGNALS
            else:
                signals = ()
            for name in signals:
                watched.connections.append(getattr(obj, name).connect(self._schedule))

    def _detach(self, key: int, watched: _Watch) -> None:
        obj = watched.object()
        if _alive(obj) and sip.unwrapinstance(obj) == key and not isinstance(obj, QScreen):
            obj.removeEventFilter(self)
        # Connection handles do not retain Qt-owned wrappers and still work if
        # such a wrapper has been collected. Disconnect only our own listeners.
        for connection in watched.connections:
            QObject.disconnect(connection)
