# SPDX-License-Identifier: GPL-3.0-or-later
"""C09 imports use private generated files, real decoders and staged results."""
from unittest.mock import Mock

import pytest
from PyQt6.QtGui import QColor, QImage, QPixmap

from teaching.application import APPLICATION_EVENTS, APPLICATION_TARGETS
from test_teaching_application import application_host, practice_request
from test_teaching_file_results import wait_for
from test_export_ui_610 import Progress


def png(host):
    path = host.request.paths.data_dir / 'generated-image.png'
    image = QImage(120, 80, QImage.Format.Format_RGB32)
    image.fill(QColor('#247c91'))
    assert image.save(str(path))
    host.panel._teaching_media_source_path = str(path)
    return path


def pdf(host):
    path = host.request.paths.data_dir / 'generated-pages.pdf'
    pixmaps = [QPixmap(200, 140), QPixmap(200, 140)]
    for item, color in zip(pixmaps, ('#247c91', '#c37835')):item.fill(QColor(color))
    host.module.ControlPanel.write_pdf(str(path), pixmaps)
    host.panel._teaching_media_source_path = str(path)
    return path


def test_c09_actual_import_target_and_event_are_registered():
    assert 'file.import' in APPLICATION_TARGETS
    assert 'media.imported' in APPLICATION_EVENTS


def test_selected_private_image_is_inserted_before_import_success(application_host, monkeypatch):
    host, _ = application_host
    path = png(host)
    engine = wait_for(host.panel, 'media.imported', kind='image', images=1, source_sample=True)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'completed' and len(host.panel.canvas.image_items) == 1
    image = host.panel.canvas.image_items[0]
    assert image['pixmap'].width() == 120 and image['pixmap'].height() == 80
    assert host.panel._teaching_media_original_id == image['id']
    assert host.panel._teaching_document_batch is None


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_import_chooser_cancel_is_only_a_cancelled_result(application_host, monkeypatch, expected):
    host, _ = application_host
    before = host.panel.canvas.document_signature()
    engine = wait_for(host.panel, 'media.imported', expected)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: ('', ''))
    host.panel.import_media_from_file_panel()
    assert host.panel.canvas.document_signature() == before
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued


def test_outside_import_is_rejected_before_file_size_or_decoder_read(application_host, tmp_path, monkeypatch):
    host, _ = application_host
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'generated invalid example')
    engine = wait_for(host.panel, 'media.imported')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(outside), ''))
    monkeypatch.setattr(host.module.os.path, 'getsize', Mock(side_effect=AssertionError('outside metadata read')))
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not host.panel.canvas.image_items and not engine._issued


def test_import_heartbeat_cleanup_failure_never_publishes_success(application_host, monkeypatch):
    host, _ = application_host
    path = png(host)
    engine = wait_for(host.panel, 'media.imported')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(host.panel, 'heartbeat_refresh', Mock(side_effect=RuntimeError('import tail')))
    with pytest.raises(RuntimeError, match='import tail'):
        host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not engine._issued
    assert host.panel._teaching_document_batch is None


def test_old_import_chooser_cannot_credit_a_resumed_step(application_host, monkeypatch):
    host, _ = application_host
    path = png(host)
    engine = wait_for(host.panel, 'media.imported')
    def choose(*args, **kwargs):
        engine.pause(); engine.resume()
        return str(path), ''
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', choose)
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not engine._issued


def test_real_pdf_import_reports_two_new_independent_pages(application_host, monkeypatch):
    host, _ = application_host
    path = pdf(host)
    panel = host.panel
    original = [page['page_id'] for page in panel.canvas.document_pages()]
    engine = wait_for(panel, 'media.imported', kind='pdf', pages_added=2, pages=3, separate_pages=True, source_sample=True)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress())
    panel.import_media_from_file_panel()
    assert engine.phase == 'completed'
    assert [page['page_id'] for page in panel.canvas.pages[:1]] == original
    assert len({page['page_id'] for page in panel.canvas.pages}) == 3
    assert panel.canvas.current_page == 1 and panel.canvas.whiteboard_mode
    assert all(len(page['images']) == 1 for page in panel.canvas.pages[1:])


def test_invalid_private_image_cannot_claim_import_success(application_host, monkeypatch):
    host, _ = application_host
    path = host.request.paths.data_dir / 'broken.png'
    path.write_bytes(b'synthetic malformed image')
    engine = wait_for(host.panel, 'media.imported')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not engine._issued and not host.panel.canvas.image_items


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_pdf_batch_cancel_preserves_original_pages_and_reports_cancel(application_host, monkeypatch, expected):
    host, _ = application_host
    path = pdf(host)
    panel = host.panel
    before = panel.canvas.serialized_document_pages()
    engine = wait_for(panel, 'media.imported', expected)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress(cancel_at=1))
    panel.import_media_from_file_panel()
    assert panel.canvas.serialized_document_pages() == before
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued and not panel._document_transition_active


def test_pdf_returned_count_without_committed_pages_is_not_import_success(application_host, monkeypatch):
    host, _ = application_host
    path = pdf(host)
    engine = wait_for(host.panel, 'media.imported')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(host.panel, 'import_pdf', lambda path: 2)
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not engine._issued


def test_existing_image_returned_without_new_object_is_not_import_success(application_host, monkeypatch):
    host, _ = application_host
    path = png(host)
    existing = host.panel.import_image_file(str(path))
    engine = wait_for(host.panel, 'media.imported')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(host.panel, 'import_image_file', lambda path: existing)
    host.panel.import_media_from_file_panel()
    assert engine.phase == 'running' and not engine._issued
