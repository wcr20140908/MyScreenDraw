# SPDX-License-Identifier: GPL-3.0-or-later
"""Fractional document coordinates and continuous one/two-finger navigation."""
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRectF

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_view import BoardGesture, BoardView


def xy(point):
    return point.x(), point.y()


def test_zoom_keeps_document_anchor_and_fit_centers_content():
    view = BoardView(x=12.25, y=-18.5, zoom=1.25)
    screen_anchor = QPointF(203.5, 119.75)
    document_anchor = view.to_document(screen_anchor)
    view.zoom_at(screen_anchor, 2.5)
    assert view.zoom == 2.5
    assert xy(view.to_document(screen_anchor)) == pytest.approx(xy(document_anchor))
    assert xy(view.to_view(document_anchor)) == pytest.approx(xy(screen_anchor))
    assert xy(view.transform().map(document_anchor)) == pytest.approx(xy(screen_anchor))

    bounds = QRectF(-100.5, -40.25, 400.0, 200.0)
    viewport = QRectF(0.0, 0.0, 1000.0, 600.0)
    view.fit(bounds, viewport)
    assert view.zoom == pytest.approx(2.25)
    assert xy(view.to_view(bounds.center())) == pytest.approx(xy(viewport.center()))
    assert view.document_rect(viewport).contains(bounds)
    assert BoardView.from_data(view.to_data()) == view


def test_gesture_pans_pinches_and_rebases_without_finger_count_jump():
    view = BoardView(x=30.5, y=-12.25, zoom=1.5)
    gesture = BoardGesture()
    before = view.to_data()
    assert not gesture.update(view, {7: QPointF(10.25, 20.75)})
    assert view.to_data() == before
    assert gesture.update(view, {7: QPointF(25.75, 35.25)})
    assert view.to_data() == pytest.approx({"x": 46.0, "y": 2.25, "zoom": 1.5})

    two_fingers = {7: QPointF(25.75, 35.25), 11: QPointF(65.75, 35.25)}
    before = view.to_data()
    document_anchor = view.to_document(QPointF(45.75, 35.25))
    assert not gesture.update(view, two_fingers)
    assert view.to_data() == before
    assert gesture.update(view, {7: QPointF(15.75, 40.25), 11: QPointF(95.75, 40.25)})
    assert view.zoom == pytest.approx(3.0)
    assert xy(view.to_view(document_anchor)) == pytest.approx((55.75, 40.25))

    before = view.to_data()
    assert not gesture.update(view, {7: QPointF(15.75, 40.25)})
    assert view.to_data() == before
    assert gesture.update(view, {7: QPointF(35.75, 32.25)})
    assert view.x == pytest.approx(before["x"] + 20.0)
    assert view.y == pytest.approx(before["y"] - 8.0)
    assert view.zoom == before["zoom"]

    before = view.to_data()
    assert not gesture.update(view, {})
    assert gesture.ids == ()
    assert view.to_data() == before
