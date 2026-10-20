# SPDX-License-Identifier: GPL-3.0-or-later
"""C10 real formats, committed output, cancellation and retry through private Qt."""
from pathlib import Path
from string import Formatter
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QProgressBar, QProgressDialog, QPushButton
from PyQt6.QtGui import QImageReader
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtSvg import QSvgRenderer

from persistence import PROJECT_KIND, normalize_project_data, read_json_maybe_gz
from teaching.packaging import collect_teaching_datas
from teaching.application import application_catalog
from test_export_ui_610 import Progress
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step, finished


def test_c10_copy_and_chapter_structure_are_complete():
    import main,i18n
    from teaching.export_copy import EXPORT_COPY
    catalog,loader=application_catalog(main,ROOT)
    course=catalog.course_by_id('c10')
    assert [chapter.id for chapter in course.chapters]==['c10.formats','c10.progress_cancel','c10.result']
    assert [len(chapter.steps) for chapter in course.chapters]==[7,4,6]
    assert len(EXPORT_COPY)==38 and sum(len(values) for values in EXPORT_COPY.values())==304
    for key,values in EXPORT_COPY.items():
        assert len(values)==8
        for language,value in zip(i18n._LANGS,values):
            assert i18n.TEXT[language][key]==value and value.strip()
            assert not any(field is not None for _,field,_,_ in Formatter().parse(value))
    bundle={Path(source) for source,_ in collect_teaching_datas(ROOT)}
    for chapter,count in zip(course.chapters,(3,24,3)):
        source=loader.asset_path(loader.fixtures[chapter.fixture])
        data=normalize_project_data(read_json_maybe_gz(str(source)),kind=PROJECT_KIND)
        assert len(data["pages"])==count and data["metadata"]["synthetic_teaching"] is True
        assert len({page["page_id"] for page in data["pages"]})==count
        assert source in bundle
        assert all(not page["images"] for page in data["pages"])


@pytest.mark.parametrize('writing_host',['c10.formats'],indirect=True)
def test_four_formats_export_all_three_pages_with_readable_real_files(writing_host,monkeypatch):
    host,progress=writing_host
    panel=host.panel
    monkeypatch.setattr(panel,'_show_export_result',Mock())
    monkeypatch.setattr(panel,'_create_document_progress',lambda *args:Progress())
    original=panel.canvas.document_signature()
    next_info(host)
    wrong_format=panel.do_export("PDF")
    assert wrong_format.success
    assert_step(host,"png")
    assert not host.presenter.engine._issued
    root=host.request.paths.export_dir
    for fmt in ('PNG','PDF','SVG','EPS'):
        assert_step(host,fmt.lower())
        getattr(panel,'btn_export_'+fmt.lower()).click()
        outputs=sorted(root.glob('c10_formats*.'+fmt.lower()))
        assert len(outputs)==(1 if fmt=='PDF' else 3)
        if fmt=='PNG':assert all(QImageReader(str(path)).canRead() for path in outputs)
        elif fmt=='SVG':assert all(QSvgRenderer(str(path)).isValid() for path in outputs)
        elif fmt=='EPS':assert all(path.read_bytes().startswith(b'%!PS-Adobe') for path in outputs)
        else:
            doc=QPdfDocument(None)
            try:
                assert doc.load(str(outputs[0]))==QPdfDocument.Error.None_ and doc.pageCount()==3
            finally:doc.close()
    assert panel.canvas.document_signature()==original
    assert_step(host,'formats_info');next_info(host)
    assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c10.progress_cancel'],indirect=True)
def test_cancel_course_keeps_committed_png_and_never_claims_all_pages(writing_host,monkeypatch):
    host,progress=writing_host
    panel=host.panel
    assert len(panel.canvas.pages)==24
    results=[]
    monkeypatch.setattr(panel,'_show_export_result',lambda result,fmt:results.append(result))
    dialogs=[]
    create=panel._create_document_progress
    def create_cancel_progress(title,total):
        dialog=create(title,total)
        assert isinstance(dialog,QProgressDialog)
        dialogs.append(dialog)
        button=dialog.findChild(QPushButton)
        assert button is not None and button.text()==host.module.tr('cancel')
        bar=dialog.findChild(QProgressBar)
        def cancel_after_first(value):
            if value==1:QTimer.singleShot(0,button.click)
        bar.valueChanged.connect(cancel_after_first)
        return dialog
    monkeypatch.setattr(panel,'_create_document_progress',create_cancel_progress)
    before=panel.canvas.document_signature()
    next_info(host)
    assert_step(host,'cancel_png');panel.btn_export_png.click()
    assert_step(host,'cancel_info')
    assert len(dialogs)==1 and dialogs[0].wasCanceled()
    assert results[-1].cancelled and not results[-1].success and not results[-1].complete
    assert results[-1].exported_indices==(1,) and not results[-1].failures
    assert not host.presenter.engine._issued
    outputs=list(host.request.paths.export_dir.glob('c10_progress_cancel*.png'))
    assert len(outputs)==1 and QImageReader(str(outputs[0])).canRead()
    assert panel.canvas.document_signature()==before
    next_info(host);next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c10.result'],indirect=True)
def test_result_course_reports_real_missing_second_page_then_retries_successfully(writing_host,monkeypatch):
    host,progress=writing_host
    panel=host.panel
    summaries=[]
    monkeypatch.setattr(panel,'_show_export_result',lambda result,fmt:summaries.append(result))
    monkeypatch.setattr(panel,'_create_document_progress',lambda *args:Progress())
    before=panel.canvas.document_signature()
    root=host.request.paths.export_dir
    next_info(host)
    assert_step(host,'partial_png');panel.btn_export_png.click()
    assert_step(host,'partial_info')
    assert summaries[-1].exported_indices==(1,3) and summaries[-1].failures[0].page==2
    assert (root/'c10_result_p2.png').is_dir()
    next_info(host)
    assert_step(host,'retry_png');panel.btn_export_png.click()
    assert summaries[-1].success and summaries[-1].exported_indices==(1,2,3)
    assert all(QImageReader(str(root/('c10_result_p'+str(index)+'.png'))).canRead() for index in (1,2,3))
    assert panel.canvas.document_signature()==before
    assert_step(host,'success_info');next_info(host)
    assert_step(host,'done');next_info(host);finished(host,progress)
