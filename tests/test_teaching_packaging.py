# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure bundle-contract tests; synthetic resources live only in pytest temp roots.

Run with --noconftest to avoid the application's offscreen session fixture.
The spec is executed with inert build targets, never with PyInstaller itself.
"""
from pathlib import Path
import os
import runpy
import stat
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def write_resource(root, relative, data=b'synthetic packaging data'):
    path = root / 'assets' / 'tutorials' / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def source_root(tmp_path):
    root = tmp_path / '中文 source with spaces'
    root.mkdir()
    return root


@pytest.fixture
def collector():
    # A missing implementation fails a test rather than aborting collection.
    from teaching.packaging import collect_teaching_datas
    return collect_teaching_datas


@pytest.fixture
def spec_runner(tmp_path, monkeypatch):
    """Exercise the real spec's emitted arguments without doing any build work."""
    calls = []
    hooks = ModuleType('PyInstaller.utils.hooks')
    hooks.collect_submodules = lambda name: ['pynput.dummy']
    monkeypatch.setitem(sys.modules, 'PyInstaller', ModuleType('PyInstaller'))
    monkeypatch.setitem(sys.modules, 'PyInstaller.utils', ModuleType('PyInstaller.utils'))
    monkeypatch.setitem(sys.modules, 'PyInstaller.utils.hooks', hooks)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.delitem(sys.modules, 'teaching', raising=False)
    monkeypatch.delitem(sys.modules, 'teaching.packaging', raising=False)
    unrelated = tmp_path / 'unrelated working directory'
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    def analysis(*args, **kwargs):
        calls.append(('Analysis', args, kwargs, os.environ.get('PATH')))
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=kwargs['datas'])

    def target(name):
        def record(*args, **kwargs):
            calls.append((name, args, kwargs, os.environ.get('PATH')))
            return object()
        return record

    def run(root, *, analysis_target=analysis):
        spec_path = root / 'MyScreenDraw.spec'
        spec_path.write_text((ROOT / 'MyScreenDraw.spec').read_text(encoding='utf-8'),
                             encoding='utf-8')
        package = root / 'teaching'
        package.mkdir(exist_ok=True)
        (package / '__init__.py').write_text('', encoding='utf-8')
        helper = ROOT / 'teaching' / 'packaging.py'
        if helper.is_file():
            (package / 'packaging.py').write_text(helper.read_text(encoding='utf-8'),
                                                encoding='utf-8')
        namespace = runpy.run_path(str(spec_path), init_globals={
            'SPEC': str(spec_path), 'SPECPATH': str(root),
            'Analysis': analysis_target, 'PYZ': target('PYZ'),
            'EXE': target('EXE'), 'COLLECT': target('COLLECT'),
        })
        return namespace, calls

    try:
        yield run, calls
    finally:
        sys.modules.pop('teaching.packaging', None)
        sys.modules.pop('teaching', None)


def test_spec_includes_every_resource_at_the_runtime_catalog_path(source_root, spec_runner):
    files = [
        write_resource(source_root, 'catalog.json', b'{}'),
        write_resource(source_root, 'courses/start.json', b'{}'),
        write_resource(source_root, 'fixtures/nested/pages.msd'),
        write_resource(source_root, 'fixtures/roster.csv'),
        write_resource(source_root, 'images/中文 help.png'),
        write_resource(source_root, 'images/nested/help.JPG'),
        write_resource(source_root, 'extra/unreferenced.json', b'{}'),
    ]
    run, _ = spec_runner
    _, calls = run(source_root)
    datas = calls[0][2]['datas']
    assert datas[:2] == [('LICENSE', '.'), ('THIRD_PARTY_LICENSES.txt', '.')]
    expected = {(str(path), path.parent.relative_to(source_root).as_posix()) for path in files}
    assert set(datas[2:]) == expected
    assert len(datas) == len(files) + 2
    assert all(isinstance(part, str) for pair in datas for part in pair)


def test_spec_keeps_legacy_release_without_resources_and_warns_unavailable(source_root, spec_runner):
    run, _ = spec_runner
    with pytest.warns(RuntimeWarning, match='teaching.*unavailable'):
        _, calls = run(source_root)
    assert calls[0][2]['datas'] == [('LICENSE', '.'), ('THIRD_PARTY_LICENSES.txt', '.')]
    exe = next(call[2] for call in calls if call[0] == 'EXE')
    collect = next(call[2] for call in calls if call[0] == 'COLLECT')
    assert exe['console'] is False
    assert exe['upx'] is False and collect['upx'] is False
    assert exe['version'] == 'version_info.txt'
    assert exe['name'] == collect['name'] == 'MyScreenDraw'
    assert not (source_root / 'assets').exists()


def test_spec_rejects_partial_resources_before_analysis(source_root, spec_runner):
    write_resource(source_root, 'courses/incomplete.json', b'{}')
    run, calls = spec_runner
    with pytest.raises(ValueError, match='catalog.json'):
        run(source_root)
    assert calls == []


