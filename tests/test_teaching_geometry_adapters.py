# SPDX-License-Identifier: GPL-3.0-or-later
"""Real C06 shape, dwell and construction results under owned offscreen paths."""
import time
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QPoint, QPointF

from test_teaching_application import application_host,practice_request
from test_teaching_business_adapters import attach_wait,mouse

POINTS={
    'LINE':[(100,160),(360,160)],'DASHED_LINE':[(100,160),(360,160)],
    'TRIANGLE':[(100,160),(360,160),(240,340)],'RECT':[(100,160),(360,340)],
    'PARALLELOGRAM':[(100,160),(300,160),(360,340)],
    'TRAPEZOID':[(100,340),(360,340),(320,160),(140,160)],
    'DIAMOND':[(100,250),(360,250),(240,340)],
    'ANGLE':[(240,240),(100,240),(240,360)],
    'CIRCLE':[(240,240),(340,240)],'ELLIPSE':[(100,160),(360,340)]}
SOLIDS=('CUBOID','CUBE','CYLINDER','CONE')


def prepare_geometry(host,shape='LINE'):
    if not host.context.ui_active:host.context.activate();host.activate()
    panel,canvas=host.panel,host.panel.canvas
    canvas.finish_active_ink()
    canvas.shape_items=[];canvas.all_segments=[];canvas.pending_points=[]
    canvas.smart_shapes_enabled=False
    canvas.shape_type=shape
    panel.set_tool('SHAPE',panel.btn_shape)
    panel.show_only_sub(panel.shape_sub)
    return panel,canvas


def shape_button(panel,kind):return next(btn for btn in panel.shape_buttons if btn.property('shape_type')==kind)


def draw_shape(canvas,kind):
    if kind in POINTS:
        for point in POINTS[kind]:mouse(canvas,'press',point);mouse(canvas,'release',point)
    else:
        mouse(canvas,'press',(100,160));mouse(canvas,'move',(360,340));mouse(canvas,'release',(360,340))


@pytest.mark.parametrize('kind',tuple(POINTS)+SOLIDS)
def test_each_shape_selection_and_real_submission_have_distinct_results(application_host,kind):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'ELLIPSE' if kind=='LINE' else 'LINE')
    engine=attach_wait(panel,'shape.type_changed',equals={'type':kind})
    shape_button(panel,kind).click()
    assert canvas.shape_type==kind and engine.phase=='completed'
    engine=attach_wait(panel,'shape.committed',equals={'type':kind,'count':1})
    draw_shape(canvas,kind)
    assert [item['type'] for item in canvas.shape_items]==[kind]
    assert engine.phase=='completed' and not engine._issued


def test_point_added_and_cancel_only_count_real_unfinished_points(application_host):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'TRIANGLE')
    engine=attach_wait(panel,'shape.point_added',equals={'type':'TRIANGLE','points':1})
    mouse(canvas,'press',(100,160))
    assert engine.phase=='running'
    mouse(canvas,'release',(100,160))
    assert engine.phase=='completed' and len(canvas.pending_points)==1
    engine=attach_wait(panel,'shape.points_cancelled',equals={'removed':1})
    panel.cancel_shape_points()
    assert not canvas.pending_points and not canvas.shape_items and engine.phase=='completed'
    engine=attach_wait(panel,'shape.points_cancelled')
    panel.cancel_shape_points()
    assert engine.phase=='running' and not engine._issued


@pytest.mark.parametrize('kind',['LINE','RECT','CUBOID'])
def test_incomplete_or_degenerate_shape_never_completes(application_host,kind):
    host,_=application_host
    panel,canvas=prepare_geometry(host,kind)
    engine=attach_wait(panel,'shape.committed')
    mouse(canvas,'press',(100,160));mouse(canvas,'release',(100,160))
    if kind!='CUBOID':mouse(canvas,'press',(100,160));mouse(canvas,'release',(100,160))
    assert engine.phase=='running' and not engine._issued


def test_shape_release_tail_failure_does_not_complete(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'CUBOID')
    engine=attach_wait(panel,'shape.committed')
    mouse(canvas,'press',(100,160));mouse(canvas,'move',(360,340))
    with monkeypatch.context() as patch:
        patch.setattr(panel,'heartbeat_refresh',Mock(side_effect=RuntimeError('shape tail')))
        with pytest.raises(RuntimeError,match='shape tail'):mouse(canvas,'release',(360,340))
    assert canvas.shape_items and engine.phase=='running' and not engine._issued


