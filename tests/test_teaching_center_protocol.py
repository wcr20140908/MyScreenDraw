# SPDX-License-Identifier: GPL-3.0-or-later
"""Authenticated center/chapter transactions; owned offscreen objects only."""
import copy
import uuid
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QApplication

from teaching.protocol import FrameCodec, PROTOCOL_VERSION
from teaching.practice import PracticeSession
from teaching.state import TutorialStateStore
from test_teaching_engine import make_catalog


KINDS=('center_request','center_state','center_close','center_closed',
       'chapter_request','chapter_offer','chapter_ready','chapter_commit')


@pytest.mark.parametrize('kind',KINDS)
def test_bounded_protocol_carries_center_and_chapter_messages(kind):
    codec=FrameCodec('session','a'*32)
    message={'protocol_version':PROTOCOL_VERSION,'session_id':'session','nonce':'a'*32,
             'message_id':uuid.uuid4().hex,'type':kind,'payload':{}}
    assert codec.feed(codec.encode(message))==[message]


@pytest.fixture
def parent(tmp_path):
    app=QApplication.instance() or QApplication([])
    store=TutorialStateStore(tmp_path/'progress.json')
    calls=[]
    broker=PracticeSession(make_catalog(),app_dir=tmp_path,resource_dir=tmp_path,
        temp_root=tmp_path/'temp',state_store=store,command_factory=Mock(side_effect=AssertionError('no third process')),
        suspend=Mock(side_effect=AssertionError('original already suspended')),
        restore=lambda token:calls.append(('restore',token)),stop_timeout_ms=10)
    broker.phase='running';broker._chapter_id='c01.save';broker._compat_revision=1
    broker._token=object();broker._hidden=False
    messages=[]
    broker._send=lambda kind,payload: messages.append((kind,copy.deepcopy(payload))) or True
    yield broker,messages,calls
    if broker.phase not in ('idle','stopped'): broker.request_stop('test complete')
    broker.deleteLater()


def deliver(broker,kind,payload):
    broker._receive({'type':kind,'payload':payload,'message_id':uuid.uuid4().hex},broker._generation)


def open_center(broker,messages):
    center=uuid.uuid4().hex
    deliver(broker,'center_request',{'center_id':center})
    assert broker.phase=='paused'
    assert messages[-1][0]=='center_state'
    assert messages[-1][1]['center_id']==center
    return center


def test_center_reads_parent_progress_without_original_restore(parent):
    broker,messages,calls=parent
    broker.state_store.record_chapter('c01.other','completed',compat_revision=1)
    token=broker._token
    center=open_center(broker,messages)
    view=messages[-1][1]['view']
    assert view['records']['c01.other']['status']=='completed'
    assert broker._token is token and calls==[]
    deliver(broker,'center_close',{'center_id':center})
    assert messages[-1]==('center_closed',{'center_id':center,'resume':True,'hidden':False})
    assert broker.phase=='running' and calls==[]


def test_center_return_preserves_explicit_pause(parent):
    broker,messages,calls=parent
    broker.phase='paused'
    center=open_center(broker,messages)
    deliver(broker,'center_close',{'center_id':center})
    assert broker.phase=='paused' and not messages[-1][1]['resume']


def test_hidden_center_close_never_wakes_the_lesson(parent):
    broker,messages,calls=parent
    center=open_center(broker,messages)
    assert broker.request_pause(hidden=True)
    deliver(broker,'center_close',{'center_id':center})
    assert broker.phase=='paused' and messages[-1][1]['hidden'] and not messages[-1][1]['resume']


def test_switch_is_committed_only_after_matching_child_ready(parent):
    broker,messages,calls=parent
    center=open_center(broker,messages); switch=uuid.uuid4().hex; token=broker._token
    payload={'center_id':center,'switch_id':switch,'from_chapter_id':'c01.save',
             'course_id':'c01','chapter_id':'c01.other'}
    deliver(broker,'chapter_request',payload)
    assert broker.phase=='switching' and broker._chapter_id=='c01.save'
    kind,offer=messages[-1]
    assert kind=='chapter_offer' and offer['switch_id']==switch and offer['compat_revision']==1
    ready={key:offer[key] for key in ('center_id','switch_id','course_id','chapter_id')}
    deliver(broker,'chapter_ready',ready)
    assert broker.phase=='running' and broker._chapter_id=='c01.other'
    assert messages[-1]==('chapter_commit',ready)
    assert broker._token is token and calls==[] and broker.command_factory.call_count==0
    deliver(broker,'chapter_state',{'chapter_id':'c01.other','status':'completed','compat_revision':1})
    assert broker.state_store.chapter_status('c01.other')=='completed'
    assert messages[-1][0]=='state_ack' and 'view' in messages[-1][1]


@pytest.mark.parametrize('corruption',['unknown','wrong_origin','wrong_center','extra'])
def test_invalid_switch_never_changes_current_chapter(parent,corruption):
    broker,messages,calls=parent;center=open_center(broker,messages)
    request={'center_id':center,'switch_id':uuid.uuid4().hex,'from_chapter_id':'c01.save',
             'course_id':'c01','chapter_id':'c01.other'}
    if corruption=='unknown': request['chapter_id']='c01.missing'
    elif corruption=='wrong_origin': request['from_chapter_id']='c01.other'
    elif corruption=='wrong_center': request['center_id']=uuid.uuid4().hex
    else: request['unsafe']='not allowed'
    deliver(broker,'chapter_request',request)
    assert broker._chapter_id=='c01.save'
    assert not any(kind=='chapter_offer' for kind,_ in messages)
    assert broker.last_error is not None


@pytest.mark.parametrize('prefix',['0','9','a','f'])
def test_transaction_uuid_is_not_a_domain_identifier(parent,prefix):
    broker,messages,calls=parent
    center=prefix*32
    deliver(broker,'center_request',{'center_id':center})
    assert broker.phase=='paused' and messages[-1][1]['center_id']==center
