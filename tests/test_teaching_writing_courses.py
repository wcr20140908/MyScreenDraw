# SPDX-License-Identifier: GPL-3.0-or-later
"""All 55 formal writing steps exercised through private Qt business methods."""
import json
from pathlib import Path
from string import Formatter
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication
from runtime_paths import RuntimeContext, RuntimePaths
from teaching.bootstrap import PracticeRequest
from teaching.application import ApplicationTeachingHost, application_catalog
from test_teaching_application_isolation import drain
from test_teaching_business_adapters import draw_ink, mouse

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def writing_host(request,tmp_path,monkeypatch):
    import main
    chapter=request.param
    paths=RuntimePaths.create_practice(ROOT,ROOT,temp_root=tmp_path/'owned')
    context=RuntimeContext(paths)
    monkeypatch.setattr(main,'RUNTIME_CONTEXT',context)
    for key,value in paths.module_aliases().items():monkeypatch.setattr(main,key,value)
    main.ensure_directories();monkeypatch.setattr(main,'notify_user',Mock())
    app=QApplication.instance();prior=set(app.topLevelWidgets());progress=[]
    host=ApplicationTeachingHost(main,PracticeRequest(paths,'writing-test',chapter.split('.')[0],chapter),
                                on_progress=lambda *row:progress.append(row))
    try:
        context.activate();host.activate()
        yield host,progress
    finally:
        host.close()
        for window in set(app.topLevelWidgets())-prior:
            if not sip.isdeleted(window):
                for timer in window.findChildren(QTimer):timer.stop()
                window.hide();window.deleteLater()
        drain(app)


def next_info(host):
    assert host.presenter.engine.current_step.kind=='information'
    host.presenter.controller.next_button.click()


def assert_step(host,name):
    assert host.presenter.engine.phase=='running',host.presenter.engine.last_error
    assert host.presenter.engine.current_step_id==name


def finished(host,progress):
    assert host.presenter.engine.phase=='completed'
    assert progress[-1]==(host.request.chapter_id,'completed',1)


def test_writing_catalog_and_eight_language_text_are_complete():
    import main,i18n
    from teaching.writing_copy import WRITING_COPY
    catalog,_=application_catalog(main,ROOT)
    courses=[catalog.course_by_id(key) for key in ('c02','c03')]
    assert [len(course.chapters) for course in courses]==[3,2]
    assert sum(len(chapter.steps) for course in courses for chapter in course.chapters)==55
    assert len(WRITING_COPY)==118
    for key,values in WRITING_COPY.items():
        assert len(values)==8
        for language,value in zip(i18n._LANGS,values):
            assert i18n.TEXT[language][key]==value and value.strip()
            assert not any(field is not None for _,field,_,_ in Formatter().parse(value))
    assert [step.id for step in courses[0].chapters[0].steps if step.id.startswith('try_')]==[
        'try_'+style for style in main.PEN_STYLES]


@pytest.mark.parametrize('writing_host',['c02.styles'],indirect=True)
def test_all_eleven_styles_require_real_selection_and_real_stroke(writing_host):
    host,progress=writing_host
    panel=host.panel;next_info(host)
    for style in panel.PEN_STYLE_META:
        assert_step(host,'choose_'+style)
        panel.pen_style_buttons[style].click()
        assert_step(host,'try_'+style)
        draw_ink(panel.canvas)
    assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c02.color_width'],indirect=True)
def test_color_width_and_private_preset_save_enable_reapply(writing_host):
    host,progress=writing_host;panel=host.panel;next_info(host)
    next(button for button in panel.color_buttons if button.property('color_val') and
         QColor(button.property('color_val'))!=panel.canvas.pen_color).click()
    assert_step(host,'width');panel.pen_slider.setValue(12 if panel.canvas.pen_width!=12 else 13)
    assert_step(host,'stroke');draw_ink(panel.canvas)
    assert_step(host,'preset_capture');panel.pen_defaults_editor.capture_button.click()
    assert_step(host,'preset_enable');panel.pen_defaults_checkbox.click()
    assert_step(host,'preset_apply');panel.btn_ann_marker.click()
    assert host.presenter.engine.sequence_index==1
    panel.pen_style_buttons['pen'].click()
    assert_step(host,'done')
    assert panel.canvas.pen_width==panel.pen_defaults['pen']['width']
    assert panel.canvas.pen_color.name()==panel.pen_defaults['pen']['color']
    next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c02.transient'],indirect=True)
def test_marker_stays_in_document_while_laser_does_not(writing_host):
    host,progress=writing_host;panel=host.panel;next_info(host)
    panel.btn_ann_marker.click();assert_step(host,'marker_stroke')
    draw_ink(panel.canvas);assert_step(host,'marker_info')
    assert panel.canvas.all_segments
    before=panel.canvas.document_signature();next_info(host)
    panel.btn_ann_laser.click();assert_step(host,'laser_trace')
    mouse(panel.canvas,'press',(30,30));mouse(panel.canvas,'move',(100,70));mouse(panel.canvas,'release',(120,80))
    assert_step(host,'fade_info');assert panel.canvas.document_signature()==before
    next_info(host);assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c03.erase'],indirect=True)