@pytest.mark.parametrize('previous_tool,drawing_mode',[('PEN',True),('SHAPE',False)])
def test_same_type_reactivated_from_another_tool_or_passthrough_completes(application_host,previous_tool,drawing_mode):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'LINE')
    if previous_tool=='PEN':panel.choose_pen_style('pen')
    panel.set_drawing_mode(drawing_mode)
    assert canvas.shape_type=='LINE' and canvas.draw_state==previous_tool
    engine=attach_wait(panel,'shape.type_changed',equals={'type':'LINE'})
    shape_button(panel,'LINE').click()
    assert canvas.draw_state=='SHAPE' and canvas.is_drawing_mode
    assert engine.phase=='completed' and not engine._issued


def test_same_shape_selection_does_not_complete(application_host):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'LINE')
    engine=attach_wait(panel,'shape.type_changed')
    shape_button(panel,'LINE').click()
    assert engine.phase=='running' and not engine._issued


def test_second_line_endpoint_reports_actual_snap_not_ordinary_line(application_host):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'LINE')
    anchor=canvas.build_point_shape('LINE',[QPointF(120,150),QPointF(240,150)])
    canvas.add_shape_item(anchor,select=False)
    engine=attach_wait(panel,'shape.committed',equals={'type':'LINE','snapped':True})
    mouse(canvas,'press',(240,340));mouse(canvas,'release',(240,340))
    mouse(canvas,'press',(248,157));mouse(canvas,'release',(248,157))
    assert canvas.shape_items[-1]['points'][-1]==QPointF(240,150)
    assert engine.phase=='completed'


def draw_held_line(canvas):
    mouse(canvas,'press',(100,460))
    for x in range(112,365,12):mouse(canvas,'move',(x,460+(x%3)))
    canvas._hold_since=time.perf_counter()-0.7
    canvas._tick_smart_hold()


def prepare_recognition(host):
    panel,canvas=prepare_geometry(host)
    panel.choose_pen_style('pen')
    canvas.smart_shapes_enabled=True
    return panel,canvas


def test_real_dwell_recognition_credits_after_conversion_and_keeps_undo(application_host):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized',equals={'type':'LINE','count':1})
    draw_held_line(canvas)
    assert [item['type'] for item in canvas.shape_items]==['LINE'] and not canvas.all_segments
    assert engine.phase=='running'
    mouse(canvas,'release',(364,460))
    assert engine.phase=='completed'
    assert canvas.undo() and canvas.all_segments and not canvas.shape_items
    assert canvas.redo() and canvas.shape_items and not canvas.all_segments


def test_dwell_with_old_epoch_cannot_complete(application_host):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized')
    mouse(canvas,'press',(100,460))
    for x in range(112,365,12):mouse(canvas,'move',(x,460))
    engine.pause();engine.resume()
    canvas._hold_since=time.perf_counter()-0.7;canvas._tick_smart_hold()
    assert canvas.shape_items and engine.phase=='running' and not engine._issued
    mouse(canvas,'release',(364,460))


