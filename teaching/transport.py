# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded Qt local transport; no process launch, UI, document or shell operations."""
from __future__ import annotations

import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from .protocol import FrameCodec, MAX_FRAME_BYTES, PROTOCOL_VERSION, ProtocolError

READ_BUFFER_BYTES = 2 * (MAX_FRAME_BYTES + 4)
MAX_QUEUED_WRITE_BYTES = 4 * (MAX_FRAME_BYTES + 4)
_READ_CHUNK_BYTES = MAX_FRAME_BYTES + 4


class TeachingConnection(QObject):
    received = pyqtSignal(dict)
    closed = pyqtSignal()
    failed = pyqtSignal(str)
    authenticated = pyqtSignal()

    def __init__(self, socket: QLocalSocket, session_id: str, nonce: str, *,
                 require_hello: bool = False, handshake_timeout_ms: int = 2000,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._codec = FrameCodec(session_id, nonce)
        self._session_id, self._nonce = session_id, nonce
        self.socket = socket
        socket.setParent(self)
        socket.setReadBufferSize(READ_BUFFER_BYTES)
        self._closed = False
        self._require_hello = require_hello
        self._authenticated = not require_hello
        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.timeout.connect(self._drain)
        self._handshake_timer = QTimer(self)
        self._handshake_timer.setSingleShot(True)
        self._handshake_timer.timeout.connect(lambda: self._fail('handshake_timeout'))
        socket.readyRead.connect(self._queue_read)
        socket.disconnected.connect(self.close)
        socket.errorOccurred.connect(lambda error: self._fail('socket_error'))
        if require_hello:
            self._handshake_timer.start(handshake_timeout_ms)
        if socket.bytesAvailable():
            self._queue_read()

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _queue_read(self) -> None:
        if not self._closed and not self._read_timer.isActive():
            self._read_timer.start(0)

    def _drain(self) -> None:
        # Yield to UI/process shutdown after each bounded burst.
        for _ in range(4):
            if self._closed or not self.socket.bytesAvailable():
                return
            raw = bytes(self.socket.read(min(self.socket.bytesAvailable(), _READ_CHUNK_BYTES)))
            try:
                packets = self._codec.feed(raw)
            except ProtocolError:
                self._fail('protocol_error')
                return
            for packet in packets:
                if self._closed:
                    return
                if not self._authenticated:
                    if packet['type'] != 'hello':
                        self._fail('expected_hello')
                        return
                    self._authenticated = True
                    self._handshake_timer.stop()
                    self.authenticated.emit()
                if self._closed:
                    return
                self.received.emit(packet)
        if not self._closed and self.socket.bytesAvailable():
            self._queue_read()

    def send(self, kind: str, payload: dict, *, message_id: str | None = None) -> str:
        if self._closed or self.socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            raise RuntimeError('teaching connection is not connected')
        identifier = message_id or uuid.uuid4().hex
        frame = self._codec.encode({
            'protocol_version': PROTOCOL_VERSION, 'session_id': self._session_id,
            'nonce': self._nonce, 'message_id': identifier, 'type': kind, 'payload': payload,
        })
        if self.socket.bytesToWrite() + len(frame) > MAX_QUEUED_WRITE_BYTES:
            self._fail('write_budget_exceeded')
            raise RuntimeError('teaching write budget exceeded')
        if self.socket.write(frame) != len(frame):
            self._fail('write_failed')
            raise RuntimeError('teaching write failed')
        self.socket.flush()
        return identifier

    def _fail(self, code: str) -> None:
        if self._closed:
            return
        self.failed.emit(code)
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._read_timer.stop()
        self._handshake_timer.stop()
        self.socket.abort()
        self.closed.emit()


class TeachingServer(QObject):
    accepted = pyqtSignal(object)
    disconnected = pyqtSignal()

    def __init__(self, session_id: str, nonce: str, *, handshake_timeout_ms: int = 2000,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        FrameCodec(session_id, nonce)  # Validate credentials before opening a pipe.
        self._session_id, self._nonce = session_id, nonce
        self._handshake_timeout_ms = handshake_timeout_ms
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.setMaxPendingConnections(2)
        self._server.newConnection.connect(self._accept_pending)
        self._pending: set[TeachingConnection] = set()
        self.connection: TeachingConnection | None = None
        self.name = 'myscreendraw-teaching-' + uuid.uuid4().hex
        self._closed = False

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def listen(self) -> str:
        if self._closed:
            raise RuntimeError('teaching server is closed')
        if self._server.isListening():
            return self.name
        if not self._server.listen(self.name):
            raise RuntimeError('could not open teaching local server')
        return self.name

    def _accept_pending(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                return
            if self._closed or self.connection is not None or len(self._pending) >= 2:
                socket.abort()
                socket.deleteLater()
                continue
            connection = TeachingConnection(socket, self._session_id, self._nonce,
                require_hello=True, handshake_timeout_ms=self._handshake_timeout_ms, parent=self)
            self._pending.add(connection)
            connection.authenticated.connect(lambda peer=connection: self._promote(peer))
            connection.closed.connect(lambda peer=connection: self._forget(peer))

    def _promote(self, peer: TeachingConnection) -> None:
        if self._closed or self.connection is not None:
            peer.close()
            return
        self._pending.discard(peer)
        self.connection = peer
        self.accepted.emit(peer)

    def _forget(self, peer: TeachingConnection) -> None:
        self._pending.discard(peer)
        was_current = self.connection is peer
        if was_current:
            self.connection = None
        peer.deleteLater()
        if was_current:
            self.disconnected.emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._server.close()
        peers = tuple(self._pending) + ((self.connection,) if self.connection is not None else ())
        for peer in peers:
            peer.close()
        self._pending.clear()
        self.connection = None
