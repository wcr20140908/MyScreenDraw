# SPDX-License-Identifier: GPL-3.0-or-later
"""Low-latency ink must not clone/repaint unrelated page content on input."""
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QLine, QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QApplication

import main
from test_document_safety_610 import document


def send(canvas, kind, pos, *, down=True):
    button=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
    buttons=Qt.MouseButton.LeftButton if down else Qt.MouseButton.NoButton
    point=QPointF(*pos)
    QApplication.sendEvent(canvas,QMouseEvent(kind,point,point,button,buttons,Qt.KeyboardModifier.NoModifier))


def mouse_stroke(canvas):
    send(canvas,QEvent.Type.MouseButtonPress,(100,110))
    send(canvas,QEvent.Type.MouseMove,(120,118))
    send(canvas,QEvent.Type.MouseMove,(140,125))
    send(canvas,QEvent.Type.MouseButtonRelease,(140,125),down=False)


def original_ink():
    pen=QPen(QColor('#125678'),4)
    return [{'id':'original','line':QLine(20+i,30,22+i,32),'pen':pen,'marker':False} for i in range(300)]


@pytest.mark.parametrize('tool',['PEN','MARKER','LASER'])
def test_ink_press_never_captures_the_whole_page(document,tool):
    _,canvas=document
    canvas.all_segments=original_ink()
    canvas.draw_state=tool
    before=list(canvas.all_segments)
    with patch.object(canvas,'capture_page',wraps=canvas.capture_page) as capture:
        send(canvas,QEvent.Type.MouseButtonPress,(100,110))
        assert capture.call_count==0
    assert canvas.pending_undo is None
    assert canvas.all_segments==before
    send(canvas,QEvent.Type.MouseButtonRelease,(100,110),down=False)


@pytest.mark.parametrize('tool',['PEN','MARKER'])
def test_ink_release_uses_only_stroke_delta_and_defers_page_snapshot(document,tool):
    _,canvas=document
    canvas.enter_whiteboard()
    canvas.all_segments=original_ink()
    canvas.mark_content_changed()
    canvas.save_current_page()
    canvas.draw_state=tool
    with patch.object(canvas,'capture_page',wraps=canvas.capture_page) as capture:
        mouse_stroke(canvas)
        assert capture.call_count==0
    assert len(canvas.undo_stack)==1
    assert canvas._is_delta(canvas.undo_stack[-1])
    assert len(canvas.undo_stack[-1]['segments'])<50
    assert canvas._ink_page_pending
    canvas.flush_pending_snapshot()
    assert len(canvas.pages[canvas.current_page]['segments'])==len(canvas.all_segments)
    assert not canvas._ink_page_pending
    assert canvas.undo()
    assert canvas.all_segments==original_ink()
    assert canvas.redo()
    assert len(canvas.all_segments)>300


def test_touch_release_defers_snapshot_but_save_still_includes_all_contacts(document,tmp_path):
    panel,canvas=document
    canvas.enter_whiteboard()
    canvas.smart_shapes_enabled=False
    with patch.object(canvas,'capture_page',wraps=canvas.capture_page) as capture:
        canvas._pointer_press(1,QPoint(100,100),1)
        canvas._pointer_press(2,QPoint(300,300),1)
        canvas._pointer_move(1,QPoint(150,130),1)
        canvas._pointer_move(2,QPoint(350,330),1)
        canvas._pointer_release(1,QPoint(150,130))
        canvas._pointer_release(2,QPoint(350,330))
        assert capture.call_count==0
    expected=main.serialize_page(canvas.capture_page())['segments']
    path=tmp_path/'touch.msd'
    assert panel.save_project(str(path))
    assert main.read_json_maybe_gz(str(path))['pages'][0]['segments']==expected
    assert len(canvas.undo_stack)==2


