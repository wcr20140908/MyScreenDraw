# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted application/IPC bridge. Offline course data never supplies callbacks."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
import shutil
import sys
from types import ModuleType

from PyQt6 import sip
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalSocket
from PyQt6.QtWidgets import QApplication

from runtime_paths import RuntimeContext, RuntimePaths
from .bootstrap import PracticeRequest, practice_arguments
from .catalog import CatalogLoader
from .presentation import TeachingPresenter
from .targets import TargetRegistry
from .transport import TeachingConnection

# Grow this manifest only alongside a real, verified business adapter/target.
APPLICATION_TARGETS = frozenset({'canvas.ink', 'toolbar.pen', 'toolbar.file', 'toolbar.tools',
                                 'file.save', 'file.open', 'pages.add'})
APPLICATION_EVENTS = frozenset({'ink.committed', 'project.saved'})


def application_catalog(module: ModuleType, resource_dir: Path):
    import i18n
    root = Path(resource_dir).resolve() / 'assets' / 'tutorials'
    loader = CatalogLoader(root, string_keys=set(i18n._BASE),
                           target_ids=set(APPLICATION_TARGETS), event_names=set(APPLICATION_EVENTS))
    return loader.load(), loader


def application_command(request: PracticeRequest) -> tuple[str, list[str]]:
    """Launch the same installed application, never a shell or catalog command."""
    arguments = practice_arguments(request.paths, request.channel, request.course_id, request.chapter_id)
    if not getattr(sys, 'frozen', False):
        entry = request.paths.app_dir / 'main.py'
        if not entry.is_file():
            raise ValueError('application entrypoint is unavailable')
        arguments.insert(0, str(entry))
    return sys.executable, arguments


