# SPDX-License-Identifier: GPL-3.0-or-later
"""6.1.0 mutation/cache audit regressions (offscreen widget paths)."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from test_document_safety_610 import document


def test_coalesced_angle_adjustment_updates_serialized_page(document):
    _, canvas = document
    canvas.enter_whiteboard()
    item = {"id": "angle", "type": "ANGLE", "kind": "angle",
            "color": QColor("black"), "width": 2,
            "vertex": QPointF(100, 100), "p1": QPointF(140, 100),
            "p2": QPointF(100, 60)}
    canvas.shape_items.append(item)
    canvas.mark_content_changed()
    canvas.serialized_document_pages()  # Prime the persistence cache.

    canvas.adjust_angle_item(item, target=110)
    first = canvas.serialized_document_pages()[0]["shapes"][0]["p2"]
    canvas.adjust_angle_item(item, target=130)  # Same coalesced undo key.
    second = canvas.serialized_document_pages()[0]["shapes"][0]["p2"]
    actual = [item["p2"].x(), item["p2"].y()]

    assert first != actual
    assert second == actual  # Must not return the previous coalesced geometry.
