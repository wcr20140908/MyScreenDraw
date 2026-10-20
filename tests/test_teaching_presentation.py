# SPDX-License-Identifier: GPL-3.0-or-later
"""Engine and real Qt presentation work together offscreen, never on the desktop."""
from dataclasses import replace
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MYSCREENDRAW_NO_KEYBOARD', '1')

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMenu, QPushButton, QVBoxLayout, QWidget

from teaching.models import (END_CHAPTER, TutorialCatalog, TutorialChapter,
                             TutorialCourse, TutorialStep, WaitClause, WaitSpec)
from teaching.targets import TargetRegistry


def drain(app):
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def info(step_id='read', next=END_CHAPTER):
    return TutorialStep(step_id, 'title', 'body', 'information', None, 'free', (), (), None, next)


def operation(step_id='write', next='read', *, sequence=False):
    clauses = (WaitClause('tool.changed', 'success', equals={'tool': 'mode'}),
               WaitClause('tool.changed', 'success', equals={'tool': 'pen'})) if sequence else (
                   WaitClause('ink.committed', 'success', min_count={'segments': 1}),)
    return TutorialStep(step_id, 'title', 'body', 'operation', 'toolbar.mode', 'target_only', (),
                        ('toolbar.mode', 'toolbar.pen') if sequence else (), WaitSpec(clauses), next)


def catalog(steps):
    return TutorialCatalog((TutorialCourse('c01', 1, 1, 'course', (
        TutorialChapter('c01.intro', 'chapter', 'private_sample', tuple(steps)),
    )),))


@pytest.fixture
def scene(monkeypatch):
    import main
    def forbidden(*args, **kwargs):
        pytest.fail('Presentation tests must not construct the production UI or a keyboard hook')
    monkeypatch.setattr(main.ControlPanel, '__init__', forbidden)
    monkeypatch.setattr(main.keyboard, 'Listener', forbidden)
    app = QApplication.instance() or QApplication([])
    previous = set(app.topLevelWidgets())
    host = QWidget()
    layout = QVBoxLayout(host)
    buttons = {}
    for name in ('mode', 'pen', 'other'):
        button = QPushButton(name, host)
        layout.addWidget(button)
        buttons[name] = button
    host.setGeometry(-650, 70, 320, 220)
    host.show()
    registry = TargetRegistry()
    for name in ('mode', 'pen'):
        registry.register(f'toolbar.{name}', lambda name=name: buttons.get(name))
    presenters = []
    records = []
    fixtures = []
    prepared = []
    def build(steps=None, **kwargs):
        from teaching.presentation import TeachingPresenter
        def translate(key):
            return '{current}/{total}' if key == 'teaching_progress' else key
        value = TeachingPresenter(
            catalog(steps or [operation(), info()]), session_id='practice', registry=registry,
            owns=kwargs.pop('owns', lambda window: window is host or host.isAncestorOf(window)),
            canvas=kwargs.pop('canvas', lambda: host), translate=translate,
            prepare_fixture=kwargs.pop('prepare_fixture', fixtures.append),
            prepare_step=kwargs.pop('prepare_step', lambda fixture, step: prepared.append(step.id)),
            on_progress=lambda *args: records.append(args),
            available_geometry=kwargs.pop('available_geometry', lambda target: QRect(-1000, -200, 900, 700)),
            **kwargs)
        presenters.append(value)
        return value
    drain(app)
    yield app, host, buttons, registry, build, records, fixtures, prepared
    for value in presenters:
        value.close()
        value.deleteLater()
    registry.close()
    registry.deleteLater()
    for widget in app.topLevelWidgets():
        if widget not in previous and not sip.isdeleted(widget):
            widget.hide()
            widget.deleteLater()
    drain(app)


def completed_event(value, name='ink.committed', outcome='success', details=None):
    context = value.events.begin_operation(name)
    assert context is not None
    return value.events.emit_result(context, name, outcome, details or {'segments': 1})


