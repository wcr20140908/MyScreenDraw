# SPDX-License-Identifier: GPL-3.0-or-later
import json
from types import SimpleNamespace
import uuid

import pytest

from runtime_paths import RuntimePaths


@pytest.fixture
def request_data(tmp_path):
    paths = RuntimePaths.create_practice(tmp_path / 'app', tmp_path / 'app' / '_internal',
                                        temp_root=tmp_path / 'temp')
    channel = 'myscreendraw-teaching-' + uuid.uuid4().hex
    args = ['--teaching-practice', '--session-root', str(paths.runtime_root),
            '--session-id', paths.session_id, '--channel', channel,
            '--course-id', 'c01', '--chapter-id', 'c01.save']
    env = {'MYSCREENDRAW_PRACTICE_NONCE': paths.nonce,
           'MYSCREENDRAW_PRACTICE_TEMP_ROOT': str(paths.temp_root)}
    return paths, channel, args, env


def parse(data, args=None, env=None):
    from teaching.bootstrap import parse_practice_request
    paths, channel, original, environment = data
    return parse_practice_request(original if args is None else args, app_dir=paths.app_dir,
        resource_dir=paths.resource_dir, environ=environment if env is None else env)


def test_normal_launch_ignores_practice_environment(request_data):
    assert parse(request_data, args=['--smoke']) is None


def test_valid_request_binds_only_private_runtime(request_data):
    from teaching.bootstrap import bind_practice_paths
    request = parse(request_data)
    paths, channel, args, env = request_data
    assert request.channel == channel and request.chapter_id == 'c01.save'
    module = SimpleNamespace(APP_DIR=str(paths.app_dir))
    context = bind_practice_paths(module, request)
    assert not context.ui_active and not context.global_keyboard and not context.tray
    assert module.APP_DIR == str(paths.app_dir)
    assert module.CONFIG_FILE == str(paths.config_file)
    assert module.RUNTIME_CONTEXT is context


@pytest.mark.parametrize('flag', ['--session-root', '--session-id', '--channel', '--course-id', '--chapter-id'])
def test_missing_required_argument_is_fail_closed(request_data, flag):
    paths, channel, args, env = request_data
    args = list(args)
    index = args.index(flag)
    del args[index:index + 2]
    with pytest.raises(ValueError):
        parse(request_data, args=args)


@pytest.mark.parametrize('flag', ['--restore', '--smoke', '--smoke-ui', '--run-script'])
def test_normal_or_unknown_argument_cannot_mix_with_practice(request_data, flag):
    with pytest.raises(ValueError):
        parse(request_data, args=request_data[2] + [flag])


def test_duplicate_argument_is_rejected(request_data):
    with pytest.raises(ValueError):
        parse(request_data, args=request_data[2] + ['--course-id', 'c02'])


def test_similar_practice_flag_cannot_fall_through_to_normal_launch(request_data):
    with pytest.raises(ValueError):
        parse(request_data, args=['--teaching-practice=false'])


def test_invalid_channel_is_rejected(request_data):
    args = list(request_data[2])
    args[args.index('--channel') + 1] = 'other-application'
    with pytest.raises(ValueError):
        parse(request_data, args=args)


def test_chapter_must_belong_to_requested_course(request_data):
    args = list(request_data[2])
    args[args.index('--chapter-id') + 1] = 'c99.save'
    with pytest.raises(ValueError):
        parse(request_data, args=args)


@pytest.mark.parametrize('key', ['MYSCREENDRAW_PRACTICE_NONCE', 'MYSCREENDRAW_PRACTICE_TEMP_ROOT'])
def test_missing_private_environment_does_not_use_default_paths(request_data, key):
    env = dict(request_data[3]);env.pop(key)
    with pytest.raises(ValueError):
        parse(request_data, env=env)


def test_bad_marker_is_rejected_before_runtime_directories_are_created(request_data):
    paths = request_data[0]
    paths.marker_file.write_bytes(b'{}')
    with pytest.raises(ValueError):
        parse(request_data)
    assert not paths.data_dir.exists() and not (paths.app_dir / 'data').exists()


def test_binding_is_rejected_after_log_handlers_exist(request_data):
    from teaching.bootstrap import bind_practice_paths
    request = parse(request_data)
    module = SimpleNamespace(APP_DIR=str(request.paths.app_dir),
                             LOGGER=SimpleNamespace(handlers=[object()]), CONFIG_FILE='keep')
    with pytest.raises(ValueError):
        bind_practice_paths(module, request)
    assert module.CONFIG_FILE == 'keep'


def test_binding_cannot_cross_installations(request_data):
    from teaching.bootstrap import bind_practice_paths
    request = parse(request_data)
    module = SimpleNamespace(APP_DIR=str(request.paths.app_dir.parent / 'other'), CONFIG_FILE='keep')
    with pytest.raises(ValueError):
        bind_practice_paths(module, request)
    assert module.CONFIG_FILE == 'keep'