@pytest.mark.parametrize('previous_path', [None, 'foreign-icu;original-path'])
@pytest.mark.parametrize('failure', [False, True])
def test_spec_preserves_icu_path_and_restores_environment(
        source_root, spec_runner, monkeypatch, previous_path, failure):
    if previous_path is None:
        monkeypatch.delenv('PATH', raising=False)
    else:
        monkeypatch.setenv('PATH', previous_path)
    monkeypatch.setenv('SystemRoot', str(source_root / 'Windows'))
    observed = []

    def analysis(*args, **kwargs):
        observed.append(os.environ.get('PATH'))
        if failure:
            raise RuntimeError('synthetic analysis failure')
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=kwargs['datas'])

    run, _ = spec_runner
    with pytest.warns(RuntimeWarning, match='teaching.*unavailable'):
        if failure:
            with pytest.raises(RuntimeError, match='synthetic analysis failure'):
                run(source_root, analysis_target=analysis)
        else:
            run(source_root, analysis_target=analysis)
    expected = previous_path
    if os.name == 'nt':
        expected = str(source_root / 'Windows' / 'System32') + os.pathsep + (previous_path or '')
    assert observed == [expected]
    assert os.environ.get('PATH') == previous_path


@pytest.mark.parametrize('assets_exists', [False, True])
def test_absent_tutorial_directory_is_explicitly_unavailable_and_not_created(
        collector, source_root, assets_exists):
    if assets_exists:
        (source_root / 'assets').mkdir()
    with pytest.warns(RuntimeWarning, match='assets/tutorials.*teaching.*unavailable'):
        assert collector(source_root) == []
    assert not (source_root / 'assets' / 'tutorials').exists()


@pytest.mark.parametrize('partial', ['empty', 'courses', 'images', 'fixtures'])
def test_any_existing_tutorial_directory_requires_catalog(collector, source_root, partial):
    tutorials = source_root / 'assets' / 'tutorials'
    tutorials.mkdir(parents=True)
    if partial != 'empty':
        (tutorials / partial).mkdir()
    with pytest.raises(ValueError, match='catalog.json'):
        collector(source_root)


@pytest.mark.parametrize('obstruction', ['assets', 'assets/tutorials', 'assets/tutorials/catalog.json'])
def test_wrong_resource_path_kind_fails_closed(collector, source_root, obstruction):
    path = source_root / obstruction
    path.parent.mkdir(parents=True, exist_ok=True)
    if obstruction.endswith('catalog.json'):
        path.mkdir()
    else:
        path.write_bytes(b'not a directory')
    with pytest.raises(ValueError):
        collector(source_root)


def test_manifest_is_recursive_deterministic_absolute_and_cwd_independent(
        collector, source_root, tmp_path, monkeypatch):
    files = [
        write_resource(source_root, 'images/z.png'),
        write_resource(source_root, 'fixtures/nested/data.json', b'{}'),
        write_resource(source_root, 'catalog.json', b'{}'),
        write_resource(source_root, 'courses/a.json', b'{}'),
    ]
    unrelated = tmp_path / 'elsewhere'
    unrelated.mkdir()
    write_resource(unrelated, 'catalog.json', b'{}')
    write_resource(unrelated, 'courses/decoy.json', b'{}')
    monkeypatch.chdir(unrelated)
    manifest = collector(source_root)
    expected = [(str(path), path.parent.relative_to(source_root).as_posix())
                for path in sorted(files)]
    assert manifest == expected
    assert manifest == collector(str(source_root))
    assert all(Path(src).is_absolute() for src, _ in manifest)


def test_default_root_uses_helper_source_not_cwd(source_root, tmp_path, monkeypatch):
    package = source_root / 'teaching'
    package.mkdir()
    helper = package / 'packaging.py'
    helper.write_text((ROOT / 'teaching' / 'packaging.py').read_text(encoding='utf-8'),
                      encoding='utf-8')
    catalog = write_resource(source_root, 'catalog.json', b'{}')
    elsewhere = tmp_path / 'decoy'
    elsewhere.mkdir()
    write_resource(elsewhere, 'catalog.json', b'{}')
    monkeypatch.chdir(elsewhere)
    collect = runpy.run_path(str(helper))['collect_teaching_datas']
    assert collect() == [(str(catalog), 'assets/tutorials')]


def test_relative_source_root_cannot_accidentally_use_cwd(collector):
    with pytest.raises(ValueError, match='absolute'):
        collector(Path('relative-checkout'))


@pytest.mark.parametrize('relative', [
    'courses/nested/course.JSON', 'fixtures/project.msd', 'fixtures/roster.csv',
    'fixtures/import.pdf', 'fixtures/import.png', 'fixtures/nested/metadata.json',
    'images/help.png', 'images/help.jpg', 'images/help.jpeg', 'images/help.bmp',
    'images/help.gif', 'images/help.webp',
])
def test_supported_json_fixtures_and_images_are_never_silently_omitted(
        collector, source_root, relative):
    catalog = write_resource(source_root, 'catalog.json', b'{}')
    resource = write_resource(source_root, relative)
    assert set(collector(source_root)) == {
        (str(catalog), 'assets/tutorials'),
        (str(resource), resource.parent.relative_to(source_root).as_posix()),
    }


