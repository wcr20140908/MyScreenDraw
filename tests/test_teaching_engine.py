# SPDX-License-Identifier: GPL-3.0-or-later
"""Only real, current-session terminal results can complete practice steps."""
from dataclasses import replace

import pytest

from teaching.models import (Branch, OperationContext, TutorialCatalog, TutorialChapter,
                             TutorialCourse, TutorialEvent, TutorialStep, WaitClause, WaitSpec)


def operation(step_id='save', event='project.saved', outcome='success', next='read', **kwargs):
    return TutorialStep(step_id, 'title', 'body', 'operation', 'file.save', 'target_only', (), (),
                        WaitSpec((WaitClause(event, outcome, **kwargs),)), next)


def information(step_id='read', next='end_chapter'):
    return TutorialStep(step_id, 'title', 'body', 'information', None, 'free', (), (), None, next)


def make_catalog(steps=None):
    chapter = TutorialChapter('c01.save', 'chapter', 'fixture', tuple(steps or [operation(), information()]))
    second = TutorialChapter('c01.other', 'chapter', 'fixture', (information(),))
    return TutorialCatalog((TutorialCourse('c01', 1, 1, 'course', (chapter, second)),))


@pytest.fixture
def engine():
    from teaching.engine import TutorialEngine
    value = TutorialEngine(make_catalog(), session_id='session')
    value.start('c01', 'c01.save')
    return value


def result(engine, name='project.saved', outcome='success', details=None, context=None):
    context = context or engine.begin_operation(name)
    assert context is not None
    return TutorialEvent(context, name, outcome, details or {})


def test_success_advances_but_information_needs_ack(engine):
    assert engine.current_step_id == 'save'
    assert engine.consume(result(engine))
    assert engine.current_step_id == 'read'
    assert engine.phase == 'running'
    assert engine.next()
    assert engine.phase == 'completed'


@pytest.mark.parametrize('outcome', ['cancelled', 'failed', 'partial'])
def test_non_success_does_not_complete_success_step(engine, outcome):
    assert not engine.consume(result(engine, outcome=outcome))
    assert engine.current_step_id == 'save'


def test_next_cannot_bypass_real_operation(engine):
    assert not engine.next()
    assert engine.current_step_id == 'save'


def test_wrong_event_does_not_receive_operation_context(engine):
    assert engine.begin_operation('button.clicked') is None


def test_duplicate_result_is_rejected(engine):
    event = result(engine)
    assert engine.consume(event)
    assert not engine.consume(event)


@pytest.mark.parametrize('field,value', [('session_id', 'other'), ('run_id', 'other'),
                                        ('step_epoch', 0), ('operation_id', 'unissued')])
def test_wrong_context_does_not_advance(engine, field, value):
    event = result(engine)
    event = replace(event, context=replace(event.context, **{field: value}))
    assert not engine.consume(event)
    assert engine.current_step_id == 'save'


def test_old_context_is_rejected_after_previous(engine):
    old = result(engine)
    assert engine.consume(old)
    assert engine.previous()
    assert engine.current_step_id == 'save'
    assert not engine.consume(old)
    assert engine.consume(result(engine))


def test_previous_at_first_step_is_noop(engine):
    assert not engine.previous()
    assert engine.current_step_id == 'save'


def test_pause_and_resume_invalidate_pending_results(engine):
    old = result(engine)
    engine.pause()
    assert engine.phase == 'paused'
    assert engine.begin_operation('project.saved') is None
    assert not engine.next()
    assert not engine.consume(old)
    engine.resume()
    assert engine.phase == 'running'
    assert not engine.consume(old)
    assert engine.consume(result(engine))


def test_restarting_has_new_run_id(engine):
    old = result(engine)
    engine.stop()
    engine.start('c01', 'c01.save')
    assert engine.run_id != old.context.run_id
    assert not engine.consume(old)


def test_cannot_start_two_courses(engine):
    with pytest.raises(RuntimeError, match='active'):
        engine.start('c01', 'c01.other')
    assert engine.current_step_id == 'save'


def test_invalid_chapter_start_does_not_damage_active_engine(engine):
    with pytest.raises((KeyError, RuntimeError)):
        engine.start('c01', 'missing')
    assert engine.current_step_id == 'save'


def test_explicit_cancel_operation_is_teachable():
    from teaching.engine import TutorialEngine
    value = TutorialEngine(make_catalog([operation(outcome='cancelled'), information()]), session_id='session')
    value.start('c01', 'c01.save')
    assert not value.consume(result(value, outcome='success'))
    assert value.consume(result(value, outcome='cancelled'))


