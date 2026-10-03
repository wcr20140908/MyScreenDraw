# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed release gates; stdlib only, no application import or GUI.

Receipts are local build evidence, not signatures. Only build.ps1 records successful
acceptance. Publishing verifies existing evidence and never regenerates it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import zipfile
import zlib

SOURCE_REQUIRED = ('main.py', 'version.py', 'version_info.txt', 'MyScreenDraw.spec',
                   'build.ps1', 'create_release.ps1', 'release_artifact.py', 'LICENSE',
                   'THIRD_PARTY_LICENSES.txt', 'requirements.txt', 'requirements.lock',
                   'requirements-build.lock')
REQUIRED_FILES = ('MyScreenDraw.exe', 'RELEASE-MANIFEST.json', 'LICENSE',
                  'THIRD_PARTY_LICENSES.txt',
                  '_internal/PyQt6/Qt6/plugins/platforms/qwindows.dll',
                  '_internal/PyQt6/Qt6/plugins/imageformats/qjpeg.dll',
                  '_internal/PyQt6/Qt6/plugins/imageformats/qpdf.dll',
                  '_internal/PyQt6/Qt6/plugins/imageformats/qsvg.dll',
                  '_internal/PyQt6/Qt6/bin/Qt6Pdf.dll',
                  '_internal/PyQt6/Qt6/bin/Qt6Svg.dll')
CHECKS = ('unit_tests', 'staging_smoke', 'extracted_files', 'extracted_smoke')


