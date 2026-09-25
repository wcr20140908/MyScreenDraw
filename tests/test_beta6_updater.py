import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload


class Beta6UpdaterTests(unittest.TestCase):
    def _release_response(self, releases):
        return _Response(json.dumps(releases).encode("utf-8"))

    def test_stable_channel_skips_prereleases_and_selects_zip(self):
        releases = [
            {"tag_name": "v6.0.0-beta.6", "prerelease": True, "assets": [
                {"name": "preview.zip", "browser_download_url": "https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.0.0-beta.6/MyScreenDraw-v6.0.0-beta.6-windows-x64.zip"}
            ]},
            {"tag_name": "v6.0.0", "prerelease": False, "assets": [
                {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
                {"name": "MyScreenDraw-v6.0.0-windows-x64.zip", "browser_download_url": "https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.0.0/MyScreenDraw-v6.0.0-windows-x64.zip"},
            ]},
        ]
        with patch("urllib.request.urlopen", return_value=self._release_response(releases)):
            release, error = main.fetch_release("stable", url="https://example.invalid/releases")
        self.assertIsNone(error)
        self.assertEqual(release["tag"], "v6.0.0")
        self.assertEqual(release["download_url"], "https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.0.0/MyScreenDraw-v6.0.0-windows-x64.zip")
        self.assertFalse(release["prerelease"])

    def test_preview_channel_accepts_first_preview_with_zip(self):
        releases = [{"tag_name": "v6.0.0-beta.6", "prerelease": True, "assets": [
            {"name": "MyScreenDraw-v6.0.0-beta.6-windows-x64.zip", "browser_download_url": "https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.0.0-beta.6/MyScreenDraw-v6.0.0-beta.6-windows-x64.zip"}
        ]}]
        with patch("urllib.request.urlopen", return_value=self._release_response(releases)):
            release, error = main.fetch_release("preview", url="https://example.invalid/releases")
        self.assertIsNone(error)
        self.assertEqual(release["tag"], "v6.0.0-beta.6")
        self.assertTrue(release["prerelease"])

    def test_validate_update_zip_rejects_missing_executable_and_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            missing = os.path.join(root, "missing.zip")
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("README.txt", "no app")
            with self.assertRaisesRegex(ValueError, "missing_application"):
                main.validate_update_zip(missing)

            unsafe = os.path.join(root, "unsafe.zip")
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("MyScreenDraw.exe", "stub")
                archive.writestr("../escape.txt", "bad")
            with self.assertRaisesRegex(ValueError, "unsafe_archive"):
                main.validate_update_zip(unsafe)

    def test_validate_update_zip_accepts_nested_application(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "good.zip")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("MyScreenDraw-v6.0.0-beta.6/MyScreenDraw.exe", "stub")
                archive.writestr("MyScreenDraw-v6.0.0-beta.6/main.py", "stub")
            self.assertEqual(main.validate_update_zip(path), 2)

    def test_validate_update_zip_rejects_oversize_member_count_and_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            too_many = os.path.join(root, "too_many.zip")
            with zipfile.ZipFile(too_many, "w") as archive:
                archive.writestr("MyScreenDraw.exe", "stub")
                for index in range(main.MAX_UPDATE_ARCHIVE_MEMBERS):
                    archive.writestr(f"extra/{index}.txt", "x")
            with self.assertRaisesRegex(ValueError, "too_many_archive_members"):
                main.validate_update_zip(too_many)

            symlink = os.path.join(root, "symlink.zip")
            info = zipfile.ZipInfo("MyScreenDraw.exe")
            info.external_attr = 0o120777 << 16
            with zipfile.ZipFile(symlink, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaisesRegex(ValueError, "unsafe_archive"):
                main.validate_update_zip(symlink)

    def test_real_powershell_launch_failure_rolls_back_and_kills_old_mutant(self):
        import shutil
        import subprocess
        if sys.platform != 'win32':
            self.skipTest('Windows transaction')
        for mutant in (False, True):
            with self.subTest(mutant=mutant), tempfile.TemporaryDirectory() as root:
                install = Path(root) / 'install with spaces'
                install.mkdir()
                (install / 'MyScreenDraw.exe').write_bytes(b'old executable')
                (install / 'old.dll').write_bytes(b'old library')
                (install / 'data').mkdir()
                (install / 'data' / 'config.json').write_text('private')
                archive = Path(root) / 'update.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('MyScreenDraw.exe', b'not an executable')
                    z.writestr('new.dll', b'new library')
                script = main.make_update_batch(str(archive), str(install))
                try:
                    if mutant:
                        text = Path(script).read_text(encoding='utf-8-sig')
                        text = text.replace("    Start-Process -FilePath", "    Remove-Item -LiteralPath $backup -Recurse -Force\n    Start-Process -FilePath")
                        Path(script).write_text(text, encoding='utf-8-sig')
                    run = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script], capture_output=True, timeout=30)
                    self.assertNotEqual(run.returncode, 0)
                    restored = ((install / 'MyScreenDraw.exe').exists() and
                                (install / 'MyScreenDraw.exe').read_bytes() == b'old executable' and
                                (install / 'old.dll').exists())
                    self.assertEqual(restored, not mutant)
                    self.assertEqual((install / 'data' / 'config.json').read_text(), 'private')
                    self.assertEqual(json.loads((install / 'data' / 'update-result.json').read_text(encoding='utf-8-sig'))['status'], 'failed')
                finally:
                    shutil.rmtree(Path(script).parent, ignore_errors=True)

    def test_packaging_excludes_runtime_directories_real_zip_known_bad(self):
        import subprocess
        if sys.platform != 'win32':
            self.skipTest('Windows packaging')
        with tempfile.TemporaryDirectory() as root:
            package = Path(root) / 'package'
            package.mkdir()
            (package / 'MyScreenDraw.exe').write_bytes(b'app')
            for name in ('data', 'exports'):
                (package / name).mkdir()
            build = (ROOT / 'build.ps1').read_text(encoding='utf-8-sig')
            block = build[build.index('$updateEntries ='):build.index('$previousPlatform =', build.index('$updateEntries ='))]
            for mutant in (False, True):
                archive = Path(root) / ('bad.zip' if mutant else 'good.zip')
                if mutant:
                    # PowerShell 5.1 omits empty directories on this host. Seed a
                    # harmless runtime marker so removing the exclusion is observable.
                    (package / 'data' / 'marker.txt').write_text('runtime')
                command = "$package = '" + str(package) + "'; $zipPath = '" + str(archive) + "'; "
                command += block.replace(" | Where-Object { $_.Name -notin @('data', 'exports') }", '') if mutant else block
                subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], check=True, capture_output=True, timeout=30)
                if mutant:
                    with self.assertRaisesRegex(ValueError, 'unsafe_archive'):
                        main.validate_update_zip(str(archive))
                else:
                    self.assertEqual(main.validate_update_zip(str(archive)), 1)

    def test_worker_cancellation_and_shutdown_known_bad(self):
        import inspect
        import textwrap
        from types import SimpleNamespace
        from unittest.mock import Mock
        # Run the real read loop synchronously with deterministic interruption.
        with tempfile.TemporaryDirectory() as root:
            worker = main.UpdateDownloadWorker('https://example.invalid/update.zip')
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.headers = {}
            response.read.side_effect = [b'payload', b'']
            for mutant in (False, True):
                response.read.side_effect = [b'payload', b'']
                errors = []
                namespace = dict(main.__dict__)
                source = textwrap.dedent(inspect.getsource(main.UpdateDownloadWorker.run))
                if mutant:
                    source = source.replace('if self.isInterruptionRequested():', 'if False:')
                namespace['_https_response'] = lambda response: None
                exec(source, namespace)
                fake = SimpleNamespace(url=worker.url, isInterruptionRequested=lambda: True,
                                       finished_download=SimpleNamespace(emit=lambda path, error: errors.append((path, error))))
                with patch('urllib.request.urlopen', return_value=response), patch.object(main, '_https_response'):
                    namespace['run'](fake)
                self.assertEqual(errors[0][0] is None, not mutant)
                if errors[0][0]:
                    import shutil
                    shutil.rmtree(Path(errors[0][0]).parent)
        # A 2s timed wait must not be mistaken for termination or drop ownership.
        for mutant in (False, True):
            calls = []
            fake_worker = SimpleNamespace(requestInterruption=lambda: calls.append('interrupt'),
                                          wait=lambda *args: calls.append(('wait', args)))
            panel = SimpleNamespace(_update_worker=fake_worker, _update_download_worker=None)
            namespace = dict(main.__dict__)
            source = textwrap.dedent(inspect.getsource(main.ControlPanel.stop_update_worker))
            if mutant:
                source = source.replace('worker.wait()', 'worker.wait(2000)')
            exec(source, namespace)
            namespace['stop_update_worker'](panel)
            self.assertEqual(calls == ['interrupt', ('wait', ())], not mutant)

    def test_lazy_status_and_reentry_known_bad(self):
        import inspect
        import textwrap
        from types import SimpleNamespace
        from unittest.mock import Mock
        for mutant in (False, True):
            namespace = dict(main.__dict__)
            source = textwrap.dedent(inspect.getsource(main.ControlPanel._set_update_status))
            if mutant:
                source = source.replace('if label is not None:', 'if True:')
            exec(source, namespace)
            panel = SimpleNamespace()
            if mutant:
                with self.assertRaises(AttributeError):
                    namespace['_set_update_status'](panel, 'new release')
            else:
                namespace['_set_update_status'](panel, 'new release')
                self.assertEqual(panel._update_status_text, 'new release')
        for mutant in (False, True):
            namespace = dict(main.__dict__)
            source = textwrap.dedent(inspect.getsource(main.ControlPanel._offer_update_page))
            if mutant:
                source = source.replace('if worker is not None and worker.isRunning():', 'if False:')
            exec(source, namespace)
            panel = SimpleNamespace(_update_download_worker=SimpleNamespace(isRunning=lambda: True),
                                    _set_update_status=Mock())
            namespace['_offer_update_page'](panel, {'tag': 'v99.0.0'})
            self.assertEqual(panel._set_update_status.called, mutant)

    def test_update_batch_checks_extract_and_copy_failures(self):
        with tempfile.TemporaryDirectory() as root:
            archive = os.path.join(root, "folder with spaces", "update.zip")
            install = os.path.join(root, "install with spaces")
            os.makedirs(os.path.dirname(archive))
            os.makedirs(install)
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("MyScreenDraw.exe", "stub")
            Path(os.path.join(install, "MyScreenDraw.exe")).write_bytes(b"old")
            batch = main.make_update_batch(archive, install)
            try:
                text = Path(batch).read_text(encoding="utf-8-sig")
                self.assertIn("Expand-Archive", text)
                self.assertIn("rollback", text.lower())
                self.assertIn("backup", text.lower())
            finally:
                updater_root = Path(batch).parent
                for child in updater_root.iterdir():
                    child.unlink()
                updater_root.rmdir()

        with tempfile.TemporaryDirectory() as root:
            archive = os.path.join(root, "update.zip")
            install = os.path.join(root, "install")
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("MyScreenDraw.exe", "stub")
            Path(os.path.join(root, "MyScreenDraw.exe")).write_bytes(b"old")
            script = main.make_update_batch(archive, root)
            try:
                text = Path(script).read_text(encoding="utf-8-sig")
                self.assertIn("data", text)
                self.assertIn("backup", text.lower())
                self.assertIn("update-result.json", text)
            finally:
                updater_root = Path(script).parent
                for child in updater_root.iterdir():
                    child.unlink()
                updater_root.rmdir()


if __name__ == "__main__":
    unittest.main()
