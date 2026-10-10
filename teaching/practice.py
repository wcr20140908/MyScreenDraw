# SPDX-License-Identifier: GPL-3.0-or-later
"""Parent-owned practice broker. A trusted launcher is required until app integration."""
from __future__ import annotations

from pathlib import Path
import stat
from typing import Callable

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from runtime_paths import RuntimePaths
from .bootstrap import PracticeRequest
from .models import TutorialCatalog
from .state import TutorialStateStore
from .transport import TeachingConnection, TeachingServer


class PracticeSession(QObject):
    phase_changed = pyqtSignal(str)
    progress_saved = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, catalog: TutorialCatalog, *, app_dir: Path, resource_dir: Path,
                 temp_root: Path, state_store: TutorialStateStore,
                 command_factory: Callable[[PracticeRequest], tuple[str, list[str]]],
                 suspend: Callable[[], object | None], restore: Callable[[object], None],
                 startup_timeout_ms: int = 15000, activation_timeout_ms: int = 5000,
                 stop_timeout_ms: int = 5000, kill_timeout_ms: int = 2000,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.app_dir = Path(app_dir).resolve()
        self.resource_dir = Path(resource_dir).resolve()
        self.temp_root = Path(temp_root).resolve()
        self.state_store = state_store
        self.command_factory, self.suspend, self.restore = command_factory, suspend, restore
        self.startup_timeout_ms = startup_timeout_ms
        self.activation_timeout_ms = activation_timeout_ms
        self.stop_timeout_ms, self.kill_timeout_ms = stop_timeout_ms, kill_timeout_ms
        self.phase = 'idle'
        self.paths: RuntimePaths | None = None
        self.process: QProcess | None = None
        self.last_error: str | None = None
        self.cleanup_retained = False
        self._generation = 0
        self._server: TeachingServer | None = None
        self._peer: TeachingConnection | None = None
        self._timers: dict[str, QTimer] = {}
        self._token: object | None = None
        self._suspending = False
        self._finishing = False
        self._restoring = False
        self._hello_seen = False
        self._chapter_id: str | None = None
        self._compat_revision: int | None = None

    @property
    def restore_pending(self) -> bool:
        """Whether a suspension token still needs successful restoration."""
        return self._token is not None

    def retry_restore(self) -> bool:
        """Explicitly retry a failed restore; already-restored calls are no-ops.

        Returns False while the child/cleanup or a restore callback is active.
        Restore callbacks must tolerate retry with the same token after an error.
        """
        if self.phase == 'stopped' and not self.restore_pending:
            return True
        if self.phase != 'restore_failed':
            return False
        return self._restore_original()

    def _set_phase(self, phase: str) -> None:
        self.phase = phase
        self.phase_changed.emit(phase)

    def _error(self, code: str) -> None:
        if self.last_error is None:
            self.last_error = code
            self.failed.emit(code)

    def _arm(self, name: str, milliseconds: int, callback: Callable[[], None]) -> None:
        self._cancel(name)
        generation = self._generation
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: callback() if generation == self._generation else None)
        self._timers[name] = timer
        timer.start(max(1, int(milliseconds)))

    def _cancel(self, name: str) -> None:
        timer = self._timers.pop(name, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def start(self, course_id: str, chapter_id: str) -> None:
        if self.phase not in ('idle', 'stopped') or self.restore_pending:
            raise RuntimeError('a practice session is already active')
        course = self.catalog.course_by_id(course_id)
        if not any(chapter.id == chapter_id for chapter in course.chapters):
            raise KeyError(chapter_id)
        self._generation += 1
        generation = self._generation
        self.last_error = None
        self.cleanup_retained = False
        self._token = None
        self._hello_seen = False
        self._chapter_id, self._compat_revision = chapter_id, course.compat_revision
        self.paths = None
        self._set_phase('starting')
        if generation != self._generation or self.phase != 'starting':
            return
        try:
            self.paths = RuntimePaths.create_practice(self.app_dir, self.resource_dir,
                                                     temp_root=self.temp_root)
            self._server = TeachingServer(self.paths.session_id, self.paths.nonce, parent=self)
            channel = self._server.listen()
            request = PracticeRequest(self.paths, channel, course_id, chapter_id)
            program, arguments = self.command_factory(request)
            if (not isinstance(program, str) or not program or type(arguments) is not list
                    or any(not isinstance(argument, str) for argument in arguments)):
                raise ValueError('invalid practice launch command')
            self._server.accepted.connect(lambda peer: self._accept(peer, generation))
            self._server.disconnected.connect(lambda: self._disconnected(generation))
            process = QProcess(self)
            self.process = process
            environment = QProcessEnvironment.systemEnvironment()
            environment.insert('MYSCREENDRAW_PRACTICE_NONCE', self.paths.nonce)
            environment.insert('MYSCREENDRAW_PRACTICE_TEMP_ROOT', str(self.paths.temp_root))
            process.setProcessEnvironment(environment)
            process.setWorkingDirectory(str(self.app_dir))
            # No unbounded Qt stdout/stderr accumulation, and no credentials in logs.
            process.setStandardOutputFile(QProcess.nullDevice())
            process.setStandardErrorFile(QProcess.nullDevice())
            process.finished.connect(lambda *_: self._exited(generation))
            process.errorOccurred.connect(lambda error: self._process_error(error, generation))
            self._arm('startup', self.startup_timeout_ms, self._startup_timeout)
            process.start(program, arguments)
        except Exception:
            self._error('start_failed')
            self.request_stop('start_failed')

    def _accept(self, peer: TeachingConnection, generation: int) -> None:
        if generation != self._generation or self.phase != 'starting' or self._peer is not None:
            peer.close()
            return
        self._peer = peer
        peer.received.connect(lambda packet: self._receive(packet, generation))
        peer.failed.connect(lambda _: self._transport_failed(generation))

    def _receive(self, message: dict, generation: int) -> None:
        if generation != self._generation or self.phase in ('idle', 'restoring', 'restore_failed', 'stopped'):
            return
        kind, payload = message['type'], message['payload']
        if self.phase == 'stopping':
            # A stopped packet is advisory, never proof the owned process exited.
            if kind not in ('stopped', 'stopping', 'error') or payload:
                self._error('invalid_message')
            return
        if kind == 'hello' and self.phase == 'starting' and not self._hello_seen and not payload:
            self._hello_seen = True
        elif kind == 'ready' and self.phase == 'starting' and self._hello_seen and not payload:
            self._cancel('startup')
            self._set_phase('ready')
            self.try_activate()
        elif kind == 'activated' and self.phase == 'activating' and not payload:
            self._cancel('activation')
            self._set_phase('running')
        elif (kind == 'control' and self.phase in ('running', 'paused')
              and set(payload) == {'action'} and payload['action'] in ('pause', 'resume')):
            # Child controller requests; the parent's response remains authoritative.
            if payload['action'] == 'pause':
                self.request_pause()
            elif self.phase == 'paused':
                self.request_resume()
            else:
                self._send('control', {'action': 'resume'})
        elif kind == 'chapter_state' and self.phase in ('running', 'paused'):
            self._record_progress(message)
        elif kind in ('stopping', 'stopped') and not payload:
            self.request_stop('child_stop')
        else:
            self._error('child_error' if kind == 'error' else 'invalid_message')
            self.request_stop('invalid_message')

    def try_activate(self) -> bool:
        if self.phase != 'ready' or self._peer is None or self._suspending:
            return False
        generation = self._generation
        self._suspending = True
        try:
            token = self.suspend()
        except Exception:
            token = None
            self._error('suspend_failed')
            self.request_stop('suspend_failed')
        finally:
            self._suspending = False
        if token is not None:
            self._token = token
        if self.phase != 'ready':
            self._finish()
            return False
        if token is None:
            return False
        self._set_phase('activating')
        if generation != self._generation or self.phase != 'activating':
            return False
        self._arm('activation', self.activation_timeout_ms, self._activation_timeout)
        return self._send('control', {'action': 'activate'})

    def request_pause(self, hidden: bool = False) -> bool:
        if type(hidden) is not bool:
            raise ValueError('hidden pause must be a boolean')
        if self.phase not in ('running', 'paused'):
            return False
        generation = self._generation
        self._set_phase('paused')
        if generation != self._generation or self.phase != 'paused':
            return False
        return self._send('control', {'action': 'pause', 'hidden': hidden})

    def request_resume(self) -> bool:
        if self.phase != 'paused':
            return False
        generation = self._generation
        self._set_phase('running')
        if generation != self._generation or self.phase != 'running':
            return False
        return self._send('control', {'action': 'resume'})

    def _record_progress(self, message: dict) -> None:
        payload = message['payload']
        if (set(payload) != {'chapter_id', 'status', 'compat_revision'}
                or payload['chapter_id'] != self._chapter_id
                or type(payload['compat_revision']) is not int
                or payload['compat_revision'] != self._compat_revision
                or not isinstance(payload['status'], str)
                or payload['status'] not in ('in_progress', 'completed', 'skipped')):
            self._error('invalid_progress')
            self.request_stop('invalid_progress')
            return
        try:
            persisted = self.state_store.record_chapter(payload['chapter_id'], payload['status'],
                                                       compat_revision=payload['compat_revision'])
        except (ValueError, OSError):
            persisted = False
        self._send('state_ack', {'message_id': message['message_id'],
                               'chapter_id': payload['chapter_id'], 'persisted': bool(persisted)})
        if persisted:
            self.progress_saved.emit(dict(payload))

    def _send(self, kind: str, payload: dict) -> bool:
        try:
            if self._peer is None:
                raise RuntimeError('no practice peer')
            self._peer.send(kind, payload)
            return True
        except (RuntimeError, ValueError):
            self._error('connection_lost')
            self.request_stop('connection_lost')
            return False

    def _transport_failed(self, generation: int) -> None:
        if generation == self._generation and self.phase not in (
                'idle', 'stopping', 'restoring', 'restore_failed', 'stopped'):
            self._error('child_exited' if self.phase == 'starting' else 'connection_lost')
            self.request_stop('connection_lost')

    def _disconnected(self, generation: int) -> None:
        if generation == self._generation:
            self._peer = None
            self._transport_failed(generation)

    def _startup_timeout(self) -> None:
        if self.phase == 'starting':
            self._error('startup_timeout')
            self.request_stop('startup_timeout')

    def _activation_timeout(self) -> None:
        if self.phase == 'activating':
            self._error('activation_timeout')
            self.request_stop('activation_timeout')

    def _process_error(self, error: QProcess.ProcessError, generation: int) -> None:
        if generation != self._generation:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._error('start_failed')
            self.request_stop('start_failed')
            self._arm('failed_start', 1, self._finish)
        elif error == QProcess.ProcessError.Crashed and self.phase not in (
                'stopping', 'restoring', 'restore_failed', 'stopped'):
            self._error('child_exited')

    def _exited(self, generation: int) -> None:
        if generation != self._generation:
            return
        if self.phase not in ('stopping', 'restoring', 'restore_failed', 'stopped'):
            self._error('child_exited')
        self._finish()

    def request_stop(self, reason: str) -> None:
        if self.phase in ('idle', 'stopped', 'stopping', 'restoring', 'restore_failed'):
            return
        self._set_phase('stopping')
        self._cancel('startup')
        self._cancel('activation')
        if self.process is None or self.process.state() == QProcess.ProcessState.NotRunning:
            self._finish()
            return
        if self._peer is not None and not self._peer.is_closed:
            self._send('control', {'action': 'stop'})
        self._arm('stop', self.stop_timeout_ms, self._terminate)

    def _terminate(self) -> None:
        if self.process is None or self.process.state() == QProcess.ProcessState.NotRunning:
            self._finish()
            return
        self.process.terminate()
        self._arm('kill', self.kill_timeout_ms, self._kill)

    def _kill(self) -> None:
        if self.process is None or self.process.state() == QProcess.ProcessState.NotRunning:
            self._finish()
            return
        self.process.kill()
        # Keep original UI suspended until finished / NotRunning is confirmed.
        self._arm('kill', self.kill_timeout_ms, self._kill)

    def _finish(self) -> None:
        if self.phase in ('stopped', 'restoring', 'restore_failed') or self._finishing:
            return
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self._finishing = True
        try:
            if self.phase != 'stopping':
                self._set_phase('stopping')
            for name in tuple(self._timers):
                self._cancel(name)
            # suspend() may pump events: do not finish before its token is returned.
            if self._suspending:
                return
            server, self._server = self._server, None
            self._peer = None
            if server is not None:
                server.close()
                server.deleteLater()
            process, self.process = self.process, None
            if process is not None:
                process.deleteLater()
            self._cleanup()
        finally:
            self._finishing = False
        self._restore_original()

    def _restore_original(self) -> bool:
        if (self.phase not in ('stopping', 'restore_failed')
                or self.process is not None or self._restoring):
            return False
        token = self._token
        if token is not None:
            self._restoring = True
            try:
                self._set_phase('restoring')
                self.restore(token)
            except Exception:
                if self.last_error is None:
                    self.last_error = 'restore_failed'
                self._set_phase('restore_failed')
                # Unlike _error(), report every restore failure, even after a child error.
                self.failed.emit('restore_failed')
                return False
            finally:
                self._restoring = False
            self._token = None
        self._set_phase('stopped')
        return True

    def _cleanup(self) -> None:
        paths = self.paths
        if paths is None:
            return
        try:
            verified = RuntimePaths.for_practice(paths.app_dir, paths.resource_dir, paths.runtime_root,
                temp_root=paths.temp_root, session_id=paths.session_id, nonce=paths.nonce)
            root = verified.runtime_root
            # Enumerate without following links; do no deletion if any component is linked.
            pending, entries = [root], []
            while pending:
                directory = pending.pop()
                for entry in directory.iterdir():
                    info = entry.lstat()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                        raise ValueError('linked practice cleanup path')
                    if not entry.resolve().is_relative_to(root):
                        raise ValueError('practice cleanup escaped root')
                    entries.append((entry, stat.S_ISDIR(info.st_mode)))
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(entry)
            # Revalidate ownership and every existing ancestor before each bottom-up removal.
            for entry, is_directory in sorted(entries, key=lambda pair: len(pair[0].parts), reverse=True):
                if entry == paths.marker_file:
                    continue
                verified.require_write_path(entry / '.cleanup-check' if is_directory else entry)
                entry.rmdir() if is_directory else entry.unlink()
            paths.marker_file.unlink()
            root.rmdir()
        except (OSError, ValueError):
            self.cleanup_retained = True