class PracticeChild(QObject):
    """One authenticated child; construction does not activate/show application UI."""

    finished = pyqtSignal(int)

    def __init__(self, request: PracticeRequest, peer: TeachingConnection, *, context: RuntimeContext,
                 host_factory: Callable[[Callable[[str, str, int], None]], object],
                 parent: QObject | None = None):
        super().__init__(parent)
        if not context.paths.practice or context.ui_active or context.paths != request.paths:
            raise ValueError('a hidden owned practice context is required')
        paths = request.paths
        RuntimePaths.for_practice(paths.app_dir, paths.resource_dir, paths.runtime_root,
                                  temp_root=paths.temp_root, session_id=paths.session_id, nonce=paths.nonce)
        self.request, self.peer, self.context = request, peer, context
        self.host_factory, self.host = host_factory, None
        self.phase = 'constructed'
        self._pending = {}
        self._queued_progress = []
        self._pending_control = None
        self._control_timer = QTimer(self)
        self._control_timer.setSingleShot(True)
        self._control_timer.setInterval(5000)
        self._control_timer.timeout.connect(self._fail)
        peer.received.connect(self._receive)
        peer.closed.connect(lambda: self.stop(send=False))
        peer.failed.connect(lambda _: self.stop(send=False, exit_code=3))

    def start(self):
        if self.phase != 'constructed' or self.peer.is_closed:
            raise RuntimeError('practice connection is unavailable')
        self.phase = 'initializing'
        try:
            self.peer.send('hello', {})
            host = self.host_factory(self.record_progress)
            self.host = host
            host.exit_requested.connect(self.stop)
            host.failed.connect(lambda _: self._fail())
            host.pause_requested.connect(self._request_pause_control)
            if self.phase != 'initializing':
                host.close()
                return
            self.phase = 'ready'
            self.peer.send('ready', {})
        except Exception:
            self._fail()

    def _receive(self, message):
        if self.phase in ('stopping', 'stopped'):
            return
        try:
            kind, payload = message['type'], message['payload']
            if kind == 'state_ack':
                self._ack(payload)
                return
            if kind != 'control' or not isinstance(payload, dict):
                raise ValueError('unexpected parent message')
            action = payload.get('action')
            if action == 'stop' and set(payload) == {'action'}:
                self.stop()
            elif action == 'activate' and self.phase == 'ready' and set(payload) == {'action'}:
                self.phase = 'activating'
                self.context.activate()
                self.host.activate()
                if self.phase != 'activating':
                    return
                self.peer.send('activated', {})
                self.phase = 'running'
                queued, self._queued_progress = self._queued_progress, []
                for progress in queued:
                    self.record_progress(*progress)
            elif action == 'pause' and self.phase in ('running', 'paused'):
                if set(payload) - {'action', 'hidden'} or type(payload.get('hidden', False)) is not bool:
                    raise ValueError('invalid pause request')
                self.host.pause(hidden=payload.get('hidden', False))
                if self.phase not in ('stopping', 'stopped'):
                    self.phase = 'paused'
            elif action == 'resume' and self.phase in ('paused', 'running') and set(payload) == {'action'}:
                if self.phase == 'paused':
                    self.host.resume()
                if self.phase not in ('stopping', 'stopped'):
                    self.phase = 'running'
            else:
                raise ValueError('invalid practice transition')
            if action in ('pause', 'resume'):
                self._pending_control = None
                self._control_timer.stop()
        except Exception:
            self._fail()

    def _request_pause_control(self):
        if self.phase not in ('running', 'paused') or self._pending_control is not None:
            return
        action = 'pause' if self.phase == 'running' else 'resume'
        self._pending_control = action
        try:
            self.peer.send('control', {'action': action})
        except Exception:
            self._fail()
            return
        if self._pending_control is not None and self.phase in ('running', 'paused'):
            self._control_timer.start()

    def record_progress(self, chapter_id, status, compat_revision):
        if (chapter_id != self.request.chapter_id or status not in ('in_progress', 'completed', 'skipped')
                or type(compat_revision) is not int or compat_revision < 1):
            raise ValueError('invalid application progress')
        if self.phase == 'activating':
            if len(self._queued_progress) >= 8:
                raise RuntimeError('practice progress budget exceeded')
            self._queued_progress.append((chapter_id, status, compat_revision))
            return
        if self.phase != 'running' and not (self.phase == 'paused' and status == 'skipped'):
            return  # Explicit Skip is allowed while paused; async completion is not.
        if len(self._pending) >= 32:
            raise RuntimeError('practice acknowledgement budget exceeded')
        message_id = self.peer.send('chapter_state', {
            'chapter_id': chapter_id, 'status': status, 'compat_revision': compat_revision})
        self._pending[message_id] = (chapter_id, status)

    def _ack(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {'message_id', 'chapter_id', 'persisted'}
                or not isinstance(payload['message_id'], str) or payload['message_id'] not in self._pending
                or type(payload['persisted']) is not bool):
            raise ValueError('invalid progress acknowledgement')
        chapter_id, status = self._pending[payload['message_id']]
        if payload['chapter_id'] != chapter_id:
            raise ValueError('progress acknowledgement does not match')
        del self._pending[payload['message_id']]
        self.host.progress_ack(chapter_id, status, payload['persisted'])

    def _fail(self):
        with suppress(Exception):
            self.peer.send('error', {})
        self.stop(exit_code=3)

    def stop(self, *, send=True, exit_code=0):
        if self.phase in ('stopping', 'stopped'):
            return
        self.phase = 'stopping'
        self._pending_control = None
        self._control_timer.stop()
        if send and not self.peer.is_closed:
            with suppress(Exception):
                self.peer.send('stopping', {})
        try:
            if self.host is not None:
                self.host.close()
        except Exception:
            exit_code = 3
        finally:
            self.context.ui_active = False
            self._pending.clear()
            self._queued_progress.clear()
            if send and not self.peer.is_closed:
                with suppress(Exception):
                    self.peer.send('stopped', {})
            self.phase = 'stopped'
            self.peer.close()
            self.finished.emit(exit_code)


