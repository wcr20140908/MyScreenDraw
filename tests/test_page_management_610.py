# SPDX-License-Identifier: GPL-3.0-or-later
"""Page operations and revision-aware visible-only thumbnail rendering."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch
from types import SimpleNamespace
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QApplication, QInputDialog
import main
from test_document_safety_610 import document, ink, two_pages


@pytest.mark.parametrize("placement,expected", [
    ("after", ["first", "first", "second"]),
    ("before", ["first", "first", "second"]),
    ("first", ["first", "first", "second"]),
    ("last", ["first", "second", "first"]),
])
def test_duplicate_is_independent_and_placed_by_setting(document, placement, expected):
    panel, canvas = document
    two_pages(canvas)
    original_id = canvas.pages[0]["page_id"]
    assert canvas.duplicate_page(0, placement)
    pages = canvas.document_pages()
    assert [p["segments"][0]["id"] for p in pages] == expected
    assert len({p["page_id"] for p in pages}) == 3
    duplicate_id = canvas._page_id
    assert duplicate_id != original_id
    original = next(p for p in pages if p["page_id"] == original_id)
    canvas.all_segments[0]["pen"].setWidth(15)
    canvas.mark_content_changed()
    assert original["segments"][0]["pen"].width() != 15
    assert panel.has_unsaved_changes()


def test_duplicate_middle_page_distinguishes_before_and_after(document):
    panel, canvas = document
    two_pages(canvas)
    canvas.new_page()
    ink(canvas, "third")
    assert canvas.duplicate_page(1, "before")
    assert canvas.current_page == 1
    assert canvas.pages[2]["segments"][0]["id"] == "second"
    assert canvas.duplicate_page(2, "after")
    assert canvas.current_page == 3


def test_rename_and_reorder_preserve_content_selection_and_roundtrip(document, tmp_path):
    panel, canvas = document
    two_pages(canvas)
    active_id = canvas._page_id
    assert canvas.rename_page(0, "章节一")
    assert canvas.move_page(0, 1)
    assert canvas.current_page == 0
    assert canvas._page_id == active_id
    assert str(canvas.all_segments[0]["id"]) == "second"
    path = str(tmp_path / "reordered.msd")
    assert panel.save_project(path)
    assert panel.open_project_from_path(path)
    assert canvas.pages[1]["name"] == "章节一"
    assert [p["segments"][0]["id"] for p in canvas.pages] == ["second", "first"]


def test_invalid_page_operations_do_not_mutate(document):
    panel, canvas = document
    two_pages(canvas)
    before = canvas.document_signature()
    for action in (lambda: canvas.rename_page(0, " "), lambda: canvas.rename_page(0, "x" * 257),
                   lambda: canvas.move_page(-1, 0), lambda: canvas.move_page(0, 99),
                   lambda: canvas.duplicate_page(99), lambda: canvas.duplicate_page(0, "invalid")):
        assert not action()
        assert canvas.document_signature() == before


def test_rename_button_updates_current_page(document, monkeypatch):
    panel, canvas = document
    two_pages(canvas)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("新标题", True))
    panel.btn_rename_page.click()
    assert canvas._page_name == "新标题"
    panel.btn_copy_page.click()
    assert len(canvas.pages) == 3
    assert canvas.current_page == 2


def test_drag_requests_actual_document_order(document):
    panel, canvas = document
    two_pages(canvas)
    canvas.switch_page(-1)
    panel.toggle_thumbnail_panel()
    widget = panel.thumbnail_list
    widget.setCurrentRow(0)
    widget.doItemsLayout()
    target = widget.visualItemRect(widget.item(1)).bottomLeft()
    accepted = []
    event = SimpleNamespace(source=lambda: widget, position=lambda: QPointF(target),
                            setDropAction=lambda action: None, accept=lambda: accepted.append(True),
                            ignore=lambda: accepted.append(False))
    widget.dropEvent(event)
    assert accepted == [True]
    assert [p["segments"][0]["id"] for p in canvas.document_pages()] == ["second", "first"]
    assert canvas.current_page == 1


def test_hidden_and_old_pages_are_not_rerendered_on_switch(document):
    panel, canvas = document
    two_pages(canvas)
    with patch.object(canvas, "render_page_pixmap", wraps=canvas.render_page_pixmap) as render:
        panel.refresh_page_thumbnails()
        render.assert_not_called()
        panel.toggle_thumbnail_panel()
        QApplication.processEvents()
        panel._tick_live_thumbnail()
        warm_count = render.call_count
        panel._tick_live_thumbnail()
        assert render.call_count == warm_count
        # Warm both pages explicitly by visiting them; then navigate again.
        canvas.switch_page(-1)
        panel.update_whiteboard_ui()
        panel._tick_live_thumbnail()
        canvas.switch_page(1)
        panel.update_whiteboard_ui()
        panel._tick_live_thumbnail()
        warmed = render.call_count
        canvas.switch_page(-1)
        panel.update_whiteboard_ui()
        panel._tick_live_thumbnail()
        assert render.call_count == warmed


def test_many_pages_only_render_visible_first(document):
    panel, canvas = document
    canvas.enter_whiteboard()
    for _ in range(39):
        canvas.new_page()
    with patch.object(canvas, "render_page_pixmap", wraps=canvas.render_page_pixmap) as render:
        panel.toggle_thumbnail_panel()
        QApplication.processEvents()
        panel._tick_live_thumbnail()
        assert 0 < render.call_count < 10
        assert render.call_count < len(canvas.pages)
    assert panel.thumbnail_list.count() == 40


def test_thumbnail_refresh_repairs_missing_view_row_even_when_order_is_unchanged(document):
    panel, canvas = document
    two_pages(canvas)
    panel.refresh_page_thumbnails(force=True)
    order = panel._thumbnail_order
    panel._syncing_thumbnails = True
    panel.thumbnail_list.takeItem(0)  # Qt's default MoveAction source cleanup
    panel._syncing_thumbnails = False
    assert panel._thumbnail_order == order
    panel.refresh_page_thumbnails(force=True)
    assert panel.thumbnail_list.count() == len(canvas.pages) == 2
    assert [panel.thumbnail_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(2)] == list(order)


def test_drop_uses_dragged_identity_not_a_later_current_row(document):
    panel, canvas = document
    two_pages(canvas)
    panel.refresh_page_thumbnails(force=True)
    widget = panel.thumbnail_list
    widget._drag_source_id = canvas.pages[0]["page_id"]
    widget.setCurrentRow(1)
    widget.doItemsLayout()
    point = widget.visualItemRect(widget.item(1)).bottomLeft()
    event = SimpleNamespace(source=lambda: widget, position=lambda: QPointF(point),
                            setDropAction=lambda _: None, accept=lambda: None, ignore=lambda: None)
    widget.dropEvent(event)
    assert [p["segments"][0]["id"] for p in canvas.document_pages()] == ["second", "first"]


def test_start_drag_does_not_use_qt_source_row_deletion(document, monkeypatch):
    import page_list
    from PyQt6.QtWidgets import QListWidget
    panel, canvas = document
    two_pages(canvas)
    panel.refresh_page_thumbnails(force=True)
    widget = panel.thumbnail_list
    widget.setCurrentRow(0)
    calls = []
    class Drag:
        def __init__(self, source): self.source = source
        def setMimeData(self, data): assert data is not None
        def setPixmap(self, pix): pass
        def setHotSpot(self, point): pass
        def deleteLater(self): pass
        def exec(self, action):
            calls.append(action)
            assert self.source._drag_source_id == canvas.pages[0]["page_id"]
            return Qt.DropAction.MoveAction
    monkeypatch.setattr(page_list, "QDrag", Drag, raising=False)
    monkeypatch.setattr(QListWidget, "startDrag", lambda *args: pytest.fail("default Qt drag deletes source rows"))
    widget.startDrag(Qt.DropAction.MoveAction)
    assert calls == [Qt.DropAction.MoveAction]
    assert widget._drag_source_id is None
    assert widget.count() == len(canvas.pages) == 2


def test_internal_drag_move_uses_generic_autoscroll_and_accepts_page_insertion(document, monkeypatch):
    from PyQt6.QtWidgets import QAbstractItemView
    from unittest.mock import Mock
    panel, canvas = document
    widget = panel.thumbnail_list
    housekeeping = Mock()
    monkeypatch.setattr(QAbstractItemView, "dragMoveEvent", housekeeping)
    accepted = []
    event = SimpleNamespace(source=lambda: widget, setDropAction=lambda _: None,
                            accept=lambda: accepted.append(True), ignore=lambda: accepted.append(False))
    widget.dragMoveEvent(event)
    housekeeping.assert_called_once_with(widget, event)
    assert accepted == [True]
