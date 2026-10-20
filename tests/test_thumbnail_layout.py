# SPDX-License-Identifier: GPL-3.0-or-later
"""Full page previews stay inside the compact thumbnail viewport, offscreen."""
import pytest
from PyQt6.QtCore import QLineF, QRect, Qt
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QApplication

from test_document_safety_610 import document
from test_teaching_application_isolation import drain


def thumbnail_contract(document, width=320, pages=1, font=13, height=300):
    panel, canvas = document
    assert QApplication.instance().platformName() == 'offscreen'
    canvas.enter_whiteboard()
    for index in range(pages):
        if index:
            canvas.new_page()
        canvas.all_segments = [
            {'id': 'left', 'line': QLineF(-900, -400, -900, 400), 'pen': QPen(QColor('#ee2020'), 60)},
            {'id': 'right', 'line': QLineF(900, -400, 900, 400), 'pen': QPen(QColor('#2050ee'), 60)}]
        canvas.mark_content_changed()
    panel.toggle_thumbnail_panel()
    panel.thumbnail_panel.resize(width, height)
    widget = panel.thumbnail_list
    widget.setStyleSheet(f'QListWidget {{ font-size: {font}px; }}')
    drain(QApplication.instance())
    panel.refresh_page_thumbnails(force=True)
    drain(QApplication.instance())
    widget.scrollToItem(widget.currentItem())
    widget.doItemsLayout()
    viewport = widget.viewport().rect()
    item_rect = widget.visualItemRect(widget.currentItem())
    assert 0 <= item_rect.left() and item_rect.right() < viewport.width(), \
        f'Thumbnail must fit horizontally: item={item_rect}, viewport={viewport}'
    assert item_rect.height() <= viewport.height(), \
        f'One complete thumbnail and label must fit: item={item_rect}, viewport={viewport}'
    assert widget.horizontalScrollBar().maximum() == 0
    assert widget.count() == pages and canvas.current_page == pages - 1
    image = widget.viewport().grab().toImage()
    colors = [image.pixelColor(x, y) for y in range(image.height()) for x in range(image.width())]
    assert any(color.red() > color.blue() * 1.5 and color.red() > color.green() * 1.5 for color in colors), \
        'The leftmost page ink must be visible in the preview'
    assert any(color.blue() > color.red() * 1.5 and color.blue() > color.green() * 1.2 for color in colors), \
        'The rightmost page ink must be visible in the preview'
    return panel, canvas


@pytest.mark.parametrize('width,pages,font', [(320, 1, 13), (320, 3, 13), (240, 3, 13), (320, 3, 20)])
def test_thumbnail_image_and_label_fit_the_available_viewport(document, width, pages, font):
    thumbnail_contract(document, width, pages, font)


@pytest.mark.parametrize('width,columns', [(1000, 4), (760, 3), (540, 2), (320, 1)])
def test_thumbnails_wrap_into_complete_columns_without_horizontal_scroll(document, width, columns):
    panel, canvas = thumbnail_contract(document, width=width, pages=13, height=580)
    widget = panel.thumbnail_list
    widget.scrollToTop()
    widget.doItemsLayout()
    rects = [widget.visualItemRect(widget.item(index)) for index in range(widget.count())]
    first_row = [rect for rect in rects if rect.top() == rects[0].top()]
    assert len(first_row) == columns, (f'Thumbnail overview must use the available columns: '
                                       f'{widget.viewport().size()=}, {widget.gridSize()=}, {rects[:4]=}')
    assert rects[columns].top() > rects[0].top()
    assert all(0 <= rect.left() <= rect.right() < widget.viewport().width() for rect in rects)
    assert all(rect.width() >= widget.iconSize().width() for rect in rects)
    assert widget.horizontalScrollBar().maximum() == 0
    assert widget.verticalScrollBar().maximum() > 0
    assert widget.dragEnabled()