def artifact_name(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('invalid stable version')
    return f'MyScreenDraw-v{version}-windows-x64.zip'


def safe_path(path, boundary):
    """Strict descendant, including missing outputs; reject reparse ancestors."""
    path, boundary = Path(os.path.abspath(path)), Path(os.path.abspath(boundary))
    if path == boundary or not path.is_relative_to(boundary):
        raise ValueError(f'path outside boundary: {boundary.name}')
    for node in (path, *path.parents):
        try:
            info = node.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('reparse point in release path')
    return path


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'invalid or missing {label}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'invalid {label}')
    return value


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def source_snapshot(root):
    """Hash current onedir inputs and release gates, never runtime data or secrets.

    Tests and documentation may be finalized/committed after acceptance without
    rebuilding identical binaries. Publishing still requires the entire tree clean.
    """
    root = Path(os.path.abspath(root))
    paths = {root / name for name in SOURCE_REQUIRED}
    for pattern in ('*.py', '*.ps1', '*.spec'):
        paths.update(root.glob(pattern))
    hashes = {}
    for path in sorted(paths):
        path = safe_path(path, root)
        if not path.is_file():
            raise ValueError(f'missing source input: {path.name}')
        hashes[path.relative_to(root.absolute()).as_posix()] = sha256(path)
    return {'schema': 1, 'files': hashes}


def source_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def write_source_snapshot(root, output):
    output = safe_path(output, Path(root) / 'build')
    snapshot = source_snapshot(root)
    _write_new(output, snapshot)
    return snapshot


def _check_pe(data):
    try:
        if data[:2] != b'MZ':
            raise ValueError
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        if pe < 64 or data[pe:pe + 4] != b'PE\0\0':
            raise ValueError
        machine, sections, _, _, _, optional_size, flags = struct.unpack_from('<HHIIIHH', data, pe + 4)
        optional = pe + 24
        if (machine != 0x8664 or not 0 < sections <= 96 or not flags & 2
                or flags & 0x2000 or optional_size < 112
                or struct.unpack_from('<H', data, optional)[0] != 0x20b):
            raise ValueError
        entry = struct.unpack_from('<I', data, optional + 16)[0]
        executable_entry = False
        for i in range(sections):
            section = optional + optional_size + 40 * i
            virtual_size, address, size, offset = struct.unpack_from('<IIII', data, section + 8)
            flags = struct.unpack_from('<I', data, section + 36)[0]
            if size and (offset < optional + optional_size + 40 * sections or offset + size > len(data)):
                raise ValueError
            if size and address <= entry < address + max(size, virtual_size) and flags & 0x20000000:
                executable_entry = True
        if not executable_entry:
            raise ValueError
    except (ValueError, struct.error) as exc:
        raise ValueError('invalid x64 executable PE') from exc


def _members(archive):
    infos = archive.infolist()
    if len(infos) > 10000 or sum(i.file_size for i in infos) > 1024 ** 3:
        raise ValueError('archive size limit exceeded')
    members, seen = {}, {}
    for info in infos:
        # Windows Compress-Archive uses backslashes. Check traversal and
        # duplicate aliases after normalization, while still detecting NUL truncation.
        name = info.filename.replace("\\", "/")
        parts = name.rstrip('/').split('/')
        if (info.orig_filename.replace("\\", "/") != name
                or any(not p or p in ('.', '..') or p.endswith((' ', '.'))
                       or re.search(r'[<>:"|?*\x00-\x1f]', p)
                       or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', p)
                       for p in parts)):
            raise ValueError('unsafe archive path')
        lowered = [p.casefold() for p in parts]
        if (set(lowered) & {'data', 'exports', 'build', 'dist', 'autosave', 'screenshots', '__pycache__'}
                or lowered[-1] in {'config.json', 'roster.json', 'events.jsonl', 'app.log'}
                or Path(lowered[-1]).suffix in {'.py', '.pyc', '.jsonl', '.tmp', '.log', '.png', '.jpg', '.jpeg'}):
            raise ValueError('private/source file in archive')
        mode = info.external_attr >> 16
        if (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                or bool(stat.S_ISDIR(mode)) and not info.is_dir() or info.flag_bits & 1):
            raise ValueError('unsafe archive member type')
        key = '/'.join(lowered)
        if key in seen:
            raise ValueError('duplicate archive member')
        seen[key] = info.is_dir()
        members[name.rstrip('/')] = info
    for key in seen:
        parts = key.split('/')
        if any(seen.get('/'.join(parts[:i])) is False for i in range(1, len(parts))):
            raise ValueError('archive file/directory collision')
    return members


def validate_release_zip(path, version):
    artifact_name(version)
    path = Path(path)
    if path.stat().st_size > 512 * 1024 ** 2:
        raise ValueError('archive size limit exceeded')
    before = sha256(path)
    try:
        with zipfile.ZipFile(path) as archive:
            members = _members(archive)
            required = list(REQUIRED_FILES)
            runtimes = [name for name in members if re.fullmatch(r'_internal/python3\d+\.dll', name)]
            if not runtimes:
                raise ValueError('missing required Python runtime')
            for name in required + runtimes:
                if name not in members or members[name].is_dir():
                    raise ValueError(f'missing required file: {name}')
                if not members[name].file_size:
                    raise ValueError(f'empty required file: {name}')
            # Read every entry to check its CRC, including non-required dependencies.
            for info in members.values():
                with archive.open(info) as stream:
                    while stream.read(1024 * 1024):
                        pass
            if members['RELEASE-MANIFEST.json'].file_size > 65536:
                raise ValueError('manifest too large')
            manifest = json.loads(archive.read('RELEASE-MANIFEST.json').decode('utf-8-sig'))
            if not isinstance(manifest, dict) or manifest.get('app_version') != version:
                raise ValueError('manifest version mismatch')
            if manifest.get('executable') != 'MyScreenDraw.exe' or manifest.get('hash_algorithm') != 'SHA-256':
                raise ValueError('invalid manifest executable/hash algorithm')
            exe = archive.read('MyScreenDraw.exe')
            _check_pe(exe)
            exe_hash = hashlib.sha256(exe).hexdigest()
            if manifest.get('sha256') != exe_hash:
                raise ValueError('manifest executable hash mismatch')
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, RuntimeError, NotImplementedError, zlib.error) as exc:
        raise ValueError('invalid release archive or manifest') from exc
    if sha256(path) != before:
        raise ValueError('archive changed during validation')
    return {'version': version, 'artifact': artifact_name(version),
            'zip_sha256': before, 'exe_sha256': exe_hash}


def check_extracted(path, directory, version):
    result = validate_release_zip(path, version)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            target = safe_path(Path(directory) / info.filename, directory)
            if not info.is_dir():
                with archive.open(info) as stream:
                    expected = hashlib.file_digest(stream, 'sha256').hexdigest()
                if not target.is_file() or sha256(target) != expected:
                    raise ValueError('extracted file mismatch')
    return result


def _acceptance(value, validated):
    if (not isinstance(value, dict) or value.get('schema') != 1
            or any(value.get(key) != validated[key] for key in ('version', 'zip_sha256', 'exe_sha256'))
            or not isinstance(value.get('checks'), dict)
            or any(value['checks'].get(check) is not True for check in CHECKS)):
        raise ValueError('missing or mismatched passed acceptance receipt')