def test_mouse_move_only_invalidates_tip_region_and_keeps_history_cache(document):
    _,canvas=document
    canvas.smart_shapes_enabled=False
    canvas.all_segments=original_ink()
    canvas._stroke_geometry_cache.sync(canvas.all_segments,main.GROUPED_STYLES,canvas.segment_ink_radius)
    cache=canvas._stroke_geometry_cache
    built=cache.parts_processed
    canvas.draw_state='PEN'
    send(canvas,QEvent.Type.MouseButtonPress,(300,300))
    with patch.object(canvas,'update',wraps=canvas.update) as update:
        send(canvas,QEvent.Type.MouseMove,(316,308))
    assert update.call_args_list
    assert all(call.args for call in update.call_args_list), 'Ink input must not request a full canvas repaint'
    region=QRectF(update.call_args_list[-1].args[0])
    assert region.contains(QPointF(300,300)) and region.contains(QPointF(316,308))
    assert region.width()<100 and region.height()<100
    cache.sync(canvas.all_segments,main.GROUPED_STYLES,canvas.segment_ink_radius)
    before_release=cache.parts_processed
    send(canvas,QEvent.Type.MouseButtonRelease,(316,308),down=False)
    cache.sync(canvas.all_segments,main.GROUPED_STYLES,canvas.segment_ink_radius)
    assert cache.parts_processed==before_release
    assert before_release>built


def test_deferred_ink_survives_page_navigation_and_document_export(document):
    _,canvas=document
    canvas.enter_whiteboard()
    canvas.smart_shapes_enabled=False
    mouse_stroke(canvas)
    expected=main.serialize_page(canvas.capture_page())['segments']
    canvas.new_page()
    canvas.switch_page(-1)
    assert main.serialize_page(canvas.capture_page())['segments']==expected
    assert canvas.serialized_document_pages()[0]['segments']==expected


@pytest.mark.parametrize('style',list(main.PEN_STYLES)+['marker'])
def test_incremental_tip_repaint_matches_full_content_pixels(document,style):
    _,canvas=document
    canvas.smart_shapes_enabled=False
    canvas.pen_style='pen' if style=='marker' else style
    canvas.draw_state='MARKER' if style=='marker' else 'PEN'
    canvas.pen_width=14
    canvas.marker_width=24
    canvas.pen_options['neon']=main.normalize_pen_options('neon',{'glow_size':500})
    canvas.all_segments=original_ink()
    canvas.mark_content_changed(repaint=False)
    image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('white'))
    def paint(target,clip=None):
        painter=QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if clip is not None:
            painter.setClipRect(clip)
            painter.fillRect(clip,QColor('white'))
        canvas.draw_content(painter,clip=clip)
        painter.end()
    paint(image)
    send(canvas,QEvent.Type.MouseButtonPress,(100,110))
    for pos in ((120,118),(140,125),(160,134)):
        with patch.object(canvas,'update',wraps=canvas.update) as update:
            send(canvas,QEvent.Type.MouseMove,pos)
        assert all(call.args for call in update.call_args_list)
        clip=QRectF(update.call_args_list[-1].args[0])
        paint(image,clip)
        expected=QImage(image.size(),image.format());expected.fill(QColor('white'))
        paint(expected)
        assert image==expected


class CountedSegments(list):
    def __init__(self, values):
        super().__init__(values)
        self.visited=0

    def __iter__(self):
        for segment in super().__iter__():
            self.visited+=1
            yield segment


def test_ordinary_stroke_finish_never_scans_unrelated_old_segments(document):
    _,canvas=document
    canvas.smart_shapes_enabled=False
    canvas.all_segments=CountedSegments(original_ink())
    mouse_stroke(canvas)
    assert canvas.all_segments.visited==0
    assert len(canvas.undo_stack[-1]['segments'])<50


def test_pen_press_invalidates_old_selection_hud_outside_new_tip(document):
    _,canvas=document
    canvas.all_segments=original_ink()
    canvas.selected_ids={'original'}
    old=canvas.selection_bounds()
    with patch.object(canvas,'update',wraps=canvas.update) as update:
        send(canvas,QEvent.Type.MouseButtonPress,(600,600))
    assert update.call_args_list
    assert any(not call.args or QRectF(call.args[0]).intersects(old) for call in update.call_args_list)
    assert not canvas.selected_ids
