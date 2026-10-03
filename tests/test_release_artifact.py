# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated release gates: synthetic archives only, no Qt/build/upload."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import release_artifact as artifact


def fake_pe():
    """Structurally valid x64 PE fixture, never executed."""
    data = bytearray(1024)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', data, 0x84, 0x8664, 1, 0, 0, 0, 240, 0x22)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<I', data, optional + 16, 0x1000)
    struct.pack_into('<II', data, optional + 32, 0x1000, 0x200)
    struct.pack_into('<II', data, optional + 56, 0x2000, 0x200)
    section = optional + 240
    data[section:section + 8] = b'.text\0\0\0'
    struct.pack_into('<IIII', data, section + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into('<I', data, section + 36, 0x60000020)
    data[0x200] = 0xc3
    return bytes(data)


class ReleaseArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='release-gate-[test]-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in artifact.SOURCE_REQUIRED:
            (self.root / name).write_text('fixture input\n', encoding='utf-8')
        self.build = self.root / 'build'
        self.build.mkdir()
        self.version = '6.0.0'
        self.zip = self.root / artifact.artifact_name(self.version)
        self.checksum = Path(str(self.zip) + '.sha256')
        self.receipt = self.build / 'release-receipts' / (self.zip.name + '.json')
        self.snapshot = self.build / 'release-source.json'
        self.write_zip()
        artifact.write_source_snapshot(self.root, self.snapshot)

    def write_zip(self, *, version='6.0.0', exe=None, manifest_hash=None, omit=(), extras=None):
        exe = fake_pe() if exe is None else exe
        manifest = {'app_version': version, 'executable': 'MyScreenDraw.exe',
                    'sha256': manifest_hash or hashlib.sha256(exe).hexdigest(),
                    'hash_algorithm': 'SHA-256', 'signature': 'none',
                    'package_type': 'PyInstaller onedir portable'}
        files = {name: b'dependency' for name in artifact.REQUIRED_FILES}
        files['_internal/python311.dll'] = b'python runtime'
        files['MyScreenDraw.exe'] = exe
        files['RELEASE-MANIFEST.json'] = ('\ufeff' + json.dumps(manifest)).encode('utf-8')
        files.update(extras or {})
        with zipfile.ZipFile(self.zip, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                if name not in omit:
                    # ZipInfo normalizes backslashes on Windows at construction;
                    # preserve the hostile on-disk spelling for validator coverage.
                    info = zipfile.ZipInfo(name)
                    info.filename = name
                    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)

    def acceptance(self, path=None):
        validated = artifact.validate_release_zip(path or self.zip, self.version)
        return dict(validated, schema=1, checks={name: True for name in artifact.CHECKS})

    def seal(self):
        return artifact.seal_candidate(self.zip, self.version, self.root,
                                       self.snapshot, self.checksum, self.receipt,
                                       acceptance=self.acceptance())

    def verify(self):
        return artifact.verify_release(self.zip, self.version, self.root,
                                       self.checksum, self.receipt)

    def test_valid_archive_and_receipt_pass_without_rewriting_sidecars(self):
        sealed = self.seal()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.checksum, self.receipt)}
        checked = self.verify()
        self.assertEqual(checked['zip_sha256'], sealed['zip_sha256'])
        for path, expected in before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)

    def test_old_version_rejected_even_with_current_filename(self):
        self.write_zip(version='6.0.0-beta.8')
        with self.assertRaisesRegex(ValueError, 'version'):
            artifact.validate_release_zip(self.zip, self.version)

    def test_wrong_manifest_exe_hash_rejected(self):
        self.write_zip(manifest_hash='0' * 64)
        with self.assertRaisesRegex(ValueError, 'executable hash'):
            artifact.validate_release_zip(self.zip, self.version)

    def test_fake_executables_with_correct_hash_are_rejected(self):
        for data in (b'not an executable', b'MZ' + b'fake' * 300,
                     fake_pe()[:200]):
            with self.subTest(size=len(data)):
                self.write_zip(exe=data)
                with self.assertRaisesRegex(ValueError, 'PE'):
                    artifact.validate_release_zip(self.zip, self.version)

    def test_non_x64_dll_and_broken_section_are_rejected(self):
        for offset, fmt, value in ((0x84, '<H', 0x14c), (0x96, '<H', 0x2022),
                                   (0x188 + 20, '<I', 999999)):
            with self.subTest(offset=offset):
                data = bytearray(fake_pe())
                struct.pack_into(fmt, data, offset, value)
                self.write_zip(exe=bytes(data))
                with self.assertRaisesRegex(ValueError, 'PE'):
                    artifact.validate_release_zip(self.zip, self.version)

    def test_all_required_dependencies_must_exist_and_not_be_empty(self):
        for name in artifact.REQUIRED_FILES + ('_internal/python311.dll',):
            if name in ('MyScreenDraw.exe', 'RELEASE-MANIFEST.json'):
                continue
            with self.subTest(name=name):
                self.write_zip(omit=(name,))
                with self.assertRaisesRegex(ValueError, 'missing|required'):
                    artifact.validate_release_zip(self.zip, self.version)
                self.write_zip(extras={name: b''})
                with self.assertRaisesRegex(ValueError, 'empty|required'):
                    artifact.validate_release_zip(self.zip, self.version)

    def test_unsafe_duplicate_private_and_receipt_members_are_rejected(self):
        for name in ('../outside', '/absolute', 'data/config.json', 'exports/a.txt',
                     'CON.txt', 'trailing./file', 'MYSCREENDRAW.EXE', 'build/receipt.json',
                     'source.py', '_internal/../bad', '_internal\\..\\alias.dll'):
            with self.subTest(name=name):
                self.write_zip(extras={name: b'bad'})
                with self.assertRaises(ValueError):
                    artifact.validate_release_zip(self.zip, self.version)

    def test_windows_archive_separators_are_normalized_before_validation(self):
        self.write_zip(extras={"_internal\\extra.dll": b"dependency"})
        self.assertEqual(artifact.validate_release_zip(self.zip, self.version)["version"], self.version)

    def test_separator_alias_collision_and_traversal_are_rejected(self):
        for extras in ({"_internal/extra.dll": b"one", "_internal\\extra.dll": b"two"},
                       {"_internal\\..\\escape.dll": b"bad"}):
            self.write_zip(extras=extras)
            with self.assertRaises(ValueError):
                artifact.validate_release_zip(self.zip, self.version)

    def test_symlink_and_file_directory_collision_are_rejected(self):
        with zipfile.ZipFile(self.zip, 'a') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            archive.writestr(info, 'outside')
        with self.assertRaises(ValueError):
            artifact.validate_release_zip(self.zip, self.version)
        self.write_zip(extras={'parent': b'file', 'parent/child': b'child'})
        with self.assertRaises(ValueError):
            artifact.validate_release_zip(self.zip, self.version)

    def test_missing_receipt_does_not_repair_or_write_anything(self):
        self.seal()
        self.receipt.unlink()
        before = self.checksum.read_bytes()
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.verify()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.checksum.read_bytes(), before)

    def test_missing_or_bad_checksum_is_not_created_or_overwritten(self):
        self.seal()
        self.checksum.unlink()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.verify()
        self.assertFalse(self.checksum.exists())
        for text in ('0' * 64 + '  ' + self.zip.name + '\n',
                     hashlib.sha256(self.zip.read_bytes()).hexdigest() + '  other.zip\n'):
            self.checksum.write_text(text, encoding='ascii')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                self.verify()
            self.assertEqual(self.checksum.read_text(encoding='ascii'), text)

    def test_replaced_zip_rejected_even_if_checksum_was_regenerated(self):
        self.seal()
        self.write_zip(extras={'new-dependency.dll': b'changed archive'})
        self.checksum.write_text(hashlib.sha256(self.zip.read_bytes()).hexdigest()
                                 + '  ' + self.zip.name + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.verify()

    def test_source_changed_during_build_refuses_sealing(self):
        (self.root / 'main.py').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.seal()
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.checksum.exists())

    def test_source_changes_after_build_refuse_release_but_docs_are_allowed(self):
        self.seal()
        (self.root / 'README.md').write_text('post-build documentation', encoding='utf-8')
        (self.root / 'docs').mkdir()
        (self.root / 'docs' / 'validation.md').write_text('approved', encoding='utf-8')
        self.verify()
        (self.root / 'main.py').write_text('new code', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.verify()

    def test_added_source_file_and_changed_build_script_invalidate_receipt(self):
        self.seal()
        extra = self.root / 'new_helper.py'
        extra.write_text('new input', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.verify()
        extra.unlink()
        (self.root / 'build.ps1').write_text('modified gate', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.verify()

    def test_malformed_or_wrong_receipt_rejected(self):
        sealed = self.seal()
        for data in ([], {}, {'schema': 0}, dict(sealed, version='old'),
                     dict(sealed, exe_sha256='0' * 64)):
            with self.subTest(data=data):
                self.receipt.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    self.verify()

    def test_candidate_can_be_sealed_but_not_published_under_candidate_name(self):
        candidate = self.build / 'candidate.zip'
        self.zip.replace(candidate)
        artifact.seal_candidate(candidate, self.version, self.root,
                                self.snapshot, self.checksum, self.receipt,
                                acceptance=self.acceptance(candidate))
        with self.assertRaisesRegex(ValueError, 'name'):
            artifact.verify_release(candidate, self.version, self.root,
                                    self.checksum, self.receipt)
        candidate.replace(self.zip)
        self.verify()

    def test_receipt_output_must_remain_in_ignored_build_directory(self):
        with self.assertRaisesRegex(ValueError, 'build'):
            artifact.seal_candidate(self.zip, self.version, self.root, self.snapshot,
                                    self.checksum, self.root / 'receipt.json')

    def test_cli_reports_errors_without_importing_main(self):
        self.write_zip(version='6.0.0-beta.8')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'release_artifact.py'),
                                 'validate', '--zip', str(self.zip), '--version', self.version],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('version', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


    def test_seal_requires_all_successful_acceptance_bound_to_exact_bytes(self):
        valid = self.acceptance()
        bad = [None, {}, dict(valid, version='old'),
               dict(valid, zip_sha256='0' * 64), dict(valid, exe_sha256='0' * 64)]
        for check in artifact.CHECKS:
            bad.extend(dict(valid, checks=dict(valid['checks'], **{check: value}))
                       for value in (False, 0, 1, 'passed', None))
        for evidence in bad:
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(ValueError, 'acceptance'):
                    artifact.seal_candidate(self.zip, self.version, self.root,
                                            self.snapshot, self.checksum, self.receipt,
                                            acceptance=evidence)
                self.assertFalse(self.checksum.exists())
                self.assertFalse(self.receipt.exists())

    def test_acceptance_from_earlier_zip_cannot_seal_replacement(self):
        evidence = self.acceptance()
        self.write_zip(extras={'dependency.dll': b'replaced'})
        with self.assertRaisesRegex(ValueError, 'acceptance'):
            artifact.seal_candidate(self.zip, self.version, self.root,
                                    self.snapshot, self.checksum, self.receipt,
                                    acceptance=evidence)

    def test_sealing_never_overwrites_existing_evidence(self):
        self.seal()
        before = self.receipt.read_bytes(), self.checksum.read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.seal()
        self.assertEqual(before, (self.receipt.read_bytes(), self.checksum.read_bytes()))

    def test_release_requires_passed_acceptance_in_receipt(self):
        sealed = self.seal()
        for evidence in (None, {}, dict(sealed['acceptance'], checks={})):
            self.receipt.write_text(json.dumps(dict(sealed, acceptance=evidence)), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'acceptance'):
                self.verify()

    def test_unzip_compares_all_files_not_only_executable(self):
        directory = self.build / 'extracted'
        with zipfile.ZipFile(self.zip) as archive:
            archive.extractall(directory)
        artifact.check_extracted(self.zip, directory, self.version)
        (directory / 'LICENSE').write_text('different', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'extracted'):
            artifact.check_extracted(self.zip, directory, self.version)

    def test_test_changes_after_build_do_not_invalidate_receipt(self):
        self.seal()
        (self.root / 'tests').mkdir()
        test_file = self.root / 'tests' / 'test_new.py'
        test_file.write_text('new acceptance test', encoding='utf-8')
        self.verify()
        test_file.write_text('updated test and results', encoding='utf-8')
        self.verify()

    def test_crc_failure_in_nonrequired_member_is_rejected(self):
        # Stored data allows deterministic corruption without breaking ZIP metadata.
        with zipfile.ZipFile(self.zip, 'a') as archive:
            archive.writestr('optional.dll', b'original payload', compress_type=zipfile.ZIP_STORED)
        data = self.zip.read_bytes()
        self.zip.write_bytes(data.replace(b'original payload', b'modified payload'))
        with self.assertRaisesRegex(ValueError, 'archive'):
            artifact.validate_release_zip(self.zip, self.version)

    def test_cli_cannot_verify_without_explicit_commit(self):
        self.seal()
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'release_artifact.py'),
                                 'verify', '--zip', str(self.zip), '--version', self.version,
                                 '--root', str(self.root), '--checksum', str(self.checksum),
                                 '--receipt', str(self.receipt)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--commit', result.stderr)

    def test_safe_paths_reject_boundary_and_prefix_sibling(self):
        for target in (self.root, self.root.parent / (self.root.name + '-other') / 'a'):
            with self.assertRaisesRegex(ValueError, 'boundary'):
                artifact.safe_path(target, self.root)
        self.assertEqual(artifact.safe_path(self.build / '[literal].zip', self.root),
                         self.build / '[literal].zip')

    def test_publish_commit_and_dirty_worktree_gate_without_creating_commits(self):
        commit = 'a' * 40
        tracked = b''.join(b'H ' + name.encode() + b'\0'
                           for name in artifact.source_snapshot(self.root)['files'])
        def git_response(root, *args):
            if args[0] == 'ls-files':
                return tracked
            if args[0] == 'status':
                return b''
            if args[-1] == '--show-toplevel':
                return os.fsencode(self.root) + b'\n'
            return (commit + '\n').encode()
        absent_tag = subprocess.CompletedProcess([], 1, stdout=b'', stderr=b'')
        with mock.patch.object(artifact, '_git', side_effect=git_response), \
                mock.patch.object(artifact.subprocess, 'run', return_value=absent_tag):
            artifact.verify_repository(self.root, commit)
            with self.assertRaisesRegex(ValueError, 'commit'):
                artifact.verify_repository(self.root, 'b' * 40)
        for dirty in (b' M main.py\0', b'M  main.py\0', b'?? extra.py\0'):
            def response(root, *args):
                return dirty if args[0] == 'status' else git_response(root, *args)
            with mock.patch.object(artifact, '_git', side_effect=response):
                with self.assertRaisesRegex(ValueError, 'clean'):
                    artifact.verify_repository(self.root, commit)
        for status in (b's main.py\0', b'S main.py\0'):
            def response(root, *args):
                return status if args[0] == 'ls-files' else git_response(root, *args)
            with mock.patch.object(artifact, '_git', side_effect=response):
                with self.assertRaisesRegex(ValueError, 'hidden'):
                    artifact.verify_repository(self.root, commit)
        with mock.patch.object(artifact, '_git', side_effect=git_response), \
                mock.patch.object(artifact.subprocess, 'run', return_value=
                                  subprocess.CompletedProcess([], 0, stdout=b'b' * 40 + b'\n')):
            with self.assertRaisesRegex(ValueError, 'tag'):
                artifact.verify_repository(self.root, commit)


class PowerShellGateTests(unittest.TestCase):
    def test_containment_and_junction_guards_without_running_build(self):
        with tempfile.TemporaryDirectory(prefix='release-paths-') as temporary:
            root = Path(temporary)
            workspace = root / 'workspace[1]'
            outside = root / 'workspace1-other'
            workspace.mkdir()
            outside.mkdir()
            (outside / 'keep.txt').write_text('untouched', encoding='utf-8')
            tree = workspace / 'build'
            tree.mkdir()
            link = tree / 'escape'
            literal = workspace / 'candidate[1].zip'
            neighbor = workspace / 'candidate1.zip'
            literal.write_bytes(b'candidate')
            neighbor.write_bytes(b'leave me alone')
            ps = lambda path: "'" + str(path).replace("'", "''") + "'"
            # Load only the path guard from its AST, never dot-source the build.
            command = (
                "$ErrorActionPreference='Stop'; $tokens=$null; $errors=$null; "
                f"$ast=[Management.Automation.Language.Parser]::ParseFile({ps(ROOT / 'build.ps1')}, [ref]$tokens, [ref]$errors); "
                "$guard=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] "
                "-and $n.Name -eq 'Assert-PathWithin'}, $true); Invoke-Expression $guard.Extent.Text; "
                f"$root={ps(workspace)}; $tree={ps(tree)}; $outside={ps(outside)}; "
                "$checked=Assert-PathWithin $tree $root -Recurse; "
                "if ($checked -ne $tree) { throw 'literal path changed' }; "
                f"$from=Assert-PathWithin {ps(literal)} $root; "
                f"$to=Assert-PathWithin {ps(workspace / 'promoted[1].zip')} $root; "
                "Move-Item -LiteralPath $from -Destination $to; "
                "if (-not (Test-Path -LiteralPath $to -PathType Leaf)) { throw 'literal move failed' }; "
                "$to=Assert-PathWithin $to $root; Remove-Item -LiteralPath $to -Force; "
                f"if (-not (Test-Path -LiteralPath {ps(neighbor)})) {{ throw 'wildcard deletion' }}; "
                "foreach ($bad in @($root, $outside, (Join-Path $root '..\\workspace1-other'))) { "
                "$rejected=$false; try { $null=Assert-PathWithin $bad $root -Recurse } catch { $rejected=$true }; "
                "if (-not $rejected) { throw 'containment failed' } }; "
                f"New-Item -ItemType Junction -Path {ps(link)} -Target $outside | Out-Null; "
                f"foreach ($bad in @($tree, {ps(link)}, {ps(link / 'missing')})) {{ "
                "$rejected=$false; try { $null=Assert-PathWithin $bad $root -Recurse } catch { $rejected=$true }; "
                "if (-not $rejected) { throw 'reparse escape accepted' } }"
            )
            result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((outside / 'keep.txt').read_text(encoding='utf-8'), 'untouched')
            self.assertFalse(literal.exists())
            self.assertEqual(neighbor.read_bytes(), b'leave me alone')
            with self.assertRaisesRegex(ValueError, 'reparse'):
                artifact.safe_path(link / 'missing', workspace)

    def test_scripts_parse_without_execution_and_paths_are_literal(self):
        for filename in ('build.ps1', 'create_release.ps1'):
            with self.subTest(filename=filename):
                path = str(ROOT / filename).replace("'", "''")
                command = ("$tokens=$null; $errors=$null; "
                           f"$ast=[Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors); "
                           "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }; "
                           "$names=@('Test-Path','Remove-Item','Move-Item','Copy-Item','Get-ChildItem',"
                           "'Get-FileHash','Get-Item','Get-Content','Set-Content'); "
                           "$bad=$ast.FindAll({param($node) $node -is [Management.Automation.Language.CommandAst] "
                           "-and $node.GetCommandName() -in $names -and "
                           "-not ($node.CommandElements | Where-Object { $_ -is "
                           "[Management.Automation.Language.CommandParameterAst] -and $_.ParameterName -eq 'LiteralPath' })}, $true); "
                           "if ($bad.Count) { $bad.Extent.Text; exit 2 }")
                result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_receipt_is_last_promotion_and_release_never_writes_checksum(self):
        build = (ROOT / 'build.ps1').read_text(encoding='utf-8-sig')
        release = (ROOT / 'create_release.ps1').read_text(encoding='utf-8-sig')
        self.assertNotIn('validate_update_zip', release)
        self.assertIn('release_artifact.py verify', release)
        self.assertNotIn('Set-Content', release)
        self.assertNotIn('git status', release)
        self.assertLess(build.index('release_artifact.py validate'), build.index('Move-Item -LiteralPath $candidateZip'))
        self.assertLess(build.index('release_artifact.py seal'), build.index('Move-Item -LiteralPath $candidateZip'))
        self.assertLess(build.index('Move-Item -LiteralPath $candidateZip'), build.index('Move-Item -LiteralPath $candidateReceipt'))
        self.assertLess(release.index('release_artifact.py verify'), release.index('Invoke-RestMethod'))
        self.assertIn('-WindowStyle Hidden', build)
        self.assertIn('ReparsePoint', build)
        self.assertIn('check-extracted', build)
        self.assertLess(build.index('Invoke-Smoke $extractedExe'), build.index('release_artifact.py seal'))
        self.assertLess(release.index('release_artifact.py verify'), release.index('$token ='))
        self.assertIn('--commit $Commit', release)
        self.assertIn('$remoteCommit.sha -ne $Commit', release)
        self.assertIn('$remoteTag.sha -ne $Commit', release)


if __name__ == '__main__':
    unittest.main()
