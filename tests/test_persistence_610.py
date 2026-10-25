"""6.1.0 project and autosave persistence safety regressions (no visible UI)."""
import base64
import gzip
import json
import os
import stat
import struct
import tempfile
import time
import unittest
import uuid
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import persistence


def png(width=2, height=2):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    pixels = (b"\x00" + b"\xff\x00\x00" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def project(*, kind=persistence.PROJECT_KIND, image=None):
    page = {"segments": [], "texts": [], "shapes": [], "images": []}
    if image is not None:
        page["images"] = [{"id": "img", "pos": [0, 0], "size": [2, 2], "data": image}]
    return persistence.make_project_data(pages=[page], current_page=0, whiteboard_mode=True,
                                         board_style="WHITE", app_version="6.1.0", kind=kind)


class ProjectTemporaryDirectory(tempfile.TemporaryDirectory):
    """Retry only a transient empty-directory Windows removal failure."""
    def __init__(self, *, retry_timeout=1.0):
        super().__init__(prefix="myscreendraw-persistence-")
        self._owned_name = os.path.abspath(self.name)
        try:
            status = self._ordinary_directory_status()
        except (OSError, ValueError):
            self._finalizer.detach()
            raise
        self._owned_identity = (status.st_dev, status.st_ino)
        self._owned_parent = Path(self.name).parent.resolve()
        self._owned_real_path = self._owned_parent / Path(self.name).name
        self._retry_timeout = retry_timeout

    def _ordinary_directory_status(self):
        status = os.lstat(self.name)
        reparse = getattr(status, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode) or reparse:
            raise ValueError("Temporary directory is not an ordinary directory")
        return status

    def _assert_owned_directory(self):
        if os.path.abspath(self.name) != self._owned_name:
            raise ValueError("Temporary directory path changed")
        try:
            status = self._ordinary_directory_status()
        except FileNotFoundError:
            return False
        resolved = Path(self.name).resolve()
        if resolved.parent != self._owned_parent:
            raise ValueError("Temporary directory escaped its parent")
        if ((status.st_dev, status.st_ino) != self._owned_identity
                or resolved != self._owned_real_path):
            raise ValueError("Temporary directory ownership changed")
        return True

    def cleanup(self):
        try:
            self._assert_owned_directory()
        except (OSError, ValueError):
            # A later finalizer must not bypass the ownership check.
            self._finalizer.detach()
            raise
        try:
            super().cleanup()
        except OSError as original_error:
            if getattr(original_error, "winerror", None) != 145:
                raise
            deadline = time.monotonic() + self._retry_timeout
            while True:
                if not self._assert_owned_directory():
                    return
                with os.scandir(self.name) as entries:
                    if next(entries, None) is not None:
                        raise original_error
                try:
                    os.rmdir(self.name)
                    return
                except OSError as error:
                    if getattr(error, "winerror", None) != 145 or time.monotonic() >= deadline:
                        raise
                time.sleep(0.01)


def project_test_directory(*, retry_timeout=1.0):
    return ProjectTemporaryDirectory(retry_timeout=retry_timeout)


class ProjectWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = project_test_directory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return str(Path(self.tmp.name) / name)

    def assert_no_temp(self):
        self.assertFalse(list(Path(self.tmp.name).glob(".*.tmp")))

    def test_project_writer_roundtrip_and_keeps_previous_on_validation_error(self):
        path = self.path("lesson.msd")
        data = project()
        data["pages"][0].update(page_id=str(uuid.uuid4()), name="第一课")
        persistence.atomic_write_project(path, data)
        original = Path(path).read_bytes()
        self.assertEqual(persistence.normalize_project_data(persistence.read_json_maybe_gz(path),
                         kind=persistence.PROJECT_KIND)["pages"][0]["name"], "第一课")
        data["pages"][0]["segments"] = [{"p1": [float("nan"), 0], "p2": [0, 0]}]
        with self.assertRaises(ValueError):
            persistence.atomic_write_project(path, data)
        self.assertEqual(Path(path).read_bytes(), original)
        self.assert_no_temp()

    def test_reader_detects_compression_instead_of_filename(self):
        plain = self.path("plain.msd.gz")
        compressed = self.path("autosave.msd")
        persistence.atomic_write_project(plain, project())
        persistence.atomic_write_autosave(compressed, project(kind=persistence.AUTOSAVE_KIND))
        self.assertEqual(persistence.read_json_maybe_gz(plain)["kind"], persistence.PROJECT_KIND)
        self.assertEqual(persistence.read_json_maybe_gz(compressed)["kind"], persistence.AUTOSAVE_KIND)

    def test_autosave_writer_roundtrip_and_rejects_wrong_kind(self):
        path = self.path("auto.json.gz")
        persistence.atomic_write_autosave(path, project(kind=persistence.AUTOSAVE_KIND))
        original = Path(path).read_bytes()
        self.assertEqual(persistence.normalize_project_data(persistence.read_json_maybe_gz(path),
                         kind=persistence.AUTOSAVE_KIND)["kind"], persistence.AUTOSAVE_KIND)
        with self.assertRaises(ValueError):
            persistence.atomic_write_autosave(path, project())
        self.assertEqual(Path(path).read_bytes(), original)
        self.assert_no_temp()

    def test_invalid_image_and_oversized_base64_rejected_before_replace(self):
        path = self.path("lesson.msd")
        persistence.atomic_write_project(path, project())
        original = Path(path).read_bytes()
        for data in ("not-base64!!!", base64.b64encode(b"not an image").decode(),
                     base64.b64encode(png()[:-10]).decode(), "A" * (persistence.MAX_IMAGE_DATA_BYTES + 1)):
            with self.subTest(data=data[:15]), self.assertRaises(ValueError):
                persistence.atomic_write_project(path, project(image=data))
            self.assertEqual(Path(path).read_bytes(), original)
            self.assert_no_temp()

    def test_plain_size_boundary_is_exact_utf8_byte_count(self):
        path = self.path("lesson.msd")
        data = project()
        data["metadata"] = {"title": "汉字"}
        raw = json.dumps(persistence.normalize_project_data(data, kind=persistence.PROJECT_KIND),
                         ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        with patch.object(persistence, "MAX_PROJECT_BYTES", len(raw)):
            persistence.atomic_write_project(path, data)
        self.assertEqual(len(Path(path).read_bytes()), len(raw))
        with patch.object(persistence, "MAX_PROJECT_BYTES", len(raw) - 1):
            with self.assertRaises(ValueError):
                persistence.atomic_write_project(path, data)
        self.assertEqual(len(Path(path).read_bytes()), len(raw))
        self.assert_no_temp()

    def test_compressed_writer_rejects_decompressed_overlimit(self):
        path = self.path("auto.json.gz")
        data = project(kind=persistence.AUTOSAVE_KIND)
        persistence.atomic_write_autosave(path, data)
        original = Path(path).read_bytes()
        data["metadata"] = {"title": "a" * 3000}
        with patch.object(persistence, "MAX_PROJECT_BYTES", 1024):
            with self.assertRaises(ValueError):
                persistence.atomic_write_autosave(path, data)
        self.assertEqual(Path(path).read_bytes(), original)
        self.assert_no_temp()

    def test_write_failure_preserves_previous_and_cleans_temp(self):
        path = self.path("lesson.msd")
        persistence.atomic_write_project(path, project())
        original = Path(path).read_bytes()
        with patch.object(persistence.os, "replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                persistence.atomic_write_project(path, project())
        self.assertEqual(Path(path).read_bytes(), original)
        self.assert_no_temp()

    def test_valid_image_is_decodable_and_runtime_revision_is_not_written(self):
        path = self.path("lesson.msd")
        encoded = base64.b64encode(png()).decode("ascii")
        data = project(image=encoded)
        data["pages"][0]["_revision"] = 12
        persistence.atomic_write_project(path, data)
        loaded = persistence.normalize_project_data(persistence.read_json_maybe_gz(path),
                                                     kind=persistence.PROJECT_KIND)
        self.assertEqual(loaded["pages"][0]["images"][0]["data"], encoded)
        self.assertNotIn("_revision", loaded["pages"][0])

    def test_gzip_read_limit_exact_boundary_and_over(self):
        path = self.path("auto.json.gz")
        data = project(kind=persistence.AUTOSAVE_KIND)
        persistence.atomic_write_autosave(path, data)
        decompressed_size = len(gzip.decompress(Path(path).read_bytes()))
        with patch.object(persistence, "MAX_PROJECT_BYTES", decompressed_size):
            self.assertEqual(persistence.read_json_maybe_gz(path)["kind"],
                             persistence.AUTOSAVE_KIND)
        with patch.object(persistence, "MAX_PROJECT_BYTES", decompressed_size - 1):
            with self.assertRaises(ValueError):
                persistence.read_json_maybe_gz(path)

    def test_bad_payload_with_no_previous_target_creates_nothing(self):
        path = self.path("auto.json.gz")
        with self.assertRaises(ValueError):
            persistence.atomic_write_autosave(path, project(image="broken",
                                        kind=persistence.AUTOSAVE_KIND))
        self.assertFalse(Path(path).exists())
        self.assert_no_temp()

    def test_duplicate_page_id_is_rejected_for_copy(self):
        data = project()
        data["pages"][0]["page_id"] = str(uuid.uuid4())
        data["pages"].append(dict(data["pages"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate page ID"):
            persistence.atomic_write_project(self.path("lesson.msd"), data)
        self.assert_no_temp()

    def test_page_metadata_invalid_types_and_uuid_rejected(self):
        data = project()
        for fields in ({"page_id": "not-uuid"}, {"page_id": 4},
                       {"name": 3}, {"name": "x" * 300}):
            with self.subTest(fields=fields):
                data["pages"][0].update(fields)
                with self.assertRaises(ValueError):
                    persistence.atomic_write_project(self.path("lesson.msd"), data)
                for key in fields:
                    del data["pages"][0][key]
        self.assert_no_temp()


class ProjectDirectoryCleanupTests(unittest.TestCase):
    def test_empty_directory_145_is_retried_and_completely_removed(self):
        temporary = project_test_directory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "lesson.msd").write_bytes(b"finished project")
        native_rmdir = os.rmdir
        calls = []
        error = OSError(145, "Directory is not empty", str(root))
        error.winerror = 145

        def pending_delete_once(path, *args, **kwargs):
            if os.path.abspath(path) == os.path.abspath(root):
                calls.append(path)
                if len(calls) == 1:
                    self.assertEqual(list(root.iterdir()), [])
                    raise error
            return native_rmdir(path, *args, **kwargs)

        with patch.object(os, "rmdir", side_effect=pending_delete_once):
            temporary.cleanup()
        self.assertEqual(len(calls), 2)
        self.assertFalse(root.exists())

    def test_persistent_145_has_deadline_and_is_not_ignored(self):
        temporary = project_test_directory(retry_timeout=0.03)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        error = OSError(145, "Directory is not empty", str(root))
        error.winerror = 145
        clock = Mock()
        clock.monotonic.side_effect = [0.0, 0.01, 0.04]
        with patch(__name__ + ".time", clock), patch.object(os, "rmdir", side_effect=error) as remove:
            with self.assertRaises(OSError) as raised:
                temporary.cleanup()
        self.assertIs(raised.exception, error)
        self.assertEqual(remove.call_count, 3)
        clock.sleep.assert_called_once()
        self.assertTrue(root.is_dir())
        self.assertEqual(list(root.iterdir()), [])

    def test_new_file_after_recursive_cleanup_is_preserved_and_fails(self):
        temporary = project_test_directory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        error = OSError(145, "Directory is not empty", str(root))
        error.winerror = 145
        unexpected = root / "unexpected-writer.txt"

        def write_during_remove(path, *args, **kwargs):
            unexpected.write_bytes(b"must not be hidden by cleanup")
            raise error

        with patch.object(os, "rmdir", side_effect=write_during_remove) as remove:
            with self.assertRaises(OSError) as raised:
                temporary.cleanup()
        self.assertIs(raised.exception, error)
        self.assertEqual(remove.call_count, 1)
        self.assertEqual(unexpected.read_bytes(), b"must not be hidden by cleanup")

    def test_permission_error_is_not_retried_or_ignored(self):
        temporary = project_test_directory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        error = PermissionError(13, "Access denied", str(root))
        error.winerror = 5
        with patch.object(tempfile.TemporaryDirectory, "cleanup", side_effect=error) as cleanup:
            with self.assertRaises(PermissionError) as raised:
                temporary.cleanup()
        self.assertIs(raised.exception, error)
        cleanup.assert_called_once()
        self.assertTrue(root.is_dir())

    def test_changed_path_does_not_delete_another_directory(self):
        temporary = project_test_directory()
        self.addCleanup(temporary.cleanup)
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        marker = Path(other.name) / "keep.txt"
        marker.write_bytes(b"not owned")
        owned_name = temporary.name
        temporary.name = other.name
        try:
            with self.assertRaisesRegex(ValueError, "path changed"):
                temporary.cleanup()
            self.assertEqual(marker.read_bytes(), b"not owned")
        finally:
            temporary.name = owned_name

    def test_replaced_directory_identity_is_not_deleted(self):
        temporary = project_test_directory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        parked = root.with_name(root.name + "-original")
        self.assertEqual(parked.resolve().parent, root.resolve().parent)
        os.rename(root, parked)
        root.mkdir()
        try:
            with self.assertRaisesRegex(ValueError, "ownership changed"):
                temporary.cleanup()
            self.assertTrue(root.is_dir())
            self.assertTrue(parked.is_dir())
        finally:
            os.rmdir(root)
            os.rename(parked, root)


if __name__ == "__main__":
    unittest.main()
