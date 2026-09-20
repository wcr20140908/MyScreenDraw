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
                {"name": "preview.zip", "browser_download_url": "https://x/preview.zip"}
            ]},
            {"tag_name": "v6.0.0", "prerelease": False, "assets": [
                {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
                {"name": "MyScreenDraw-v6.0.0-windows-x64.zip", "browser_download_url": "https://x/stable.zip"},
            ]},
        ]
        with patch("urllib.request.urlopen", return_value=self._release_response(releases)):
            release, error = main.fetch_release("stable", url="https://example.invalid/releases")
        self.assertIsNone(error)
        self.assertEqual(release["tag"], "v6.0.0")
        self.assertEqual(release["download_url"], "https://x/stable.zip")
        self.assertFalse(release["prerelease"])

    def test_preview_channel_accepts_first_preview_with_zip(self):
        releases = [{"tag_name": "v6.0.0-beta.6", "prerelease": True, "assets": [
            {"name": "MyScreenDraw-v6.0.0-beta.6-windows-x64.zip", "browser_download_url": "https://x/preview.zip"}
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

    def test_update_batch_checks_extract_and_copy_failures(self):
        with tempfile.TemporaryDirectory() as root:
            batch = main.make_update_batch(os.path.join(root, "folder with spaces", "update.zip"),
                                           os.path.join(root, "install with spaces"))
            try:
                text = Path(batch).read_text(encoding="utf-8")
                self.assertIn("$ErrorActionPreference='Stop'", text)
                self.assertIn("if errorlevel 1 goto fail", text)
                self.assertIn("if errorlevel 8 goto fail", text)
                self.assertIn("MSD_ZIP=", text)
                self.assertIn("MSD_INSTALL=", text)
            finally:
                updater_root = Path(batch).parent
                for child in updater_root.iterdir():
                    child.unlink()
                updater_root.rmdir()

        with tempfile.TemporaryDirectory() as root:
            archive = os.path.join(root, "update.zip")
            batch = main.make_update_batch(archive, root)
            try:
                text = Path(batch).read_text(encoding="utf-8")
                self.assertIn("/XD", text)
                self.assertIn("data", text)
                self.assertIn("exports", text)
                self.assertIn("config.json", text)
                self.assertIn("roster.json", text)
                self.assertIn("events.jsonl", text)
                self.assertIn("robocopy", text)
            finally:
                updater_root = Path(batch).parent
                for child in updater_root.iterdir():
                    child.unlink()
                updater_root.rmdir()


if __name__ == "__main__":
    unittest.main()
