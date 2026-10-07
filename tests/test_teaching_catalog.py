# SPDX-License-Identifier: GPL-3.0-or-later
"""Teaching content is validated before it can affect any UI or file operation."""
import copy
import json

import pytest


@pytest.fixture
def course_json():
    return {
        'schema_version': 1, 'id': 'c01', 'revision': 1, 'compat_revision': 1,
        'title_key': 'course',
        'chapters': [{
            'id': 'c01.save', 'title_key': 'chapter', 'fixture': 'project_basic',
            'steps': [
                {'id': 'save', 'title_key': 'title', 'body_key': 'body',
                 'target': 'file.save', 'input_policy': 'target_only',
                 'reveal': ['open_file_panel'],
                 'wait': {'event': 'project.saved', 'outcome': 'success'}, 'next': 'read'},
                {'id': 'read', 'title_key': 'title', 'body_key': 'body',
                 'kind': 'information', 'next': 'end_chapter'},
            ]
        }]
    }


@pytest.fixture
def loader(tmp_path):
    from teaching.catalog import CatalogLoader
    fixtures = tmp_path / 'fixtures'
    fixtures.mkdir()
    (fixtures / 'basic.msd').write_bytes(b'synthetic placeholder for path validation')
    return CatalogLoader(
        tmp_path, string_keys={'course', 'chapter', 'title', 'body', 'group'},
        target_ids={'file.save', 'canvas.ink', 'toolbar.pen', 'toolbar.mode'},
        event_names={'project.saved', 'ink.committed', 'tool.changed'},
        fixtures={'project_basic': 'fixtures/basic.msd'},
    )


def test_course_is_immutable_and_has_resolved_next(loader, course_json):
    from dataclasses import FrozenInstanceError
    course = loader.validate(course_json)
    assert course.id == 'c01'
    assert len(course.chapters[0].steps) == 2
    assert course.chapters[0].steps[0].wait.clauses[0].event == 'project.saved'
    with pytest.raises(FrozenInstanceError):
        course.id = 'replaced'


@pytest.mark.parametrize('field,value', [
    ('schema_version', 2), ('schema_version', True), ('id', '../c01'),
    ('revision', 0), ('revision', True), ('compat_revision', -1),
    ('title_key', 'missing'), ('script', 'shell.execute()'), ('chapters', []),
])
def test_invalid_course_header_is_rejected(loader, course_json, field, value):
    course_json[field] = value
    with pytest.raises(ValueError):
        loader.validate(course_json)


@pytest.mark.parametrize('field,value', [
    ('id', 'other.save'), ('fixture', 'missing_fixture'), ('script', 'eval(1)'),
    ('title_key', 'missing'), ('steps', []),
])
def test_invalid_chapter_is_rejected(loader, course_json, field, value):
    course_json['chapters'][0][field] = value
    with pytest.raises(ValueError):
        loader.validate(course_json)


@pytest.mark.parametrize('field,value', [
    ('id', 'end_chapter'), ('target', 'hidden.legacy'), ('title_key', 'missing'),
    ('next', 'missing'), ('kind', 'shell'), ('input_policy', 'desktop_block'),
    ('reveal', ['run_command']), ('init_script', 'dangerous()'),
    ('allowed_targets', ['unregistered']), ('wait', None),
])
def test_invalid_step_is_rejected(loader, course_json, field, value):
    course_json['chapters'][0]['steps'][0][field] = value
    with pytest.raises(ValueError):
        loader.validate(course_json)


@pytest.mark.parametrize('wait', [
    {'event': 'button.clicked', 'outcome': 'success'},
    {'event': 'project.saved', 'outcome': 'pending'},
    {'event': 'project.saved', 'outcome': 'success', 'min_count': {'pages': True}},
    {'event': 'project.saved', 'outcome': 'success', 'equals': {'x': float('nan')}},
    {'event': 'project.saved', 'outcome': 'success', 'equals': {'x': {'eval': 'x'}}},
    {'event': 'project.saved', 'outcome': 'success', 'predicate': 'eval(1)'},
    {'sequence': []},
    {'sequence': [{'event': 'project.saved', 'outcome': 'success'}], 'event': 'ink.committed'},
])
def test_invalid_wait_is_rejected(loader, course_json, wait):
    course_json['chapters'][0]['steps'][0]['wait'] = wait
    with pytest.raises(ValueError):
        loader.validate(course_json)