def test_start_presents_real_target_and_prepares_private_fixture_once(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    value = build()
    value.start('c01', 'c01.intro')
    drain(app)
    assert fixtures == ['private_sample'] and prepared == ['write']
    assert value.controller.isVisible() and value.highlight.isVisible()
    assert value.highlight.geometry() == registry.global_rect('toolbar.mode')
    assert value.active_target_id == 'toolbar.mode'
    assert value.controller.progress_label.text() == '1/2'
    assert not value.controller.previous_button.isEnabled()
    assert not value.controller.next_button.isEnabled()
    assert value.barrier.installed
    assert records == [('c01.intro', 'in_progress', 1)]


def test_only_terminal_success_advances_and_information_requires_next(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    value = build()
    value.start('c01', 'c01.intro')
    assert not completed_event(value, outcome='cancelled')
    value.controller.next_button.click()
    assert value.engine.current_step_id == 'write'
    assert completed_event(value)
    assert value.engine.current_step_id == 'read'
    assert value.controller.previous_button.isEnabled()
    value.controller.next_button.click()
    assert value.engine.phase == 'completed'
    assert not value.controller.isVisible() and not value.highlight.isVisible()
    assert not value.barrier.installed
    assert records[-1] == ('c01.intro', 'completed', 1)


def test_sequence_retargets_and_only_current_stage_is_allowed(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build([operation(sequence=True), info()])
    value.start('c01', 'c01.intro')
    clicks = []
    for name, button in buttons.items():
        button.clicked.connect(lambda _, name=name: clicks.append(name))
    QTest.mouseClick(buttons['pen'], Qt.MouseButton.LeftButton)
    QTest.mouseClick(buttons['mode'], Qt.MouseButton.LeftButton)
    assert clicks == ['mode']
    assert completed_event(value, 'tool.changed', details={'tool': 'mode'})
    assert value.active_target_id == 'toolbar.pen'
    assert value.highlight.geometry() == registry.global_rect('toolbar.pen')
    QTest.mouseClick(buttons['mode'], Qt.MouseButton.LeftButton)
    QTest.mouseClick(buttons['pen'], Qt.MouseButton.LeftButton)
    assert clicks == ['mode', 'pen']
    assert completed_event(value, 'tool.changed', details={'tool': 'pen'})
    assert value.engine.current_step_id == 'read'


def test_fixture_and_programmatic_reveal_cannot_issue_learning_operations(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    observations = []
    value = None
    def prepare(fixture):
        observations.append(value.events.begin_operation('ink.committed'))
    def reveal():
        observations.append(value.events.begin_operation('ink.committed'))
    value = build([replace(operation(), reveal=('expand_toolbar',)), info()],
                  prepare_fixture=prepare, reveal_actions={'expand_toolbar': reveal})
    value.start('c01', 'c01.intro')
    assert observations == [None, None]
    assert value.engine.current_step_id == 'write'
    assert not any(item[1] == 'completed' for item in records)


def test_pause_releases_input_and_resume_preserves_private_work_and_rejects_old_result(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    value = build()
    value.start('c01', 'c01.intro')
    old = value.events.begin_operation('ink.committed')
    value.controller.pause_button.click()
    assert value.engine.phase == 'paused'
    assert not value.barrier.installed and not value.highlight.isVisible()
    assert value.controller.exit_button.isEnabled()
    value.controller.pause_button.click()
    assert value.engine.phase == 'running'
    assert fixtures == ['private_sample'] and prepared == ['write']
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    assert completed_event(value)


def test_previous_reprepares_step_without_changing_completion_state(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    value = build()
    value.start('c01', 'c01.intro')
    assert completed_event(value)
    value.controller.previous_button.click()
    assert value.engine.current_step_id == 'write'
    assert prepared == ['write', 'read', 'write']
    assert fixtures == ['private_sample']
    assert records == [('c01.intro', 'in_progress', 1)]


def test_missing_target_pauses_without_locking_and_retry_reacquires(scene):
    app, host, buttons, registry, build, records, *_ = scene
    buttons['mode'].hide()
    value = build(missing_timeout_ms=20)
    value.start('c01', 'c01.intro')
    assert value.engine.phase == 'paused'
    assert not value.barrier.installed and not value.highlight.isVisible()
    assert value.controller.retry_button.isEnabled() and value.controller.skip_button.isEnabled()
    assert value.controller.exit_button.isEnabled()
    QTest.qWait(35)
    buttons['mode'].show()
    drain(app)
    assert value.engine.phase == 'paused'
    value.controller.retry_button.click()
    drain(app)
    assert value.engine.phase == 'running'
    assert value.highlight.isVisible() and value.barrier.installed
    assert not any(item[1] == 'completed' for item in records)


def test_target_rebuild_inside_grace_resumes_and_rejects_old_operation(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build(missing_timeout_ms=200)
    value.start('c01', 'c01.intro')
    old = value.events.begin_operation('ink.committed')
    previous = buttons.pop('mode')
    previous.hide()
    previous.deleteLater()
    drain(app)
    assert value.engine.phase == 'paused'
    replacement = QPushButton('replacement', host)
    host.layout().addWidget(replacement)
    buttons['mode'] = replacement
    replacement.show()
    drain(app)
    assert value.engine.phase == 'running'
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    assert value.highlight.geometry() == registry.global_rect('toolbar.mode')


def test_skip_missing_target_never_counts_as_complete(scene):
    app, host, buttons, registry, build, records, *_ = scene
    buttons['mode'].hide()
    value = build(missing_timeout_ms=20)
    value.start('c01', 'c01.intro')
    value.controller.skip_button.click()
    QTest.qWait(35)
    drain(app)
    assert value.engine.phase == 'stopped'
    assert records[-1] == ('c01.intro', 'skipped', 1)
    assert not value.controller.isVisible() and not value.highlight.isVisible()
    assert not value.barrier.installed


def test_native_dialog_suspends_nested_barrier_and_keeps_real_result_context(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build()
    value.start('c01', 'c01.intro')
    context = value.events.begin_operation('ink.committed')
    with value.native_dialog():
        assert not value.barrier.installed and not value.controller.isVisible()
        with value.native_dialog():
            buttons['mode'].hide()
            drain(app)
            assert value.engine.phase == 'running'
        assert not value.barrier.installed
        assert value.events.emit_result(context, 'ink.committed', 'success', {'segments': 1})
        assert not value.controller.isVisible()
    assert value.engine.current_step_id == 'read'
    assert value.controller.isVisible()


def test_native_dialog_exception_restores_and_closing_inside_never_resurrects(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build()
    value.start('c01', 'c01.intro')
    with pytest.raises(ValueError):
        with value.native_dialog():
            raise ValueError('synthetic cancelled chooser')
    assert value.barrier.installed and value.controller.isVisible()
    with value.native_dialog():
        value.close()
    drain(app)
    assert not value.barrier.installed
    assert registry._on_change is None


def test_actual_target_popup_and_submenu_are_allowed_but_other_owned_controls_are_not(scene):
    app, host, buttons, registry, build, *_ = scene
    menu = QMenu(buttons['mode'])
    submenu = menu.addMenu('submenu')
    action = submenu.addAction('operation')
    buttons['mode'].setMenu(menu)
    value = build(owns=lambda window: window in (host, menu, submenu))
    value.start('c01', 'c01.intro')
    blocked = QEvent(QEvent.Type.ShortcutOverride)
    assert not value.barrier.eventFilter(action, blocked)
    assert value.barrier.eventFilter(buttons['other'], QEvent(QEvent.Type.ShortcutOverride))


def test_controller_stays_in_explicit_negative_coordinate_work_area(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build()
    value.start('c01', 'c01.intro')
    assert QRect(-1000, -200, 900, 700).contains(value.controller.geometry())
    host.move(-880, -100)
    drain(app)
    assert value.highlight.geometry() == registry.global_rect('toolbar.mode')
    assert QRect(-1000, -200, 900, 700).contains(value.controller.geometry())


def test_close_is_idempotent_releases_watches_and_managed_windows(scene):
    app, host, buttons, registry, build, records, *_ = scene
    managed, removed, exits = [], [], []
    value = build(manage_window=managed.append, unmanage_window=removed.append)
    value.exit_requested.connect(lambda: exits.append(True))
    value.start('c01', 'c01.intro')
    value.controller.exit_button.click()
    value.close()
    drain(app)
    assert value.engine.phase == 'stopped'
    assert not value.barrier.installed and registry._on_change is None
    assert len(managed) == 2 and removed == managed
    assert exits == [True]
    assert records[-1] == ('c01.intro', 'in_progress', 1)
    assert value.events.begin_operation('ink.committed') is None


def test_invalid_reveal_hook_fails_before_fixture_or_progress(scene):
    app, host, buttons, registry, build, records, fixtures, *_ = scene
    value = build([replace(operation(), reveal=('expand_toolbar',)), info()])
    with pytest.raises(ValueError, match='reveal'):
        value.start('c01', 'c01.intro')
    assert fixtures == records == []
    assert value.engine.phase == 'idle'


@pytest.mark.parametrize('timeout', [0, -1, 2001, True])
def test_missing_target_deadline_is_bounded_to_two_seconds(scene, timeout):
    *_, build, records, fixtures, prepared = scene
    with pytest.raises(ValueError):
        build(missing_timeout_ms=timeout)


def test_fixture_failure_does_not_show_ui_or_record_chapter(scene):
    app, host, buttons, registry, build, records, *_ = scene
    def fail(fixture):
        raise RuntimeError('synthetic fixture failure')
    value = build(prepare_fixture=fail)
    with pytest.raises(RuntimeError, match='fixture failure'):
        value.start('c01', 'c01.intro')
    assert value.engine.phase == 'idle' and records == []
    assert not value.controller.isVisible() and not value.barrier.installed


def test_disabling_current_target_pauses_and_reenabling_recovers(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build(missing_timeout_ms=200)
    value.start('c01', 'c01.intro')
    buttons['mode'].setEnabled(False)
    drain(app)
    assert value.engine.phase == 'paused' and not value.barrier.installed
    buttons['mode'].setEnabled(True)
    drain(app)
    assert value.engine.phase == 'running' and value.barrier.installed


def test_slot_presentation_exception_fails_closed_and_invalidates_pending_result(scene):
    app, host, buttons, registry, build, records, *_ = scene
    def area(target):
        return QRect(-1000, -200, 900, 700)
    value = build(available_geometry=area)
    failures = []
    value.failed.connect(failures.append)
    value.start('c01', 'c01.intro')
    old = value.events.begin_operation('ink.committed')
    value._available_geometry = lambda target: QRect()
    buttons['mode'].move(15, 12)
    drain(app)
    assert failures == ['presentation_failed']
    assert value.engine.phase in ('stopped', 'error')
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    assert not any(item[1] == 'completed' for item in records)
    assert not value.barrier.installed


def test_manual_pause_collapses_explanation_but_keeps_resume_and_exit(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build()
    value.start('c01', 'c01.intro')
    assert value.controller.body_label.isVisible()
    value.pause()
    assert value.controller.isVisible()
    assert not value.controller.body_label.isVisible()
    assert value.controller.pause_button.isEnabled() and value.controller.exit_button.isEnabled()
    value.resume()
    assert value.controller.body_label.isVisible()


def test_partial_topmost_registration_is_rolled_back_on_failure(scene):
    app, host, buttons, registry, build, records, fixtures, *_ = scene
    managed, removed = [], []
    def manage(window):
        if managed:
            raise RuntimeError('synthetic topmost registration failure')
        managed.append(window)
    value = build(manage_window=manage, unmanage_window=removed.append)
    with pytest.raises(RuntimeError, match='registration failure'):
        value.start('c01', 'c01.intro')
    assert removed == managed
    assert value.engine.phase == 'idle' and records == []
    assert not value.controller.isVisible() and not value.barrier.installed


def test_topmost_cleanup_exception_still_disposes_both_windows_and_barrier(scene):
    app, host, buttons, registry, build, *_ = scene
    removed, failures = [], []
    def remove(window):
        removed.append(window)
        raise RuntimeError('synthetic unregister failure')
    value = build(manage_window=lambda window: None, unmanage_window=remove)
    value.failed.connect(failures.append)
    value.start('c01', 'c01.intro')
    value.close()
    value.close()
    drain(app)
    assert len(removed) == 2 and failures == ['window_cleanup_failed']
    assert sip.isdeleted(value.controller) and sip.isdeleted(value.highlight)
    assert not value.barrier.installed and registry._on_change is None


def test_canvas_policy_allows_canvas_subtree_without_faking_ink_success(scene):
    app, host, buttons, registry, build, records, *_ = scene
    canvas_step = replace(operation(), target=None, input_policy='canvas')
    value = build([canvas_step, info()])
    value.start('c01', 'c01.intro')
    clicks = []
    buttons['other'].clicked.connect(lambda: clicks.append(True))
    QTest.mouseClick(buttons['other'], Qt.MouseButton.LeftButton)
    assert clicks == [True]
    assert value.engine.current_step_id == 'write'
    assert not any(item[1] == 'completed' for item in records)


def test_one_hundred_complete_replay_cycles_leave_no_active_watches_or_filter(scene):
    app, host, buttons, registry, build, records, fixtures, prepared = scene
    value = build()
    for _ in range(100):
        value.start('c01', 'c01.intro')
        assert completed_event(value)
        assert value.engine.next()
        drain(app)
        assert value.engine.phase == 'completed'
        assert not value.barrier.installed and registry._on_change is None
        assert not value.controller.isVisible() and not value.highlight.isVisible()
    assert len(fixtures) == 100
    assert len([item for item in records if item[1] == 'completed']) == 100


@pytest.mark.parametrize('hook', ['fixture', 'prepare_step', 'reveal_action', 'target_reveal', 'manage', 'geometry', 'canvas'])
def test_synchronous_close_from_host_hook_never_resurrects_engine_views_or_watches(scene, hook):
    app, host, buttons, registry, build, records, *_ = scene
    holder, managed, removed = {}, [], []
    def cancel(*args):
        holder['value'].close()
    options = {}
    steps = [operation(), info()]
    if hook == 'fixture':
        options['prepare_fixture'] = cancel
    elif hook == 'prepare_step':
        options['prepare_step'] = cancel
    elif hook == 'reveal_action':
        steps[0] = replace(steps[0], reveal=('expand_toolbar',))
        options['reveal_actions'] = {'expand_toolbar': cancel}
    elif hook == 'target_reveal':
        registry.register('cancel.target', lambda: buttons['mode'], reveal=cancel)
        steps[0] = replace(steps[0], target='cancel.target')
    elif hook == 'manage':
        def manage(window):
            managed.append(window)
            cancel()
        options.update(manage_window=manage, unmanage_window=removed.append)
    elif hook == 'geometry':
        def area(target):
            cancel()
            return QRect(-1000, -200, 900, 700)
        options['available_geometry'] = area
    else:
        def canvas():
            cancel()
            return host
        options['canvas'] = canvas
    value = build(steps, **options)
    holder['value'] = value
    value.start('c01', 'c01.intro')
    assert value._closed and value.engine.phase not in ('running', 'paused')
    assert registry._on_change is None and registry._timer is None and registry._watched == {}
    assert not value.barrier.installed
    assert value.events.begin_operation('ink.committed') is None
    assert not value.controller.isVisible() and not value.highlight.isVisible()
    assert not any(item[1] == 'completed' for item in records)
    assert managed == removed


def test_canvas_without_semantic_target_is_watched_and_releases_barrier_when_hidden(scene):
    app, host, buttons, registry, build, *_ = scene
    value = build([replace(operation(), target=None, input_policy='canvas'), info()], missing_timeout_ms=200)
    value.start('c01', 'c01.intro')
    old = value.events.begin_operation('ink.committed')
    drain(app)
    host.hide()
    drain(app)
    assert value.engine.phase == 'paused' and not value.barrier.installed
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    host.show()
    drain(app)
    assert value.engine.phase == 'running' and value.barrier.installed


def test_deferred_resolver_exception_stops_presentation_without_escaping_qt_slot(scene, monkeypatch):
    import sys
    app, host, buttons, registry, build, records, *_ = scene
    broken, uncaught, failures = [False], [], []
    def resolve():
        if broken[0]:
            raise ValueError('target mapping temporarily invalid')
        return buttons['mode']
    registry.register('volatile.target', resolve)
    value = build([replace(operation(), target='volatile.target'), info()])
    value.failed.connect(failures.append)
    value.start('c01', 'c01.intro')
    drain(app)
    old = value.events.begin_operation('ink.committed')
    monkeypatch.setattr(sys, 'excepthook', lambda *args: uncaught.append(args))
    broken[0] = True
    buttons['mode'].setEnabled(False)
    drain(app)
    assert uncaught == []
    assert failures == ['presentation_failed']
    assert value.engine.phase in ('stopped', 'error') and not value.barrier.installed
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    assert not any(item[1] == 'completed' for item in records)


def test_native_dialog_return_geometry_error_fails_closed_instead_of_hiding_live_run(scene):
    app, host, buttons, registry, build, records, *_ = scene
    value = build()
    failures = []
    value.failed.connect(failures.append)
    value.start('c01', 'c01.intro')
    old = value.events.begin_operation('ink.committed')
    with value.native_dialog():
        value._available_geometry = lambda target: QRect()
    assert failures == ['presentation_failed']
    assert value.engine.phase in ('stopped', 'error')
    assert not value.barrier.installed and not value.controller.isVisible()
    assert not value.events.emit_result(old, 'ink.committed', 'success', {'segments': 1})
    assert not any(item[1] == 'completed' for item in records)


def test_new_actual_submenus_are_allowed_dynamically_but_unrelated_owned_menu_is_blocked(scene):
    app, host, buttons, registry, build, *_ = scene
    menu = QMenu(buttons['mode'])
    existing = menu.addMenu('existing')
    unrelated = QMenu(host)
    buttons['mode'].setMenu(menu)
    owned = {host, menu, existing, unrelated}
    value = build(owns=lambda window: window in owned)
    value.start('c01', 'c01.intro')
    drain(app)
    added = menu.addMenu('added after activation')
    action = added.addAction('semantic action')
    owned.add(added)
    for receiver in (menu, existing, added, action):
        assert not value.barrier.eventFilter(receiver, QEvent(QEvent.Type.ShortcutOverride))
    assert value.barrier.eventFilter(unrelated, QEvent(QEvent.Type.ShortcutOverride))
    assert value.barrier.eventFilter(buttons['other'], QEvent(QEvent.Type.ShortcutOverride))


def test_skip_is_reachable_while_manually_paused_and_never_completes(scene):
    app, host, buttons, registry, build, records, *_ = scene
    value = build()
    value.start('c01', 'c01.intro')
    value.pause()
    assert value.controller.skip_button.isEnabled()
    value.controller.skip_button.click()
    assert value.engine.phase == 'stopped'
    assert records[-1] == ('c01.intro', 'skipped', 1)
    assert not value.barrier.installed