def test_recognition_tail_failure_never_completes(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized')
    mouse(canvas,'press',(100,460))
    for x in range(112,365,12):mouse(canvas,'move',(x,460))
    canvas._hold_since=time.perf_counter()-0.7
    with monkeypatch.context() as patch:
        patch.setattr(canvas,'update',Mock(side_effect=RuntimeError('recognition tail')))
        with pytest.raises(RuntimeError,match='recognition tail'):canvas._tick_smart_hold()
    assert engine.phase=='running' and not engine._issued
    mouse(canvas,'release',(364,460))


def test_recognition_setting_requires_changed_saved_private_option(application_host):
    host,_=application_host
    panel,canvas=prepare_geometry(host)
    panel.open_settings_panel()
    engine=attach_wait(panel,'shape.recognition_changed',equals={'enabled':True})
    panel.btn_settings_smart.click()
    assert canvas.smart_shapes_enabled and engine.phase=='completed'
    engine=attach_wait(panel,'shape.recognition_changed')
    panel.set_smart_shapes(True)
    assert engine.phase=='running' and not engine._issued


@pytest.mark.parametrize('operation',['midpoint','perp_bisector'])
def test_actual_more_menu_action_builds_auxiliary_geometry(application_host,monkeypatch,operation):
    host,_=application_host
    panel,canvas=prepare_geometry(host)
    draw_shape(canvas,'LINE')
    source=canvas.shape_items[0]
    engine=attach_wait(panel,'shape.constructed',equals={'operation':operation,'source_type':'LINE'})
    label=dict(canvas.shape_op_list(source))[operation]
    def choose(menu,*args):next(action for action in menu.actions() if action.text()==label).trigger()
    monkeypatch.setattr(host.module.QMenu,'exec',choose)
    panel.open_more_menu()
    assert len(canvas.shape_items)>1 and source in canvas.shape_items
    assert engine.phase=='completed'


def test_more_menu_cancel_and_stale_action_do_not_complete(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_geometry(host)
    draw_shape(canvas,'LINE')
    engine=attach_wait(panel,'shape.constructed')
    monkeypatch.setattr(host.module.QMenu,'exec',lambda *args:None)
    panel.open_more_menu()
    assert len(canvas.shape_items)==1 and engine.phase=='running' and not engine._issued
    def stale(menu,*args):
        engine.pause();engine.resume();menu.actions()[0].trigger()
    monkeypatch.setattr(host.module.QMenu,'exec',stale)
    panel.open_more_menu()
    assert len(canvas.shape_items)>1 and engine.phase=='running' and not engine._issued


@pytest.mark.parametrize('kind,points',[
    ('ANGLE',((240,240),(100,240),(100,240))),
    ('TRAPEZOID',((100,340),(360,340),(320,160),(320,160))),
])
def test_overlapping_angle_arms_and_zero_top_trapezoid_do_not_complete(application_host,kind,points):
    host,_=application_host
    panel,canvas=prepare_geometry(host,kind)
    engine=attach_wait(panel,'shape.committed',equals={'type':kind,'count':1})
    for point in points:mouse(canvas,'press',point);mouse(canvas,'release',point)
    assert engine.phase=='running' and not engine._issued


def test_recognized_shape_still_waits_for_successful_mouse_release_tail(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized')
    draw_held_line(canvas)
    with monkeypatch.context() as patch:
        patch.setattr(panel,'heartbeat_refresh',Mock(side_effect=RuntimeError('release tail')))
        with pytest.raises(RuntimeError,match='release tail'):mouse(canvas,'release',(364,460))
    assert canvas.shape_items and engine.phase=='running' and not engine._issued


def draw_pointer_held_line(canvas,key):
    canvas._pointer_press(key,QPoint(100,460),1.0)
    for x in range(112,365,12):canvas._pointer_move(key,QPoint(x,460),1.0)
    with canvas._pointer_scope(key):
        canvas._hold_since=time.perf_counter()-0.7
        canvas._tick_smart_hold()


def test_other_pointer_release_cannot_claim_or_drop_recognition_owner(application_host):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized',equals={'type':'LINE','count':1})
    draw_pointer_held_line(canvas,11)
    canvas._pointer_press(22,QPoint(500,500),1.0)
    canvas._pointer_move(22,QPoint(540,530),1.0)
    canvas._pointer_release(22,QPoint(550,540))
    assert engine.phase=='running' and 11 in canvas._pointer_slots
    canvas._pointer_release(11,QPoint(364,460))
    assert engine.phase=='completed' and not engine._issued and not canvas._pointer_slots


def test_pointer_cleanup_failure_cannot_complete_recognition(application_host,monkeypatch):
    host,_=application_host
    panel,canvas=prepare_recognition(host)
    engine=attach_wait(panel,'shape.recognized')
    draw_pointer_held_line(canvas,11)
    with monkeypatch.context() as patch:
        patch.setattr(canvas,'_drop_pointer',Mock(side_effect=RuntimeError('pointer tail')))
        with pytest.raises(RuntimeError,match='pointer tail'):canvas._pointer_release(11,QPoint(364,460))
    assert canvas.shape_items and engine.phase=='running' and not engine._issued
    canvas._drop_pointer(11)


def test_point_release_after_pause_is_stale_and_retires_its_context(application_host):
    host,_=application_host
    panel,canvas=prepare_geometry(host,'TRIANGLE')
    engine=attach_wait(panel,'shape.point_added')
    mouse(canvas,'press',(120,160))
    engine.pause();engine.resume()
    mouse(canvas,'release',(120,160))
    assert len(canvas.pending_points)==1 and engine.phase=='running' and not engine._issued