def test_sequence_wait_and_branch_are_supported(loader, course_json):
    step = course_json['chapters'][0]['steps'][0]
    step['allowed_targets'] = ['toolbar.mode', 'toolbar.pen']
    step['wait'] = {'sequence': [
        {'event': 'tool.changed', 'outcome': 'success', 'equals': {'drawing': False}},
        {'event': 'tool.changed', 'outcome': 'success', 'equals': {'drawing': True}},
    ]}
    step['branches'] = [{'condition': 'touch_available', 'equals': True, 'next': 'end_chapter'}]
    course = loader.validate(course_json)
    assert len(course.chapters[0].steps[0].wait.clauses) == 2
    assert course.chapters[0].steps[0].branches[0].next == 'end_chapter'


def test_closed_loop_without_end_is_rejected(loader, course_json):
    course_json['chapters'][0]['steps'][1]['next'] = 'save'
    with pytest.raises(ValueError, match='end'):
        loader.validate(course_json)


def test_unreachable_step_is_rejected(loader, course_json):
    course_json['chapters'][0]['steps'][0]['next'] = 'end_chapter'
    with pytest.raises(ValueError, match='unreachable'):
        loader.validate(course_json)


def test_loop_branch_without_escape_is_rejected(loader, course_json):
    steps = course_json['chapters'][0]['steps']
    steps[1]['next'] = 'read'
    with pytest.raises(ValueError, match='end'):
        loader.validate(course_json)


@pytest.mark.parametrize('which', ['chapter', 'step'])
def test_duplicate_ids_are_rejected(loader, course_json, which):
    if which == 'chapter':
        course_json['chapters'].append(copy.deepcopy(course_json['chapters'][0]))
    else:
        course_json['chapters'][0]['steps'].append(copy.deepcopy(course_json['chapters'][0]['steps'][0]))
    with pytest.raises(ValueError, match='duplicate'):
        loader.validate(course_json)


def test_information_cannot_hide_an_operation_wait(loader, course_json):
    course_json['chapters'][0]['steps'][0]['kind'] = 'information'
    with pytest.raises(ValueError):
        loader.validate(course_json)


def test_fixture_cannot_escape_resource_root(loader, course_json, tmp_path):
    outside = tmp_path.parent / 'outside.msd'
    outside.write_bytes(b'not a user file')
    loader.fixtures['project_basic'] = '../outside.msd'
    with pytest.raises(ValueError, match='outside'):
        loader.validate(course_json)


def test_fixture_symlink_escape_is_rejected(loader, course_json, tmp_path):
    outside = tmp_path.parent / 'outside-link.msd'
    outside.write_bytes(b'synthetic')
    link = tmp_path / 'fixtures' / 'external.msd'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Host does not permit symlinks; Windows junction coverage is separate.')
    loader.fixtures['project_basic'] = 'fixtures/external.msd'
    with pytest.raises(ValueError, match='outside'):
        loader.validate(course_json)


def test_catalog_load_and_cross_references(loader, course_json, tmp_path):
    (tmp_path / 'courses').mkdir()
    (tmp_path / 'courses' / 'c01.json').write_text(json.dumps(course_json), encoding='utf-8')
    (tmp_path / 'catalog.json').write_text(json.dumps({
        'schema_version': 1, 'courses': ['courses/c01.json'],
        'groups': [{'id': 'intro', 'title_key': 'group', 'courses': ['c01']}],
    }), encoding='utf-8')
    catalog = loader.load()
    assert catalog.step_count('c01') == 2
    assert len(tuple(catalog.all_steps())) == 2
    assert catalog.chapter_by_id('c01.save').id == 'c01.save'


def test_json_duplicate_keys_are_rejected(loader, tmp_path):
    (tmp_path / 'catalog.json').write_text('{"schema_version":1,"schema_version":2}', encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate'):
        loader.load()


def test_hero_image_must_exist_and_stay_inside_root(loader, course_json):
    course_json['chapters'][0]['steps'][0]['hero_image'] = '../outside.png'
    with pytest.raises(ValueError):
        loader.validate(course_json)