def test_detail_predicates_cannot_be_satisfied_by_boolean():
    from teaching.engine import TutorialEngine
    value = TutorialEngine(make_catalog([operation(min_count={'pages': 2}), information()]), session_id='session')
    value.start('c01', 'c01.save')
    assert not value.consume(result(value, details={'pages': True}))
    assert not value.consume(result(value, details={'pages': 1}))
    assert value.consume(result(value, details={'pages': 2}))


def test_sequence_requires_order_and_fresh_operation_for_each_stage():
    from teaching.engine import TutorialEngine
    step = replace(operation(), wait=WaitSpec((
        WaitClause('tool.changed', 'success', equals={'drawing': False}),
        WaitClause('tool.changed', 'success', equals={'drawing': True}),
    )))
    value = TutorialEngine(make_catalog([step, information()]), session_id='session')
    value.start('c01', 'c01.save')
    too_early = result(value, 'tool.changed', details={'drawing': True})
    assert not value.consume(too_early)
    late_old = result(value, 'tool.changed', details={'drawing': True})
    assert value.consume(result(value, 'tool.changed', details={'drawing': False}))
    assert value.sequence_index == 1 and value.current_step_id == 'save'
    assert not value.consume(late_old)
    assert value.consume(result(value, 'tool.changed', details={'drawing': True}))
    assert value.current_step_id == 'read'


def test_branch_changes_applicable_path_not_fake_operations():
    from teaching.engine import TutorialEngine
    first = replace(operation(), branches=(Branch('touch_available', True, 'end_chapter'),))
    reports = []
    value = TutorialEngine(make_catalog([first, information()]), session_id='session',
                           condition_reader=lambda name, argument: True,
                           on_progress=lambda *args: reports.append(args))
    value.start('c01', 'c01.save')
    assert value.consume(result(value))
    assert value.phase == 'completed'
    assert reports[-1] == ('c01.save', 'completed', 1)


def test_stop_and_skip_never_report_completed():
    from teaching.engine import TutorialEngine
    for action in ('stop', 'skip_chapter'):
        reports = []
        value = TutorialEngine(make_catalog(), session_id='session', on_progress=lambda *args: reports.append(args))
        value.start('c01', 'c01.save')
        getattr(value, action)()
        assert all(report[1] != 'completed' for report in reports)
        assert reports[-1][1] == ('skipped' if action == 'skip_chapter' else 'in_progress')


def test_step_presentation_failure_leaves_engine_closed():
    from teaching.engine import TutorialEngine, TutorialEngineError
    def fail(step):
        if step is not None:
            raise RuntimeError('synthetic missing widget')
    value = TutorialEngine(make_catalog(), session_id='session', on_step=fail)
    with pytest.raises(TutorialEngineError):
        value.start('c01', 'c01.save')
    assert value.phase == 'error'
    assert value.begin_operation('project.saved') is None


def test_pending_operations_are_bounded(engine):
    from teaching.engine import MAX_PENDING_OPERATIONS
    contexts = [engine.begin_operation('project.saved') for _ in range(MAX_PENDING_OPERATIONS + 5)]
    assert sum(item is not None for item in contexts) == MAX_PENDING_OPERATIONS


def test_cleanup_runs_before_reporting_completion():
    from teaching.engine import TutorialEngine
    order = []
    value = TutorialEngine(make_catalog([information()]), session_id='session',
                           on_step=lambda step: order.append('clear' if step is None else 'show'),
                           on_progress=lambda chapter, status, revision: order.append(status))
    value.start('c01', 'c01.save')
    value.next()
    assert order.index('clear') < order.index('completed')


def test_programmatic_presentation_cannot_create_success_context():
    from teaching.engine import TutorialEngine
    created = []
    value = None
    def prepare(step):
        if step is not None and step.kind == 'operation':
            created.append(value.begin_operation('project.saved'))
    value = TutorialEngine(make_catalog(), session_id='session', on_step=prepare)
    value.start('c01', 'c01.save')
    assert created == [None]
    assert value.current_step_id == 'save'


def test_cleanup_is_not_an_active_operation_stage():
    from teaching.engine import TutorialEngine
    contexts = []
    value = None
    def prepare(step):
        if step is None:
            contexts.append(value.begin_operation('project.saved'))
    value = TutorialEngine(make_catalog([operation(next='end_chapter')]),
                           session_id='session', on_step=prepare)
    value.start('c01', 'c01.save')
    assert value.consume(result(value))
    assert contexts == [None]
    assert value.phase == 'completed'


def test_unrelated_result_does_not_destroy_legitimate_pending_result(engine):
    event = result(engine)
    unrelated = replace(event, name='other.result')
    assert not engine.consume(unrelated)
    assert engine.consume(event)


