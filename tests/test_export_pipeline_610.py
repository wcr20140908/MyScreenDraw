"""Offscreen, real Qt codec regression tests for the streaming export engine."""
import gc
import importlib.util
import sys
import os
from pathlib import Path
import weakref

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtGui import QColor, QGuiApplication, QPdfWriter, QPixmap
from PyQt6.QtPdf import QPdfDocument

import export_pipeline as engine


@pytest.fixture(scope="module", autouse=True)
def gui_app():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def render(page, index, total):
    pix = QPixmap(180, 120)
    pix.fill(QColor(page))
    return pix


def assert_no_temps(directory: Path):
    assert not list(directory.glob(".msd-export-*"))


def test_png_real_readback_original_page_numbers_and_failure(tmp_path):
    target = tmp_path / "lesson.png"

    def render_with_failure(page, index, total):
        if index == 2:
            raise RuntimeError("broken drawing")
        return render(page, index, total)

    result = engine.export_document("PNG", target, ["red", "green", "blue"], render_with_failure)
    assert result.total == 3
    assert result.complete and not result.success and not result.cancelled
    assert result.exported_indices == (1, 3)
    assert result.exported_paths == (str(tmp_path / "lesson_p1.png"), str(tmp_path / "lesson_p3.png"))
    assert [(f.page, f.detail) for f in result.failures] == [(2, "broken drawing")]
    assert QPixmap(result.exported_paths[0]).toImage().pixelColor(0, 0) == QColor("red")
    assert QPixmap(result.exported_paths[1]).toImage().pixelColor(0, 0) == QColor("blue")
    assert not (tmp_path / "lesson_p2.png").exists()
    assert_no_temps(tmp_path)


def test_png_null_and_save_false_preserve_old_files(tmp_path, monkeypatch):
    target = tmp_path / "drawing.png"
    (tmp_path / "drawing_p2.png").write_bytes(b"OLD")
    real_save = QPixmap.save

    def fail_blue(self, *args, **kwargs):
        if self.toImage().pixelColor(0, 0) == QColor("blue"):
            return False
        return real_save(self, *args, **kwargs)

    monkeypatch.setattr(QPixmap, "save", fail_blue)

    def renderer(page, index, total):
        return QPixmap() if index == 1 else render(page, index, total)

    result = engine.export_document("PNG", target, ["red", "green", "blue"], renderer)
    assert [(f.page, f.detail) for f in result.failures] == [
        (1, "renderer returned a null or invalid QPixmap"),
        (3, "QPixmap.save returned false"),
    ]
    assert result.exported_indices == (2,)
    assert QPixmap(str(tmp_path / "drawing_p2.png")).toImage().pixelColor(0, 0) == QColor("green")
    assert not result.success and result.complete
    assert_no_temps(tmp_path)


def test_png_failed_save_never_overwrites_existing_target(tmp_path, monkeypatch):
    dest = tmp_path / "existing.png"
    dest.write_bytes(b"OLD")
    monkeypatch.setattr(QPixmap, "save", lambda self, *args: False)
    result = engine.export_document("PNG", dest, ["red"], render)
    assert result.failures[0].page == 1 and not result.exported_paths
    assert dest.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_real_page_count_and_one_pixmap_at_a_time(tmp_path):
    target = tmp_path / "lesson.pdf"
    weak_images = []
    events = []

    def tracked(page, index, total):
        assert (index, total) == (page, 4)
        assert all(image() is None for image in weak_images), "previous bitmap still retained"
        pix = render("red", index, total)
        weak_images.append(weakref.ref(pix))
        return pix

    result = engine.export_document("PDF", target, [1, 2, 3, 4], tracked,
                                    lambda i, n, phase: events.append((i, n, phase)))
    assert result.success and result.complete and not result.failures
    assert result.exported_indices == (1, 2, 3, 4)
    assert result.exported_paths == (str(target),)
    assert events == [(i, 4, phase) for i in range(1, 5) for phase in ("before", "after")]
    document = QPdfDocument(None)
    try:
        assert document.load(str(target)) == QPdfDocument.Error.None_
        assert document.pageCount() == 4
    finally:
        document.close()
    gc.collect()
    assert all(image() is None for image in weak_images)
    assert_no_temps(tmp_path)


