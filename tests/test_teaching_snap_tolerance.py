# SPDX-License-Identifier: GPL-3.0-or-later
"""Endpoint lessons judge real snap targets, not prescribed click coordinates."""
from dataclasses import replace
import inspect
import textwrap
import time

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from board_view import BoardView
from test_teaching_application_isolation import drain
from test_teaching_geometry_adapters import shape_button
from test_teaching_writing_courses import writing_host, assert_step

ANCHOR = '83ed9223-1658-5c07-ae30-c0b1f9058dce'


def click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    drain(QApplication.instance())


def point_input(canvas, kind, point):
    position = canvas.to_view(QPointF(*point)).toPoint()
    getattr(QTest, 'mouse' + kind)(canvas, Qt.MouseButton.LeftButton, pos=position)
    drain(QApplication.instance())


@pytest.fixture
def snap_host(writing_host, monkeypatch):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    assert QApplication.instance().platformName() == 'offscreen'
    click(host.presenter.controller.next_button)
    click(panel.btn_settings_smart)
    click(panel.pen_style_buttons['pen'])
    assert_step(host, 'recognize_line')
    point_input(canvas, 'Press', (100, 460))
    for x in range(112, 365, 12):
        QTest.mouseMove(canvas, canvas.to_view(QPointF(x, 460 + x % 3)).toPoint())
    canvas._hold_since = time.perf_counter() - 0.7
    canvas._tick_smart_hold()
    point_input(canvas, 'Release', (364, 460))
    assert_step(host, 'undo_recognition')
    click(panel.icon_buttons['undo'])
    click(panel.icon_buttons['redo'])
    click(host.presenter.controller.next_button)
    click(shape_button(panel, 'LINE'))
    assert_step(host, 'snap_line')
    assert host.presenter.barrier.installed and host.presenter.active_target_id == 'canvas.ink'
    records = []
    emit = host.presenter.events.emit_result

    def record(context, name, outcome, details):
        accepted = emit(context, name, outcome, details)
        if context is not None and name == 'shape.committed':
            records.append((dict(details), accepted))
        return accepted

    monkeypatch.setattr(host.presenter.events, 'emit_result', record)
    return host, records


def draw_line(host, start, end):
    canvas = host.panel.canvas
    for point in (start, end):
        point_input(canvas, 'Press', point)
        assert_step(host, 'snap_line')
        point_input(canvas, 'Release', point)


def snap_contract(snap_host, start=(330, 310), offset=(8, 7)):
    host, records = snap_host
    canvas = host.panel.canvas
    anchor = next(item for item in canvas.shape_items if str(item['id']) == ANCHOR)
    target = QPointF(anchor['points'][1])
    undo_depth, count = len(canvas.undo_stack), len(canvas.shape_items)
    end = (target.x() + offset[0], target.y() + offset[1])
    draw_line(host, start, end)
    assert len(canvas.shape_items) == count + 1 and len(canvas.undo_stack) == undo_depth + 1
    line = canvas.shape_items[-1]
    assert line['points'][1] == target
    assert host.presenter.engine.current_step_id == 'midpoint', 'A real anchor connection must advance'
    assert len(records) == 1 and records[0][1]
    details = records[0][0]
    assert details['snapped'] and details['snap_target_id'] == ANCHOR and details['snap_target_endpoint'] == 1
    assert canvas.selected_ids == {line['id']}
    point_input(canvas, 'Release', end)
    assert len(records) == 1 and host.presenter.engine.current_step_id == 'midpoint'
    assert canvas.undo() and len(canvas.shape_items) == count
    assert canvas.redo() and canvas.shape_items[-1]['points'][1] == target
    assert len(records) == 1


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
@pytest.mark.parametrize('start', [(239, 341), (330, 310), (450, 260)])
@pytest.mark.parametrize('offset', [(0, 0), (8, 7), (-10, -6)])
def test_first_endpoint_is_free_and_near_or_exact_anchor_hits_complete(snap_host, start, offset):
    snap_contract(snap_host, start, offset)


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
@pytest.mark.parametrize('camera', [BoardView(), BoardView(40, 20, 1.25)])
def test_anchor_identity_survives_relocation_and_camera_changes(snap_host, camera):
    host, _ = snap_host
    canvas = host.panel.canvas
    anchor = next(item for item in canvas.shape_items if str(item['id']) == ANCHOR)
    anchor['points'] = [point + QPointF(61.25, 30.5) for point in anchor['points']]
    canvas.mark_content_changed()
    canvas.board_view = camera
    snap_contract(snap_host)


