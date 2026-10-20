# SPDX-License-Identifier: GPL-3.0-or-later
"""Real private center and scene restoration through owned offscreen Qt methods."""
import copy
import json
import uuid
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from persistence import atomic_write_project, make_project_data
from runtime_paths import RuntimeContext
from teaching.application import ApplicationTeachingHost
from teaching.session_view import parent_progress_view
from teaching.state import TutorialStateStore
from test_teaching_application import practice_request
from test_teaching_application_isolation import drain
from test_teaching_business_adapters import draw_ink


@pytest.fixture
def center_host(practice_request,monkeypatch):
    import main
    root=practice_request.paths.resource_dir/'assets/tutorials'
    data=json.loads((root/'course.json').read_text(encoding='utf-8'))
    data['chapters'].append({'id':'c01.second','fixture':'second','title_key':'teaching_center_title',
        'steps':[{'id':'read','title_key':'teaching_center_title','body_key':'teaching_resume',
                  'kind':'information','next':'end_chapter'}]})
    (root/'course.json').write_text(json.dumps(data),encoding='utf-8')
    index=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
    index['fixtures']['second']='fixtures/second.msd'
    (root/'catalog.json').write_text(json.dumps(index),encoding='utf-8')
    page={'id':uuid.uuid4().hex,'name':'Synthetic second scene','segments':[],'texts':[],
          'shapes':[],'images':[]}
    atomic_write_project(str(root/'fixtures/second.msd'),make_project_data(
        pages=[page],current_page=0,whiteboard_mode=True,board_style='BLACK',app_version='6.1.0'))
    context=RuntimeContext(practice_request.paths)
    monkeypatch.setattr(main,'RUNTIME_CONTEXT',context)
    for name,value in practice_request.paths.module_aliases().items(): monkeypatch.setattr(main,name,value)
    main.ensure_directories();monkeypatch.setattr(main,'notify_user',Mock())
    app=QApplication.instance();before=set(app.topLevelWidgets());progress=[]
    host=ApplicationTeachingHost(main,practice_request,on_progress=lambda *record:progress.append(record))
    context.activate();host.activate()
    yield host,progress
    host.close()
    for window in set(app.topLevelWidgets())-before:
        if not sip.isdeleted(window):
            for timer in window.findChildren(QTimer):timer.stop()
            window.hide();window.deleteLater()
    drain(app)


def require(host,name):
    method=getattr(host,name,None)
    assert callable(method),'private center business adapter is not connected: '+name
    return method


def accepted_center(host,tmp_path):
    store=TutorialStateStore(tmp_path/'parent-learning.json')
    store.record_chapter('c01.second','completed',compat_revision=1)
    assert require(host,'request_center')()
    require(host,'accept_center')(parent_progress_view(host.catalog,store))
    assert host.center.isVisible()
    return store


def test_practice_tools_teaching_entry_is_active_and_requests_parent_view(center_host):
    host,_=center_host
    assert host.panel.btn_teaching.isEnabled()
    requests=QSignalSpy(host.center_requested)
    assert host.panel.open_teaching_center()
    assert len(requests)==1
    assert host.presenter._dialog_depth==1 and host.panel._teaching_suspended
    assert not host.panel.canvas.isVisible()


def test_center_displays_parent_progress_with_no_child_mutation_capabilities(center_host,tmp_path):
    host,_=center_host;store=accepted_center(host,tmp_path);before=store.path.read_bytes()
    center=host.center
    assert not center.context_hints_check.isEnabled() and not center.reset_button.isEnabled()
    assert center._course_items['c01'].text(1)==host.module.tr('teaching_course_progress').format(completed=1,total=2)
    center.context_hints_check.click();center.reset_button.click()
    assert store.path.read_bytes()==before


def test_center_return_preserves_private_work_and_epoch(center_host,tmp_path):
    host,_=center_host;panel=host.panel
    draw_ink(panel.canvas)
    signature=panel.canvas.document_signature();history=(len(panel.canvas.undo_stack),len(panel.canvas.redo_stack))
    epoch=host.presenter.engine.step_epoch;step=host.presenter.engine.current_step_id
    accepted_center(host,tmp_path)
    require(host,'finish_center')(resume=True)
    assert panel.canvas.isVisible() and not panel._teaching_suspended
    assert host.presenter._dialog_depth==0
    assert panel.canvas.document_signature()==signature
    assert (len(panel.canvas.undo_stack),len(panel.canvas.redo_stack))==history
    assert host.presenter.engine.current_step_id==step and host.presenter.engine.step_epoch==epoch


