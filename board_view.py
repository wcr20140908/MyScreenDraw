# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-page whiteboard camera; document geometry is never scaled in place."""
from dataclasses import dataclass
from math import hypot

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform


@dataclass
class BoardView:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0

    MIN_ZOOM = 0.1
    MAX_ZOOM = 8.0

    @classmethod
    def from_data(cls, data=None):
        return cls(**data) if data else cls()

    def to_data(self):
        return {'x': self.x, 'y': self.y, 'zoom': self.zoom}

    def transform(self):
        return QTransform(self.zoom, 0.0, 0.0, self.zoom, self.x, self.y)

    def to_document(self, point):
        return QPointF((point.x() - self.x) / self.zoom,
                       (point.y() - self.y) / self.zoom)

    def to_view(self, point):
        return QPointF(point.x() * self.zoom + self.x,
                       point.y() * self.zoom + self.y)

    def document_rect(self, rect):
        return QRectF(self.to_document(rect.topLeft()), self.to_document(rect.bottomRight()))

    def zoom_at(self, point, zoom):
        anchor = self.to_document(point)
        self.place_anchor(anchor, point, zoom)

    def place_anchor(self, anchor, point, zoom):
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        self.x = point.x() - anchor.x() * self.zoom
        self.y = point.y() - anchor.y() * self.zoom

    def fit(self, bounds, viewport):
        if bounds.isEmpty():
            self.x, self.y, self.zoom = 0.0, 0.0, 1.0
            return
        zoom = min(viewport.width() / bounds.width(), viewport.height() / bounds.height()) * 0.9
        self.place_anchor(bounds.center(), viewport.center(), zoom)


class BoardGesture:
    """Keep the world point under one/two fingers fixed during navigation."""
    def __init__(self):
        self.ids = ()

    def clear(self):
        self.ids = ()

    def update(self, view, points):
        ids = tuple(sorted(points)[:2])
        if not ids:
            self.clear()
            return False
        first = QPointF(points[ids[0]])
        second = QPointF(points[ids[-1]])
        center = (first + second) / 2.0
        distance = hypot(first.x() - second.x(), first.y() - second.y())
        if ids != self.ids:
            self.ids = ids
            self.anchor = view.to_document(center)
            self.zoom = view.zoom
            self.distance = distance
            return False
        before = view.to_data()
        zoom = self.zoom * distance / self.distance if self.distance > 0 else self.zoom
        view.place_anchor(self.anchor, center, zoom)
        return view.to_data() != before
