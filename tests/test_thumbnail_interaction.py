# SPDX-License-Identifier: GPL-3.0-or-later
"""Thumbnail activation, persistent page names and visible insertion boundaries."""
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QLine, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QDragLeaveEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QListWidget

import main
from test_document_safety_610 import document
from test_teaching_application_isolation import drain


def labels(panel):
    panel.refresh_page_thumbnails(force=True)
    return [panel.thumbnail_list.item(i).text() for i in range(panel.thumbnail_list.count())]


def overview(panel, canvas, count=9, width=760):
    canvas.enter_whiteboard()
    for _ in range(count - 1):
        canvas.new_page()
    panel.toggle_thumbnail_panel()
    drain(QApplication.instance())
    panel.thumbnail_panel.resize(width, 580)
    drain(QApplication.instance())
    panel.thumbnail_list.doItemsLayout()
    return panel.thumbnail_list


def test_default_names_follow_identity_through_reorder_and_save(document, tmp_path):
    panel, canvas = document
    overview(panel, canvas, 27)
    original = labels(panel)
    assert original == [main.trf('page_label', index=i + 1) for i in range(27)]
    ids = [page['page_id'] for page in canvas.pages]
    assert canvas.rename_page(2, 'Named chapter')
    original[2] = 'Named chapter'
    assert canvas.move_page(18, 13)
    expected = original[:]
    expected.insert(13, expected.pop(18))
    assert labels(panel) == expected
    assert labels(panel)[12:16] == [main.trf('page_label', index=i) for i in (13, 19, 14, 15)]
    assert canvas._page_id == ids[-1]
    assert panel.save_project(str(tmp_path / 'ordered.msd'))
    assert panel.open_project_from_path(str(tmp_path / 'ordered.msd'))
    assert labels(panel) == expected
    assert canvas.delete_page(0)
    assert labels(panel) == expected[1:]
    canvas.new_page()
    assert len(canvas.pages) == 27
    assert labels(panel)[:-1] == expected[1:]
    assert len(set(labels(panel))) == 27
    source_name = labels(panel)[13]
    assert canvas.duplicate_page(13)
    assert canvas._page_name == main.trf('page_copy_name', name=source_name)


def test_legacy_unnamed_pages_get_names_before_first_move(document, tmp_path):
    panel, canvas = document
    path = str(tmp_path / 'legacy.msd')
    main.atomic_write_json(path, main.make_project_data(
        pages=[{'segments': [], 'texts': [], 'shapes': [], 'images': [], 'name': ''}
               for _ in range(4)], current_page=2, whiteboard_mode=True,
        board_style='WHITE', app_version=main.APP_VERSION))
    assert panel.open_project_from_path(path)
    assert not panel.has_unsaved_changes()
    assert canvas.move_page(3, 1)
    assert labels(panel) == [main.trf('page_label', index=i) for i in (1, 4, 2, 3)]
    assert canvas._page_name == main.trf('page_label', index=3)


@pytest.mark.parametrize('already_selected', [False, True])
def test_single_click_stays_open_double_click_enters_and_closes(document, already_selected):
    panel, canvas = document
    listing = overview(panel, canvas, 3)
    point = listing.visualItemRect(listing.item(0)).center()
    if already_selected:
        QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert canvas.current_page == 0
        assert panel.thumbnail_panel.isVisible()
    # QTest.mouseDClick sends only the second press, unlike a physical double click.
    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseDClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.qWait(600)
    assert canvas.current_page == 0
    assert not panel.thumbnail_panel.isVisible()
    assert not panel._thumbnail_live_timer.isActive()


def drag_event(listing, point):
    return SimpleNamespace(source=lambda: listing, position=lambda: QPointF(point),
        setDropAction=lambda _: None, accept=lambda: None, ignore=lambda: None)


def blue_pixels(image):
    return sum(image.pixelColor(x, y) == QColor('#1688ff')
               for x in range(image.width()) for y in range(image.height()))


@pytest.mark.parametrize('width', [320, 760])
@pytest.mark.parametrize('after', [False, True])
def test_indicator_matches_actual_before_after_drop(document, monkeypatch, width, after):
    panel, canvas = document
    listing = overview(panel, canvas, 9, width)
    listing.setCurrentRow(0)
    panel.thumbnail_panel.resize(width, 580)
    drain(QApplication.instance())
    listing.verticalScrollBar().setValue(0)
    QApplication.processEvents()
    before = [page['page_id'] for page in canvas.pages]
    target = 1
    rect = listing.visualItemRect(listing.item(target))
    point = rect.bottomRight() - QPoint(10, 10) if after else rect.topLeft() + QPoint(10, 10)
    listing._drag_source_id = before[0]
    listing._drag_source_row = 0
    monkeypatch.setattr(QAbstractItemView, 'dragMoveEvent', lambda *_: None)
    baseline = blue_pixels(listing.viewport().grab().toImage())
    listing.dragMoveEvent(drag_event(listing, point))
    assert listing._drop_insertion == target + int(after)
    line = listing._drop_line
    assert isinstance(line, QLine) and not line.isNull()
    if width == 320:
        assert line.y1() == line.y2()
        assert abs(line.y1() - (rect.bottom() if after else rect.top())) <= 4
    else:
        assert line.x1() == line.x2()
        assert abs(line.x1() - (rect.right() if after else rect.left())) <= 4
    def assert_painted():
        assert blue_pixels(listing.viewport().grab().toImage()) > baseline + 100

    with monkeypatch.context() as patch:
        patch.setattr(type(listing), 'paintEvent', lambda self, event: QListWidget.paintEvent(self, event))
        with pytest.raises(AssertionError):
            assert_painted()
    assert_painted()
    insertion = listing._drop_insertion
    listing.dropEvent(drag_event(listing, point))
    expected = before[:]
    expected.insert(insertion - 1, expected.pop(0))
    assert [page['page_id'] for page in canvas.pages] == expected
    assert listing._drop_insertion is None and listing._drop_line is None


def test_gaps_cross_rows_scroll_and_leave_update_indicator(document, monkeypatch):
    panel, canvas = document
    listing = overview(panel, canvas, 18)
    listing.verticalScrollBar().setValue(0)
    QApplication.processEvents()
    monkeypatch.setattr(QAbstractItemView, 'dragMoveEvent', lambda *_: None)
    first = listing.visualItemRect(listing.item(0))
    second = listing.visualItemRect(listing.item(1))
    gap = QPoint((first.right() + second.left()) // 2, first.center().y())
    assert not listing.indexAt(gap).isValid()
    listing.dragMoveEvent(drag_event(listing, gap))
    assert listing._drop_insertion == 1
    columns = sum(listing.visualItemRect(listing.item(i)).top() == first.top()
                  for i in range(listing.count()))
    rect = listing.visualItemRect(listing.item(columns))
    listing.dragMoveEvent(drag_event(listing, rect.topLeft() + QPoint(5, 5)))
    assert listing._drop_insertion == columns
    listing.verticalScrollBar().setValue(listing.gridSize().height())
    assert listing._drop_insertion == columns * 2
    listing.dragLeaveEvent(QDragLeaveEvent())
    assert listing._drop_insertion is None and listing._drop_line is None
    assert listing._drag_point is None
    listing.verticalScrollBar().setValue(listing.verticalScrollBar().maximum())
    last = listing.visualItemRect(listing.item(listing.count() - 1))
    listing.dragMoveEvent(drag_event(listing, last.bottomRight() + QPoint(10, 5)))
    assert listing._drop_insertion == listing.count()