def test_pdf_render_failure_attempts_later_pages_but_preserves_old_target(tmp_path):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")
    calls = []

    def intermittent(page, index, total):
        calls.append(index)
        if index == 2:
            raise RuntimeError("render error")
        return render("green", index, total)

    result = engine.export_document("PDF", target, [None] * 3, intermittent)
    assert calls == [1, 2, 3]
    assert result.complete and not result.success
    assert result.failures == (engine.ExportFailure(2, "render error"),)
    assert result.exported_indices == (1, 3)
    assert len(result.exported_paths) == 1
    assert Path(result.exported_paths[0]).name.startswith("old_partial_")
    partial = QPdfDocument(None)
    try:
        assert partial.load(result.exported_paths[0]) == QPdfDocument.Error.None_
        assert partial.pageCount() == 2
    finally:
        partial.close()
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_null_discarded_without_target(tmp_path):
    target = tmp_path / "missing.pdf"
    result = engine.export_document("PDF", target, [1, 2],
                                    lambda p, i, n: QPixmap() if i == 2 else render("red", i, n))
    assert result.complete and not result.success and result.failures[0].page == 2
    assert not target.exists()
    assert result.exported_indices == (1,)
    assert len(result.exported_paths) == 1 and Path(result.exported_paths[0]).exists()
    assert_no_temps(tmp_path)


def test_pdf_writer_newpage_failure_is_fatal_and_does_not_replace(tmp_path, monkeypatch):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")
    calls = []

    class FailedWriter(QPdfWriter):
        def newPage(self):
            return False

    monkeypatch.setattr(engine, "QPdfWriter", FailedWriter)
    result = engine.export_document("PDF", target, [1, 2, 3],
                                    lambda page, index, total: (calls.append(index) or
                                                                render("red", index, total)))
    assert calls == [1, 2]
    assert result.failures[0].page == 2
    assert not result.complete and not result.success
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_painter_begin_failure_discards_temp_and_preserves_old(tmp_path, monkeypatch):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")

    class FailedPainter(engine.QPainter):
        def begin(self, device):
            return False

    monkeypatch.setattr(engine, "QPainter", FailedPainter)
    result = engine.export_document("PDF", target, [1], render)
    assert result.failures[0].page == 1 and not result.success
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_cancel_before_and_after_page_png_retains_committed(tmp_path):
    target = tmp_path / "pages.png"
    state = {"cancel": False}
    calls = []

    def progress(index, total, phase):
        if index == 1 and phase == "after":
            state["cancel"] = True

    def renderer(page, index, total):
        calls.append(index)
        return render("blue", index, total)

    result = engine.export_document("PNG", target, [1, 2, 3], renderer, progress,
                                    lambda: state["cancel"])
    assert result.cancelled and not result.complete and not result.success
    assert result.exported_indices == (1,) and calls == [1]
    assert Path(result.exported_paths[0]).exists()
    assert_no_temps(tmp_path)


def test_pdf_cancel_discards_temp_and_preserves_destination(tmp_path):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")
    seen = []
    state = {"cancel": False}

    def progress(index, total, phase):
        if (index, phase) == (2, "before"):
            state["cancel"] = True

    def renderer(page, index, total):
        seen.append(index)
        return render("blue", index, total)

    result = engine.export_document("PDF", target, [1, 2, 3], renderer, progress,
                                    lambda: state["cancel"])
    assert result.cancelled and not result.success and not result.complete
    assert seen == [1]
    assert not result.exported_paths and target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_empty_and_invalid_format(tmp_path):
    result = engine.export_document("PDF", tmp_path / "empty.pdf", [], render)
    assert result.total == 0 and not result.success and result.complete
    assert result.failures[0].page == 0
    with pytest.raises(ValueError):
        engine.export_document("SVG", tmp_path / "wrong.svg", [1], render)
    assert_no_temps(tmp_path)



def test_png_stream_does_not_hold_previous_page_bitmap(tmp_path):
    refs = []

    def tracked(page, index, total):
        assert all(ref() is None for ref in refs)
        pix = render("red", index, total)
        refs.append(weakref.ref(pix))
        return pix

    result = engine.export_document("PNG", tmp_path / "stream.png", list(range(12)), tracked)
    assert result.success and result.exported_indices == tuple(range(1, 13))
    assert all(ref() is None for ref in refs)
    assert_no_temps(tmp_path)


