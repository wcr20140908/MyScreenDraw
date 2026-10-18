# SPDX-License-Identifier: GPL-3.0-or-later
"""Private offscreen C05 roaming through the real chapter and input handlers."""
from copy import deepcopy

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication

from board_view import BoardView
from teaching.application import application_catalog
from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step, finished


def wheel(canvas, delta, point=(360, 280)):
    position = QPointF(*point)
    event = QWheelEvent(position, QPointF(canvas.mapToGlobal(position.toPoint())),
                        QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(canvas, event)


def pan(canvas, start=(360, 300), end=(450, 360)):
    mouse(canvas, 'press', start)
    mouse(canvas, 'move', end)
    mouse(canvas, 'release', end)


def enter_roam(host):
    next_info(host)
    host.panel.icon_buttons['mode'].click()
    assert_step(host, 'pan')


def content(canvas):
    import main
    page = main.serialize_page(canvas.live_page())
    page.pop('view', None)
    return deepcopy(page)


def test_roam_chapter_appends_ten_steps_without_invalidating_c05_progress():
    import main
    from teaching.pages_copy import PAGES_COPY
    catalog, _ = application_catalog(main, ROOT)
    course = catalog.course_by_id('c05')
    assert course.revision == 2 and course.compat_revision == 1
    assert course.chapters[-1].id == 'c05.roam'
    assert [step.id for step in course.chapters[-1].steps] == [
        'intro', 'enter_roam', 'pan', 'zoom_in', 'zoom_out', 'fit', 'home', 'pen', 'ink', 'done']
    assert sum(len(chapter.steps) for chapter in course.chapters) == 49
    assert len(PAGES_COPY) == 105


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_complete_roam_chapter_preserves_content_history_then_commits_new_ink(writing_host):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    assert canvas.whiteboard_mode and panel.infinite_whiteboard and canvas.is_drawing_mode
    assert canvas.draw_state == 'PEN' and canvas.pen_style == 'pen'
    assert canvas.board_view.to_data() == {'x': 0.0, 'y': 0.0, 'zoom': 1.0}
    assert len(canvas.pages) == 1
    before, history = content(canvas), (list(canvas.undo_stack), list(canvas.redo_stack))
    assert any(segment['line'].x1() < 0 for segment in canvas.all_segments)
    enter_roam(host)
    assert canvas.is_roaming and not canvas._mouse_passthrough
    pan(canvas)
    assert_step(host, 'zoom_in')
    anchor = canvas.to_document(QPointF(360, 280))
    wheel(canvas, 120)
    assert_step(host, 'zoom_out')
    assert canvas.to_document(QPointF(360, 280)) == anchor
    wheel(canvas, -120)
    assert_step(host, 'fit')
    QApplication.processEvents()
    for name in ('fit', 'home'):
        assert_step(host, name)
        target = host.registry.global_rect('settings.view_' + name)
        viewport = panel.settings_scroll.viewport()
        assert QRect(viewport.mapToGlobal(QPoint()), viewport.size()).contains(target)
        assert canvas.is_roaming
        getattr(panel, 'btn_view_' + name).click()
    assert_step(host, 'pen')
    assert not panel.settings_panel.isVisible() and canvas.is_roaming
    assert canvas.board_view.to_data() == {'x': 0.0, 'y': 0.0, 'zoom': 1.0}
    assert content(canvas) == before
    assert (canvas.undo_stack, canvas.redo_stack) == history
    panel.icon_buttons['pen'].click()
    assert_step(host, 'ink')
    assert canvas.is_drawing_mode and not canvas.is_roaming
    pan(canvas, (120, 460), (220, 470))
    assert_step(host, 'done')
    assert len(canvas.all_segments) > len(before['segments'])
    next_info(host)
    finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('fault', ['passthrough', 'finite_board', 'annotation'])
def test_enter_roam_requires_actual_infinite_board_not_mouse_mode(writing_host, monkeypatch, fault):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    with monkeypatch.context() as patch:
        if fault == 'finite_board':
            panel.infinite_whiteboard = False
        elif fault == 'annotation':
            canvas.whiteboard_mode = False
        else:
            original = panel.sync_canvas_input_mode
            def wrong_passthrough():
                original()
                canvas._mouse_passthrough = True
            patch.setattr(panel, 'sync_canvas_input_mode', wrong_passthrough)
        panel.icon_buttons['mode'].click()
        assert_step(host, 'enter_roam')
        assert canvas._mouse_passthrough
    panel.infinite_whiteboard = canvas.whiteboard_mode = True
    panel.set_drawing_mode(True)
    panel.icon_buttons['mode'].click()
    assert_step(host, 'pan')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('end', [(360, 300), (390, 300)])
def test_pan_requires_net_distance_and_waits_for_release(writing_host, end):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host)
    mouse(canvas, 'press', (360, 300))
    mouse(canvas, 'move', (470, 400))
    assert_step(host, 'pan')
    mouse(canvas, 'move', end)
    mouse(canvas, 'release', end)
    assert_step(host, 'pan')
    pan(canvas)
    assert_step(host, 'zoom_in')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('mutation', ['content', 'undo', 'redo'])