class ApplicationTeachingHost(QObject):
    """Real ControlPanel/DrawingCanvas using private paths and semantic adapters."""

    exit_requested = pyqtSignal()
    failed = pyqtSignal(str)
    pause_requested = pyqtSignal()

    def __init__(self, module, request, *, on_progress):
        super().__init__()
        self.module, self.request, self.context = module, request, module.RUNTIME_CONTEXT
        if not self.context.paths.practice or self.context.ui_active or self.context.paths != request.paths:
            raise ValueError('application must be bound to the hidden private runtime')
        self._closed, self._hidden_token = False, None
        self._on_progress, self._progress_warning_shown = on_progress, False
        self.catalog, self.loader = application_catalog(module, request.paths.resource_dir)
        course = self.catalog.course_by_id(request.course_id)
        if not any(chapter.id == request.chapter_id for chapter in course.chapters):
            raise ValueError('unknown practice chapter')
        self.panel = module.ControlPanel(runtime=self.context)
        self.panel.canvas = module.DrawingCanvas(self.panel, runtime=self.context)
        self.panel.apply_theme()
        self.panel.load_settings()
        self.registry = TargetRegistry()
        bindings = {
            'canvas.ink': lambda: self.panel.canvas,
            'toolbar.pen': lambda: self.panel.icon_buttons.get('pen'),
            'toolbar.file': lambda: self.panel.icon_buttons.get('file'),
            'toolbar.tools': lambda: self.panel.icon_buttons.get('tools'),
            'file.save': lambda: self.panel.btn_save_project,
            'file.open': lambda: self.panel.btn_open_project,
            'pages.add': lambda: self.panel.rail_new,
        }
        for target_id, resolver in bindings.items():
            self.registry.register(target_id, resolver)
        self.presenter = TeachingPresenter(
            self.catalog, session_id=request.paths.session_id, registry=self.registry,
            owns=self.panel.lifecycle._owns_window, canvas=lambda: self.panel.canvas, translate=module.tr,
            prepare_fixture=self._prepare_fixture,
            reveal_actions={'open_file_panel': self._reveal_file}, on_progress=self._record_progress,
            pause_action=self.pause_requested.emit,
            manage_window=self.panel.lifecycle.register_tool_window,
            unmanage_window=self.panel.lifecycle.unregister_tool_window)
        self.panel.teaching_events = self.presenter.events
        self.panel.teaching_presenter = self.presenter
        self.presenter.exit_requested.connect(self.exit_requested)
        self.presenter.failed.connect(self.failed)
        self.panel.exit_requested.disconnect(module.QApplication.quit)
        self.panel.exit_requested.connect(self.exit_requested)

    def _reveal_file(self):
        if not self.panel.file_sub.isVisible():
            self.panel.handle_file_click()

    def _prepare_fixture(self, fixture):
        # The catalog maps IDs to bounded bundled data only, never executable code.
        source = self.loader.asset_path(self.loader.fixtures[fixture])
        directory = self.request.paths.require_directory_path(self.request.paths.data_dir / 'fixtures')
        directory.mkdir(parents=True, exist_ok=True)
        destination = self.request.paths.require_write_path(directory / (fixture + '.msd'))
        shutil.copyfile(source, destination)
        if not self.panel.open_project_from_path(str(destination)):
            raise ValueError('practice fixture could not be prepared')
        self.panel.project_path = None
        self.panel.project_dirty = False

    def activate(self):
        if self._closed or not self.context.ui_active:
            raise RuntimeError('practice has not been activated')
        self.panel.canvas.show()
        self.panel.show()
        self.panel.set_ui_mode('icon', persist=False)
        self.presenter.start(self.request.course_id, self.request.chapter_id)
        self.panel.resume_callbacks()
        self.panel.bind_topmost_stack()

    def pause(self, *, hidden=False):
        self.presenter.pause()
        if hidden and self._hidden_token is None:
            self._hidden_token = self.panel.lifecycle.suspend_for_teaching()

    def resume(self):
        if self._hidden_token is not None:
            self.panel.lifecycle.restore_after_teaching(self._hidden_token)
            self._hidden_token = None
        self.presenter.resume()

    def _record_progress(self, chapter_id, status, compat_revision):
        self._on_progress(chapter_id, status, compat_revision)
        if not self._closed and status in ('completed', 'skipped'):
            self.presenter.controller.set_finished(status)
            self.presenter._show_controller()

    def progress_ack(self, chapter_id, status, persisted):
        if not self._closed and not persisted and not self._progress_warning_shown:
            self._progress_warning_shown = True
            self.presenter.controller.set_persistence_warning()
            self.module.LOGGER.warning('Practice progress could not be saved to disk')

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.presenter.close()
        self.registry.close()
        self.panel.teaching_events = None
        self.panel.teaching_presenter = None
        self.panel._teaching_suspended = True
        self.panel.pause_callbacks()
        self.panel.stop_update_worker()
        self.panel.shutdown_autosave()
        for window in QApplication.topLevelWidgets():
            if not sip.isdeleted(window) and self.panel.lifecycle._owns_window(window):
                for timer in window.findChildren(QTimer):
                    timer.stop()
                window.hide()