@pytest.mark.parametrize('busy',['pointer','text','file','modal','future'])
def test_busy_center_entry_never_cancels_original_private_work(center_host,monkeypatch,busy):
    host,_=center_host;panel=host.panel
    enter=require(host,'request_center')
    requests=QSignalSpy(host.center_requested)
    original_future=panel._autosave_future
    original_transition=panel._document_transition_active
    try:
        if busy=='pointer':panel.canvas._pointer_press(1,QPoint(30,40),1.0)
        elif busy=='text':
            editor=QWidget(panel)
            monkeypatch.setattr(editor,'isVisible',lambda:True)
            monkeypatch.setattr(panel,'text_panel',editor)
        elif busy=='file':panel._document_transition_active=True
        elif busy=='modal':monkeypatch.setattr(QApplication,'activeModalWidget',lambda:panel)
        else:panel._autosave_future=object()
        assert not enter()
        assert len(requests)==0 and not panel._teaching_suspended
        if busy=='pointer':assert 1 in panel.canvas._pointer_slots
    finally:
        panel._document_transition_active=original_transition
        panel._autosave_future=original_future


def test_cancelled_switch_keeps_same_private_lesson(center_host,tmp_path,monkeypatch):
    host,_=center_host
    accepted_center(host,tmp_path)
    before=host.panel.canvas.document_signature();epoch=host.presenter.engine.step_epoch
    requests=QSignalSpy(host.chapter_requested)
    monkeypatch.setattr(host.module.QMessageBox,'exec',lambda dialog:QMessageBox.StandardButton.Cancel)
    assert host.center.select_chapter('c01','c01.second')
    host.center.start_button.click()
    assert len(requests)==0 and host.center.isVisible()
    assert host.panel.canvas.document_signature()==before and host.presenter.engine.step_epoch==epoch


def test_accepted_switch_rebuilds_fixture_without_another_unsaved_prompt(center_host,tmp_path,monkeypatch):
    host,progress=center_host;draw_ink(host.panel.canvas)
    accepted_center(host,tmp_path)
    requests=QSignalSpy(host.chapter_requested)
    monkeypatch.setattr(host.module.QMessageBox,'exec',lambda dialog:QMessageBox.StandardButton.Yes)
    host.center.select_chapter('c01','c01.second');host.center.start_button.click()
    assert len(requests)==1 and list(requests[0])==['c01','c01.second']
    require(host,'prepare_chapter_change')()
    monkeypatch.setattr(host.module.QMessageBox,'exec',Mock(side_effect=AssertionError('no second unsaved prompt')))
    require(host,'prepare_chapter')('c01','c01.second')
    assert host.presenter.engine.phase=='paused' and host.center.isVisible()
    require(host,'commit_chapter')()
    assert host.presenter.engine.chapter_id=='c01.second' and host.presenter.engine.phase=='running'
    assert host.panel.canvas.pages[0]['name']=='Synthetic second scene'
    assert host.panel.canvas.board_style=='BLACK' and not host.panel._teaching_suspended
    assert host.presenter._dialog_depth==0 and host.request.chapter_id=='c01.foundation'


def test_f12_during_center_hides_views_without_nested_suspension(center_host,tmp_path):
    host,_=center_host;accepted_center(host,tmp_path)
    host.pause(hidden=True)
    assert not host.center.isVisible() and not host.panel.canvas.isVisible()
    host.resume()
    assert host.center.isVisible() and not host.panel.canvas.isVisible()
    require(host,'finish_center')(resume=False,hidden=True)
    assert not host.panel.canvas.isVisible()
    host.resume()
    assert host.panel.canvas.isVisible() and not host.panel._teaching_suspended


def test_practice_center_exemption_never_applies_to_ordinary_or_inactive_ui(center_host):
    host,_=center_host
    manager=host.panel.lifecycle
    allow=getattr(manager,'allow_practice_teaching_window',None)
    assert callable(allow)
    window=QWidget(host.panel);window.setWindowFlag(host.module.Qt.WindowType.Tool)
    host.context.ui_active=False
    with pytest.raises((ValueError,RuntimeError)):allow(window)
    host.context.ui_active=True
    window.deleteLater()
