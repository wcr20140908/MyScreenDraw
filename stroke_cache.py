# SPDX-License-Identifier: GPL-3.0-or-later
"""Current-page geometry cache. Completed paths survive repaints; appends extend them.

The owner invalidates after in-place geometry/style edits. Replaced/shortened
lists are detected independently. No pixel surfaces or cross-page copies live here.
"""
from dataclasses import dataclass
import math
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
    index: int = -1


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
        self._cells = {}
        self._command_cells = {}
        self._wide_commands = set()
        self.query_candidates = 0

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
                    command.index = len(self.commands)
                    self.commands.append(command)
                if command.end != line.p1():
                    command.path.moveTo(QPointF(line.p1()))
                command.path.lineTo(QPointF(line.p2()))
                command.end = line.p2()
                command.bounds = _union(command.bounds, geometry)
                touched[key] = command
            else:
                command = StrokeCommand(segment, bounds=geometry,
                                        clip_bounds=_rect(geometry, ink_radius(segment) + 1.0),
                                        index=len(self.commands))
                self.commands.append(command)
                self._index_command(command)
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
            self._index_command(command)
        self.count = len(segments)
        self.tail = segments[-1] if segments else None
        return self.commands

    def bounds_for(self, object_id):
        bounds = self.object_bounds.get(object_id)
        return _rect(bounds, 8.0) if bounds is not None else QRectF()


    CELL_SIZE = 128
    MAX_COMMAND_CELLS = 256

    @property
    def index_entries(self):
        return sum(len(indices) for indices in self._cells.values()) + len(self._wide_commands)

    @classmethod
    def _covered_cells(cls, rect):
        left, right = math.floor(rect.left()/cls.CELL_SIZE), math.floor(rect.right()/cls.CELL_SIZE)
        top, bottom = math.floor(rect.top()/cls.CELL_SIZE), math.floor(rect.bottom()/cls.CELL_SIZE)
        if (right-left+1)*(bottom-top+1) > cls.MAX_COMMAND_CELLS:
            return None
        return tuple((x,y) for x in range(left,right+1) for y in range(top,bottom+1))

    def _index_command(self, command):
        index = command.index
        cells = self._covered_cells(command.clip_bounds)
        previous = self._command_cells.get(index, ())
        if cells == previous:
            return
        if previous is None:
            self._wide_commands.discard(index)
        else:
            for cell in previous:
                bucket = self._cells[cell]
                bucket.discard(index)
                if not bucket:
                    del self._cells[cell]
        self._command_cells[index] = cells
        if cells is None:
            self._wide_commands.add(index)
        else:
            for cell in cells:
                self._cells.setdefault(cell,set()).add(index)

    def visible_commands(self, clip):
        """Cull in Python before painting; sorted indices preserve alpha/z order."""
        cells = None if clip is None else self._covered_cells(clip)
        if cells is None:
            candidates = range(len(self.commands))
        else:
            indices = set(self._wide_commands)
            for cell in cells:
                indices.update(self._cells.get(cell, ()))
            candidates = sorted(indices)
        self.query_candidates = len(candidates)
        for index in candidates:
            command = self.commands[index]
            if clip is None or clip.intersects(command.clip_bounds):
                yield command
