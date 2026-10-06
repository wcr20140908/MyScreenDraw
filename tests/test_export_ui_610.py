# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen integration: progress, original numbering and explicit outcomes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import Mock
from PyQt6.QtGui import QPixmap, QColor
import pytest
import main
from test_document_safety_610 import document, two_pages


class Progress:
    def __init__(self, cancel_at=None):
        self.values = []
        self.cancel_at = cancel_at
    def setValue(self, value): self.values.append(value)
    def setLabelText(self, text): self.label = text
    def wasCanceled(self): return self.cancel_at is not None and max(self.values or [0]) >= self.cancel_at
    def hide(self): self.hidden = True
    def show(self): self.hidden = False
    def close(self): pass
    def deleteLater(self): pass


def setup_export(panel, canvas, tmp_path, monkeypatch, cancel_at=None):
    two_pages(canvas)
    progress = Progress(cancel_at)
    monkeypatch.setattr(main, "EXPORT_DIR", str(tmp_path))
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: progress)
    report = Mock()
    monkeypatch.setattr(panel, "_show_export_result", report)
    return progress, report


def test_streams_export_without_collecting_bitmap_list(document, tmp_path, monkeypatch):
    panel, canvas = document
    progress, report = setup_export(panel, canvas, tmp_path, monkeypatch)
    monkeypatch.setattr(panel, "collect_export_pages", Mock(side_effect=AssertionError("eager render")))
    result = panel.export_pages("PNG")
    assert result.success
    assert result.exported_indices == (1, 2)
    assert len(list(tmp_path.glob("*.png"))) == 2
    assert progress.values[-1] == 2
    report.assert_called_once()
    assert not panel._document_transition_active


def test_failed_render_keeps_original_number_and_modal_summary(document, tmp_path, monkeypatch):
    panel, canvas = document
    progress, report = setup_export(panel, canvas, tmp_path, monkeypatch)
    count = 0
    def render(page, size):
        nonlocal count
        count += 1
        if count == 1: return QPixmap()
        pix = QPixmap(50, 50); pix.fill(QColor("white")); return pix
    monkeypatch.setattr(canvas, "render_page_pixmap", render)
    stamp = Mock()
    monkeypatch.setattr(panel, "_stamp_page_number", stamp)
    result = panel.export_pages("PNG")
    assert not result.success
    assert [failure.page for failure in result.failures] == [1]
    assert result.exported_indices == (2,)
    assert list(tmp_path.glob("*_p2.png"))
    assert stamp.call_args.args[1:] == (2, 2)
    assert report.call_args.args[0] is result


def test_cancel_keeps_only_committed_pages(document, tmp_path, monkeypatch):
    panel, canvas = document
    progress, report = setup_export(panel, canvas, tmp_path, monkeypatch, cancel_at=1)
    result = panel.export_pages("PNG")
    assert result.cancelled
    assert result.exported_indices == (1,)
    assert len(list(tmp_path.glob("*.png"))) == 1
    assert not list(tmp_path.glob(".msd-export-*"))


@pytest.mark.parametrize("fmt", ["SVG", "EPS"])
def test_vector_exports_are_validated_and_page_failures_reported(document, tmp_path, monkeypatch, fmt):
    panel, canvas = document
    progress, report = setup_export(panel, canvas, tmp_path, monkeypatch)
    if fmt == "SVG":
        monkeypatch.setattr(canvas, "write_svg_page", lambda *args: None)
    else:
        monkeypatch.setattr(main.eps_export, "write_eps", lambda *args, **kwargs: None)
    result = panel.export_pages(fmt)
    assert not result.success
    assert [failure.page for failure in result.failures] == [1, 2]
    assert not list(tmp_path.glob("*." + fmt.lower()))
    assert not list(tmp_path.glob(".msd-export-*"))


@pytest.mark.parametrize("fmt", ["SVG", "EPS", "PDF"])
def test_real_document_export_outputs(document, tmp_path, monkeypatch, fmt):
    panel, canvas = document
    setup_export(panel, canvas, tmp_path, monkeypatch)
    result = panel.export_pages(fmt)
    assert result.success
    assert result.exported_indices == (1, 2)
    assert all(os.path.getsize(p) > 0 for p in result.exported_paths)


def test_incomplete_export_uses_modal_not_success_notification(document, monkeypatch):
    from export_pipeline import ExportResult, ExportFailure
    panel, canvas = document
    boxes = []
    monkeypatch.setattr(main.QMessageBox, "exec", lambda box: boxes.append(box))
    result = ExportResult(3, (1, 3), ("partial.pdf",), (ExportFailure(2, "bad page"),), False, True)
    panel._show_export_result(result, "PDF")
    assert len(boxes) == 1
    assert "2" in boxes[0].informativeText()
    assert "bad page" in boxes[0].detailedText()
    main.notify_user.assert_not_called()


def test_real_progress_cancel_before_render(document, tmp_path, monkeypatch):
    from PyQt6.QtCore import QTimer
    panel, canvas = document
    two_pages(canvas)
    monkeypatch.setattr(main, "EXPORT_DIR", str(tmp_path))
    original = panel._create_document_progress
    def progress(title, count):
        widget = original(title, count)
        QTimer.singleShot(0, widget.cancel)
        return widget
    monkeypatch.setattr(panel, "_create_document_progress", progress)
    monkeypatch.setattr(panel, "_show_export_result", Mock())
    result = panel.export_pages("PNG")
    assert result.cancelled
    assert not list(tmp_path.iterdir())


def test_desktop_export_hides_progress_without_real_screen_capture(document, tmp_path, monkeypatch):
    panel, canvas = document
    progress = Progress()
    monkeypatch.setattr(main, "EXPORT_DIR", str(tmp_path))
    monkeypatch.setattr(panel, "_create_document_progress", lambda *args: progress)
    monkeypatch.setattr(panel, "_show_export_result", Mock())
    def fake_capture():
        assert progress.hidden
        pix = QPixmap(20, 20); pix.fill(QColor("white")); return pix
    monkeypatch.setattr(panel, "grab_screen", fake_capture)
    assert panel.export_pages("PNG").success
