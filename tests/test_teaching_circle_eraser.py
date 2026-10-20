# SPDX-License-Identifier: GPL-3.0-or-later
"""C03 circular erasing through real Qt input and the formal input barrier."""
from collections import Counter
from dataclasses import replace

import pytest
from PyQt6.QtCore import QLineF, QPoint, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from test_teaching_writing_courses import assert_step, writing_host

UPPER = 'dadb8e81cea976ac79e5d213276df443'
LOWER = '72c2ee1f9618e1eae59dcb7eb9931a99'
UPPER_PATH = [(120, 120), (220, 180), (320, 120), (420, 180)]


@pytest.fixture
def circle_host(writing_host, monkeypatch):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    assert QApplication.instance().platformName() == 'offscreen'
    assert host.context.paths.practice
    QTest.mouseClick(host.presenter.controller.next_button, Qt.MouseButton.LeftButton)
    assert_step(host, 'eraser')
    QTest.mouseClick(panel.icon_buttons['eraser'], Qt.MouseButton.LeftButton)
    assert_step(host, 'circle')
    assert canvas.eraser_type == 'STROKE'
    QTest.mouseClick(panel.btn_circ, Qt.MouseButton.LeftButton)
    assert_step(host, 'size')
    assert canvas.eraser_type == 'CIRCLE' and canvas.eraser_size == 40
    for _ in range(20):
        QTest.keyClick(panel.e_slider, Qt.Key.Key_Right)
    assert_step(host, 'circle_erase')
    assert canvas.draw_state == 'ERASER' and canvas.eraser_size == 60
    assert host.presenter.barrier.installed and host.presenter.active_target_id == 'canvas.ink'
    # The drawing step must not allow a stray tool/mode/size click.
    QTest.mouseClick(panel.btn_stroke, Qt.MouseButton.LeftButton)
    QTest.mouseClick(panel.icon_buttons['pen'], Qt.MouseButton.LeftButton)
    QTest.keyClick(panel.e_slider, Qt.Key.Key_Right)
    assert canvas.draw_state == 'ERASER' and canvas.eraser_type == 'CIRCLE' and canvas.eraser_size == 60
    records = []
    emit = host.presenter.events.emit_result

    def record(context, name, outcome, details):
        accepted = emit(context, name, outcome, details)
        if context is not None and name == 'ink.erased':
            records.append((dict(details), accepted))
        return accepted

    monkeypatch.setattr(host.presenter.events, 'emit_result', record)
    return host, progress, records


def count_samples(canvas):
    return Counter(segment['id'].hex for segment in canvas.all_segments)


def sample_geometry(canvas, sample):
    return [(segment['line'], segment['pen']) for segment in canvas.all_segments
            if segment['id'].hex == sample]


def ink_frame(canvas):
    image = QImage(600, 500, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        canvas.draw_segments(painter, canvas.all_segments)
    finally:
        painter.end()
    return image


def drag(host, points):
    canvas = host.panel.canvas
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(*points[0]))
    for point in points[1:]:
        QTest.mouseMove(canvas, QPoint(*point))
    assert_step(host, 'circle_erase')  # Only release may satisfy the lesson.
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(*points[-1]))


def assert_local_circle_and_following_stroke(circle_host):
    host, progress, records = circle_host
    canvas = host.panel.canvas
    before = ink_frame(canvas)
    lower = sample_geometry(canvas, LOWER)
    counts = count_samples(canvas)
    drag(host, [(170, 150), (174, 152)])
    after = ink_frame(canvas)
    assert after.pixelColor(120, 120) == before.pixelColor(120, 120) != QColor('white'), \
        'Circular erase must preserve distant ink on the same sample segment'
    assert after.pixelColor(170, 150) == QColor('white') != before.pixelColor(170, 150)
    assert after != before and canvas.undo_stack
    assert 0 < count_samples(canvas)[UPPER] < counts[UPPER]
    assert sample_geometry(canvas, LOWER) == lower
    assert_step(host, 'stroke_mode')
    assert records == [({'removed_segments': counts[UPPER] - count_samples(canvas)[UPPER],
                        'removed_objects': 0, 'eraser_type': 'CIRCLE', 'eraser_size': 60,
                        'stroke_id': 'dadb8e81-cea9-76ac-79e5-d213276df443',
                        'remaining_segments': count_samples(canvas)[UPPER]}, True)]
    assert host.presenter.active_target_id == 'eraser.type.stroke'
    assert canvas.undo() and ink_frame(canvas) == before
    assert canvas.redo() and ink_frame(canvas) == after
    assert_step(host, 'stroke_mode')
    assert len(records) == 1  # History replay is not another eraser gesture.
    QTest.mouseClick(host.panel.btn_stroke, Qt.MouseButton.LeftButton)
    assert_step(host, 'stroke_erase')
    upper = sample_geometry(canvas, UPPER)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(170, 390))
    assert_step(host, 'stroke_erase')
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(170, 390))
    assert_step(host, 'done')
    assert not count_samples(canvas)[LOWER] and sample_geometry(canvas, UPPER) == upper
    assert len(records) == 2 and all(accepted for _, accepted in records)
    QTest.mouseClick(host.presenter.controller.next_button, Qt.MouseButton.LeftButton)
    assert host.presenter.engine.phase == 'completed' and not host.presenter.barrier.installed
    assert progress[-1] == ('c03.erase', 'completed', 1)


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_real_circle_is_local_and_next_mode_removes_only_lower_stroke(circle_host):
    assert_local_circle_and_following_stroke(circle_host)


