"""Regression coverage for bounded image/PDF import and batch transaction semantics."""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MediaImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import main
        cls.main = main

    def test_bounded_image_size_respects_side_and_pixel_budget(self):
        size = self.main._bounded_image_size(10000, 5000, 2560, 8_000_000)
        self.assertLessEqual(max(size.width(), size.height()), 2560)
        self.assertLessEqual(size.width() * size.height(), 8_000_000)
        self.assertEqual(self.main._bounded_image_size(0, 100, 2560, 8_000_000).isEmpty(), True)

    def test_image_reader_is_scaled_before_read(self):
        calls = []

        class FakeSize:
            def width(self): return 10000
            def height(self): return 5000
            def isValid(self): return True

        class FakeImage:
            def isNull(self): return False
            def width(self): return 2560
            def height(self): return 1280
            def size(self): return FakeSize()
            def scaled(self, target, *args):
                self._size = target
                return self

        class FakeReader:
            def __init__(self, path): pass
            def setAutoTransform(self, value): pass
            def size(self): return FakeSize()
            def setScaledSize(self, value): calls.append(("scaled", value.width(), value.height()))
            def read(self): calls.append(("read",)); return FakeImage()

        class FakePixmap:
            def isNull(self): return False
            def width(self): return 2560
            def height(self): return 1280

        panel = types.SimpleNamespace(
            MAX_IMPORT_PIXELS=2560,
            MAX_IMAGE_PIXELS=8_000_000,
            canvas=types.SimpleNamespace(width=lambda: 1000, height=lambda: 800),
            insert_image_pixmap=lambda pixmap: pixmap,
        )
        with patch.object(self.main, "QImageReader", FakeReader), patch.object(
                self.main, "QPixmap", types.SimpleNamespace(fromImage=lambda image: FakePixmap())):
            self.main.ControlPanel.import_image_file(panel, "cloud-image.png")
        self.assertEqual(calls[0][0], "scaled")
        self.assertEqual(calls[1][0], "read")

    def test_insert_image_rejects_page_pixel_budget_overflow(self):
        class FakePixmap:
            def __init__(self, width, height): self._width, self._height = width, height
            def isNull(self): return False
            def width(self): return self._width
            def height(self): return self._height

        existing = {"pixmap": FakePixmap(4000, 8000)}
        canvas = types.SimpleNamespace(image_items=[existing], width=lambda: 1000, height=lambda: 800)
        panel = types.SimpleNamespace(canvas=canvas, MAX_PDF_TOTAL_PIXELS=32_000_000)
        with self.assertRaises(ValueError):
            self.main.ControlPanel.insert_image_pixmap(panel, FakePixmap(1, 1))

    def test_import_media_uses_non_native_dialog_for_cloud_files(self):
        panel = types.SimpleNamespace(
            timer=types.SimpleNamespace(stop=lambda: None, start=lambda ms: None),
            HEARTBEAT_MS=500,
            heartbeat_refresh=lambda: None,
        )
        seen = {}

        def fake_dialog(*args, **kwargs):
            seen["options"] = kwargs.get("options")
            return "", ""

        with patch.object(self.main.QFileDialog, "getOpenFileName", side_effect=fake_dialog):
            self.main.ControlPanel.import_media(panel)
        self.assertEqual(seen["options"], self.main.QFileDialog.Option.DontUseNativeDialog)

    # PDF no longer inserts every page into the active image list. The stronger
    # actual-widget transactional/independent-page tests live in test_pdf_pages_610.


if __name__ == "__main__":
    unittest.main()
