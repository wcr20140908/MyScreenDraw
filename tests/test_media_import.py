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

    def test_pdf_failure_rolls_back_inserted_pages_and_undo_state(self):
        from PyQt6.QtGui import QImage, QColor

        class FailingDocument:
            class Error:
                None_ = object()

            def __init__(self, parent=None): pass
            def load(self, path): return self.Error.None_
            def pageCount(self): return 3
            def pagePointSize(self, index):
                from PyQt6.QtCore import QSizeF
                return QSizeF(72, 72)
            def render(self, index, size):
                if index == 1:
                    raise RuntimeError("render failed")
                image = QImage(size.width(), size.height(), QImage.Format.Format_RGB32)
                image.fill(QColor(0, 0, 0))
                return image
            def close(self): pass

        fake_qtpdf = types.ModuleType("PyQt6.QtPdf")
        fake_qtpdf.QPdfDocument = FailingDocument
        before = {"segments": [], "texts": [], "shapes": [], "images": []}
        panel = types.SimpleNamespace()
        canvas = types.SimpleNamespace(
            image_items=[], selected_ids=set(), whiteboard_mode=False,
            capture_page=lambda: before, undo_stack=[], redo_stack=[], last_undo_key=None,
            commit_undo=lambda snapshot: canvas.undo_stack.append(snapshot), load_page=lambda page: canvas.image_items.clear(),
            mark_content_changed=lambda: None, panel=panel, width=lambda: 1000, height=lambda: 800,
            selection_bounds=lambda: None,
        )
        panel.canvas = canvas
        panel.MAX_PDF_PAGES = 50; panel.PDF_EXPORT_DPI = 120
        panel.MAX_IMPORT_PIXELS = 2560; panel.MAX_PDF_TOTAL_PIXELS = 32_000_000
        panel.autosave_timer = types.SimpleNamespace(isActive=lambda: False)
        panel.insert_image_pixmap = self.main.ControlPanel.insert_image_pixmap.__get__(panel)
        panel.sync_selection_controls = lambda: None
        panel.position_selection_panel = lambda rect: None
        panel.update_history_ui = lambda: None
        with patch.dict(sys.modules, {"PyQt6.QtPdf": fake_qtpdf}), self.assertRaises(RuntimeError):
            self.main.ControlPanel.import_pdf(panel, "broken.pdf")
        self.assertEqual(canvas.image_items, [])
        self.assertEqual(len(canvas.undo_stack), 0)

    def test_pdf_import_batches_undo_save_and_ui_refresh(self):
        from PyQt6.QtGui import QImage, QColor

        test_case = self
        canvas = None

        class FakeDocument:
            class Error:
                None_ = object()

            def __init__(self, parent=None): pass
            def load(self, path): return self.Error.None_
            def pageCount(self): return 3
            def pagePointSize(self, index):
                from PyQt6.QtCore import QSizeF
                return QSizeF(72, 72)
            def render(self, index, size):
                # Incremental proof: page N is not rendered until pages < N have
                # already entered the canvas. The old all-pixmaps list fails this.
                test_case.assertEqual(len(canvas.image_items), index)
                image = QImage(size.width(), size.height(), QImage.Format.Format_RGB32)
                image.fill(QColor(index * 40, 0, 0))
                return image
            def close(self): pass

        fake_qtpdf = types.ModuleType("PyQt6.QtPdf")
        fake_qtpdf.QPdfDocument = FakeDocument
        before = {"segments": [], "texts": [], "shapes": [], "images": []}
        panel = types.SimpleNamespace()
        canvas = types.SimpleNamespace(
            image_items=[], selected_ids=set(), whiteboard_mode=True,
            capture_page=lambda: before,
            undo_stack=[], redo_stack=[], last_undo_key=None,
            commit_undo=lambda snapshot: canvas.undo_stack.append(snapshot),
            load_page=lambda page: None,
            mark_content_changed=lambda: None,
            panel=panel,
            width=lambda: 1000, height=lambda: 800,
            selection_bounds=lambda: None,
            save_current_page=lambda: setattr(panel, "save_calls", getattr(panel, "save_calls", 0) + 1),
        )
        panel.canvas = canvas
        panel.MAX_PDF_PAGES = 50
        panel.PDF_EXPORT_DPI = 120
        panel.MAX_IMPORT_PIXELS = 2560
        panel.MAX_PDF_TOTAL_PIXELS = 32_000_000
        panel.autosave_timer = types.SimpleNamespace(isActive=lambda: False)
        panel.insert_image_pixmap = self.main.ControlPanel.insert_image_pixmap.__get__(panel)
        panel.sync_selection_controls = lambda: setattr(panel, "sync_calls", getattr(panel, "sync_calls", 0) + 1)
        panel.position_selection_panel = lambda rect: setattr(panel, "position_calls", getattr(panel, "position_calls", 0) + 1)
        with patch.dict(sys.modules, {"PyQt6.QtPdf": fake_qtpdf}), patch.object(
                self.main.QApplication, "processEvents") as process_events:
            count = self.main.ControlPanel.import_pdf(panel, "pages.pdf")
        self.assertEqual(count, 3)
        self.assertEqual(len(canvas.undo_stack), 1)
        self.assertEqual(getattr(panel, "save_calls", 0), 1)
        self.assertEqual(getattr(panel, "sync_calls", 0), 1)
        self.assertEqual(getattr(panel, "position_calls", 0), 1)
        self.assertEqual(process_events.call_count, 3)
        self.assertEqual(len(canvas.image_items), 3)


if __name__ == "__main__":
    unittest.main()