@pytest.mark.parametrize('relative', [
    'courses/execute.py', 'fixtures/payload.exe', 'images/help.txt',
    'fixtures/library.dll', 'images/help.svg', 'notes.md', 'images/.DS_Store',
    'courses/project.msd', 'unregistered/image.png',
])
def test_unsupported_files_abort_instead_of_returning_partial_datas(
        collector, source_root, relative):
    write_resource(source_root, 'catalog.json', b'{}')
    bad = write_resource(source_root, relative)
    with pytest.raises(ValueError, match='unsupported') as error:
        collector(source_root)
    assert bad.name in str(error.value)


@pytest.mark.parametrize('relative', [
    '.', 'assets', 'assets/tutorials', 'assets/tutorials/catalog.json',
    'assets/tutorials/fixtures', 'assets/tutorials/fixtures/pages.msd',
])
@pytest.mark.parametrize('link_kind', ['symlink', 'reparse'])
def test_links_are_rejected_even_when_the_target_would_stay_inside_root(
        collector, source_root, monkeypatch, relative, link_kind):
    write_resource(source_root, 'catalog.json', b'{}')
    write_resource(source_root, 'fixtures/pages.msd')
    linked = source_root / relative
    real_lstat = Path.lstat

    def lstat(path, *args, **kwargs):
        result = real_lstat(path, *args, **kwargs)
        if path == linked:
            return SimpleNamespace(
                st_mode=stat.S_IFLNK if link_kind == 'symlink' else result.st_mode,
                st_nlink=result.st_nlink,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if link_kind == 'reparse' else 0,
            )
        return result

    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ValueError, match='link|reparse'):
        collector(source_root)


def test_hardlinked_fixture_cannot_smuggle_external_data(collector, source_root, tmp_path):
    write_resource(source_root, 'catalog.json', b'{}')
    fixture = write_resource(source_root, 'fixtures/shared.msd')
    os.link(fixture, tmp_path / 'outside-teaching.msd')
    with pytest.raises(ValueError, match='link'):
        collector(source_root)


def test_resolved_resource_must_stay_inside_exact_tutorial_root(
        collector, source_root, tmp_path, monkeypatch):
    write_resource(source_root, 'catalog.json', b'{}')
    escaping = write_resource(source_root, 'fixtures/escaping.msd')
    outside = source_root / 'assets' / 'tutorials-sibling' / 'escaping.msd'
    outside.parent.mkdir()
    outside.write_bytes(b'not a tutorial resource')
    real_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == escaping:
            return outside
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', resolve)
    with pytest.raises(ValueError, match='outside|escape'):
        collector(source_root)


@pytest.mark.parametrize('failure', ['unreadable', 'vanished', 'special-file'])
def test_uninspectable_or_non_regular_resources_abort_inventory(
        collector, source_root, monkeypatch, failure):
    write_resource(source_root, 'catalog.json', b'{}')
    broken = write_resource(source_root, 'fixtures/broken.json', b'{}')
    real_lstat = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == broken:
            if failure == 'unreadable':
                raise PermissionError('synthetic permission failure')
            if failure == 'vanished':
                raise FileNotFoundError('synthetic disappearance')
            return SimpleNamespace(st_mode=stat.S_IFIFO, st_nlink=1, st_file_attributes=0)
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ValueError):
        collector(source_root)


def test_directory_scan_error_is_not_treated_as_empty(collector, source_root, monkeypatch):
    write_resource(source_root, 'catalog.json', b'{}')
    tutorials = source_root / 'assets' / 'tutorials'
    real_iterdir = Path.iterdir

    def iterdir(path):
        if path == tutorials:
            raise PermissionError('synthetic directory read failure')
        return real_iterdir(path)

    monkeypatch.setattr(Path, 'iterdir', iterdir)
    with pytest.raises(ValueError):
        collector(source_root)

@pytest.mark.parametrize('target_kind', ['inside', 'outside', 'dangling'])
def test_real_symlinks_are_never_followed(collector, source_root, tmp_path, target_kind):
    write_resource(source_root, 'catalog.json', b'{}')
    if target_kind == 'inside':
        target = write_resource(source_root, 'fixtures/original.msd')
    else:
        target = tmp_path / 'outside-tutorial-tree.msd'
        if target_kind == 'outside':
            target.write_bytes(b'synthetic outside fixture')
    link = source_root / 'assets' / 'tutorials' / 'fixtures' / 'linked.msd'
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except OSError as exc:
        if getattr(exc, 'winerror', None) == 1314:
            pytest.skip('Windows symlink privilege unavailable; stat/reparse cases are tested separately')
        raise
    with pytest.raises(ValueError, match='link'):
        collector(source_root)
