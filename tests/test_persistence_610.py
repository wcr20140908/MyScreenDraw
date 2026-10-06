"""6.1.0 project and autosave persistence safety regressions (no visible UI)."""
import base64
import gzip
import json
import os
import struct
import tempfile
import unittest
import uuid
import zlib
from pathlib import Path
from unittest.mock import patch

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


class ProjectWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
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


if __name__ == "__main__":
    unittest.main()
