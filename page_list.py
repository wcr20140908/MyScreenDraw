# SPDX-License-Identifier: GPL-3.0-or-later
"""Page thumbnails with explicit model-order dragging, not free icon placement."""
from contextlib import nullcontext

from PyQt6.QtCore import QEvent, Qt, QLine, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QDragLeaveEvent, QPainter, QPen
from PyQt6.QtWidgets import QListWidget, QAbstractItemView


class PageListWidget(QListWidget):
    reorder_requested = pyqtSignal(int, int)

    def __init__(self, parent=None, *, reorder_scope=None):
        super().__init__(parent)
        self._reorder_scope = reorder_scope or nullcontext
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._drag_source_id = None
        self._drag_source_row = None
        self._drag_point = None
        self._drop_insertion = None
        self._drop_line = None
        self.verticalScrollBar().valueChanged.connect(self._update_drop_indicator)
        self._fitting_thumbnails = False
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.model().rowsInserted.connect(self._fit_thumbnails)

    def _fit_thumbnails(self):
        if getattr(self, '_fitting_thumbnails', True):
            return
        self._fitting_thumbnails = True
        try:
            viewport = self.viewport().size()
            caption = self.fontMetrics().height() + 12
            columns = max(1, viewport.width() // 230)
            cell_width = max(1, (viewport.width() - 1) // columns)
            scale = min(1.0, max(1, cell_width - 24) / 260,
                        max(1, viewport.height() - caption - 12) / 170)
            icon = QSize(max(1, int(260 * scale)), max(1, int(170 * scale)))
            grid = QSize(cell_width, icon.height() + caption + 12)
            if self.iconSize() != icon:
                self.setIconSize(icon)
            if self.gridSize() != grid:
                self.setGridSize(grid)
            hint = QSize(max(1, grid.width() - 8), max(1, grid.height() - 8))
            for index in range(self.count()):
                item = self.item(index)
                if item.sizeHint() != hint:
                    item.setSizeHint(hint)
        finally:
            self._fitting_thumbnails = False

    def viewportEvent(self, event):
        result = super().viewportEvent(event)
        if event.type() == QEvent.Type.Resize:
            self._fit_thumbnails()
        return result

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit_thumbnails()

    def startDrag(self, supported_actions):
        # Our drop handler updates the document and rebuilds its view. The
        # inherited startDrag would ALSO remove selected source rows after a
        # MoveAction, deleting a fresh thumbnail and changing the active page.
        item = self.currentItem()
        if item is None:
            return
        with self._reorder_scope():
            drag = None
            try:
                self._drag_source_id = item.data(Qt.ItemDataRole.UserRole)
                self._drag_source_row = self.row(item)
                drag = QDrag(self)
                drag.setMimeData(self.model().mimeData([self.indexFromItem(item)]))
                pixmap = item.icon().pixmap(self.iconSize())
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(120, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                    drag.setPixmap(pixmap)
                    drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
                drag.exec(Qt.DropAction.MoveAction)
            finally:
                self._drag_source_id = None
                self._drag_source_row = None
                self._clear_drop_indicator()
                try:
                    QAbstractItemView.dragLeaveEvent(self, QDragLeaveEvent())
                finally:
                    if drag is not None:
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
        self._drag_point = event.position().toPoint()
        self._update_drop_indicator()
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._clear_drop_indicator()
        QAbstractItemView.dragLeaveEvent(self, event)

    def _insertion_at(self, point):
        if not self.count():
            return 0, None
        rects = [self.visualItemRect(self.item(row)) for row in range(self.count())]
        # Gaps belong to their nearest thumbnail, not to the end of the document.
        def distance(rect):
            dx = max(rect.left() - point.x(), 0, point.x() - rect.right())
            dy = max(rect.top() - point.y(), 0, point.y() - rect.bottom())
            return dx * dx + dy * dy
        target = min(range(self.count()), key=lambda row: distance(rects[row]))
        rect = rects[target]
        multi_column = self.viewport().width() >= 2 * self.gridSize().width()
        if multi_column:
            after = point.x() >= rect.center().x()
            if point.y() > rects[-1].bottom():
                target, rect, after = self.count() - 1, rects[-1], True
            x = rect.right() + 3 if after else rect.left() - 3
            x = max(5, min(self.viewport().width() - 6, x))
            line = QLine(x, rect.top() + 6, x, rect.bottom() - 6)
        else:
            after = point.y() >= rect.center().y()
            y = rect.bottom() + 3 if after else rect.top() - 3
            y = max(5, min(self.viewport().height() - 6, y))
            line = QLine(rect.left() + 6, y, rect.right() - 6, y)
        return target + int(after), line

    def _update_drop_indicator(self, *_):
        if self._drag_point is not None:
            self._drop_insertion, self._drop_line = self._insertion_at(self._drag_point)
            self.viewport().update()

    def _clear_drop_indicator(self):
        self._drag_point = self._drop_insertion = self._drop_line = None
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_line is None:
            return
        painter = QPainter(self.viewport())
        line = self._drop_line
        vertical = line.x1() == line.x2()
        cap = QPoint(5, 0) if vertical else QPoint(0, 5)
        for color, width in ((QColor('white'), 7), (QColor('#1688ff'), 3)):
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(line)
            painter.drawLine(line.p1() - cap, line.p1() + cap)
            painter.drawLine(line.p2() - cap, line.p2() + cap)
        painter.end()

    def dropEvent(self, event):
        # IconMode's default drop can merely reposition an icon without changing
        # document order. Convert the visual insertion point to a page index.
        source = self.currentRow() if self._drag_source_row is None else self._drag_source_row
        if self._drag_source_id is not None:
            source = next((row for row in range(self.count())
                           if self.item(row).data(Qt.ItemDataRole.UserRole) == self._drag_source_id), -1)
        if event.source() is not self or source < 0:
            self._clear_drop_indicator()
            event.ignore()
            return
        insertion, _ = self._insertion_at(event.position().toPoint())
        self._clear_drop_indicator()
        destination = insertion - (source < insertion)
        destination = max(0, min(self.count() - 1, destination))
        if destination != source:
            self.reorder_requested.emit(source, destination)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
