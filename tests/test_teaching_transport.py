# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual Qt local sockets, not simulated frame delivery."""
import os
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QProcess, QProcessEnvironment
from PyQt6.QtNetwork import QLocalSocket
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate, timeout=3000):
    deadline = time.monotonic() + timeout / 1000
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert predicate(), 'Local transport did not reach the expected state'


@pytest.fixture
def peer(app):
    from teaching.transport import TeachingConnection, TeachingServer
    server = TeachingServer('session', 'nonce')
    name = server.listen()
    socket = QLocalSocket()
    client = TeachingConnection(socket, 'session', 'nonce')
    socket.connectToServer(name)
    until(app, lambda: socket.state() == QLocalSocket.LocalSocketState.ConnectedState)
    client.send('hello', {})
    until(app, lambda: server.connection is not None)
    yield server, client
    client.close()
    server.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_authenticated_messages_roundtrip(peer, app):
    server, client = peer
    seen = []
    client.received.connect(seen.append)
    server.connection.send('control', {'action': 'pause'})
    until(app, lambda: len(seen) == 1)
    assert seen[0]['type'] == 'control'
    assert seen[0]['payload']['action'] == 'pause'


def test_socket_read_buffer_is_bounded(peer):
    from teaching.transport import READ_BUFFER_BYTES
    server, client = peer
    assert client.socket.readBufferSize() == READ_BUFFER_BYTES
    assert server.connection.socket.readBufferSize() == READ_BUFFER_BYTES


def test_wrong_nonce_is_rejected_without_blocking_legitimate_peer(app):
    from teaching.transport import TeachingConnection, TeachingServer
    server = TeachingServer('session', 'nonce')
    name = server.listen()
    wrong = TeachingConnection(QLocalSocket(), 'session', 'wrong')
    valid = TeachingConnection(QLocalSocket(), 'session', 'nonce')
    try:
        wrong.socket.connectToServer(name)
        until(app, lambda: wrong.socket.state() == QLocalSocket.LocalSocketState.ConnectedState)
        wrong.send('hello', {})
        until(app, lambda: wrong.is_closed)
        assert server.connection is None
        valid.socket.connectToServer(name)
        until(app, lambda: valid.socket.state() == QLocalSocket.LocalSocketState.ConnectedState)
        valid.send('hello', {})
        until(app, lambda: server.connection is not None)
    finally:
        wrong.close(); valid.close(); server.close()


def test_first_authenticated_packet_must_be_hello(app):
    from teaching.transport import TeachingConnection, TeachingServer
    server = TeachingServer('session', 'nonce')
    bad = TeachingConnection(QLocalSocket(), 'session', 'nonce')
    try:
        bad.socket.connectToServer(server.listen())
        until(app, lambda: bad.socket.state() == QLocalSocket.LocalSocketState.ConnectedState)
        bad.send('ready', {})
        until(app, lambda: bad.is_closed)
        assert server.connection is None
    finally:
        bad.close(); server.close()


def test_second_peer_cannot_replace_authenticated_connection(peer, app):
    from teaching.transport import TeachingConnection
    server, client = peer
    original = server.connection
    extra = TeachingConnection(QLocalSocket(), 'session', 'nonce')
    try:
        extra.socket.connectToServer(server.name)
        until(app, lambda: extra.is_closed)
        assert server.connection is original
        assert not client.is_closed
    finally:
        extra.close()


def test_malformed_frame_closes_real_connection(peer, app):
    server, client = peer
    client.socket.write((65537).to_bytes(4, 'big'))
    client.socket.flush()
    until(app, lambda: client.is_closed)
    assert server.connection is None


def test_disconnection_is_reported_once(peer, app):
    server, client = peer
    closed = []
    client.closed.connect(lambda: closed.append(True))
    server.connection.close()
    until(app, lambda: client.is_closed)
    client.close(); client.close()
    assert closed == [True]


def test_send_after_close_is_rejected(peer):
    server, client = peer
    client.close()
    with pytest.raises(RuntimeError):
        client.send('ready', {})


def test_invalid_outbound_control_does_not_poison_transport(peer, app):
    from teaching.protocol import ProtocolError
    server, client = peer
    with pytest.raises(ProtocolError):
        client.send('control', {'action': 'shell'})
    assert not client.is_closed
    seen = []
    server.connection.received.connect(seen.append)
    client.send('ready', {})
    until(app, lambda: len(seen) == 1)


def test_handshake_deadline_closes_idle_client(app):
    from teaching.transport import TeachingConnection, TeachingServer
    server = TeachingServer('session', 'nonce', handshake_timeout_ms=30)
    client = TeachingConnection(QLocalSocket(), 'session', 'nonce')
    try:
        client.socket.connectToServer(server.listen())
        until(app, lambda: client.is_closed)
        assert server.connection is None
    finally:
        client.close(); server.close()


def test_server_close_cleans_pending_and_active_peers(peer, app):
    server, client = peer
    server.close()
    until(app, lambda: client.is_closed)
    assert server.connection is None
    assert server.pending_count == 0


def test_real_subprocess_can_use_the_same_local_protocol(app, tmp_path):
    from teaching.transport import TeachingServer
    server = TeachingServer('session', 'nonce')
    child_file = tmp_path / 'child_probe.py'
    child_file.write_text(r"""
import sys
sys.path.insert(0, sys.argv[2])
from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtNetwork import QLocalSocket
from teaching.transport import TeachingConnection
app=QCoreApplication([])
peer=TeachingConnection(QLocalSocket(), 'session', 'nonce')
peer.socket.connected.connect(lambda: peer.send('hello', {}))
def received(packet):
    if packet['type']=='control' and packet['payload']['action']=='activate':
        peer.send('activated', {})
        peer.socket.flush()
        QTimer.singleShot(100, app.quit)
peer.received.connect(received)
peer.socket.connectToServer(sys.argv[1])
QTimer.singleShot(5000, lambda: app.exit(5))
sys.exit(app.exec())
""", encoding='utf-8')
    process = QProcess()
    process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
    seen = []
    def accepted(connection):
        connection.received.connect(seen.append)
        connection.send('control', {'action': 'activate'})
    server.accepted.connect(accepted)
    try:
        process.start(sys.executable, [str(child_file), server.listen(), str(Path.cwd())])
        until(app, lambda: any(packet['type'] == 'activated' for packet in seen), timeout=5000)
        until(app, lambda: process.state() == QProcess.ProcessState.NotRunning, timeout=5000)
        assert process.exitCode() == 0
    finally:
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(2000)
        server.close()


def test_close_during_authentication_never_delivers_received_packet(app):
    from teaching.transport import TeachingConnection, TeachingServer
    server=TeachingServer('session','nonce')
    client=TeachingConnection(QLocalSocket(),'session','nonce')
    seen=[]
    def accepted(peer):
        peer.received.connect(seen.append)
        peer.close()
    server.accepted.connect(accepted)
    try:
        client.socket.connectToServer(server.listen())
        until(app,lambda:client.socket.state()==QLocalSocket.LocalSocketState.ConnectedState)
        client.send('hello',{})
        until(app,lambda:client.is_closed)
        assert seen==[]
    finally:
        client.close();server.close()
