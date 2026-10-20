# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from teaching.models import OperationContext, TutorialEvent, WaitClause


@pytest.fixture
def context():
    return OperationContext('session', 'run', 1, 'operation')


@pytest.mark.parametrize('outcome', [[], {}, True, 'pending'])
def test_invalid_event_outcome_raises_validation_error(context, outcome):
    with pytest.raises(ValueError):
        TutorialEvent(context, 'ink.committed', outcome)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), pytest.param(10 ** 1000, id='oversized-int'), [], {'nested': 1}])
def test_event_details_are_bounded_json_scalars(context, value):
    with pytest.raises(ValueError):
        TutorialEvent(context, 'ink.committed', 'success', {'count': value})


def test_details_are_copied_and_immutable(context):
    details = {'count': 2}
    event = TutorialEvent(context, 'ink.committed', 'success', details)
    details['count'] = 9
    assert event.details['count'] == 2
    with pytest.raises(TypeError):
        event.details['count'] = 3


def test_boolean_cannot_satisfy_numeric_minimum(context):
    event = TutorialEvent(context, 'ink.committed', 'success', {'count': True})
    assert not WaitClause('ink.committed', 'success', min_count={'count': 1}).matches(event)


def test_boolean_is_not_equal_to_numeric_one(context):
    event = TutorialEvent(context, 'ink.committed', 'success', {'count': 1})
    assert not WaitClause('ink.committed', 'success', equals={'count': True}).matches(event)
