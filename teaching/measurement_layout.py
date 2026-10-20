# SPDX-License-Identifier: GPL-3.0-or-later
"""Initial instrument placement in the private measurement lesson."""
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF

from .widgets import controller_geometry


def view_bounds(canvas, aid):
    bounds = canvas.aid_bounds(aid)
    return QRectF(canvas.to_view(bounds.topLeft()), canvas.to_view(bounds.bottomRight())).toAlignedRect().translated(
        canvas.mapToGlobal(QPoint()))


def place_aid(host, aid):
    canvas = host.panel.canvas
    viewport = QRect(canvas.mapToGlobal(QPoint()), canvas.size())
    area = host.presenter._available_geometry(canvas).intersected(viewport).adjusted(16, 16, -16, -16)
    if area.isEmpty():
        return
    obstacles = (*host._layout_obstacles(), host.presenter.controller.frameGeometry(),
                 *(view_bounds(canvas, other).adjusted(-24, -24, 24, 24) for other in canvas.aids))
    original_scale = aid['scale']
    # Keep handle spacing usable: close/rotate centers are only 30 local pixels apart.
    scales = (original_scale,) if aid['kind'] == 'ruler' else (
        original_scale, .9, .8, .7, .6)
    candidates = []
    for scale in scales:
        aid['scale'] = scale
        bounds = view_bounds(canvas, aid)
        target = controller_geometry(QRect(), bounds.size(), area, gap=24, obstacles=obstacles)
        # Instruments are not widgets: a clamped rectangle must not silently
        # shrink a physical ruler or claim that an oversized instrument fits.
        target.setSize(bounds.size())
        visible = target.intersected(area)
        covered = target.width() * target.height() - visible.width() * visible.height()
        for obstacle in obstacles:
            overlap = target.intersected(obstacle)
            covered += overlap.width() * overlap.height() if not overlap.isEmpty() else 0
        candidates.append((covered, scale, target, bounds))
        if covered == 0:
            break
    _, scale, target, bounds = min(candidates, key=lambda row: (row[0], -row[1]))
    aid['scale'] = scale
    delta = QPointF(target.topLeft() - bounds.topLeft())
    aid['pos'] = canvas.to_document(canvas.to_view(aid['pos']) + delta)
