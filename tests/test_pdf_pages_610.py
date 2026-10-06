# SPDX-License-Identifier: GPL-3.0-or-later
"""PDF import is one board page per PDF page, with a transaction boundary."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import Mock
from PyQt6.QtCore import QSizeF
from PyQt6.QtGui import QImage, QColor
import pytest
import main
from test_document_safety_610 import document, ink
from test_export_ui_610 import Progress


class PDF:
    class Error:
        None_ = 0
    instances = []
    fail_at = None
    null_at = None
    def __init__(self, parent=None):
        self.closed = False
        self.sizes = []
        type(self).instances.append(self)
    def load(self, path): return 0
    def pageCount(self): return 3
    def pagePointSize(self, index): return QSizeF(720, 360)
    def render(self, index, size):
        self.sizes.append(size)
        if index == self.fail_at: raise RuntimeError("broken renderer")
        if index == self.null_at: return QImage()
        image = QImage(size, QImage.Format.Format_RGB32)
        image.fill(QColor(index * 60, 20, 40))
        return image
    def close(self): self.closed = True


@pytest.fixture
def pdf(monkeypatch):
    from PyQt6 import QtPdf
    PDF.fail_at = PDF.null_at = None
    PDF.instances = []
    monkeypatch.setattr(QtPdf, "QPdfDocument", PDF)
    return PDF


def test_import_creates_independent_pages_and_preserves_existing_ink(document, pdf, monkeypatch):
    panel, canvas = document
    ink(canvas, "old")
    progress = Progress()
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: progress)
    refreshed = Mock(wraps=panel.update_whiteboard_ui)
    monkeypatch.setattr(panel, "update_whiteboard_ui", refreshed)
    assert panel.import_pdf("lesson.pdf") == 3
    pages = canvas.document_pages()
    assert canvas.whiteboard_mode
    assert len(pages) == 4
    assert pages[0]["segments"][0]["id"] == "old"
    assert all(len(p["images"]) == 1 for p in pages[1:])
    assert len({p["page_id"] for p in pages}) == 4
    assert len({p["images"][0]["id"] for p in pages[1:]}) == 3
    assert canvas.current_page == 1
    assert panel.has_unsaved_changes()
    assert progress.values[-1] == 3
    assert pdf.instances[-1].closed
    assert refreshed.call_count == 1
    assert not canvas.undo_stack  # histories never cross independent page boundaries


@pytest.mark.parametrize("failure", ["fail_at", "null_at"])
def test_pdf_failed_page_preserves_document_selection_and_history(document, pdf, monkeypatch, failure):
    panel, canvas = document
    ink(canvas, "old")
    canvas.push_undo()
    canvas.selected_ids = {"old"}
    before = canvas.document_signature()
    old_undo = list(canvas.undo_stack)
    setattr(pdf, failure, 1)
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: Progress())
    with pytest.raises(RuntimeError, match="2"):
        panel.import_pdf("broken.pdf")
    assert canvas.document_signature() == before
    assert not canvas.whiteboard_mode
    assert canvas.selected_ids == {"old"}
    assert canvas.undo_stack == old_undo
    assert pdf.instances[-1].closed
    assert not panel._document_transition_active


def test_cancel_is_transactional_and_never_inserts_partial_pdf(document, pdf, monkeypatch):
    panel, canvas = document
    ink(canvas, "old")
    before = canvas.document_signature()
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: Progress(cancel_at=1))
    assert panel.import_pdf("cancel.pdf") == 0
    assert canvas.document_signature() == before
    assert not canvas.whiteboard_mode
    assert len(pdf.instances[-1].sizes) == 1
    assert pdf.instances[-1].closed


def test_import_pixel_budget_applies_to_all_staged_pages(document, pdf, monkeypatch):
    panel, canvas = document
    panel.MAX_PDF_TOTAL_PIXELS = 30_000
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: Progress())
    assert panel.import_pdf("bounded.pdf") == 3
    total = sum(p["images"][0]["pixmap"].width() * p["images"][0]["pixmap"].height()
                for p in canvas.document_pages()[1:])
    assert total <= panel.MAX_PDF_TOTAL_PIXELS


def test_real_pdf_import_and_project_reopen(document, tmp_path, monkeypatch):
    from PyQt6.QtGui import QPixmap
    from export_pipeline import export_document
    panel, canvas = document
    path = tmp_path / "real.pdf"
    def render(page, *_):
        pix = QPixmap(80, 40); pix.fill(QColor(page)); return pix
    assert export_document("PDF", path, ["red", "blue"], render).success
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: Progress())
    assert panel.import_pdf(str(path)) == 2
    project = tmp_path / "import.msd"
    assert panel.save_project(str(project))
    assert panel.open_project_from_path(str(project))
    assert len(canvas.pages) == 3
    assert all(len(p["images"]) == 1 for p in canvas.pages[1:])
