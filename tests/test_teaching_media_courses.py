# SPDX-License-Identifier: GPL-3.0-or-later
"""C09 real image/PDF import and independent page workflows in private Qt."""
from pathlib import Path
from string import Formatter

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QImage

from persistence import PROJECT_KIND, normalize_project_data, read_json_maybe_gz
from teaching.application import application_catalog
from teaching.packaging import collect_teaching_datas
from test_export_ui_610 import Progress
from test_teaching_business_adapters import draw_ink, mouse
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step, finished


def test_c09_copy_catalog_and_synthetic_offline_assets_are_complete():
    import main, i18n
    from teaching.media_copy import MEDIA_COPY
    catalog, loader = application_catalog(main, ROOT)
    course = catalog.course_by_id('c09')
    assert [chapter.id for chapter in course.chapters] == ['c09.image', 'c09.pdf_pages']
    assert [len(chapter.steps) for chapter in course.chapters] == [6, 7]
    assert len(MEDIA_COPY) == 29 and sum(len(values) for values in MEDIA_COPY.values()) == 232
    for key, values in MEDIA_COPY.items():
        assert len(values) == 8
        for language, value in zip(i18n._LANGS, values):
            assert i18n.TEXT[language][key] == value and value.strip()
            assert not any(field is not None for _, field, _, _ in Formatter().parse(value))
    bundle = {Path(source) for source, _ in collect_teaching_datas(ROOT)}
    for chapter in course.chapters:
        source = loader.asset_path(loader.fixtures[chapter.fixture])
        data = normalize_project_data(read_json_maybe_gz(str(source)), kind=PROJECT_KIND)
        assert len(data['pages']) == 1 and data['metadata']['synthetic_teaching'] is True
        assert source in bundle
    for name in ('media-c09-sample.png', 'media-c09-sample.pdf'):
        assert loader.asset_path('fixtures/'+name) in bundle
    image = QImage(str(loader.asset_path('fixtures/media-c09-sample.png')))
    assert not image.isNull() and (image.width(), image.height()) == (320, 200)
    for key in ('teaching_c09_image_size_info_body', 'teaching_c09_image_done_body',
                'teaching_c09_pdf_pages_limits_info_body', 'teaching_c09_pdf_pages_done_body'):
        for language, value in zip(i18n._LANGS, MEDIA_COPY[key]):
            assert i18n.TEXT[language]['teaching_next'] in value
    for key in ('teaching_c09_image_import_image_body', 'teaching_c09_pdf_pages_import_pdf_body'):
        assert i18n.TEXT['ja']['import_media'] in MEDIA_COPY[key][7]


@pytest.mark.parametrize('writing_host', ['c09.image'], indirect=True)
def test_c09_image_imports_sample_then_resizes_that_same_image(writing_host, monkeypatch):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    path = Path(panel._teaching_media_source_path)
    assert path.suffix == '.png' and path.is_relative_to(host.request.paths.data_dir)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    next_info(host)
    assert_step(host, 'import_image'); panel.btn_import_media.click()
    assert len(canvas.image_items) == 1
    original = canvas.image_items[0]
    assert_step(host, 'select_mode'); panel.btn_select.click()
    assert canvas.selected_ids == {original['id']}
    before = original['size'].width(), original['size'].height()
    assert_step(host, 'resize_image')
    start = canvas.selection_handles()['scale'].center().toPoint()
    end = start + QPoint(45, 30)
    mouse(canvas, 'press', (start.x(), start.y())); mouse(canvas, 'move', (end.x(), end.y())); mouse(canvas, 'release', (end.x(), end.y()))
    assert (original['size'].width(), original['size'].height()) != before
    assert original['id'] == panel._teaching_media_original_id
    assert_step(host, 'size_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c09.pdf_pages'], indirect=True)
def test_c09_pdf_imports_two_pages_then_keeps_annotation_on_second_only(writing_host, monkeypatch):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    path = Path(panel._teaching_media_source_path)
    original_id = canvas._page_id
    assert path.suffix == '.pdf' and path.is_relative_to(host.request.paths.data_dir)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(path), ''))
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress())
    next_info(host)
    assert_step(host, 'import_pdf'); panel.btn_import_media.click()
    assert len(canvas.pages) == 3 and canvas.current_page == 1
    assert canvas.pages[0]['page_id'] == original_id
    imported_ids = [page['page_id'] for page in canvas.pages[1:]]
    assert len(set(imported_ids)) == 2 and original_id not in imported_ids
    assert_step(host, 'next_page'); panel.rail_next.click()
    assert canvas._page_id == imported_ids[1] and len(canvas.image_items) == 1
    assert_step(host, 'annotate'); draw_ink(canvas)
    assert canvas.all_segments
    assert_step(host, 'previous_page'); panel.rail_prev.click()
    assert canvas._page_id == imported_ids[0] and not canvas.all_segments and len(canvas.image_items) == 1
    assert canvas.pages[2]['segments'] and not canvas.pages[0]['segments']
    assert_step(host, 'limits_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c09.pdf_pages'], indirect=True)
def test_c09_cancelled_pdf_batch_cannot_advance_lesson(writing_host, monkeypatch):
    host, _ = writing_host
    panel = host.panel
    path = panel._teaching_media_source_path
    before = panel.canvas.serialized_document_pages()
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (path, ''))
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress(cancel_at=1))
    next_info(host); panel.btn_import_media.click()
    assert_step(host, 'import_pdf')
    assert panel.canvas.serialized_document_pages() == before
