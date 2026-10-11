# SPDX-License-Identifier: GPL-3.0-or-later
"""A private child drains old ACKs before replacing a chapter in the same process."""
import copy
import json
import uuid
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import pyqtSignal

from runtime_paths import RuntimeContext
from teaching.application import PracticeChild, application_catalog
from teaching.session_view import parent_progress_view
from teaching.state import TutorialStateStore
from test_teaching_application import Peer, Host, practice_request


class CenterHost(Host):
    center_requested=pyqtSignal()
    center_closed=pyqtSignal()
    chapter_requested=pyqtSignal(str,str)
    def __init__(self, progress, catalog):
        super().__init__(progress);self.catalog=catalog
        self.chapter='c01.foundation';self.update_parent_view=Mock()
    def accept_center(self, view, *, hidden=False):
        self.calls.append(('center',hidden));self.update_parent_view(view)
    def finish_center(self, *, resume, hidden=False):
        self.calls.append(('close_center',resume,hidden))
    def prepare_chapter_change(self):
        self.calls.append('stop_old');self.progress(self.chapter,'in_progress',1)
    def prepare_chapter(self,course,chapter):
        self.chapter=chapter;self.calls.append(('prepare',course,chapter))
        self.progress(chapter,'in_progress',1)
    def commit_chapter(self):
        self.calls.append('commit')


@pytest.fixture
def child_center(practice_request,monkeypatch,tmp_path):
    import main
    path=practice_request.paths.resource_dir/'assets/tutorials/course.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    second=copy.deepcopy(data['chapters'][0]);second['id']='c01.second'
    data['chapters'].append(second);path.write_text(json.dumps(data),encoding='utf-8')
    catalog,_=application_catalog(main,practice_request.paths.resource_dir)
    peer=Peer();context=RuntimeContext(practice_request.paths);hosts=[]
    def factory(progress):
        host=CenterHost(progress,catalog);hosts.append(host);return host
    runtime=PracticeChild(practice_request,peer,context=context,host_factory=factory)
    runtime.start();peer.control('activate')
    store=TutorialStateStore(tmp_path/'parent-state.json')
    yield runtime,peer,hosts[0],parent_progress_view(catalog,store)
    runtime.stop(send=False)


def ack(runtime,peer,view=None):
    for mid,(chapter,status) in list(runtime._pending.items()):
        payload={'message_id':mid,'chapter_id':chapter,'persisted':True}
        if view is not None: payload['view']=copy.deepcopy(view)
        peer.received.emit({'type':'state_ack','payload':payload})


def open_center(runtime,peer,host,view):
    ack(runtime,peer)
    host.center_requested.emit()
    request=next(payload for kind,payload,_ in reversed(peer.messages) if kind=='center_request')
    peer.received.emit({'type':'center_state','payload':{'center_id':request['center_id'],
        'view':copy.deepcopy(view),'resume_on_close':True,'hidden':False}})
    assert runtime.phase=='paused' and host.calls[-1]==('center',False)
    return request['center_id']


def test_center_request_waits_for_original_progress_ack(child_center):
    runtime,peer,host,view=child_center
    assert runtime._pending
    host.center_requested.emit()
    assert not any(kind=='center_request' for kind,_,_ in peer.messages)
    ack(runtime,peer)
    assert peer.messages[-1][0]=='center_request'


def test_center_close_returns_to_same_chapter_and_parent_authority(child_center):
    runtime,peer,host,view=child_center
    center=open_center(runtime,peer,host,view)
    host.center_closed.emit()
    assert peer.messages[-1][:2]==('center_close',{'center_id':center})
    peer.received.emit({'type':'center_closed','payload':{'center_id':center,'resume':True,'hidden':False}})
    assert runtime.phase=='running' and host.calls[-1]==('close_center',True,False)
    assert runtime.request.chapter_id=='c01.foundation'


def test_chapter_offer_prepares_but_does_not_send_progress_before_commit(child_center):
    runtime,peer,host,view=child_center
    center=open_center(runtime,peer,host,view)
    host.chapter_requested.emit('c01','c01.second')
    assert host.calls[-1]=='stop_old'
    assert not any(kind=='chapter_request' for kind,_,_ in peer.messages)
    ack(runtime,peer,view)
    request=peer.messages[-1][1]
    assert peer.messages[-1][0]=='chapter_request' and request['from_chapter_id']=='c01.foundation'
    offer={key:request[key] for key in ('center_id','switch_id','course_id','chapter_id')}
    offer.update(revision=1,compat_revision=1)
    peer.received.emit({'type':'chapter_offer','payload':offer})
    assert runtime.phase=='switching' and peer.messages[-1][0]=='chapter_ready'
    assert not any(kind=='chapter_state' and payload['chapter_id']=='c01.second' for kind,payload,_ in peer.messages)
    commit={key:offer[key] for key in ('center_id','switch_id','course_id','chapter_id')}
    peer.received.emit({'type':'chapter_commit','payload':commit})
    assert runtime.phase=='running' and host.calls[-1]=='commit'
    assert peer.messages[-1][0]=='chapter_state' and peer.messages[-1][1]['chapter_id']=='c01.second'
    assert runtime.request.paths is runtime.context.paths and runtime.request.chapter_id=='c01.foundation'


@pytest.mark.parametrize('corruption',['center','switch','revision','unknown','extra'])
def test_bad_chapter_offer_fails_closed_without_preparing(child_center,corruption):
    runtime,peer,host,view=child_center
    center=open_center(runtime,peer,host,view)
    host.chapter_requested.emit('c01','c01.second');ack(runtime,peer,view)
    request=peer.messages[-1][1]
    offer={key:request[key] for key in ('center_id','switch_id','course_id','chapter_id')}
    offer.update(revision=1,compat_revision=1)
    if corruption=='center': offer['center_id']=uuid.uuid4().hex
    elif corruption=='switch': offer['switch_id']=uuid.uuid4().hex
    elif corruption=='revision': offer['compat_revision']=True
    elif corruption=='unknown': offer['chapter_id']='c01.unknown'
    else: offer['unexpected']=True
    peer.received.emit({'type':'chapter_offer','payload':offer})
    assert runtime.phase=='stopped' and not runtime.context.ui_active
    assert not any(isinstance(call,tuple) and call[0]=='prepare' for call in host.calls)


def test_unsolicited_center_snapshot_is_not_a_ui_capability(child_center):
    runtime,peer,host,view=child_center
    peer.received.emit({'type':'center_state','payload':{'center_id':uuid.uuid4().hex,
        'view':view,'resume_on_close':True,'hidden':False}})
    assert runtime.phase=='stopped'
    assert not any(isinstance(call,tuple) and call[0]=='center' for call in host.calls)