def run_practice_application(request: PracticeRequest, module: ModuleType) -> int:
    """Private startup branch: connect first; never fall through to normal startup."""
    context = module.RUNTIME_CONTEXT
    if not context.paths.practice or context.ui_active or context.paths != request.paths:
        return 2
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    socket = QLocalSocket()
    socket.connectToServer(request.channel)
    if not socket.waitForConnected(2000):
        socket.abort()
        return 2
    module.ensure_directories()
    module.setup_logging()
    module.install_qt_translations(app)
    peer = TeachingConnection(socket, request.paths.session_id, request.paths.nonce)
    child = PracticeChild(request, peer, context=context,
                          host_factory=lambda progress: ApplicationTeachingHost(module, request, on_progress=progress))
    child.finished.connect(app.exit)
    QTimer.singleShot(0, child.start)
    try:
        return app.exec()
    finally:
        child.stop(send=False)


class TeachingCoordinator(QObject):
    """Normal-process Tools/welcome entry and safe owned-process lifecycle."""

    def __init__(self, module, panel, *, state_store=None, command_factory=application_command,
                 temp_root=None, foreground=None):
        super().__init__(panel)
        import tempfile
        from PyQt6.QtCore import Qt
        from .onboarding import WelcomePolicy, TeachingStartupContext
        from .practice import PracticeSession
        from .state import TutorialStateStore
        from .welcome import WelcomeCoordinator
        if panel.runtime_context.paths.practice:
            raise ValueError('a practice process cannot launch another practice process')
        self.module, self.panel = module, panel
        self.catalog, self.loader = application_catalog(module, panel.runtime_context.paths.resource_dir)
        self.state_store = state_store or TutorialStateStore(Path(module.DATA_DIR) / 'tutorial_state.json')
        self.state_store.sync_catalog(self.catalog.chapter_revisions())
        self.center = None
        self.last_notice = None
        self._closed = False
        self._notices = []
        self._pending_failure = None
        self._recovery_box = None
        self._background_after_stop = False
        self._practice_hidden = False
        self._pending_lifecycle_action = None
        self._action_timer = QTimer(self)
        self._action_timer.setSingleShot(True)
        self._action_timer.timeout.connect(self._run_lifecycle_action)
        self._updates_timer = QTimer(self)
        self._updates_timer.setSingleShot(True)
        self._updates_timer.timeout.connect(panel._resume_teaching_updates)
        self._foreground = foreground or (lambda: QApplication.applicationState() == Qt.ApplicationState.ApplicationActive)
        self.session = PracticeSession(self.catalog, app_dir=panel.runtime_context.paths.app_dir,
            resource_dir=panel.runtime_context.paths.resource_dir,
            temp_root=Path(temp_root if temp_root is not None else tempfile.gettempdir()),
            state_store=self.state_store, command_factory=command_factory,
            suspend=self._suspend, restore=panel.lifecycle.restore_after_teaching, parent=self)
        self._ready_timer = QTimer(self)
        self._ready_timer.setInterval(200)
        self._ready_timer.timeout.connect(self.session.try_activate)
        self.session.phase_changed.connect(self._phase_changed)
        self.session.failed.connect(self._failed)
        self.session.progress_saved.connect(self._refresh_center)
        context = TeachingStartupContext.from_arguments(sys.argv[1:])
        self.policy = WelcomePolicy(self.state_store, context=context, warn=self._notice)
        self.welcome = WelcomeCoordinator(self.policy, translate=module.tr,
                                         start_core=self.start_core, parent=panel)
        self.welcome.failed.connect(self._notice)
        self._welcome_timer = QTimer(self)
        self._welcome_timer.setInterval(250)
        self._welcome_timer.timeout.connect(self.request_startup_welcome)

    @property
    def active(self):
        return (self._pending_lifecycle_action is not None or self.session.restore_pending
                or self.session.phase not in ('idle', 'stopped'))

    @property
    def background_hidden(self):
        return self._practice_hidden

    def _sync_background_action(self):
        from app_lifecycle import LifecycleState
        lifecycle = self.panel.lifecycle
        action = getattr(lifecycle, 'action_toggle_ui', None)
        if action is not None:
            hidden = (self._practice_hidden or self.session.phase == 'restore_failed'
                      or lifecycle.state == LifecycleState.HIDDEN)
            lifecycle._set_action_text(action, self.module.tr('show_main_ui' if hidden else 'hide_main_ui'))

    def request_lifecycle_action(self, action):
        """Consume quit/restart until owned exit AND original restoration are proven."""
        if action not in ('quit', 'restart'):
            raise ValueError('unsupported teaching lifecycle action')
        if self.session.phase == 'restore_failed':
            self._notice('teaching_session_restore_failed', recovery=True)
            return True
        if self._pending_lifecycle_action is not None:
            return True
        if not self.active:
            return False
        self._pending_lifecycle_action = action
        self._background_after_stop = False
        self._welcome_timer.stop()
        self.session.request_stop('parent_' + action)
        return True

    def _run_lifecycle_action(self):
        from PyQt6.QtCore import QProcess
        if (self._closed or self._pending_lifecycle_action is None
                or self.session.phase != 'stopped' or self.session.restore_pending
                or getattr(self.panel, '_teaching_suspended', False)
                or self.session.process is not None
                and self.session.process.state() != QProcess.ProcessState.NotRunning):
            return
        action, self._pending_lifecycle_action = self._pending_lifecycle_action, None
        if action == 'restart':
            self.panel.lifecycle._restart_app()
        else:
            self.panel.lifecycle._quit_app()

    def readiness(self, *, for_activation=False):
        from .onboarding import TeachingReadiness
        from app_lifecycle import LifecycleState
        canvas = self.panel.canvas
        app = QApplication.instance()
        focus = app.focusWidget()
        center_focus = (self.center is not None and not sip.isdeleted(self.center)
                        and focus is not None and self.center.isAncestorOf(focus))
        text_panel = getattr(self.panel, 'text_panel', None)
        editing = bool(text_panel is not None and text_panel.isVisible())
        if not center_focus and focus is not None and focus.isVisible():
            editing = editing or isinstance(focus, (self.module.QLineEdit, self.module.QTextEdit))
        active = self.active
        if for_activation:
            active = self.session.restore_pending or self._pending_lifecycle_action is not None
        return TeachingReadiness(
            lifecycle_ready=hasattr(self.panel, 'lifecycle'),
            restore_finished=bool(getattr(self.panel, '_teaching_restore_finished', False)),
            layout_ready=bool(canvas is not None and canvas.width() > 1 and canvas.height() > 1),
            foreground=bool(self._foreground()),
            application_visible=bool(self.panel.toolbar_window.isVisible()
                and self.panel.lifecycle.state not in (LifecycleState.HIDDEN, LifecycleState.QUITTING)),
            modal_active=app.activeModalWidget() is not None,
            gesture_active=bool(canvas is not None and (canvas._pointer_slots or any(
                getattr(canvas, name, None) is not None for name in (
                    'last_point', 'shape_start', 'selection_start', 'drag_start', 'drag_action',
                    'text_drag_start', 'transform_start_distance', 'transform_start_angle', 'aid_drag')))),
            composition_active=False,  # Visible/focused editors conservatively block the entire edit session.
            text_edit_active=editing,
            file_operation_active=bool(self.panel._document_transition_active or self.panel._unsaved_prompt_active
                or getattr(self.panel, "_update_flow_busy", False) or getattr(self.panel, "_update_download_active", False)
                or getattr(self.panel, "_update_install_handoff", False) or self.panel._autosave_future is not None),
            practice_active=active)

    def open_center(self):
        from .widgets import TeachingCenter
        if self._closed or not self.policy.can_open_center(self.readiness()):
            self._notice('teaching_waiting_operation')
            return False
        if self.center is None or sip.isdeleted(self.center):
            self.center = TeachingCenter(self.catalog, self.state_store, self.module.tr, self.panel)
            self.center.start_requested.connect(self.start)
            self.panel.lifecycle.register_tool_window(self.center)
        self.center.refresh()
        self.center.show()
        return True

    def maybe_show_welcome(self):
        return False if self._closed else self.welcome.maybe_show(self.readiness())

    def request_startup_welcome(self):
        if (self._closed or not self.policy.context.automatic_allowed or self.state_store.read_only
                or self.state_store.welcome != 'unseen'):
            self._welcome_timer.stop()
            return False
        shown = self.maybe_show_welcome()
        if shown or self.state_store.read_only or self.welcome.dialog is not None:
            self._welcome_timer.stop()
        else:
            self._welcome_timer.start()
        return shown

    def start_core(self):
        courses = self.catalog.courses
        if not courses or not courses[0].chapters:
            raise ValueError('onboarding course is unavailable')
        self.start(courses[0].id, courses[0].chapters[0].id)

    def start(self, course_id, chapter_id):
        if self._closed or not self.readiness().safe:
            self._notice('teaching_waiting_operation')
            return False
        self._welcome_timer.stop()
        if self.state_store.welcome == "unseen":
            self.state_store.set_welcome("accepted")
        if self.center is not None and not sip.isdeleted(self.center):
            self.center.hide()
        try:
            self.session.start(course_id, chapter_id)
        except (ValueError, KeyError, OSError, RuntimeError):
            self._notice('teaching_session_start_failed')
            return False
        return self.session.last_error is None

    def _suspend(self):
        if not self.readiness(for_activation=True).safe:
            return None
        return self.panel.lifecycle.suspend_for_teaching()

    def hide_to_background(self):
        if self._pending_lifecycle_action is not None:
            return True
        phase = self.session.phase
        if phase in ('running', 'paused'):
            if self.session.request_pause(hidden=True):
                self._practice_hidden = True
                self._sync_background_action()
            return True
        if phase == 'restore_failed':
            self._notice('teaching_session_restore_failed', recovery=True)
            return True
        if phase not in ('idle', 'stopped'):
            self._background_after_stop = True
            self.session.request_stop('parent_background')
            return True
        return False

    def restore_from_background(self):
        if self._pending_lifecycle_action is not None:
            return True
        if self.session.phase == 'paused':
            self.session.request_resume()
            return True
        if self.session.phase == 'restore_failed':
            self._notice('teaching_session_restore_failed', recovery=True)
            return True
        return self.session.phase not in ('idle', 'stopped')

    def _refresh_center(self, _=None):
        if self.center is not None and not sip.isdeleted(self.center):
            self.center.refresh()

    def _phase_changed(self, phase):
        if phase != 'stopped':
            self._action_timer.stop()
            self._updates_timer.stop()
        if phase in ('running', 'stopped', 'restore_failed'):
            self._practice_hidden = False
            self._sync_background_action()
        if phase == 'ready':
            self._ready_timer.start()
        else:
            self._ready_timer.stop()
        if phase == 'stopped':
            if self._background_after_stop:
                self._background_after_stop = False
                self.panel.lifecycle.hide_to_background()
            if self.center is not None and not sip.isdeleted(self.center):
                self.center.refresh()
            if self._pending_lifecycle_action is not None:
                self._pending_failure = None
                self._action_timer.start(0)
            else:
                self._updates_timer.start(0)
                if self._pending_failure is not None:
                    key, self._pending_failure = self._pending_failure, None
                    self._notice(key)
        elif phase == 'restore_failed':
            # Recovery requires a fresh user decision; a later retry must not quit unexpectedly.
            self._pending_lifecycle_action = None
            self._background_after_stop = False
            self._notice('teaching_session_restore_failed', recovery=True)

    def _failed(self, code):
        if code == 'restore_failed':
            self._pending_failure = None
        else:
            self._pending_failure = ('teaching_session_connection_lost'
                if code == 'connection_lost' or code == 'child_exited' and self.session.restore_pending
                else 'teaching_session_start_failed')

    def _notice(self, key, *, recovery=False):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QMessageBox
        self.last_notice = key
        if self._closed:
            return
        if recovery and self._recovery_box is not None and not sip.isdeleted(self._recovery_box):
            self._recovery_box.show()
            return
        box = QMessageBox(self.panel)
        box.setWindowTitle(self.module.tr('teaching_center_title'))
        box.setText(self.module.tr(key))
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        box.setModal(False)
        self.panel.lifecycle.register_tool_window(box)
        self._notices.append(box)
        if recovery:
            from PyQt6.QtCore import QProcess
            if self.session.process is not None and self.session.process.state() != QProcess.ProcessState.NotRunning:
                box.deleteLater()
                return
            self._recovery_box = box
            self.panel.lifecycle.allow_teaching_recovery_window(box)
            box.setStandardButtons(QMessageBox.StandardButton.Retry)
            box.buttonClicked.connect(lambda _: self._retry_restore(box))
        else:
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.show()

    def _retry_restore(self, box):
        if self.session.retry_restore():
            self.panel.lifecycle.disallow_teaching_recovery_window(box)
            box.hide()
        else:
            QTimer.singleShot(0, box.show)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._pending_lifecycle_action = None
        self._action_timer.stop()
        self._updates_timer.stop()
        self._ready_timer.stop()
        self._welcome_timer.stop()
        self.welcome.close()
        if self.center is not None and not sip.isdeleted(self.center):
            self.panel.lifecycle.unregister_tool_window(self.center)
            self.center.hide()
        for box in self._notices:
            if not sip.isdeleted(box):
                self.panel.lifecycle.unregister_tool_window(box)
                box.hide()
        if self.session.phase not in ('idle', 'stopped'):
            self.session.request_stop('coordinator_closed')
