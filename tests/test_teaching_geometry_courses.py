# SPDX-License-Identifier: GPL-3.0-or-later
"""All C06 formal operations use owned Qt controls and the actual geometry pipeline."""
from string import Formatter

import pytest
from PyQt6.QtCore import QPointF

from teaching.application import application_catalog
from test_teaching_geometry_adapters import POINTS,SOLIDS,draw_shape,draw_held_line,shape_button
from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import ROOT,writing_host,next_info,assert_step,finished


def test_geometry_catalog_and_eight_language_copy_are_complete():
    import main,i18n
    from teaching.geometry_copy import GEOMETRY_COPY
    catalog,_=application_catalog(main,ROOT)
    course=catalog.course_by_id('c06')
    assert [chapter.id for chapter in course.chapters]==['c06.plane','c06.solid','c06.points','c06.recognition_snap']
    assert [len(chapter.steps) for chapter in course.chapters]==[22,10,10,13]
    assert len(GEOMETRY_COPY)==115
    for key,values in GEOMETRY_COPY.items():
        assert len(values)==8
        for language,value in zip(i18n._LANGS,values):
            assert i18n.TEXT[language][key]==value and value.strip()
            assert not any(field is not None for _,field,_,_ in Formatter().parse(value))


@pytest.mark.parametrize('writing_host',['c06.plane','c06.solid'],indirect=True)
def test_every_plane_or_solid_shape_is_chosen_and_created_separately(writing_host):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    kinds=tuple(POINTS) if host.request.chapter_id=='c06.plane' else SOLIDS
    next_info(host)
    for kind in kinds:
        assert_step(host,'choose_'+kind.lower())
        shape_button(panel,kind).click()
        assert_step(host,'draw_'+kind.lower())
        before=len(canvas.shape_items)
        draw_shape(canvas,kind)
        assert len(canvas.shape_items)==before+1 and canvas.shape_items[-1]['type']==kind
    assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c06.points'],indirect=True)
def test_cancel_discards_only_unfinished_triangle_points_then_three_clicks_finish(writing_host):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    next_info(host);shape_button(panel,'TRIANGLE').click()
    for step,point in [('point1',(120,160)),('point2',(360,160))]:
        assert_step(host,step);mouse(canvas,'press',point);mouse(canvas,'release',point)
    assert len(canvas.pending_points)==2 and not canvas.shape_items
    assert_step(host,'cancel');panel.btn_cancel_points.click()
    assert not canvas.pending_points and not canvas.shape_items
    for step,point in [('restart1',(120,160)),('restart2',(360,160)),('finish3',(240,340))]:
        assert_step(host,step);mouse(canvas,'press',point);mouse(canvas,'release',point)
    assert len(canvas.shape_items)==1 and canvas.shape_items[0]['type']=='TRIANGLE'
    assert_step(host,'order_info');next_info(host);next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c06.recognition_snap'],indirect=True)
def test_dwell_undo_redo_snap_and_two_real_constructions(writing_host,monkeypatch):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    assert len(canvas.shape_items)==1 and not canvas.smart_shapes_enabled
    next_info(host);panel.btn_settings_smart.click()
    assert_step(host,'pen');panel.pen_style_buttons['pen'].click()
    assert_step(host,'recognize_line');draw_held_line(canvas)
    mouse(canvas,'release',(364,460))
    assert len(canvas.shape_items)==2 and not canvas.all_segments
    assert_step(host,'undo_recognition');panel.icon_buttons['undo'].click()
    assert len(canvas.shape_items)==1 and canvas.all_segments
    assert_step(host,'redo_recognition');panel.icon_buttons['redo'].click()
    assert len(canvas.shape_items)==2 and not canvas.all_segments
    assert_step(host,'limits_info');next_info(host)
    assert_step(host,'choose_line');shape_button(panel,'LINE').click()
    assert_step(host,'snap_line')
    for point in ((240,340),(248,157)):
        mouse(canvas,'press',point);mouse(canvas,'release',point)
    line=canvas.shape_items[-1]
    assert line['points'][-1]==QPointF(240,150)
    for operation in ('midpoint','perp_bisector'):
        assert_step(host,operation)
        label=dict(canvas.shape_op_list(line))[operation]
        def choose(menu,*args):next(action for action in menu.actions() if action.text()==label).trigger()
        monkeypatch.setattr(host.module.QMenu,'exec',choose)
        before=len(canvas.shape_items)
        panel.btn_more.click()
        assert len(canvas.shape_items)>before and line in canvas.shape_items
    assert_step(host,'construction_info');next_info(host);next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c06.recognition_snap'],indirect=True)
@pytest.mark.parametrize('endpoint',[(128,157),(240,150)])
def test_wrong_anchor_or_exact_unsnapped_point_does_not_complete_formal_snap(writing_host,endpoint):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    next_info(host);panel.btn_settings_smart.click();panel.pen_style_buttons['pen'].click()
    draw_held_line(canvas);mouse(canvas,'release',(364,460))
    panel.icon_buttons['undo'].click();panel.icon_buttons['redo'].click()
    next_info(host);shape_button(panel,'LINE').click()
    assert_step(host,'snap_line')
    for point in ((240,340),endpoint):mouse(canvas,'press',point);mouse(canvas,'release',point)
    assert host.presenter.engine.current_step_id=='snap_line'
    assert not any(status=='completed' for _,status,_ in progress)
