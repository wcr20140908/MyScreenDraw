# SPDX-License-Identifier: GPL-3.0-or-later
"""C05 business results and owned thumbnail dragging; no native input."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from PyQt6.QtCore import QLine, QPointF, Qt
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QMessageBox

from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait


def prepare_pages(host, count=3):
    if not host.context.ui_active:
        host.context.activate()
        host.activate()
    canvas = host.panel.canvas
    canvas.whiteboard_mode = True
    canvas.pages = [dict(page_id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'teaching-page-test-'+str(index))),
                         name=chr(65+index), segments=[dict(id=uuid.uuid4(), line=QLine(50,80,250,80),pen=QPen())],
                         texts=[], shapes=[], images=[]) for index in range(count)]
    canvas.current_page = 0
    canvas.load_page(canvas.pages[0])
    canvas.reset_history()
    host.panel.update_whiteboard_ui()
    return canvas


def test_board_style_reports_real_whiteboard_color(application_host):
    host, _ = application_host
    canvas = prepare_pages(host)
    canvas.board_style = 'WHITE'
    engine = attach_wait(host.panel, 'board.style_changed', equals={'style':'BLACK','whiteboard_mode':True})
    host.panel.toggle_board_style()
    assert canvas.board_style == 'BLACK' and engine.phase == 'completed'


@pytest.mark.parametrize('name,accepted', [('Practice',False), ('',True), ('A',True)])
def test_cancelled_empty_or_same_rename_does_not_complete(application_host, monkeypatch, name, accepted):
    host, _ = application_host
    canvas = prepare_pages(host)
    engine = attach_wait(host.panel, 'page.renamed')
    monkeypatch.setattr(host.module.QInputDialog,'getText',lambda *args,**kwargs:(name,accepted))
    host.panel.rename_whiteboard_page()
    assert canvas._page_name == 'A' and engine.phase == 'running' and not engine._issued


def test_rename_reports_stable_identity_after_real_change(application_host, monkeypatch):
    host, _ = application_host
    canvas = prepare_pages(host)
    page_id = canvas._page_id
    engine = attach_wait(host.panel, 'page.renamed', equals={'page_id':page_id})
    monkeypatch.setattr(host.module.QInputDialog,'getText',lambda *args,**kwargs:('Practice',True))
    host.panel.rename_whiteboard_page()
    assert canvas._page_name == 'Practice' and canvas._page_id == page_id
    assert engine.phase == 'completed'


def test_delete_cancel_is_an_explicit_cancelled_result_with_page_retained(application_host, monkeypatch):
    host, _ = application_host
    canvas = prepare_pages(host,2)
    before = [page['page_id'] for page in canvas.pages]
    engine = attach_wait(host.panel,'page.deleted',sequence=(WaitClause('page.deleted','cancelled',{'retained':True}),))
    monkeypatch.setattr(QMessageBox,'exec',lambda box:QMessageBox.StandardButton.Cancel)
    host.panel.delete_whiteboard_page()
    assert [page['page_id'] for page in canvas.pages] == before
    assert engine.phase == 'completed'


def test_delete_success_removes_only_requested_page_and_keeps_survivor(application_host, monkeypatch):
    host, _ = application_host
    canvas = prepare_pages(host,2)
    removed, survivor = [page['page_id'] for page in canvas.pages]
    engine = attach_wait(host.panel,'page.deleted',equals={'page_id':removed,'removed':1,'pages':1})
    monkeypatch.setattr(QMessageBox,'exec',lambda box:QMessageBox.StandardButton.Yes)
    host.panel.delete_whiteboard_page()
    assert [page['page_id'] for page in canvas.pages] == [survivor]
    assert engine.phase == 'completed'


@pytest.mark.parametrize('placement,destination',[('before',1),('after',2),('first',0),('last',3)])
def test_copy_validates_new_identity_content_and_insertion_position(application_host, placement, destination):
    host, _ = application_host
    canvas = prepare_pages(host)
    canvas.switch_page(1)
    before = [page['page_id'] for page in canvas.pages]
    source = canvas._page_id
    host.panel.set_page_copy_placement(placement,persist=False)
    engine = attach_wait(host.panel,'page.copied',equals={'placement':placement,'source_page_id':source,
                                                      'page':destination+1,'added':1,'content_matches':True})
    host.panel.copy_whiteboard_page()
    assert len(canvas.pages) == 4 and canvas.current_page == destination
    assert canvas._page_id not in before and source in {page['page_id'] for page in canvas.pages}
    assert canvas.all_segments[0]['id'] == canvas.pages[next(i for i,p in enumerate(canvas.pages) if p['page_id']==source)]['segments'][0]['id']
    assert engine.phase == 'completed'


def test_copy_limit_and_same_or_invalid_placement_do_not_complete(application_host, monkeypatch):
    host, _ = application_host
    canvas = prepare_pages(host)
    monkeypatch.setattr(host.module,'MAX_PAGES',3)
    engine = attach_wait(host.panel,'page.copied')
    host.panel.copy_whiteboard_page()
    assert len(canvas.pages)==3 and engine.phase=='running' and not engine._issued
    engine = attach_wait(host.panel,'page.copy_placement_changed')
    host.panel.set_page_copy_placement('after')
    host.panel.set_page_copy_placement('unknown')
    assert engine.phase=='running' and not engine._issued


def test_copy_placement_is_real_saved_private_setting(application_host):
    host,_ = application_host
    prepare_pages(host)
    host.panel.open_settings_panel()
    engine=attach_wait(host.panel,'page.copy_placement_changed',equals={'placement':'before'})
    host.panel.set_page_copy_placement('before')
    assert host.panel.document_preferences.copy_combo.currentData()=='before'
    assert engine.phase=='completed'


def test_failed_placement_write_does_not_complete(application_host,monkeypatch):
    host,_=application_host
    prepare_pages(host)
    engine=attach_wait(host.panel,'page.copy_placement_changed')
    monkeypatch.setattr(host.module,'atomic_write_json',Mock(side_effect=OSError('readonly')))
    host.panel.set_page_copy_placement('before')
    assert engine.phase=='running' and not engine._issued


def test_thumbnail_open_requires_actual_visible_list(application_host):
    host,_=application_host
    prepare_pages(host)
    engine=attach_wait(host.panel,'thumbnails.opened',equals={'pages':3})
    host.panel.toggle_thumbnail_panel()
    assert host.panel.thumbnail_panel.isVisible() and host.panel.thumbnail_list.count()==3
    assert engine.phase=='completed'


def test_thumbnail_selection_delivers_after_ui_tail_not_before(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    engine=attach_wait(host.panel,'page.changed')
    with monkeypatch.context() as patch:
        patch.setattr(host.panel,'update_whiteboard_ui',Mock(side_effect=RuntimeError('thumbnail tail')))
        with pytest.raises(RuntimeError,match='thumbnail tail'):
            host.panel._thumbnail_page_changed(2)
    assert canvas.current_page==2
    assert engine.phase=='running' and not engine._issued


def test_reorder_preserves_active_identity_and_reports_actual_move(application_host):
    host,_=application_host
    canvas=prepare_pages(host)
    canvas.switch_page(2)
    active=canvas._page_id
    engine=attach_wait(host.panel,'page.reordered',equals={'page_id':active,'source':2,'destination':0})
    host.panel.reorder_whiteboard_page(2,0)
    assert [page['name'] for page in canvas.pages]==['C','A','B']
    assert canvas._page_id==active and canvas.current_page==0
    assert engine.phase=='completed'


def drag_to_front(panel,monkeypatch,during=None):
    import page_list
    widget=panel.thumbnail_list
    widget.doItemsLayout()
    class Drag:
        def __init__(self,source):self.source=source
        def setMimeData(self,data):assert data is not None
        def setPixmap(self,pixmap):pass
        def setHotSpot(self,point):pass
        def deleteLater(self):pass
        def exec(self,actions):
            if during is not None:during()
            rect=widget.visualItemRect(widget.item(0))
            point=rect.topLeft()
            event=SimpleNamespace(source=lambda:widget,position=lambda:QPointF(point),
                                  setDropAction=lambda _:None,accept=lambda:None,ignore=lambda:None)
            widget.dropEvent(event)
            return Qt.DropAction.MoveAction
    monkeypatch.setattr(page_list,'QDrag',Drag)
    widget.startDrag(Qt.DropAction.MoveAction)


def test_owned_drag_reports_after_cleanup_and_keeps_page_identity(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    host.panel.thumbnail_list.setCurrentRow(2)
    engine=attach_wait(host.panel,'page.reordered')
    drag_to_front(host.panel,monkeypatch)
    assert [page['name'] for page in canvas.pages]==['C','A','B']
    assert engine.phase=='completed'
    assert host.panel.thumbnail_list._drag_source_id is None


def test_old_drag_cannot_credit_new_epoch_at_drop(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    host.panel.thumbnail_list.setCurrentRow(2)
    engine=attach_wait(host.panel,'page.reordered')
    drag_to_front(host.panel,monkeypatch,lambda:(engine.pause(),engine.resume()))
    assert [page['name'] for page in canvas.pages]==['C','A','B']
    assert engine.phase=='running' and not engine._issued


def test_drag_cleanup_failure_cannot_credit_completed_reorder(application_host,monkeypatch):
    from PyQt6.QtWidgets import QAbstractItemView
    host,_=application_host
    canvas=prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    host.panel.thumbnail_list.setCurrentRow(2)
    engine=attach_wait(host.panel,'page.reordered')
    with monkeypatch.context() as patch:
        patch.setattr(QAbstractItemView,'dragLeaveEvent',Mock(side_effect=RuntimeError('drag cleanup')))
        with pytest.raises(RuntimeError,match='drag cleanup'):
            drag_to_front(host.panel,patch)
    assert engine.phase=='running' and not engine._issued


@pytest.mark.parametrize('action,event',[('copy','page.copied'),('rename','page.renamed'),('delete','page.deleted'),('reorder','page.reordered'),('board','board.style_changed')])
def test_page_ui_tail_failure_never_completes(action,event,application_host,monkeypatch):
    host,_=application_host
    prepare_pages(host)
    engine=attach_wait(host.panel,event)
    monkeypatch.setattr(host.module.QInputDialog,'getText',lambda *args,**kwargs:('Practice',True))
    monkeypatch.setattr(QMessageBox,'exec',lambda box:QMessageBox.StandardButton.Yes)
    with monkeypatch.context() as patch:
        patch.setattr(host.panel,'update_whiteboard_ui',Mock(side_effect=RuntimeError('page tail')))
        with pytest.raises(RuntimeError,match='page tail'):
            if action=='copy':host.panel.copy_whiteboard_page()
            elif action=='rename':host.panel.rename_whiteboard_page()
            elif action=='delete':host.panel.delete_whiteboard_page()
            elif action=='reorder':host.panel.reorder_whiteboard_page(2,0)
            else:host.panel.toggle_board_style()
    assert engine.phase=='running' and not engine._issued


def test_page_targets_resolve_to_actual_controls_without_altering_content(application_host):
    host,_=application_host
    host.context.activate();host.activate()
    canvas=prepare_pages(host)
    host.panel.set_ui_mode('icon',persist=False)
    host.panel.open_settings_panel()
    expected={'toolbar.board_style':host.panel.icon_buttons['board_style'],
              'pages.thumbnails_button':host.panel.rail_count,'pages.thumbnail_list':host.panel.thumbnail_list,
              'pages.rename':host.panel.btn_rename_page,'pages.delete':host.panel.btn_delete_page,
              'pages.copy':host.panel.btn_copy_page,'pages.copy_position':host.panel.document_preferences.copy_combo}
    before=[host.module.serialize_page(page) for page in canvas.document_pages()]
    for target,widget in expected.items():
        host.registry.reveal(target)
        assert host.registry.resolve(target) is widget
    assert [host.module.serialize_page(page) for page in canvas.document_pages()]==before


def test_drag_setup_failure_retires_context_and_disposes_drag_source(application_host,monkeypatch):
    import page_list
    host,_=application_host
    prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    widget=host.panel.thumbnail_list
    widget.setCurrentRow(2)
    engine=attach_wait(host.panel,'page.reordered')
    instances=[]
    class BrokenDrag:
        def __init__(self,source):self.deleted=False;instances.append(self)
        def setMimeData(self,data):raise RuntimeError('drag setup')
        def deleteLater(self):self.deleted=True
    monkeypatch.setattr(page_list,'QDrag',BrokenDrag)
    with pytest.raises(RuntimeError,match='drag setup'):
        widget.startDrag(Qt.DropAction.MoveAction)
    assert engine.phase=='running' and not engine._issued
    assert widget._drag_source_id is None and widget._drag_source_row is None
    assert len(instances)==1 and instances[0].deleted


def test_copy_cannot_complete_if_ui_tail_removes_an_existing_page(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    canvas.switch_page(1)
    host.panel.set_page_copy_placement('first',persist=False)
    original_count=len(canvas.pages)
    engine=attach_wait(host.panel,'page.copied')
    refresh=host.panel.update_whiteboard_ui
    def corrupt_tail():
        canvas.pages.pop(1)
        refresh()
    monkeypatch.setattr(host.panel,'update_whiteboard_ui',corrupt_tail)
    host.panel.copy_whiteboard_page()
    assert len(canvas.pages)==original_count
    assert engine.phase=='running' and not engine._issued


def test_reorder_cannot_complete_if_ui_tail_restores_original_order(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    before=list(canvas.pages)
    engine=attach_wait(host.panel,'page.reordered')
    refresh=host.panel.update_whiteboard_ui
    def undo_tail():
        canvas.pages=before
        canvas.current_page=0
        refresh()
    monkeypatch.setattr(host.panel,'update_whiteboard_ui',undo_tail)
    host.panel.reorder_whiteboard_page(2,0)
    assert [page['name'] for page in canvas.pages]==['A','B','C']
    assert engine.phase=='running' and not engine._issued


def test_drag_leave_failure_still_deletes_the_actual_owned_drag(application_host,monkeypatch):
    import page_list
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication,QEvent
    from PyQt6.QtGui import QDrag
    from PyQt6.QtWidgets import QAbstractItemView
    host,_=application_host
    prepare_pages(host)
    host.panel.toggle_thumbnail_panel()
    widget=host.panel.thumbnail_list
    widget.setCurrentRow(2)
    engine=attach_wait(host.panel,'page.reordered')
    created=[]
    def make_drag(source):
        drag=QDrag(source)
        created.append(drag)
        return drag
    monkeypatch.setattr(page_list,'QDrag',make_drag)
    monkeypatch.setattr(QDrag,'exec',lambda *args:Qt.DropAction.IgnoreAction)
    monkeypatch.setattr(QAbstractItemView,'dragLeaveEvent',Mock(side_effect=RuntimeError('owned leave')))
    with pytest.raises(RuntimeError,match='owned leave'):
        widget.startDrag(Qt.DropAction.MoveAction)
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    assert len(created)==1 and sip.isdeleted(created[0])
    assert widget._drag_source_id is None and not engine._issued


def test_delete_cancel_requires_original_page_content_and_order_to_survive(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host,2)
    engine=attach_wait(host.panel,'page.deleted',sequence=(WaitClause('page.deleted','cancelled',{'retained':True}),))
    def corrupt_cancel(box):
        canvas.pages[1]['name']='Changed'
        return QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox,'exec',corrupt_cancel)
    host.panel.delete_whiteboard_page()
    assert canvas.pages[1]['name']=='Changed'
    assert engine.phase=='running' and not engine._issued


def test_rename_result_never_carries_the_entered_page_name(application_host,monkeypatch):
    host,_=application_host
    canvas=prepare_pages(host)
    engine=attach_wait(host.panel,'page.renamed')
    results=[]
    emit=host.panel.teaching_events.emit_result
    def observe(context,name,outcome,details):
        results.append(dict(details))
        return emit(context,name,outcome,details)
    monkeypatch.setattr(host.panel.teaching_events,'emit_result',observe)
    entered='Private practice example name'
    monkeypatch.setattr(host.module.QInputDialog,'getText',lambda *args,**kwargs:(entered,True))
    host.panel.rename_whiteboard_page()
    assert canvas._page_name==entered and engine.phase=='completed'
    assert len(results)==1 and entered not in results[0].values()
    assert set(results[0])=={'page_id','page','pages'}
