# SPDX-License-Identifier: GPL-3.0-or-later
"""Current-page geometry cache. Completed paths survive repaints; appends extend them.

The owner invalidates after in-place geometry/style edits. Replaced/shortened
lists are detected independently. No pixel surfaces or cross-page copies live here.
"""
from dataclasses import dataclass
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath


def _union(a, b):
    if a is None: return b
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _rect(bounds, margin=0):
    left, top, right, bottom = bounds
    return QRectF(left - margin, top - margin, right - left + 2 * margin, bottom - top + 2 * margin)


@dataclass
class StrokeCommand:
    segment: dict
    path: object = None
    end: object = None
    bounds: object = None
    clip_bounds: object = None
    clip_margin: float = 0.0


class StrokeGeometryCache:
    def __init__(self):
        self.parts_processed = 0
        self.invalidate()

    def invalidate(self):
        self.source = None
        self.count = 0
        self.tail = None
        self.commands = []
        self.groups = {}
        self.object_bounds = {}

    def sync(self, segments, grouped_styles, ink_radius):
        if (segments is not self.source or len(segments) < self.count or
                (self.count and segments[self.count - 1] is not self.tail)):
            self.invalidate()
            self.source = segments
        touched = {}
        for index in range(self.count, len(segments)):
            segment = segments[index]
            line = segment["line"]
            geometry = (min(line.x1(), line.x2()), min(line.y1(), line.y2()),
                        max(line.x1(), line.x2()), max(line.y1(), line.y2()))
            style = segment.get("style")
            marker = bool(segment.get("marker"))
            if marker or style in grouped_styles:
                key = (segment["id"], style, marker)
                command = self.groups.get(key)
                if command is None:
                    command = StrokeCommand(segment, QPainterPath(QPointF(line.p1())), line.p1(),
                                            clip_margin=ink_radius(segment) + 1.0)
                    self.groups[key] = command
                    self.commands.append(command)
                if command.end != line.p1():
                    command.path.moveTo(QPointF(line.p1()))
                command.path.lineTo(QPointF(line.p2()))
                command.end = line.p2()
                command.bounds = _union(command.bounds, geometry)
                touched[key] = command
            else:
                self.commands.append(StrokeCommand(segment, bounds=geometry,
                                                     clip_bounds=_rect(geometry, ink_radius(segment) + 1.0)))
            # Preserve the original selection margin semantics, including normal
            # and marker strokes whose bounds intentionally omit their pen width.
            margin = ink_radius(segment) if style else 0.0
            selection = (geometry[0] - margin, geometry[1] - margin,
                         geometry[2] + margin, geometry[3] + margin)
            object_id = segment["id"]
            self.object_bounds[object_id] = _union(self.object_bounds.get(object_id), selection)
            self.parts_processed += 1
        for command in touched.values():
            command.clip_bounds = _rect(command.bounds, command.clip_margin)
        self.count = len(segments)
        self.tail = segments[-1] if segments else None
        return self.commands

    def bounds_for(self, object_id):
        bounds = self.object_bounds.get(object_id)
        return _rect(bounds, 8.0) if bounds is not None else QRectF()
