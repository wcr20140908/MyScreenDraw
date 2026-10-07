# SPDX-License-Identifier: GPL-3.0-or-later
import pytest


def test_inactive_bus_is_a_low_cost_noop():
    from teaching.events import TeachingEventBus
    bus = TeachingEventBus()
    assert bus.begin_operation('project.saved') is None
    assert not bus.emit_result(None, 'project.saved', 'success', {})


def test_preparation_does_not_manufacture_user_success():
    from teaching.engine import TutorialEngine
    from teaching.events import TeachingEventBus
    from test_teaching_engine import make_catalog
    engine = TutorialEngine(make_catalog(), session_id='session')
    engine.start('c01', 'c01.save')
    bus = TeachingEventBus(engine)
    with bus.suppress():
        assert bus.begin_operation('project.saved') is None
        with bus.suppress():
            assert bus.begin_operation('project.saved') is None
    context = bus.begin_operation('project.saved')
    with bus.suppress():
        assert not bus.emit_result(context, 'project.saved', 'success', {})
    assert engine.current_step_id == 'save'
    assert bus.emit_result(context, 'project.saved', 'success', {})
    assert engine.current_step_id == 'read'


def test_suppression_is_restored_after_exception():
    from teaching.engine import TutorialEngine
    from teaching.events import TeachingEventBus
    from test_teaching_engine import make_catalog
    engine = TutorialEngine(make_catalog(), session_id='session')
    engine.start('c01', 'c01.save')
    bus = TeachingEventBus(engine)
    with pytest.raises(RuntimeError):
        with bus.suppress():
            raise RuntimeError('synthetic preparation failed')
    assert bus.begin_operation('project.saved') is not None


def test_close_invalidates_existing_operation_context():
    from teaching.engine import TutorialEngine
    from teaching.events import TeachingEventBus
    from test_teaching_engine import make_catalog
    engine = TutorialEngine(make_catalog(), session_id='session')
    engine.start('c01', 'c01.save')
    bus = TeachingEventBus(engine)
    context = bus.begin_operation('project.saved')
    bus.close()
    assert bus.begin_operation('project.saved') is None
    assert not bus.emit_result(context, 'project.saved', 'success', {})
    assert engine.current_step_id == 'save'
