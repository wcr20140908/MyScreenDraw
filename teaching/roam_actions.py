# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe completed whiteboard navigation without changing document or view.

Entry tokens belong to one complete input sequence. Only matching tutorial steps
pay for snapshots; moves never serialize the document or issue new operations.
"""
from dataclasses import dataclass
from math import hypot, isclose

from PyQt6.QtCore import QLine, QLineF, QPoint, QPointF, QRect, QRectF, QSize, QSizeF
from PyQt6.QtGui import QColor, QPen, QPixmap

from board_view import BoardView


EVENT = 'board.view_changed'


def _freeze(value):
    if isinstance(value, dict):
        return {key: _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, QPixmap):
        return ('pixmap', value.cacheKey(), value.width(), value.height())
    if isinstance(value, (QLine, QLineF, QPoint, QPointF, QRect, QRectF,
                          QSize, QSizeF, QColor, QPen)):
        return type(value)(value)
    return value


def _content_snapshot(canvas):
    live = canvas.live_page()
    pages = canvas.pages or [live]
    return (canvas.board_style, tuple(_freeze({key: value for key, value in
        (live if index == canvas.current_page else page).items()
        if key not in ('view', '_revision')}) for index, page in enumerate(pages)))


def _history_snapshot(canvas):
    return _freeze((canvas.undo_stack, canvas.redo_stack, canvas.last_undo_key))


def _same_view(left, right):
    return all(isclose(left[key], right[key], rel_tol=1e-9, abs_tol=1e-7)
               for key in ('x', 'y', 'zoom'))


@dataclass
class _TouchObservation:
    view: dict
    ids: tuple = ()
    anchor: object = None
    zoom: float = 1.0
    distance: float = 0.0
    valid: bool = True


@dataclass
class RoamAction:
    bus: object
    context: object
    canvas: object
    action: str
    source: str
    page_id: str
    view: dict
    content: object
    history: object
    anchor: object = None
    expected_fit: object = None
    nonempty: bool = False
    closed: bool = False
    touch: object = None


def begin_roam_action(canvas, action, source, anchor=None):
    """Capture at press/wheel/button entry, never at release or in a move loop."""
    bus = getattr(getattr(canvas, 'panel', None), 'teaching_events', None)
    if bus is None or not canvas.board_view_active:
        return None
    if action not in ('pan', 'zoom', 'fit', 'home', 'gesture'):
        raise ValueError('unknown whiteboard navigation action')
    if action in ('pan', 'zoom', 'gesture') and not canvas.is_roaming:
        return None
    operation = bus.begin_operation(EVENT)
    if operation is None:
        return None
    try:
        view = dict(canvas.board_view.to_data())
        expected, nonempty = None, False
        if action == 'fit':
            bounds = canvas.page_content_bounds(canvas.live_page())
            nonempty = not bounds.isEmpty()
            expected = BoardView()
            expected.fit(bounds, QRectF(canvas.rect()))
            expected = expected.to_data()
        return RoamAction(bus, operation, canvas, action, source, str(canvas._page_id), view,
                          _content_snapshot(canvas), _history_snapshot(canvas),
                          QPointF(anchor) if anchor is not None else None, expected, nonempty)
    except Exception:
        bus.discard_operation(operation)
        raise


def observe_roam_touch(canvas, token, points):
    """Check one BoardGesture.update result, including contact-ID rebases.

    The caller passes the same point mapping immediately after each business
    update (also after removing released points). A rebase never trusts the
    possibly corrupted current view: expected views derive from the entry view
    and input alone. Only two IDs affect navigation, just as in BoardGesture.
    """
    if token is None or token.closed:
        return
    if token.touch is None:
        token.touch = _TouchObservation(dict(token.view))
    observation = token.touch
    ids = tuple(sorted(points)[:2])
    if ids:
        first, second = QPointF(points[ids[0]]), QPointF(points[ids[-1]])
        center = (first + second) / 2.0
        distance = hypot(first.x() - second.x(), first.y() - second.y())
        if ids != observation.ids:
            observation.anchor = BoardView.from_data(observation.view).to_document(center)
            observation.zoom = observation.view['zoom']
            observation.distance = distance
        else:
            zoom = (observation.zoom * distance / observation.distance
                    if observation.distance > 0 else observation.zoom)
            zoom = max(BoardView.MIN_ZOOM, min(BoardView.MAX_ZOOM, zoom))
            observation.view = {'x': center.x() - observation.anchor.x() * zoom,
                                'y': center.y() - observation.anchor.y() * zoom,
                                'zoom': zoom}
    observation.ids = ids
    observation.valid = (observation.valid and canvas is token.canvas
                         and str(canvas._page_id) == token.page_id
                         and _same_view(canvas.board_view.to_data(), observation.view))


def cancel_roam_action(token):
    if token is not None and not token.closed:
        token.closed = True
        token.bus.discard_operation(token.context)


def finish_roam_action(canvas, token, anchor=None):
    """Submit only after the normal business tail, once, with observed facts."""
    if token is None or token.closed:
        return False
    token.closed = True
    try:
        if (canvas is not token.canvas or str(canvas._page_id) != token.page_id
                or not canvas.board_view_active
                or token.action in ('pan', 'zoom', 'gesture') and not canvas.is_roaming):
            return False
        view = dict(canvas.board_view.to_data())
        changed = not _same_view(token.view, view)
        content_unchanged = token.content == _content_snapshot(canvas)
        history_unchanged = token.history == _history_snapshot(canvas)
        zoom_changed = not isclose(token.view['zoom'], view['zoom'], rel_tol=1e-9)
        action = ('zoom' if zoom_changed else 'pan') if token.action == 'gesture' else token.action
        distance = hypot(view['x'] - token.view['x'], view['y'] - token.view['y'])
        direction = ('in' if view['zoom'] > token.view['zoom'] else 'out') if zoom_changed else 'none'
        anchor_preserved = False
        if token.source == 'touch':
            anchor_preserved = (token.touch is not None and token.touch.valid
                                and _same_view(view, token.touch.view))
        elif token.anchor is not None and anchor is not None:
            before = BoardView.from_data(token.view).to_document(token.anchor)
            after = canvas.board_view.to_document(QPointF(anchor))
            anchor_preserved = hypot(before.x() - after.x(), before.y() - after.y()) <= 1e-5
        valid = (changed and content_unchanged and history_unchanged
                 and (token.source != 'touch' or anchor_preserved))
        if action == 'pan':
            valid = valid and not zoom_changed
        elif action == 'zoom':
            valid = valid and zoom_changed and anchor_preserved
        elif action == 'fit':
            valid = valid and token.nonempty and _same_view(view, token.expected_fit)
        elif action == 'home':
            valid = valid and _same_view(view, {'x': 0.0, 'y': 0.0, 'zoom': 1.0})
        details = {'action': action, 'source': token.source, 'page_id': token.page_id,
                   'changed': changed, 'content_unchanged': content_unchanged,
                   'history_unchanged': history_unchanged,
                   'x_before': token.view['x'], 'y_before': token.view['y'],
                   'zoom_before': token.view['zoom'], 'x': view['x'], 'y': view['y'],
                   'zoom': view['zoom'], 'distance': distance, 'direction': direction,
                   'anchor_preserved': anchor_preserved, 'nonempty': token.nonempty,
                   'fitted': action == 'fit' and token.nonempty and _same_view(view, token.expected_fit),
                   'whiteboard_mode': bool(canvas.whiteboard_mode),
                   'board_view_active': bool(canvas.board_view_active),
                   'roaming': bool(canvas.is_roaming),
                   'mouse_passthrough': bool(canvas._mouse_passthrough)}
        if token.anchor is not None:
            details.update(anchor_x=token.anchor.x(), anchor_y=token.anchor.y())
        return token.bus.emit_result(token.context, EVENT, 'success' if valid else 'cancelled', details)
    finally:
        token.bus.discard_operation(token.context)
