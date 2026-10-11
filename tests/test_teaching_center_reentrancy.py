# SPDX-License-Identifier: GPL-3.0-or-later
"""Center teardown and synchronous Qt/protocol reentrancy; offscreen only."""
import uuid
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QMessageBox

from test_teaching_application import practice_request
from test_teaching_center_protocol import parent, deliver, open_center
from test_teaching_center_results import visit_host
from test_teaching_private_center import center_host, accepted_center


def test_failed_scene_restore_releases_native_scope_without_crediting_visit(visit_host, tmp_path, monkeypatch):
    host, progress = visit_host
    accepted_center(host, tmp_path)
    restore = host.panel.lifecycle.restore_after_teaching
    with monkeypatch.context() as patch:
        patch.setattr(host.panel.lifecycle, 'restore_after_teaching', Mock(side_effect=RuntimeError('controlled restore failure')))
        with pytest.raises(RuntimeError, match='controlled restore failure'):
            host.finish_center(resume=True)
    assert host.presenter._dialog_depth == 0
    assert host._center_native is None and host._center_batch is None
    assert host.panel._teaching_suspended and not host.panel.canvas.isVisible()
    assert host.presenter.engine.phase == 'paused'
    assert not any(record[1] == 'completed' for record in progress)
    monkeypatch.setattr(host.panel.lifecycle, 'restore_after_teaching', restore)


def test_close_cleans_every_resource_even_if_scene_restore_would_fail(visit_host, tmp_path, monkeypatch):
    host, _ = visit_host
    accepted_center(host, tmp_path)
    restore = Mock(side_effect=RuntimeError('controlled restore failure'))
    monkeypatch.setattr(host.panel.lifecycle, 'restore_after_teaching', restore)
    try:
        host.close()
    except RuntimeError:
        pass
    host.close()
    assert host.presenter._closed and host.presenter.engine.phase == 'stopped'
    assert host.presenter._dialog_depth == 0 and host._center_native is None
    assert host.panel.teaching_host is None and host.panel.teaching_presenter is None
    assert host.panel.teaching_events is None
    assert all(not timer.isActive() for timer in host.panel.findChildren(QTimer))
    assert not host.panel.canvas.isVisible()
    assert not restore.called  # A child that is exiting does not need its scene shown again.


def test_close_during_confirmation_handles_synchronously_deleted_dialog(center_host, tmp_path, monkeypatch):
    host, _ = center_host
    accepted_center(host, tmp_path)
    requests = QSignalSpy(host.chapter_requested)
    center = host.center
    def close_and_delete(box):
        host.close()
        if not sip.isdeleted(center):
            sip.delete(center)
        assert sip.isdeleted(box)
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(host.module.QMessageBox, 'exec', close_and_delete)
    assert not host._select_chapter('c01', 'c01.second')
    assert len(requests) == 0


def test_confirmation_reserves_request_before_reentrant_finished_callback(center_host, tmp_path, monkeypatch):
    host, _ = center_host
    accepted_center(host, tmp_path)
    requests = QSignalSpy(host.chapter_requested)
    count = 0
    inner = []
    def accept(box):
        nonlocal count
        count += 1
        if count == 1:
            inner.append(host._select_chapter('c01', 'c01.foundation'))
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(host.module.QMessageBox, 'exec', accept)
    assert host._select_chapter('c01', 'c01.second')
    assert inner == [False] and count == 1
    assert list(requests) == [['c01', 'c01.second']]


@pytest.mark.parametrize('hidden', [False, True])
def test_pause_during_scene_restore_survives_outer_resume(visit_host, tmp_path, monkeypatch, hidden):
    host, progress = visit_host
    accepted_center(host, tmp_path)
    original = host.panel.lifecycle.restore_after_teaching
    def restore(token):
        original(token)
        host.pause(hidden=hidden)
    monkeypatch.setattr(host.panel.lifecycle, 'restore_after_teaching', restore)
    host.finish_center(resume=True)
    assert host.presenter.engine.phase == 'paused'
    assert host.panel.canvas.isVisible() is (not hidden)
    assert (host._hidden_token is not None) is hidden
    assert not any(record[1] == 'completed' for record in progress)
    monkeypatch.setattr(host.panel.lifecycle, 'restore_after_teaching', original)
    host.resume()
    assert host.panel.canvas.isVisible() and host.presenter.engine.phase == 'running'


@pytest.mark.parametrize('hidden', [False, True])
def test_parent_center_reply_precedes_observer_pause(parent, hidden):
    broker, messages, _ = parent
    center = open_center(broker, messages)
    broker.phase_changed.connect(lambda phase: broker.request_pause(hidden=hidden) if phase == 'running' else None)
    deliver(broker, 'center_close', {'center_id': center})
    assert messages[-2:] == [('center_closed', {'center_id': center, 'resume': True, 'hidden': False}),
                            ('control', {'action': 'pause', 'hidden': hidden})]
    assert broker.phase == 'paused' and broker._hidden is hidden


def test_parent_chapter_commit_precedes_observer_hidden_pause(parent):
    broker, messages, _ = parent
    center = open_center(broker, messages)
    deliver(broker, 'chapter_request', {'center_id': center, 'switch_id': uuid.uuid4().hex,
                                      'from_chapter_id': 'c01.save', 'course_id': 'c01', 'chapter_id': 'c01.other'})
    ready = {key: messages[-1][1][key] for key in ('center_id', 'switch_id', 'course_id', 'chapter_id')}
    broker.phase_changed.connect(lambda phase: broker.request_pause(hidden=True) if phase == 'running' else None)
    deliver(broker, 'chapter_ready', ready)
    assert messages[-2:] == [('chapter_commit', ready), ('control', {'action': 'pause', 'hidden': True})]
    assert broker.phase == 'paused' and broker._hidden