def test_circle_size_and_whole_stroke_modes_erase_two_separate_samples(writing_host):
    host,progress=writing_host;panel=host.panel;next_info(host)
    upper_before = sum(segment['id'].hex == 'dadb8e81cea976ac79e5d213276df443'
                       for segment in panel.canvas.all_segments)
    lower_before = sum(segment['id'].hex == '72c2ee1f9618e1eae59dcb7eb9931a99'
                       for segment in panel.canvas.all_segments)
    panel.handle_eraser_click();assert_step(host,'circle')
    panel.btn_circ.click();assert_step(host,'size');panel.e_slider.setValue(60)
    assert_step(host,'circle_erase')
    mouse(panel.canvas,'press',(170,150));mouse(panel.canvas,'move',(220,180));mouse(panel.canvas,'release',(220,180))
    assert_step(host,'stroke_mode')
    upper_count = sum(segment['id'].hex == 'dadb8e81cea976ac79e5d213276df443'
                      for segment in panel.canvas.all_segments)
    assert 0 < upper_count < upper_before
    assert sum(segment['id'].hex == '72c2ee1f9618e1eae59dcb7eb9931a99'
               for segment in panel.canvas.all_segments) == lower_before
    panel.btn_stroke.click()
    assert_step(host,'stroke_erase')
    mouse(panel.canvas,'press',(170,390));mouse(panel.canvas,'move',(220,420));mouse(panel.canvas,'release',(220,420))
    assert {segment['id'].hex for segment in panel.canvas.all_segments} == {
        'dadb8e81cea976ac79e5d213276df443'}
    assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host',['c03.history_clear'],indirect=True)
def test_history_clear_is_reversible_and_confirmed_as_real_content_change(writing_host):
    host,progress=writing_host;panel=host.panel;next_info(host)
    assert panel.canvas.undo();assert_step(host,'redo');assert panel.canvas.redo()
    assert_step(host,'clear');panel.clear();assert not panel.canvas.all_segments
    assert_step(host,'undo_clear');assert panel.canvas.undo();assert panel.canvas.all_segments
    assert_step(host,'limits');next_info(host);assert_step(host,'done');next_info(host);finished(host,progress)


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_circle_erasing_lower_sample_does_not_complete_upper_sample_step(writing_host):
    host, _ = writing_host
    panel = host.panel
    next_info(host)
    panel.handle_eraser_click()
    panel.btn_circ.click()
    panel.e_slider.setValue(60)
    assert_step(host, 'circle_erase')
    before = panel.canvas.document_signature()

    mouse(panel.canvas, 'press', (170, 390))
    mouse(panel.canvas, 'move', (220, 420))
    mouse(panel.canvas, 'release', (220, 420))

    assert panel.canvas.document_signature() != before
    assert_step(host, 'circle_erase')
    assert not host.presenter.engine._issued


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_whole_stroke_erasing_upper_remainder_does_not_complete_lower_sample_step(writing_host):
    host, _ = writing_host
    panel = host.panel
    next_info(host)
    panel.handle_eraser_click()
    panel.btn_circ.click()
    panel.e_slider.setValue(60)
    mouse(panel.canvas, 'press', (170, 150))
    mouse(panel.canvas, 'move', (220, 180))
    mouse(panel.canvas, 'release', (220, 180))
    panel.btn_stroke.click()
    assert_step(host, 'stroke_erase')
    before = panel.canvas.document_signature()

    mouse(panel.canvas, 'press', (370, 150))
    mouse(panel.canvas, 'release', (370, 150))

    assert panel.canvas.document_signature() != before
    assert {segment['id'].hex for segment in panel.canvas.all_segments} == {
        '72c2ee1f9618e1eae59dcb7eb9931a99'}
    assert_step(host, 'stroke_erase')
    assert not host.presenter.engine._issued


@pytest.mark.parametrize('writing_host', ['c03.erase'], indirect=True)
def test_circle_erasing_entire_upper_sample_meets_visible_instruction(writing_host):
    host, _ = writing_host
    panel = host.panel
    next_info(host)
    panel.handle_eraser_click()
    panel.btn_circ.click()
    panel.e_slider.setValue(60)
    assert_step(host, 'circle_erase')

    mouse(panel.canvas, 'press', (120, 120))
    for point in ((220, 180), (320, 120), (420, 180)):
        mouse(panel.canvas, 'move', point)
    mouse(panel.canvas, 'release', (420, 180))

    assert {segment['id'].hex for segment in panel.canvas.all_segments} == {
        '72c2ee1f9618e1eae59dcb7eb9931a99'}
    assert_step(host, 'stroke_mode')
    assert not host.presenter.engine._issued
