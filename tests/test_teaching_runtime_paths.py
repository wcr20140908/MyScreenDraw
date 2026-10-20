# SPDX-License-Identifier: GPL-3.0-or-later
"""Private practice cannot read/write normal portable data or external paths."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import uuid

import pytest


@pytest.fixture
def private(tmp_path):
    from runtime_paths import RuntimePaths
    app = tmp_path / 'app'
    resources = app / '_internal'
    resources.mkdir(parents=True)
    return RuntimePaths.create_practice(app, resources, temp_root=tmp_path / 'temp',
                                        session_id=uuid.uuid4().hex, nonce='a' * 64)


def test_normal_paths_preserve_existing_portable_layout(tmp_path):
    from runtime_paths import RuntimePaths, RuntimeContext
    paths = RuntimePaths.for_normal(tmp_path, tmp_path / '_internal')
    assert paths.data_dir == tmp_path / 'data'
    assert paths.export_dir == tmp_path / 'exports'
    assert paths.autosave_dir == tmp_path / 'data' / 'autosave'
    assert paths.config_file == tmp_path / 'data' / 'config.json'
    assert paths.roster_file == tmp_path / 'data' / 'roster.json'
    assert paths.log_file == tmp_path / 'data' / 'app.log'
    assert paths.telemetry_file == tmp_path / 'data' / 'events.jsonl'
    context = RuntimeContext(paths)
    assert context.ui_active and context.tray and context.global_keyboard
    assert context.updates and context.autostart and context.usage_tracking


def test_private_paths_share_resources_but_not_runtime(private):
    from runtime_paths import RuntimeContext
    assert private.practice
    assert not private.runtime_root.is_relative_to(private.app_dir)
    assert private.config_file.is_relative_to(private.runtime_root)
    assert private.export_dir.is_relative_to(private.runtime_root)
    assert private.resource_dir == private.app_dir / '_internal'
    context = RuntimeContext(private)
    assert not context.ui_active
    assert not any((context.tray, context.global_keyboard, context.updates,
                    context.autostart, context.usage_tracking))
    context.activate()
    assert context.ui_active
    assert not context.global_keyboard and not context.tray
    with pytest.raises(FrozenInstanceError):
        private.runtime_root = private.app_dir


def test_marker_is_required_before_child_binding(private):
    from runtime_paths import RuntimePaths
    private.marker_file.unlink()
    with pytest.raises(ValueError, match='marker'):
        RuntimePaths.for_practice(private.app_dir, private.resource_dir, private.runtime_root,
                                  temp_root=private.temp_root, session_id=private.session_id,
                                  nonce='a' * 64)


@pytest.mark.parametrize('field,value', [('magic', 'other'), ('schema_version', 99),
                                       ('session_id', 'other'), ('nonce', 'b' * 64),
                                       ('app_key', 'other'), ('extra', 'unsafe')])
def test_marker_mismatch_is_rejected(private, field, value):
    from runtime_paths import RuntimePaths
    record = json.loads(private.marker_file.read_text(encoding='utf-8'))
    record[field] = value
    private.marker_file.write_text(json.dumps(record), encoding='utf-8')
    with pytest.raises(ValueError):
        RuntimePaths.for_practice(private.app_dir, private.resource_dir, private.runtime_root,
                                  temp_root=private.temp_root, session_id=private.session_id,
                                  nonce='a' * 64)


def test_session_directory_name_must_match_identity(private):
    from runtime_paths import RuntimePaths
    with pytest.raises(ValueError):
        RuntimePaths.for_practice(private.app_dir, private.resource_dir, private.runtime_root,
                                  temp_root=private.temp_root, session_id=uuid.uuid4().hex,
                                  nonce='a' * 64)


def test_wrong_nonce_error_does_not_echo_secret(private):
    from runtime_paths import RuntimePaths
    secret = 'b' * 64
    with pytest.raises(ValueError) as error:
        RuntimePaths.for_practice(private.app_dir, private.resource_dir, private.runtime_root,
                                  temp_root=private.temp_root, session_id=private.session_id, nonce=secret)
    assert secret not in str(error.value)


@pytest.mark.parametrize('relative', ['../../outside.msd', '../outside.msd', 'C:escape.msd',
                                     r'\\server\share\project.msd'])
def test_private_write_cannot_escape(private, relative):
    with pytest.raises(ValueError):
        private.require_write_path(relative)


def test_private_read_rejects_actual_external_file(private, tmp_path):
    outside = tmp_path / 'user-project.msd'
    outside.write_bytes(b'original sentinel')
    with pytest.raises(ValueError, match='outside'):
        private.require_read_path(outside)
    assert outside.read_bytes() == b'original sentinel'


def test_internal_reads_and_new_output_paths_are_allowed(private):
    source = private.runtime_root / 'fixtures' / 'example.msd'
    source.parent.mkdir()
    source.write_bytes(b'synthetic')
    assert private.require_read_path(source) == source
    assert private.require_write_path('exports/new/result.png') == private.export_dir / 'new' / 'result.png'
    assert not (private.export_dir / 'new').exists(), 'Validation must not create output folders'


def test_read_rejects_missing_file_and_directories(private):
    with pytest.raises(ValueError):
        private.require_read_path(private.runtime_root / 'missing.msd')
    with pytest.raises(ValueError):
        private.require_read_path(private.runtime_root)


def test_private_cannot_overwrite_ownership_marker(private):
    with pytest.raises(ValueError, match='marker'):
        private.require_write_path(private.marker_file)


def test_normal_user_file_locations_are_not_restricted(tmp_path):
    from runtime_paths import RuntimePaths
    paths = RuntimePaths.for_normal(tmp_path / 'app')
    outside = tmp_path / 'normal-project.msd'
    outside.write_bytes(b'user chosen file')
    assert paths.require_read_path(outside) == outside
    assert paths.require_write_path(tmp_path / 'user-output.png') == tmp_path / 'user-output.png'


def test_symlink_output_escape_is_rejected(private, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = private.runtime_root / 'redirect'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink privilege unavailable; native junction tests are separate.')
    with pytest.raises(ValueError):
        private.require_write_path(link / 'user-file.msd')


def test_resource_paths_cannot_escape_bundled_root(private):
    (private.resource_dir / 'sample.json').write_text('{}', encoding='utf-8')
    assert private.resource_path('sample.json') == private.resource_dir / 'sample.json'
    with pytest.raises(ValueError):
        private.resource_path('../user.json')


def test_create_practice_does_not_reuse_existing_session(private):
    from runtime_paths import RuntimePaths
    sentinel = private.runtime_root / 'keep.txt'
    sentinel.write_bytes(b'original session')
    with pytest.raises(ValueError, match='exists'):
        RuntimePaths.create_practice(private.app_dir, private.resource_dir,
                                     temp_root=private.temp_root, session_id=private.session_id,
                                     nonce='a' * 64)
    assert sentinel.read_bytes() == b'original session'


def test_private_path_aliases_are_ready_for_bootstrap_binding(private):
    aliases = private.module_aliases()
    assert set(aliases) == {'DATA_DIR', 'EXPORT_DIR', 'AUTOSAVE_DIR', 'CONFIG_FILE',
                            'ROSTER_FILE', 'TELEMETRY_FILE', 'LOG_FILE'}
    assert all(Path(path).is_relative_to(private.runtime_root) for path in aliases.values())
