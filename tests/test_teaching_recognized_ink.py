# SPDX-License-Identifier: GPL-3.0-or-later
"""Real pen recognition must satisfy ink lessons without inventing user input."""
from contextlib import nullcontext
from dataclasses import replace
import math
import sys
import time
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from teaching.models import WaitClause, WaitSpec
from test_teaching_core_course import core_host, step


@pytest.fixture
def ink_host(core_host, monkeypatch):
    host, progress = core_host
    assert QApplication.instance().platformName() == 'offscreen'
    assert host.context.paths.practice
    QTest.mouseClick(host.presenter.controller.next_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(host.panel.icon_buttons['pen'], Qt.MouseButton.LeftButton)
    step(host, 'stroke')
    canvas = host.panel.canvas
    canvas.smart_shapes_enabled = True
    assert canvas.draw_state == 'PEN' and canvas.pen_style == 'pen'
    assert host.presenter.barrier.installed and host.presenter.active_target_id == 'canvas.ink'
    records = []
    emit = host.presenter.events.emit_result

    def record(context, name, outcome, details):
        accepted = emit(context, name, outcome, details)
        if context is not None and name == 'ink.committed':
            records.append((outcome, dict(details), accepted))
        return accepted

    monkeypatch.setattr(host.presenter.events, 'emit_result', record)
    yield host, records


def pen_points(kind):
    if kind == 'CIRCLE':
        return [QPoint(round(340 + 65 * math.cos(i * math.tau / 48)),
                       round(260 + 65 * math.sin(i * math.tau / 48))) for i in range(49)]
    return [QPoint(x, 260 if kind == 'LINE' else 240 + (x // 12 % 3) * 8)
            for x in range(220, 485, 12)]


def begin_pen(host, kind='LINE', pointer=None):
    canvas = host.panel.canvas
    points = pen_points(kind)
    if pointer is None:
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=points[0])
        for point in points[1:]:
            QTest.mouseMove(canvas, point)
    else:
        # Exercise the same isolated per-contact path used by Qt touch dispatch;
        # this is not OS touch injection and never touches the real screen.
        canvas._pointer_press(pointer, points[0], 1.0)
        for point in points[1:]:
            canvas._pointer_move(pointer, point, 1.0)
    scope = canvas._pointer_scope(pointer) if pointer is not None else nullcontext()
    with scope:
        raw_count = len(canvas.current_stroke_segments)
        assert raw_count > 0
        if kind != 'free':
            # Advance only elapsed dwell time, never mock recognition or its result.
            canvas._hold_since = time.perf_counter() - 1
            canvas._tick_smart_hold()
            assert canvas.current_stroke_id is None
            assert canvas.shape_items[-1]['type'] == kind
    return points[-1], raw_count


def release_pen(host, point, pointer=None):
    if pointer is None:
        QTest.mouseRelease(host.panel.canvas, Qt.MouseButton.LeftButton, pos=point)
    else:
        host.panel.canvas._pointer_release(pointer, point)


def require_two_strokes(host, monkeypatch, events=('ink.committed', 'ink.committed')):
    chapter = host.catalog.chapter_by_id('c01.interface')
    stroke = chapter.step_by_id('stroke')
    ink_clause = replace(stroke.wait.clauses[0], equals={'tool': 'PEN', 'style': 'pen'})
    clauses = tuple(ink_clause if name == 'ink.committed' else WaitClause(name, 'success')
                    for name in events)
    changed = replace(chapter, steps=tuple(
        replace(item, wait=WaitSpec(clauses)) if item.id == 'stroke' else item
        for item in chapter.steps))
    monkeypatch.setattr(host.presenter.engine, '_chapter', changed)
    monkeypatch.setattr(host.presenter, '_chapter', changed)


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
@pytest.mark.parametrize('kind', ['free', 'LINE', 'CIRCLE'])
def test_actual_pen_commits_once_whether_kept_as_ink_or_recognized(ink_host, kind, pointer):
    host, records = ink_host
    canvas = host.panel.canvas
    before = canvas.document_signature()
    point, raw_count = begin_pen(host, kind, pointer)
    step(host, 'stroke')
    assert not records  # A held or cancelled contact is not a completed gesture.
    release_pen(host, point, pointer)
    assert canvas.document_signature() != before and canvas.undo_stack
    assert canvas.smart_shapes_enabled
    if kind != 'free':
        assert not canvas.all_segments and [item['type'] for item in canvas.shape_items] == [kind]
    else:
        assert canvas.all_segments and not canvas.shape_items
    assert host.presenter.engine.current_step_id == 'mode', 'Committed pen stroke must finish the ink wait'
    step(host, 'mode')
    assert records == [('success', {'tool': 'PEN', 'style': 'pen', 'segments': raw_count}, True)]
    release_pen(host, point, pointer)
    assert len(records) == 1 and not host.presenter.engine._issued


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
def test_recognized_pen_cannot_replay_into_the_next_ink_wait(ink_host, monkeypatch, pointer):
    host, records = ink_host
    require_two_strokes(host, monkeypatch)
    point, _ = begin_pen(host, 'LINE', pointer)
    release_pen(host, point, pointer)
    step(host, 'stroke')
    assert host.presenter.engine.sequence_index == 1 and len(records) == 1
    release_pen(host, point, pointer)
    canvas = host.panel.canvas
    assert canvas.undo() and canvas.redo()
    release_pen(host, point, pointer)
    assert host.presenter.engine.sequence_index == 1 and len(records) == 1
    point, _ = begin_pen(host, 'CIRCLE', pointer)
    release_pen(host, point, pointer)
    step(host, 'mode')
    assert len(records) == 2 and all(record[2] for record in records)


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
def test_recognized_contact_can_continue_without_losing_or_double_counting_ink(ink_host, monkeypatch, pointer):
    host, records = ink_host
    require_two_strokes(host, monkeypatch)
    point, _ = begin_pen(host, 'LINE', pointer)
    for offset in (QPoint(0, 20), QPoint(30, 40)):
        point = point + offset
        if pointer is None:
            QTest.mouseMove(host.panel.canvas, point)
        else:
            host.panel.canvas._pointer_move(pointer, point, 1.0)
    assert not records
    release_pen(host, point, pointer)
    assert host.panel.canvas.shape_items and host.panel.canvas.all_segments
    assert host.presenter.engine.sequence_index == 1 and len(records) == 1


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
@pytest.mark.parametrize('kind', ['free', 'LINE'])
def test_cancelled_contact_does_not_complete_even_if_ink_or_shape_remains(ink_host, kind, pointer):
    host, records = ink_host
    point, _ = begin_pen(host, kind, pointer)
    QApplication.sendEvent(host.panel.canvas, QEvent(QEvent.Type.TouchCancel))
    release_pen(host, point, pointer)
    step(host, 'stroke')
    assert not records and not host.presenter.engine._issued
    assert host.panel.canvas.all_segments or host.panel.canvas.shape_items


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
@pytest.mark.parametrize('invalidate', ['undo', 'fixture', 'pause'])
def test_recognition_lost_or_stale_before_release_cannot_complete(ink_host, pointer, invalidate):
    host, records = ink_host
    point, _ = begin_pen(host, 'LINE', pointer)
    if invalidate == 'undo':
        assert host.panel.canvas.undo()
        assert not host.panel.canvas.shape_items
    elif invalidate == 'fixture':
        assert host.panel.load_teaching_fixture(str(host.request.paths.data_dir / 'fixtures/core.interface.msd'))
    else:
        host.presenter.pause()
        host.presenter.resume()
    release_pen(host, point, pointer)
    step(host, 'stroke')
    assert not any(record[2] for record in records) and not host.presenter.engine._issued


def test_manual_shape_and_fixture_content_are_not_a_user_pen_stroke(ink_host):
    host, records = ink_host
    canvas, panel = host.panel.canvas, host.panel
    with host.presenter.events.suppress():
        panel.set_tool('SHAPE', panel.btn_shape)
        canvas.shape_type = 'LINE'
    for point in (QPoint(220, 180), QPoint(480, 180)):
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=point)
    assert canvas.shape_items and not canvas.all_segments
    assert canvas.undo() and canvas.redo()
    # A programmatic shape insertion has no pen-entry context either.
    canvas.add_shape_item(canvas.build_recognized_item(
        {'type': 'LINE', 'points': [(220, 120), (480, 120)]}), select=False)
    step(host, 'stroke')
    assert not records and not host.presenter.engine._issued
    assert panel.load_teaching_fixture(str(host.request.paths.data_dir / 'fixtures/core.interface.msd'))
    step(host, 'stroke')
    assert not records
    with host.presenter.events.suppress():
        panel.set_tool('PEN', panel.btn_pen)
    point, _ = begin_pen(host, 'LINE')
    release_pen(host, point)
    step(host, 'mode')
    assert len(records) == 1 and records[0][2]


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
def test_recognized_ink_waits_for_successful_release_cleanup(ink_host, monkeypatch, pointer):
    host, records = ink_host
    point, _ = begin_pen(host, 'LINE', pointer)
    with monkeypatch.context() as patch:
        if pointer is None:
            errors = []
            patch.setattr(sys, 'excepthook', lambda kind, error, tb: errors.append(error))
            patch.setattr(host.panel, 'heartbeat_refresh', Mock(side_effect=RuntimeError('release tail')))
            release_pen(host, point)
            assert len(errors) == 1 and str(errors[0]) == 'release tail'
        else:
            patch.setattr(host.panel.canvas, '_drop_pointer', Mock(side_effect=RuntimeError('pointer tail')))
            with pytest.raises(RuntimeError, match='pointer tail'):
                release_pen(host, point, pointer)
    step(host, 'stroke')
    assert host.panel.canvas.shape_items and not records and not host.presenter.engine._issued
    if pointer is not None:
        host.panel.canvas._drop_pointer(pointer)


def test_other_pointer_release_does_not_claim_recognized_ink(ink_host):
    host, records = ink_host
    point, _ = begin_pen(host, 'LINE', 11)
    canvas = host.panel.canvas
    canvas._pointer_press(22, QPoint(530, 400), 1.0)
    canvas._pointer_release(22, QPoint(530, 400))  # Empty second contact.
    step(host, 'stroke')
    assert not records and 11 in canvas._pointer_slots
    release_pen(host, point, 11)
    step(host, 'mode')
    assert len(records) == 1 and not canvas._pointer_slots


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
@pytest.mark.parametrize('events', [
    ('ink.committed', 'shape.recognized'), ('shape.recognized', 'ink.committed'),
])
def test_one_recognized_stroke_cannot_supply_both_ink_and_next_shape_wait(ink_host, monkeypatch, pointer, events):
    host, records = ink_host
    require_two_strokes(host, monkeypatch, events)
    point, _ = begin_pen(host, 'LINE', pointer)
    release_pen(host, point, pointer)
    step(host, 'stroke')
    assert host.presenter.engine.sequence_index == 1
    release_pen(host, point, pointer)
    assert host.presenter.engine.sequence_index == 1
    point, _ = begin_pen(host, 'CIRCLE', pointer)
    release_pen(host, point, pointer)
    step(host, 'mode')
    assert len(records) == 1 and records[0][2]


@pytest.mark.parametrize('pointer', [None, 11], ids=['qt-mouse', 'pointer'])
def test_old_missing_recognized_ink_result_fails_the_same_user_input_regression(ink_host, monkeypatch, pointer):
    host, records = ink_host
    finish = host.panel.canvas._finish_teaching_recognition
    # Exact behavioral mutation: omit only the ink result of the recognized
    # stroke, as before the fix, preserving drawing, recognition and the barrier.
    monkeypatch.setattr(host.panel.canvas, '_finish_teaching_recognition',
                        lambda result: finish((result[0], result[1], None)))
    with pytest.raises(AssertionError, match='Committed pen stroke must finish the ink wait'):
        test_actual_pen_commits_once_whether_kept_as_ink_or_recognized(ink_host, 'LINE', pointer)
    step(host, 'stroke')
    assert not records and not host.presenter.engine._issued