def test_png_fake_success_with_corrupt_bytes_does_not_replace_old(tmp_path, monkeypatch):
    target = tmp_path / "old.png"
    target.write_bytes(b"OLD")

    def corrupt(self, path, fmt):
        Path(path).write_bytes(b"not actually a PNG")
        return True

    monkeypatch.setattr(QPixmap, "save", corrupt)
    result = engine.export_document("PNG", target, [1], render)
    assert result.failures[0].page == 1
    assert "read-back" in result.failures[0].detail
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_painter_end_failure_discards_temp(tmp_path, monkeypatch):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")

    class FailedEndPainter(engine.QPainter):
        def end(self):
            super().end()
            return False

    monkeypatch.setattr(engine, "QPainter", FailedEndPainter)
    result = engine.export_document("PDF", target, [1, 2], render)
    assert not result.success and result.failures[0].page == 0
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_readback_failure_discards_temp(tmp_path, monkeypatch):
    target = tmp_path / "old.pdf"
    target.write_bytes(b"OLD")
    monkeypatch.setattr(engine, "_valid_pdf", lambda *args: False)
    result = engine.export_document("PDF", target, [1, 2], render)
    assert not result.success and result.failures[0].page == 0
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_cancel_after_render_leaves_no_partial_output(tmp_path):
    target = tmp_path / "cancel.png"
    state = {"cancel": False}

    def renderer(page, index, total):
        state["cancel"] = True
        return render("red", index, total)

    result = engine.export_document("PNG", target, [1, 2], renderer,
                                    cancelled=lambda: state["cancel"])
    assert result.cancelled and not result.exported_indices
    assert not list(tmp_path.iterdir())


def test_png_atomic_replace_failure_only_reports_original_page(tmp_path, monkeypatch):
    target = tmp_path / "document.png"
    old = tmp_path / "document_p2.png"
    old.write_bytes(b"OLD")
    real_replace = os.replace

    def fail_second(source, dest):
        if str(dest) == str(old):
            raise PermissionError("locked output")
        return real_replace(source, dest)

    monkeypatch.setattr(engine.os, "replace", fail_second)
    result = engine.export_document("PNG", target, [1, 2, 3], render)
    assert result.complete and not result.success
    assert result.exported_indices == (1, 3)
    assert result.failures[0].page == 2
    assert old.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_progress_exception_disposes_partial_document(tmp_path):
    target = tmp_path / "existing.pdf"
    target.write_bytes(b"OLD")

    def progress(index, total, phase):
        if index == 1 and phase == "after":
            raise RuntimeError("dialog closed")

    result = engine.export_document("PDF", target, [1, 2], render, progress)
    assert not result.success and not result.complete
    assert result.failures[0].page == 1
    assert target.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_pdf_invalid_render_type_does_not_hide_later_pages(tmp_path):
    target = tmp_path / "invalid.pdf"
    seen = []

    def renderer(page, index, total):
        seen.append(index)
        return "not a pixmap" if index == 2 else render("red", index, total)

    result = engine.export_document("PDF", target, [1, 2, 3], renderer)
    assert seen == [1, 2, 3]
    assert result.complete and not result.success
    assert result.failures[0].page == 2
    assert result.exported_indices == (1, 3)
    assert len(result.exported_paths) == 1
    assert not target.exists()
    assert_no_temps(tmp_path)


def test_import_without_qtpdf_keeps_png_available_and_fails_pdf_closed(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "PyQt6.QtPdf", None)
    spec = importlib.util.spec_from_file_location("export_pipeline_without_pdf", engine.__file__)
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, isolated)
    spec.loader.exec_module(isolated)

    png = isolated.export_document("PNG", tmp_path / "works.png", [1], render)
    assert png.success and QPixmap(str(tmp_path / "works.png")).isNull() is False

    pdf_path = tmp_path / "existing.pdf"
    pdf_path.write_bytes(b"OLD")
    pdf = isolated.export_document("PDF", pdf_path, [1], render)
    assert not pdf.success and pdf.failures[0].page == 0
    assert "validation" in pdf.failures[0].detail
    assert pdf_path.read_bytes() == b"OLD"
    assert_no_temps(tmp_path)


def test_failure_details_are_single_line_and_bounded(tmp_path):
    detail = "S" * 10000 + "\ntraceback-like text"

    def broken(page, index, total):
        raise RuntimeError(detail)

    def broken_progress(index, total, phase):
        raise RuntimeError(detail)

    for callback in (dict(render_page=broken),
                     dict(render_page=render, progress=broken_progress)):
        result = engine.export_document("PNG", tmp_path / "error.png", [1], **callback)
        assert not result.success and len(result.failures) == 1
        message = result.failures[0].detail
        assert len(message) <= 512 and "\n" not in message and "\r" not in message
        assert_no_temps(tmp_path)