def seal_candidate(path, version, root, snapshot, checksum, receipt, *, acceptance=None):
    path = safe_path(path, root)
    snapshot = safe_path(snapshot, Path(root) / 'build')
    receipt = safe_path(receipt, Path(root) / 'build')
    checksum = safe_path(checksum, root)
    validated = validate_release_zip(path, version)
    current = source_snapshot(root)
    if _json(snapshot, 'source snapshot') != current:
        raise ValueError('source changed during build')
    _acceptance(acceptance, validated)
    if receipt.exists() or checksum.exists():
        raise ValueError('refusing to overwrite existing release evidence')
    sealed = dict(validated, schema=1, source_sha256=source_hash(current), acceptance=acceptance)
    checksum.parent.mkdir(parents=True, exist_ok=True)
    with checksum.open('x', encoding='ascii', newline='\n') as stream:
        stream.write(f"{validated['zip_sha256']}  {artifact_name(version)}\n")
    _write_new(receipt, sealed)  # Last write is the acceptance commit marker.
    return sealed


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode:
        raise ValueError('Git release verification failed')
    return result.stdout


def verify_repository(root, commit, version='6.0.0'):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('invalid release commit')
    top = os.fsdecode(_git(root, 'rev-parse', '--show-toplevel')).strip()
    if Path(top).resolve() != Path(root).resolve():
        raise ValueError('release root is not repository root')
    head = _git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    target = _git(root, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    if head != commit or target != commit:
        raise ValueError('release commit does not match HEAD')
    if _git(root, 'status', '--porcelain=v1', '--untracked-files=all', '--ignore-submodules=none'):
        raise ValueError('release requires a clean index and worktree (including untracked files)')
    entries = _git(root, 'ls-files', '-v', '-z').split(b'\0')
    if any(entry and (entry[:1].islower() or entry[:1] == b'S') for entry in entries):
        raise ValueError('hidden worktree changes: skip-worktree/assume-unchanged is not allowed')
    tracked = {os.fsdecode(entry[2:]) for entry in entries if entry}
    if not set(source_snapshot(root)['files']).issubset(tracked):
        raise ValueError('source inputs must be tracked by the release commit')
    tag = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify',
                          '--quiet', f'refs/tags/v{version}^{{commit}}'], capture_output=True)
    if tag.returncode not in (0, 1) or (tag.returncode == 0 and tag.stdout.decode().strip() != commit):
        raise ValueError('existing release tag does not match commit')


def verify_release(path, version, root, checksum, receipt, *, commit=None):
    path = safe_path(path, root)
    checksum = safe_path(checksum, root)
    receipt = safe_path(receipt, Path(root) / 'build')
    if path.name != artifact_name(version):
        raise ValueError('wrong release artifact name')
    if commit is not None:
        verify_repository(root, commit, version)
    validated = validate_release_zip(path, version)
    try:
        text = checksum.read_text(encoding='ascii')
    except (OSError, UnicodeError) as exc:
        raise ValueError('invalid or missing checksum') from exc
    if text != f"{validated['zip_sha256']}  {artifact_name(version)}\n":
        raise ValueError('checksum mismatch')
    sealed = _json(receipt, 'receipt')
    if sealed.get('schema') != 1 or any(sealed.get(key) != value for key, value in validated.items()):
        raise ValueError('receipt does not match artifact')
    _acceptance(sealed.get('acceptance'), validated)
    if sealed.get('source_sha256') != source_hash(source_snapshot(root)):
        raise ValueError('source does not match accepted build')
    return sealed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    snapshot = sub.add_parser('snapshot')
    snapshot.add_argument('--root', required=True)
    snapshot.add_argument('--output', required=True)
    for command in ('validate', 'check-extracted', 'seal', 'verify'):
        child = sub.add_parser(command)
        child.add_argument('--zip', required=True)
        child.add_argument('--version', required=True)
        if command == 'check-extracted':
            child.add_argument('--directory', required=True)
        if command in ('seal', 'verify'):
            for name in ('root', 'checksum', 'receipt'):
                child.add_argument('--' + name, required=True)
            if command == 'seal':
                child.add_argument('--snapshot', required=True)
                child.add_argument('--acceptance', required=True)
            else:
                child.add_argument('--commit', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'snapshot':
            write_source_snapshot(args.root, args.output)
            result = {'source_snapshot': 'saved'}
        elif args.command == 'validate':
            result = validate_release_zip(args.zip, args.version)
        elif args.command == 'check-extracted':
            result = check_extracted(args.zip, args.directory, args.version)
        elif args.command == 'seal':
            result = seal_candidate(args.zip, args.version, args.root, args.snapshot,
                                    args.checksum, args.receipt,
                                    acceptance=_json(safe_path(args.acceptance, Path(args.root) / 'build'), 'acceptance'))
        else:
            result = verify_release(args.zip, args.version, args.root, args.checksum,
                                    args.receipt, commit=args.commit)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError) as exc:
        print(f'Release gate rejected: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
