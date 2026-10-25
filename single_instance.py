# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt IPC service for an ownership decision made before Qt is imported."""
from __future__ import annotations

import os
import tempfile

from PyQt6.QtCore import QObject, QLockFile, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from single_instance_bootstrap import (
    ACTIVATE_MESSAGE,
    NativeInstanceLease,
    application_endpoint,
    preflight_startup,
    replacement_pid,
    wait_for_process_exit,
)


class SingleInstanceGuard(QObject):
    """Host the activation pipe and retain the early native ownership lease."""

    activation_requested = pyqtSignal()

    def __init__(self, endpoint: str | None = None, *, lease: NativeInstanceLease | None = None,
                 parent=None):
        super().__init__(parent)
        if lease is not None and endpoint is not None and endpoint != lease.endpoint:
            raise ValueError("instance lease endpoint does not match server endpoint")
        self.endpoint = endpoint or (lease.endpoint if lease is not None else application_endpoint())
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self._sockets = set()
        self._primary = False
        self._lease = lease
        self._lock_file = None

    def start_primary_server(self) -> bool:
        """Start IPC after the native preflight has established ownership."""
        if self._primary:
            return True
        if os.name == "nt" and (self._lease is None or not self._lease.is_open):
            raise RuntimeError("Windows primary server requires an open native instance lease")
        if self.server.listen(self.endpoint):
            self._primary = True
            return True
        self._release_ownership()
        raise RuntimeError(f"cannot listen on application endpoint {self.endpoint!r}")

    def acquire_or_notify(self, timeout_ms: int = 1500) -> bool:
        """Compatibility entry used by tests and the non-Windows Qt fallback."""
        if self._lease is not None:
            return self.start_primary_server()
        if os.name == "nt":
            decision = preflight_startup([], endpoint=self.endpoint, timeout_ms=timeout_ms)
            if decision.role == "secondary":
                return False
            if decision.role != "primary" or decision.lease is None:
                raise RuntimeError(f"cannot decide application ownership for {self.endpoint!r}")
            self._lease = decision.lease
            return self.start_primary_server()

        if not self._claim_posix_ownership():
            if self._notify_primary(timeout_ms):
                return False
            if not self._claim_posix_ownership():
                raise RuntimeError(f"application owner exists but cannot be contacted: {self.endpoint!r}")
        try:
            return self.start_primary_server()
        except RuntimeError:
            if self._notify_primary(timeout_ms):
                return False
            raise

    def _claim_posix_ownership(self) -> bool:
        lock = QLockFile(os.path.join(tempfile.gettempdir(), f"{self.endpoint}.lock"))
        lock.setStaleLockTime(30000)
        if not lock.tryLock(0):
            return False
        self._lock_file = lock
        return True

    def _release_ownership(self):
        if self._lease is not None:
            self._lease.close()
            self._lease = None
        if self._lock_file is not None:
            self._lock_file.unlock()
            self._lock_file = None

    def _notify_primary(self, timeout_ms: int) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.endpoint)
        if not socket.waitForConnected(max(0, int(timeout_ms))):
            return False
        if socket.write(ACTIVATE_MESSAGE) < 0:
            return False
        socket.flush()
        socket.waitForBytesWritten(max(0, int(timeout_ms)))
        socket.disconnectFromServer()
        return True

    def _accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            self._sockets.add(socket)
            socket.readyRead.connect(lambda s=socket: self._read_request(s))
            socket.disconnected.connect(lambda s=socket: self._discard_socket(s))
            self._read_request(socket)

    def _read_request(self, socket):
        if socket not in self._sockets or socket.bytesAvailable() <= 0:
            return
        if ACTIVATE_MESSAGE.strip() in bytes(socket.readAll()):
            self.activation_requested.emit()
        socket.disconnectFromServer()

    def _discard_socket(self, socket):
        self._sockets.discard(socket)
        socket.deleteLater()

    def close(self):
        for socket in tuple(self._sockets):
            socket.abort()
            self._discard_socket(socket)
        if self.server.isListening():
            self.server.close()
        if self._primary:
            QLocalServer.removeServer(self.endpoint)
            self._primary = False
        self._release_ownership()


__all__ = [
    "SingleInstanceGuard", "application_endpoint", "replacement_pid",
    "wait_for_process_exit",
]