def test_pan_rejects_content_or_history_edits_even_with_valid_view_change(writing_host, mutation):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host)
    mouse(canvas, 'press', (360, 300))
    mouse(canvas, 'move', (460, 360))
    if mutation == 'content':
        canvas.all_segments[0]['line'].setP1(QPointF(141, 160))
    else:
        getattr(canvas, mutation + '_stack').append(canvas.capture_page())
    mouse(canvas, 'release', (460, 360))
    assert_step(host, 'pan')
    pan(canvas)
    assert_step(host, 'zoom_in')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('interrupt', ['pause', 'page', 'mode', 'cancel'])
def test_interrupted_pan_cannot_complete_on_late_release(writing_host, interrupt):
    from PyQt6.QtCore import QEvent
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host)
    mouse(canvas, 'press', (360, 300))
    mouse(canvas, 'move', (460, 360))
    if interrupt == 'pause':
        host.pause(); host.resume()
    elif interrupt == 'page':
        canvas.load_page(canvas.capture_page())
    elif interrupt == 'mode':
        host.panel.set_drawing_mode(True)
        host.panel.set_drawing_mode(False)
    else:
        QApplication.sendEvent(canvas, QEvent(QEvent.Type.TouchCancel))
    mouse(canvas, 'release', (460, 360))
    assert_step(host, 'pan')
    pan(canvas)
    assert_step(host, 'zoom_in')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_wheel_requires_actual_direction_and_preserves_the_cursor_anchor(writing_host):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host); pan(canvas)
    wheel(canvas, 0)
    assert_step(host, 'zoom_in')
    wheel(canvas, -120)
    assert_step(host, 'zoom_in')
    canvas.board_view.zoom_at(QPointF(360, 280), BoardView.MAX_ZOOM)
    wheel(canvas, 120)
    assert_step(host, 'zoom_in')
    wheel(canvas, -120)
    wheel(canvas, 120)
    assert_step(host, 'zoom_out')
    canvas.board_view.zoom_at(QPointF(360, 280), BoardView.MIN_ZOOM)
    wheel(canvas, -120)
    assert_step(host, 'zoom_out')
    wheel(canvas, 120)
    assert_step(host, 'zoom_out')
    wheel(canvas, -120)
    assert_step(host, 'fit')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_zoom_rejects_changed_view_with_wrong_anchor(writing_host, monkeypatch):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host); pan(canvas)
    original = BoardView.zoom_at
    def wrong_anchor(view, point, zoom):
        original(view, point, zoom)
        view.x += 2
    with monkeypatch.context() as patch:
        patch.setattr(BoardView, 'zoom_at', wrong_anchor)
        wheel(canvas, 120)
    assert_step(host, 'zoom_in')
    wheel(canvas, 120)
    assert_step(host, 'zoom_out')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('fault', ['noop', 'wrong_view', 'empty'])
