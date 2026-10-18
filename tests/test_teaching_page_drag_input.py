# SPDX-License-Identifier: GPL-3.0-or-later
"""Reach page reordering through Qt mouse dispatch, not startDrag() directly."""
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QListWidget

from test_teaching_application_isolation import drain
from test_teaching_writing_courses import writing_host, assert_step


def click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    drain(QApplication.instance())


def page_drag_contract(writing_host, monkeypatch, *, intermediate=False, wrong_order=False):
    import page_list
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    assert QApplication.instance().platformName() == 'offscreen'
    click(host.presenter.controller.next_button)
    click(panel.rail_count)
    assert_step(host, 'select_last')
    listing = panel.thumbnail_list
    listing.scrollToItem(listing.item(2))
    drain(QApplication.instance())
    position = listing.visualItemRect(listing.item(2)).center()
    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=position)
    drain(QApplication.instance())
    assert_step(host, 'identity_info')
    click(host.presenter.controller.next_button)
    assert_step(host, 'reorder')
    before = [page['page_id'] for page in canvas.pages]
    records, drags = [], []
    emit = host.presenter.events.emit_result

    if wrong_order:
        panel.reorder_whiteboard_page(0, 1)
        assert [page['page_id'] for page in canvas.pages] == [before[1], before[0], before[2]]
        assert_step(host, 'reorder')

    def record(context, name, outcome, details):
        accepted = emit(context, name, outcome, details)
        if context is not None and name == 'page.reordered':
            records.append((dict(details), accepted))
        return accepted

    monkeypatch.setattr(host.presenter.events, 'emit_result', record)
    destinations = (1, 0) if intermediate else (0,)

    class Drag:
        # Only the OS drag loop is replaced. Qt must call our startDrag from
        # actual mouse movement, and the real drop handler commits the model.
        def __init__(self, source):
            assert source is listing
        def setMimeData(self, data):
            assert data is not None
        def setPixmap(self, pixmap):
            pass
        def setHotSpot(self, point):
            pass
        def deleteLater(self):
            pass
        def exec(self, action):
            destination = destinations[len(drags)]
            drags.append(True)
            assert panel._teaching_document_batch is not None
            assert host.presenter._dialog_depth and not host.presenter.barrier.installed
            expected = [page['page_id'] for page in canvas.pages]
            expected.insert(destination, expected.pop(listing.currentRow()))
            listing.scrollToItem(listing.item(destination))
            drain(QApplication.instance())
            point = listing.visualItemRect(listing.item(destination)).topLeft() + QPoint(5, 5)
            event = SimpleNamespace(source=lambda: listing, position=lambda: QPointF(point),
                                    setDropAction=lambda _: None, accept=lambda: None,
                                    ignore=lambda: pytest.fail('Owned drop rejected'))
            listing.dropEvent(event)
            assert [page['page_id'] for page in canvas.pages] == expected
            assert_step(host, 'reorder')  # Credit only after drag cleanup.
            return Qt.DropAction.MoveAction

    monkeypatch.setattr(page_list, 'QDrag', Drag)
    for count, destination in enumerate(destinations, 1):
        listing.scrollToItem(listing.currentItem())
        drain(QApplication.instance())
        start = listing.viewport().mapTo(panel.thumbnail_panel, listing.visualItemRect(listing.currentItem()).center())
        surface = panel.thumbnail_panel.windowHandle()
        QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(surface, start + QPoint(0, -45), delay=30)
        # The fake native loop returns without consuming the release. Release
        # over the moved page, not over an unrelated thumbnail in its old row.
        end = listing.viewport().mapTo(panel.thumbnail_panel, listing.visualItemRect(listing.currentItem()).center())
        QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=end)
        drain(QApplication.instance())
        assert len(drags) == count, 'Real thumbnail movement must enter the owned reorder drag'
        assert listing._drag_source_id is None and panel._teaching_document_batch is None
        assert not host.presenter._dialog_depth and not host.presenter.barrier._suspensions
        if destination != 0:
            assert_step(host, 'reorder')
            assert host.presenter.barrier.installed

    if wrong_order:
        assert [page['page_id'] for page in canvas.pages] == [before[2], before[1], before[0]]
        assert host.presenter.engine.current_step_id == 'reorder', 'C/B/A must not complete the C/A/B lesson'
        assert host.presenter.barrier.installed
        assert not any(accepted for _, accepted in records)
    else:
        assert host.presenter.engine.current_step_id == 'verify_info', 'Real reorder must advance the lesson'
        assert [page['page_id'] for page in canvas.pages] == [before[2], before[0], before[1]]
        assert not host.presenter.barrier.installed  # Information steps allow free input.
        assert len(records) == len(destinations) and records[-1][1]
        assert not any(accepted for _, accepted in records[:-1])
    assert canvas._page_id == before[2] and canvas.current_page == 0
    assert listing.currentRow() == 0 and panel.rail_count.text() == '1/3'


@pytest.mark.parametrize('writing_host', ['c05.reorder'], indirect=True)
@pytest.mark.parametrize('intermediate', [False, True], ids=['direct', 'via-middle'])
def test_real_thumbnail_mouse_drag_completes_formal_reorder(writing_host, monkeypatch, intermediate):
    page_drag_contract(writing_host, monkeypatch, intermediate=intermediate)


@pytest.mark.parametrize('writing_host', ['c05.reorder'], indirect=True)
def test_correct_current_page_with_wrong_remaining_order_does_not_complete(writing_host, monkeypatch):
    page_drag_contract(writing_host, monkeypatch, wrong_order=True)


@pytest.mark.parametrize('writing_host', ['c05.reorder'], indirect=True)
def test_static_movement_mutation_disables_owned_drag(writing_host, monkeypatch):
    writing_host[0].panel.thumbnail_list.setMovement(QListWidget.Movement.Static)
    with pytest.raises(AssertionError, match='Real thumbnail movement must enter the owned reorder drag'):
        page_drag_contract(writing_host, monkeypatch)