def test_condition_failure_does_not_report_completion():
    from teaching.engine import TutorialEngine, TutorialEngineError
    reports = []
    def fail(*args):
        raise RuntimeError('synthetic unavailable condition')
    step = replace(operation(), branches=(Branch('touch_available', True, 'end_chapter'),))
    value = TutorialEngine(make_catalog([step, information()]), session_id='session',
                           condition_reader=fail, on_progress=lambda *args: reports.append(args))
    value.start('c01', 'c01.save')
    with pytest.raises(TutorialEngineError):
        value.consume(result(value))
    assert value.phase == 'error'
    assert not any(item[1] == 'completed' for item in reports)


def test_failing_cleanup_does_not_report_completion():
    from teaching.engine import TutorialEngine, TutorialEngineError
    reports = []
    def fail(step):
        if step is None:
            raise RuntimeError('synthetic cleanup failed')
    value = TutorialEngine(make_catalog([information()]), session_id='session',
                           on_step=fail, on_progress=lambda *args: reports.append(args))
    value.start('c01', 'c01.save')
    with pytest.raises(TutorialEngineError):
        value.next()
    assert value.phase == 'error'
    assert not any(item[1] == 'completed' for item in reports)


def test_failed_durable_progress_is_not_a_failed_learning_operation():
    from teaching.engine import TutorialEngine
    value = TutorialEngine(make_catalog([information()]), session_id='session',
                           on_progress=lambda *args: False)
    value.start('c01', 'c01.save')
    assert value.next()
    assert value.phase == 'completed'


# Sequence presentation is a separate notification, not another user operation.
def test_sequence_notifies_new_stage_only_after_accepted_result():
    from teaching.engine import TutorialEngine
    stages = []
    step = replace(operation(next='end_chapter'), wait=WaitSpec((
        WaitClause('tool.changed', 'success', equals={'drawing': False}),
        WaitClause('tool.changed', 'success', equals={'drawing': True}),
    )))
    value = TutorialEngine(make_catalog([step]), session_id='session', on_sequence=stages.append)
    value.start('c01', 'c01.save')
    assert not value.consume(result(value, 'tool.changed', outcome='cancelled'))
    assert stages == []
    assert value.consume(result(value, 'tool.changed', details={'drawing': False}))
    assert stages == [1]
    assert value.consume(result(value, 'tool.changed', details={'drawing': True}))
    assert stages == [1] and value.phase == 'completed'


def test_sequence_presentation_cannot_issue_or_consume_user_operation():
    from teaching.engine import TutorialEngine
    observations = []
    step = replace(operation(next='end_chapter'), wait=WaitSpec((
        WaitClause('tool.changed', 'success'), WaitClause('project.saved', 'success'),
    )))
    value = None
    def changed(index):
        observations.append((index, value.begin_operation('project.saved')))
    value = TutorialEngine(make_catalog([step]), session_id='session', on_sequence=changed)
    value.start('c01', 'c01.save')
    assert value.consume(result(value, 'tool.changed'))
    assert observations == [(1, None)]
    assert value.begin_operation('project.saved') is not None


def test_sequence_presentation_failure_stops_without_completion():
    from teaching.engine import TutorialEngine, TutorialEngineError
    reports = []
    step = replace(operation(next='end_chapter'), wait=WaitSpec((
        WaitClause('tool.changed', 'success'), WaitClause('project.saved', 'success'),
    )))
    def fail(index):
        raise RuntimeError('synthetic stage layout failure')
    value = TutorialEngine(make_catalog([step]), session_id='session', on_sequence=fail,
                           on_progress=lambda *args: reports.append(args))
    value.start('c01', 'c01.save')
    with pytest.raises(TutorialEngineError):
        value.consume(result(value, 'tool.changed'))
    assert value.phase == 'error'
    assert value.begin_operation('project.saved') is None
    assert not any(item[1] == 'completed' for item in reports)


def test_previous_availability_is_read_only_navigation_state(engine):
    assert engine.can_previous is False
    assert engine.consume(result(engine))
    assert engine.can_previous is True
    engine.pause()
    assert engine.can_previous is True
    engine.resume()
    assert engine.previous()
    assert engine.can_previous is False



def test_progress_callback_stop_during_start_never_enters_first_step():
    from teaching.engine import TutorialEngine
    presentations = []
    value = None
    def progress(chapter, status, revision):
        if status == 'in_progress' and value.phase == 'running':
            value.stop()
    value = TutorialEngine(make_catalog(), session_id='session', on_progress=progress,
                           on_step=presentations.append)
    value.start('c01', 'c01.save')
    assert value.phase == 'stopped' and value.current_step_id is None
    assert presentations == [None]