def rejected_contract(snap_host, start, end):
    host, records = snap_host
    canvas = host.panel.canvas
    count = len(canvas.shape_items)
    draw_line(host, start, end)
    assert len(canvas.shape_items) == count + 1
    assert host.presenter.engine.current_step_id == 'snap_line', 'Wrong or absent snap must not advance'
    assert len(records) == 1 and not records[0][1]


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
@pytest.mark.parametrize('start,end', [((330, 310), (128, 157)), ((330, 310), (372, 467)),
                                      ((330, 310), (450, 230)), ((248, 157), (450, 230))],
                         ids=['left-anchor', 'different-line', 'ordinary-line', 'first-end-only'])
def test_other_endpoint_other_line_and_unsnapped_lines_do_not_complete(snap_host, start, end):
    rejected_contract(snap_host, start, end)


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
@pytest.mark.parametrize('boundary', ['cancel', 'epoch'])
def test_unfinished_or_stale_connection_does_not_advance(snap_host, boundary):
    host, records = snap_host
    canvas = host.panel.canvas
    point_input(canvas, 'Press', (330, 310))
    point_input(canvas, 'Release', (330, 310))
    if boundary == 'cancel':
        canvas.cancel_pending_points()
    point_input(canvas, 'Press', (248, 157))
    if boundary == 'epoch':
        host.presenter.engine.pause()
        host.presenter.engine.resume()
    point_input(canvas, 'Release', (248, 157))
    assert_step(host, 'snap_line')
    assert not any(accepted for _, accepted in records)


def change_condition(host, monkeypatch, equals):
    chapter = host.presenter.engine._chapter
    step = chapter.step_by_id('snap_line')
    clause = replace(step.wait.clauses[0], equals=equals)
    changed = replace(chapter, steps=tuple(replace(item, wait=replace(item.wait, clauses=(clause,)))
                                          if item.id == 'snap_line' else item for item in chapter.steps))
    monkeypatch.setattr(host.presenter.engine, '_chapter', changed)
    monkeypatch.setattr(host.presenter, '_chapter', changed)


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
def test_original_fixed_coordinates_fail_the_same_valid_connection(snap_host, monkeypatch):
    host, _ = snap_host
    change_condition(host, monkeypatch, {'type': 'LINE', 'count': 1, 'snapped': True,
                                        'start_x': 240, 'start_y': 340, 'end_x': 240, 'end_y': 150})
    with pytest.raises(AssertionError, match='A real anchor connection must advance'):
        snap_contract(snap_host)


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
def test_original_displacement_check_rejects_the_same_exact_hit(snap_host, monkeypatch):
    host, _ = snap_host
    source = textwrap.dedent(inspect.getsource(host.module.DrawingCanvas._finish_teaching_edit))
    old = 'details.update(snapped=True, snap_target_id=str(source["id"]),'
    assert source.count(old) == 1
    namespace = dict(vars(host.module))
    exec(compile(source.replace(old, 'details.update(snapped=last != before[3], snap_target_id=str(source["id"]),'),
                 '<old-displacement-snap-check>', 'exec'), namespace)
    monkeypatch.setattr(host.module.DrawingCanvas, '_finish_teaching_edit', namespace['_finish_teaching_edit'])
    with pytest.raises(AssertionError, match='A real anchor connection must advance'):
        snap_contract(snap_host, offset=(0, 0))


@pytest.mark.parametrize('writing_host', ['c06.recognition_snap'], indirect=True)
def test_removing_target_identity_fails_the_same_wrong_anchor_check(snap_host, monkeypatch):
    host, _ = snap_host
    change_condition(host, monkeypatch, {'type': 'LINE', 'count': 1, 'snapped': True})
    with pytest.raises(AssertionError, match='Wrong or absent snap must not advance'):
        rejected_contract(snap_host, (330, 310), (128, 157))


def test_snap_instruction_has_no_fixed_coordinate_requirement():
    from teaching.geometry_copy import GEOMETRY_COPY
    copy = GEOMETRY_COPY['teaching_c06_recognition_snap_snap_line_body']
    assert len(copy) == 8
    for text in copy:
        assert not any(point in text for point in ('240,340', '248,157', '240,150'))