def test_fit_needs_nonempty_content_and_the_computed_view(writing_host, monkeypatch, fault):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    enter_roam(host); pan(canvas); wheel(canvas, 120); wheel(canvas, -120)
    assert_step(host, 'fit')
    segments = list(canvas.all_segments)
    if fault == 'empty':
        canvas.all_segments.clear()
        panel.btn_view_fit.click()
    else:
        # Mutate only the business fit operation; keep the observer's expected
        # fit computation intact so a changed-but-wrong view cannot pass.
        original = canvas.board_view.fit
        def broken_fit(bounds, viewport):
            if fault == 'wrong_view':
                original(bounds, viewport)
                canvas.board_view.x += 1
        with monkeypatch.context() as patch:
            patch.setattr(canvas.board_view, 'fit', broken_fit)
            panel.btn_view_fit.click()
    assert_step(host, 'fit')
    canvas.all_segments = segments
    panel.btn_view_fit.click()
    assert_step(host, 'home')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_home_noop_and_reveal_never_supply_the_answer(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    enter_roam(host); pan(canvas); wheel(canvas, 120); wheel(canvas, -120)
    original = canvas.board_view.to_data()
    for name in ('settings.view_fit', 'settings.view_home'):
        host.registry.reveal(name)
        assert canvas.board_view.to_data() == original and canvas.is_roaming
    panel.btn_view_fit.click()
    assert_step(host, 'home')
    canvas.board_view = BoardView()
    panel.btn_view_home.click()
    assert_step(host, 'home')
    canvas.board_view.x = 80
    panel.btn_view_home.click()
    assert_step(host, 'pen')
    assert canvas.is_roaming and not panel.settings_panel.isVisible()


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_unmatched_steps_and_mouse_moves_take_no_content_snapshots(writing_host, monkeypatch):
    from unittest.mock import Mock
    from teaching import roam_actions
    host, _ = writing_host
    canvas = host.panel.canvas
    snapshot = Mock(wraps=roam_actions._content_snapshot)
    monkeypatch.setattr(roam_actions, '_content_snapshot', snapshot)
    # No matching board-view wait at intro, even if a real fit is requested.
    canvas.fit_board_view()
    assert snapshot.call_count == 0
    enter_roam(host)
    mouse(canvas, 'press', (360, 300))
    assert snapshot.call_count == 1
    for x in range(361, 461):
        mouse(canvas, 'move', (x, 300))
    assert snapshot.call_count == 1
    mouse(canvas, 'release', (460, 300))
    assert snapshot.call_count == 2
    assert_step(host, 'zoom_in')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('interrupt', ['pause', 'close', 'chapter_change'])
def test_host_interruption_retires_roam_token_and_gesture_immediately(writing_host, tmp_path, interrupt):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host)
    mouse(canvas, 'press', (360, 300))
    mouse(canvas, 'move', (460, 360))
    token = canvas._teaching_roam_action
    assert token is not None and not token.closed
    if interrupt == 'pause':
        host.pause()
    elif interrupt == 'close':
        host.close()
    else:
        from test_teaching_private_center import accepted_center
        accepted_center(host, tmp_path)
        host.prepare_chapter_change()
    assert token.closed
    assert canvas._teaching_roam_action is None and canvas._teaching_roam_anchor is None
    assert canvas._pan_point is None and not canvas._board_gesture.ids


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_touch_sequence_uses_one_entry_token_for_pan_and_sequential_two_finger_zoom(writing_host):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QEventPoint
    from test_infinite_whiteboard import touch
    host, _ = writing_host
    canvas = host.panel.canvas
    P, U, R = QEventPoint.State.Pressed, QEventPoint.State.Updated, QEventPoint.State.Released
    enter_roam(host)
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P)])
    token = canvas._teaching_roam_action
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (400, 350), U)])
    assert canvas._teaching_roam_action is token
    assert_step(host, 'pan')
    touch(canvas, QEvent.Type.TouchEnd, [(1, (400, 350), R)])
    assert_step(host, 'zoom_in')
    for expected, delta in [('zoom_out', 50), ('fit', -25)]:
        touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P)])
        token = canvas._teaching_roam_action
        touch(canvas, QEvent.Type.TouchUpdate, [(1, (300, 300), U), (2, (400, 300), P)])
        touch(canvas, QEvent.Type.TouchUpdate, [(1, (300-delta, 300), U), (2, (400+delta, 300), U)])
        assert canvas._teaching_roam_action is token and not token.closed
        # Lift one finger before the other, as a real pinch commonly ends.
        touch(canvas, QEvent.Type.TouchUpdate, [(1, (300-delta, 300), R), (2, (400+delta, 300), U)])
        assert canvas._teaching_roam_action is token and not token.closed
        touch(canvas, QEvent.Type.TouchEnd, [(2, (400+delta, 300), R)])
        assert token.closed and canvas._teaching_roam_action is None
        assert_step(host, expected)


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_third_touch_is_not_a_zoom_anchor_or_a_completion(writing_host):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QEventPoint
    from test_infinite_whiteboard import touch
    host, _ = writing_host
    canvas = host.panel.canvas
    P, U, R = QEventPoint.State.Pressed, QEventPoint.State.Updated, QEventPoint.State.Released
    enter_roam(host); pan(canvas)
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P), (2, (400, 300), P), (3, (700, 450), P)])
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (300, 300), U), (2, (400, 300), U), (3, (780, 480), U)])
    touch(canvas, QEvent.Type.TouchEnd, [(1, (300, 300), R), (2, (400, 300), R), (3, (780, 480), R)])
    assert_step(host, 'zoom_in')
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P), (2, (400, 300), P), (3, (700, 450), P)])
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (250, 300), U), (2, (450, 300), U), (3, (780, 480), U)])
    touch(canvas, QEvent.Type.TouchEnd, [(1, (250, 300), R), (2, (450, 300), R), (3, (780, 480), R)])
    assert_step(host, 'zoom_out')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
