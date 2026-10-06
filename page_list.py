# SPDX-License-Identifier: GPL-3.0-or-later
"""Page thumbnails with explicit model-order dragging, not free icon placement."""
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QDrag, QDragLeaveEvent
from PyQt6.QtWidgets import QListWidget, QAbstractItemView


class PageListWidget(QListWidget):
    reorder_requested = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._drag_source_id = None
        self._drag_source_row = None

    def startDrag(self, supported_actions):
        # Our drop handler updates the document and rebuilds its view. The
        # inherited startDrag would ALSO remove selected source rows after a
        # MoveAction, deleting a fresh thumbnail and changing the active page.
        item = self.currentItem()
        if item is None:
            return
        self._drag_source_id = item.data(Qt.ItemDataRole.UserRole)
        self._drag_source_row = self.row(item)
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData([self.indexFromItem(item)]))
        pixmap = item.icon().pixmap(self.iconSize())
        if not pixmap.isNull():
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._drag_source_id = None
            self._drag_source_row = None
            QAbstractItemView.dragLeaveEvent(self, QDragLeaveEvent())
            drag.deleteLater()

    def dragEnterEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        QAbstractItemView.dragEnterEvent(self, event)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragMoveEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        # Bypass IconMode's free-position filter. Keep the generic view's edge
        # autoscroll, then accept our before/after-page insertion even though
        # the ordinary QListWidget items aren't drop-into containers.
        QAbstractItemView.dragMoveEvent(self, event)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event):
        QAbstractItemView.dragLeaveEvent(self, event)

    def dropEvent(self, event):
        # IconMode's default drop can merely reposition an icon without changing
        # document order. Convert the visual insertion point to a page index.
        source = self.currentRow() if self._drag_source_row is None else self._drag_source_row
        if self._drag_source_id is not None:
            source = next((row for row in range(self.count())
                           if self.item(row).data(Qt.ItemDataRole.UserRole) == self._drag_source_id), -1)
        if event.source() is not self or source < 0:
            event.ignore()
            return
        point = event.position().toPoint()
        target = self.indexAt(point).row()
        if target < 0:
            insertion = self.count()
        else:
            rect = self.visualItemRect(self.item(target))
            insertion = target + (point.y() >= rect.center().y())
        destination = insertion - (source < insertion)
        destination = max(0, min(self.count() - 1, destination))
        if destination != source:
            self.reorder_requested.emit(source, destination)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
