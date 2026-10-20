# SPDX-License-Identifier: GPL-3.0-or-later
"""C10 actual private file conflicts, retries and export metadata."""
import pytest
from unittest.mock import Mock

from teaching.application import APPLICATION_TARGETS
from teaching.engine import TutorialEngine
from teaching.events import TeachingEventBus
from teaching.models import TutorialCatalog, TutorialCourse, TutorialChapter, TutorialStep, WaitClause, WaitSpec
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import draw_ink
from test_export_ui_610 import Progress


def export_engine(host, chapter='result'):
    panel = host.panel
    host.context.activate(); host.activate()
    panel.canvas.enter_whiteboard()
    draw_ink(panel.canvas)
    panel.canvas.new_page(); draw_ink(panel.canvas)
    panel.canvas.new_page(); draw_ink(panel.canvas)
    panel._teaching_export_fixture = 'export.c10.' + chapter
    panel._show_export_result = Mock()
    first = TutorialStep('partial_png', 'teaching_center_title', 'teaching_resume', 'operation', None,
        'free', (), (), WaitSpec((WaitClause('export.finished', 'failed', {'pages':2,'total':3,'failed_pages':1,'partial':True}),)), 'retry_png')
    second = TutorialStep('retry_png', 'teaching_center_title', 'teaching_resume', 'operation', None,
        'free', (), (), WaitSpec((WaitClause('export.finished', 'success', {'pages':3,'total':3,'failed_pages':0,'partial':False}),)), 'end_chapter')
    tutorial = TutorialChapter('c10.'+chapter, 'teaching_center_title', 'blank', (first,second))
    course = TutorialCourse('c10',1,1,'teaching_center_title',(tutorial,))
    engine = TutorialEngine(TutorialCatalog((course,)),session_id='export-adapter')
    panel.teaching_events = TeachingEventBus(engine)
    host.presenter.engine = engine
    engine.start('c10','c10.'+chapter)
    return engine


def test_all_four_export_targets_are_real_registered_controls():
    assert {'export.png','export.pdf','export.svg','export.eps'} <= APPLICATION_TARGETS


def test_private_result_lesson_uses_real_path_conflict_then_retries_all_pages(application_host, monkeypatch):
    host, _ = application_host
    engine = export_engine(host)
    panel = host.panel
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress())
    before = panel.canvas.document_signature()
    result = panel.do_export('PNG')
    assert result.exported_indices == (1,3) and len(result.failures) == 1 and result.failures[0].page == 2
    assert not result.success and result.complete and not result.cancelled
    assert engine.current_step_id == 'retry_png'
    root = host.request.paths.export_dir
    assert (root/'c10_result_p2.png').is_dir()
    assert (root/'c10_result_p1.png').is_file() and (root/'c10_result_p3.png').is_file()
    retried = panel.do_export('PNG')
    assert retried.success and retried.exported_indices == (1,2,3)
    assert (root/'c10_result_p2.png').is_file()
    assert engine.phase == 'completed' and not engine._issued
    assert panel.canvas.document_signature() == before


def test_export_fixture_marker_alone_cannot_override_unrelated_course_output(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    panel._teaching_export_fixture = 'export.c10.result'
    panel._show_export_result = Mock()
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: Progress())
    result = panel.do_export('PNG')
    assert result.success
    assert not (host.request.paths.export_dir/'c10_result_p2.png').exists()
    assert all('c10_result' not in path for path in result.exported_paths)