@pytest.mark.parametrize('interrupt', ['pause', 'cancel'])
def test_touch_never_creates_a_replacement_token_on_late_end(writing_host, interrupt):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QEventPoint
    from test_infinite_whiteboard import touch
    host, _ = writing_host
    canvas = host.panel.canvas
    P, U, R = QEventPoint.State.Pressed, QEventPoint.State.Updated, QEventPoint.State.Released
    enter_roam(host)
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P)])
    token = canvas._teaching_roam_action
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (400, 350), U)])
    if interrupt == 'pause':
        host.pause(); host.resume()
    else:
        QApplication.sendEvent(canvas, QEvent(QEvent.Type.TouchCancel))
    assert token.closed
    touch(canvas, QEvent.Type.TouchEnd, [(1, (500, 350), R)])
    assert_step(host, 'pan')
    assert canvas._teaching_roam_action is None


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_touch_anchor_failure_cannot_be_forgiven_by_contact_rebase(writing_host, monkeypatch):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QEventPoint
    from board_view import BoardGesture
    from test_infinite_whiteboard import touch
    host, _ = writing_host
    canvas = host.panel.canvas
    P, U, R = QEventPoint.State.Pressed, QEventPoint.State.Updated, QEventPoint.State.Released
    enter_roam(host); pan(canvas)
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P), (2, (400, 300), P)])
    token = canvas._teaching_roam_action
    original = BoardGesture.update
    def broken_update(gesture, view, points):
        result = original(gesture, view, points)
        if result:
            view.x += 2
        return result
    with monkeypatch.context() as patch:
        patch.setattr(BoardGesture, 'update', broken_update)
        touch(canvas, QEvent.Type.TouchUpdate, [(1, (250, 300), U), (2, (450, 300), U)])
    # Restore the correct endpoint, then rebase onto the remaining finger. The
    # earlier broken anchor must remain rejected even though the final view fits.
    canvas.board_view.x -= 2
    touch(canvas, QEvent.Type.TouchUpdate, [(1, (250, 300), R), (2, (450, 300), U)])
    touch(canvas, QEvent.Type.TouchEnd, [(2, (450, 300), R)])
    assert token.closed
    assert_step(host, 'zoom_in')
    touch(canvas, QEvent.Type.TouchBegin, [(1, (300, 300), P), (2, (400, 300), P)])
    touch(canvas, QEvent.Type.TouchEnd, [(1, (250, 300), R), (2, (450, 300), R)])
    assert_step(host, 'zoom_out')


@pytest.mark.parametrize('writing_host', ['c05.roam'], indirect=True)
def test_view_changed_exception_discards_entry_operation(writing_host, monkeypatch):
    host, _ = writing_host
    canvas = host.panel.canvas
    enter_roam(host); pan(canvas)
    def failed_tail():
        raise RuntimeError('synthetic navigation failure')
    with monkeypatch.context() as patch:
        patch.setattr(canvas, 'view_changed', failed_tail)
        # Direct Qt handler invocation keeps the synthetic exception in Python,
        # rather than throwing through Qt's event delivery trampoline.
        event = QWheelEvent(QPointF(360, 280), QPointF(360, 280), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        with pytest.raises(RuntimeError, match='synthetic navigation failure'):
            canvas.wheelEvent(event)
    assert_step(host, 'zoom_in')
    assert not host.presenter.engine._issued
    wheel(canvas, 120)
    assert_step(host, 'zoom_out')