def assert_entire_upper_is_allowed(circle_host):
    host, _, records = circle_host
    lower = sample_geometry(host.panel.canvas, LOWER)
    drag(host, UPPER_PATH)
    assert not count_samples(host.panel.canvas)[UPPER]
    assert sample_geometry(host.panel.canvas, LOWER) == lower
    assert host.presenter.engine.current_step_id == 'stroke_mode', \
        'Erasing the upper sample must not get stuck on an invisible remainder condition'
    assert len(records) == 1 and records[0][1] and records[0][0]['remaining_segments'] == 0
    QTest.mouseRelease(host.panel.canvas, Qt.MouseButton.LeftButton, pos=QPoint(*UPPER_PATH[-1]))
    assert len(records) == 1 and not host.presenter.engine._issued


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_erasing_all_upper_ink_with_circle_60_also_meets_visible_instruction(circle_host):
    assert_entire_upper_is_allowed(circle_host)


def assert_invalid_erase_rejected(circle_host, invalid):
    host, _, records = circle_host
    panel, canvas = host.panel, host.panel.canvas
    before = canvas.document_signature()
    # Invalid states are installed without teaching events; the actual deletion
    # still goes through Qt input. Normal UI attempts were blocked in the fixture.
    with host.presenter.events.suppress():
        if invalid == 'mode':
            panel.set_eraser_type('STROKE')
        elif invalid == 'size':
            panel.e_slider.setValue(40)
    points = {'blank': [(520, 220), (560, 220)],
              'lower': [(170, 390), (174, 392)],
              'both': [(170, 150), (170, 390)]}.get(invalid, [(170, 150), (174, 152)])
    drag(host, points)
    assert (canvas.document_signature() == before) == (invalid == 'blank')
    assert host.presenter.engine.current_step_id == 'circle_erase', \
        'Invalid erasing must not satisfy the upper CIRCLE/60 condition'
    assert not any(accepted for _, accepted in records) and not host.presenter.engine._issued
    if invalid == 'blank':
        assert not records
    else:
        assert len(records) == 1
        details = records[0][0]
        if invalid == 'both':
            assert details['stroke_id'] is None
        if invalid == 'size':
            assert details['eraser_size'] == 40


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
@pytest.mark.parametrize('invalid', ['blank', 'mode', 'size', 'lower', 'both'])
def test_empty_wrong_mode_wrong_size_and_lower_damage_do_not_complete(circle_host, invalid):
    assert_invalid_erase_rejected(circle_host, invalid)


def change_circle_condition(host, monkeypatch, *, require_remainder=False, omit=None):
    chapter = host.presenter.engine._chapter
    step = chapter.step_by_id('circle_erase')
    clause = step.wait.clauses[0]
    minimum = dict(clause.min_count)
    equals = dict(clause.equals)
    if require_remainder:
        minimum['remaining_segments'] = 1
    if omit:
        equals.pop(omit)
    changed = replace(chapter, steps=tuple(
        replace(item, wait=replace(item.wait, clauses=(replace(clause, min_count=minimum, equals=equals),)))
        if item.id == 'circle_erase' else item for item in chapter.steps))
    monkeypatch.setattr(host.presenter.engine, '_chapter', changed)
    monkeypatch.setattr(host.presenter, '_chapter', changed)


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_old_coarse_fixture_fails_the_same_local_circle_oracle(circle_host):
    host, _, _ = circle_host
    canvas = host.panel.canvas
    original = canvas.all_segments
    canvas.all_segments = []
    for sample, offset in ((UPPER, 0), (LOWER, 240)):
        template = next(segment for segment in original if segment['id'].hex == sample)
        for start, end in zip(UPPER_PATH, UPPER_PATH[1:]):
            canvas.all_segments.append(dict(template, line=QLineF(
                start[0], start[1] + offset, end[0], end[1] + offset)))
    canvas.mark_content_changed()
    with pytest.raises(AssertionError, match='Circular erase must preserve distant ink'):
        assert_local_circle_and_following_stroke(circle_host)


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_old_hidden_remainder_condition_fails_the_same_full_erase_oracle(circle_host, monkeypatch):
    host, _, _ = circle_host
    change_circle_condition(host, monkeypatch, require_remainder=True)
    with pytest.raises(AssertionError, match='invisible remainder condition'):
        assert_entire_upper_is_allowed(circle_host)
    assert_step(host, 'circle_erase')


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
@pytest.mark.parametrize('invalid,omit', [('mode', 'eraser_type'), ('size', 'eraser_size'),
                                         ('lower', 'stroke_id'), ('both', 'stroke_id')])
def test_dropped_conditions_are_rejected_by_the_same_negative_oracle(circle_host, monkeypatch, invalid, omit):
    host, _, _ = circle_host
    change_circle_condition(host, monkeypatch, omit=omit)
    with pytest.raises(AssertionError, match='Invalid erasing must not satisfy'):
        assert_invalid_erase_rejected(circle_host, invalid)
