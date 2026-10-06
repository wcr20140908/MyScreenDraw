"""Synchronous, one-bitmap-at-a-time PNG/PDF export for GUI-thread callers.

The caller owns the document snapshot and rendering (including page-number stamps).
Do not call this from a worker if render_page uses Qt GUI objects. Progress callbacks
may process UI events; snapshot pages before entering this function.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import tempfile
from typing import Any, Callable, Sequence

from PyQt6.QtCore import QMarginsF, QSizeF
from PyQt6.QtGui import QImageReader, QPageSize, QPainter, QPdfWriter, QPixmap


class _WriterError(OSError):
    """A PDF device failure: continuing would risk an invalid document."""


@dataclass(frozen=True)
class ExportFailure:
    page: int  # 1-based original document page; 0 denotes an output-wide failure
    detail: str


@dataclass(frozen=True)
class ExportResult:
    total: int
    exported_indices: tuple[int, ...]  # 1-based, only files actually committed
    exported_paths: tuple[str, ...]  # per PNG page; one PDF (full or partial)
    failures: tuple[ExportFailure, ...]
    cancelled: bool
    complete: bool  # every source page attempted, even if some failed

    @property
    def success(self) -> bool:
        return (self.complete and not self.cancelled and not self.failures
                and len(self.exported_indices) == self.total and self.total > 0)


def _failure(page: int, detail: object) -> ExportFailure:
    """Keep callback/OS errors compact and safe for a UI failure dialog."""
    raw = str(detail)
    text = " ".join(raw[:511].split())
    if len(raw) > 511:
        text += "?"
    return ExportFailure(page, text[:512])


def _temporary_path(destination: str, suffix: str) -> str:
    fd, path = tempfile.mkstemp(prefix=".msd-export-", suffix=suffix,
                                dir=os.path.dirname(os.path.abspath(destination)))
    os.close(fd)
    return path


def _valid_pdf(path: str, expected: int) -> bool:
    # QtPdf is optional in this application. Never prevent PNG export or app
    # startup; without a reader, fail closed rather than claim PDF success.
    try:
        from PyQt6.QtPdf import QPdfDocument
    except ImportError:
        return False
    doc = QPdfDocument(None)
    try:
        return (doc.load(path) == QPdfDocument.Error.None_
                and doc.pageCount() == expected)
    finally:
        doc.close()


def export_document(
    fmt: str,
    destination: str | os.PathLike[str],
    pages: Sequence[Any],
    render_page: Callable[[Any, int, int], QPixmap],
    progress: Callable[[int, int, str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ExportResult:
    """Export snapshot pages in order, without pre-rendering or retaining bitmaps.

    ``render_page(page, index, total)`` receives the original 1-based page index.
    It must run on the GUI thread and return a non-null QPixmap; it is responsible
    for stamping the original page number. ``progress(index, total, phase)`` gets
    ``before`` and ``after`` events and may call QApplication.processEvents().
    ``cancelled()`` is checked before and after each page (and after progress).

    For multiple PNGs, ``destination`` is a stem: ``foo.png`` yields
    ``foo_p1.png``, ``foo_p2.png`` etc.; a single page uses ``foo.png``.
    PNG files already committed remain on later failure/cancellation. A PDF is
    committed only if every page and its final page-count validation succeed;
    a PDF with only page-render failures is saved as a distinct ``*_partial_*.pdf``
    with ``success=False``. Writer failure/cancellation discards the temporary PDF.
    The requested destination is never overwritten on any failure.
    An invalid format is a programming error (ValueError).
    """
    fmt = fmt.upper()
    if fmt not in ("PNG", "PDF"):
        raise ValueError("format must be PNG or PDF")
    total = len(pages)
    destination = os.fspath(destination)
    failures: list[ExportFailure] = []
    committed_indices: list[int] = []
    committed_paths: list[str] = []
    stopped = False
    processed = 0
    temporary: str | None = None
    writer: QPdfWriter | None = None
    painter: QPainter | None = None
    pdf_pages = 0
    pdf_written: list[int] = []
    partial_allowed = True
    if not total:
        return ExportResult(0, (), (), (_failure(0, "no pages to export"),), False, True)

    try:
        for index, page in enumerate(pages, 1):
            try:
                if cancelled is not None and cancelled():
                    stopped = True
                    break
                if progress is not None:
                    progress(index, total, "before")
                if cancelled is not None and cancelled():
                    stopped = True
                    break
            except Exception as exc:
                failures.append(_failure(index, f"progress/cancellation callback: {exc}"))
                partial_allowed = False
                break

            pix: QPixmap | None = None
            try:
                pix = render_page(page, index, total)
                if not isinstance(pix, QPixmap) or pix.isNull():
                    raise ValueError("renderer returned a null or invalid QPixmap")
                if cancelled is not None and cancelled():
                    stopped = True
                    break
                if fmt == "PNG":
                    stem, ext = os.path.splitext(destination)
                    target = f"{stem}_p{index}{ext}" if total > 1 else destination
                    temporary = _temporary_path(target, ".png")
                    if not pix.save(temporary, "PNG"):
                        raise OSError("QPixmap.save returned false")
                    image = QImageReader(temporary).read()
                    if image.isNull() or image.size() != pix.size():
                        raise OSError("PNG read-back validation failed")
                    del image
                    # Do not commit a just-rendered page after a cancel request.
                    if cancelled is not None and cancelled():
                        stopped = True
                        break
                    os.replace(temporary, target)
                    temporary = None
                    committed_indices.append(index)
                    committed_paths.append(target)
                else:
                    if painter is None:
                        temporary = _temporary_path(destination, ".pdf")
                        writer = QPdfWriter(temporary)
                        writer.setResolution(96)
                        writer.setCreator("MyScreenDraw")
                        size = QSizeF(max(1, pix.width()) * 25.4 / 96,
                                      max(1, pix.height()) * 25.4 / 96)
                        writer.setPageSize(QPageSize(size, QPageSize.Unit.Millimeter))
                        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
                        painter = QPainter()
                        if not painter.begin(writer):
                            raise _WriterError("QPainter.begin(QPdfWriter) returned false")
                    elif not writer.newPage():
                        raise _WriterError("QPdfWriter.newPage returned false")
                    painter.drawPixmap(painter.viewport(), pix, pix.rect())
                    pdf_pages += 1
                    pdf_written.append(index)
            except Exception as exc:
                failures.append(_failure(index, str(exc) or type(exc).__name__))
                # A failed writer cannot safely accept further pages. A failed
                # renderer, however, must not suppress subsequent page attempts.
                if isinstance(exc, _WriterError) or (
                    fmt == "PDF" and painter is not None
                    and isinstance(pix, QPixmap) and not pix.isNull()
                ):
                    partial_allowed = False
                    processed += 1
                    break
            finally:
                del pix
                if fmt == "PNG" and temporary is not None:
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass
                    temporary = None

            processed += 1
            try:
                if progress is not None:
                    progress(index, total, "after")
                if cancelled is not None and cancelled():
                    stopped = True
                    break
            except Exception as exc:
                failures.append(_failure(index, f"progress/cancellation callback: {exc}"))
                partial_allowed = False
                break

        if painter is not None:
            if not painter.end():
                failures.append(_failure(0, "QPainter.end(QPdfWriter) returned false"))
                partial_allowed = False
            painter = None
            writer = None
        if fmt == "PDF" and not stopped and processed == total and partial_allowed and pdf_pages:
            if not _valid_pdf(temporary, pdf_pages):
                failures.append(_failure(0, "PDF page-count or read-back validation failed"))
            else:
                target = destination
                if failures:
                    stem = os.path.splitext(os.path.basename(destination))[0]
                    fd, target = tempfile.mkstemp(
                        prefix=f"{stem}_partial_", suffix=".pdf",
                        dir=os.path.dirname(os.path.abspath(destination)))
                    os.close(fd)
                try:
                    os.replace(temporary, target)
                    temporary = None
                    committed_indices.extend(pdf_written)
                    committed_paths.append(target)
                except OSError as exc:
                    if failures:
                        try:
                            os.unlink(target)
                        except OSError:
                            pass
                    failures.append(_failure(0, f"PDF commit failed: {exc}"))
    except Exception as exc:
        failures.append(_failure(0, f"export output failed: {exc}"))
    finally:
        if painter is not None and painter.isActive():
            painter.end()
        # Release Qt's file handle before unlinking on Windows.
        painter = None
        writer = None
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return ExportResult(total, tuple(committed_indices), tuple(committed_paths),
                        tuple(failures), stopped, processed == total)

