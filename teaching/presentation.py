# SPDX-License-Identifier: GPL-3.0-or-later
"""Practice-local engine/view bridge, with no document or desktop side effects.

The application supplies trusted fixture/navigation callbacks and its window
ownership/topmost policy. Nothing here launches the application, writes user
progress, injects native input or executes instructions from course JSON.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

from .catalog import REVEAL_ACTIONS
from .engine import TutorialEngine
from .events import TeachingEventBus
from .models import TutorialCatalog, TutorialStep
from .targets import TargetRegistry
from .widgets import HighlightOverlay, InputBarrier, TutorialController


def _live(widget: QWidget | None) -> bool:
    return widget is not None and not sip.isdeleted(widget)


def _work_area(target: QWidget | None) -> QRect:
    screen = target.screen() if _live(target) else QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError('no practice screen available')
    return screen.availableGeometry()


class TeachingPresenter(QObject):
    """One reusable chapter presenter inside an already-isolated practice app.

    A lost target invalidates pending operations and releases the input barrier.
    Event-driven rebuilding may recover for at most two seconds, after which
    Retry/Skip/Exit remain available without an application-wide lock. The host
    must wrap real native file choosers in native_dialog(); this is not a native
    dialog test or an OS hook.
    """

    exit_requested = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, catalog: TutorialCatalog, *, session_id: str,
                 registry: TargetRegistry, owns: Callable[[QWidget], bool],
                 canvas: Callable[[], QWidget | None], translate: Callable[[str], str],
                 prepare_fixture: Callable[[str], None],
                 prepare_step: Callable[[str, TutorialStep], None] | None = None,
                 reveal_actions: Mapping[str, Callable[[], None]] | None = None,
                 on_progress: Callable[[str, str, int], object] | None = None,
                 condition_reader: Callable[[str, str | None], object] | None = None,
                 available_geometry: Callable[[QWidget | None], QRect] = _work_area,
                 manage_window: Callable[[QWidget], None] | None = None,
                 unmanage_window: Callable[[QWidget], None] | None = None,
                 missing_timeout_ms: int = 2000, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if type(missing_timeout_ms) is not int or not 1 <= missing_timeout_ms <= 2000:
            raise ValueError('target recovery deadline must be 1..2000 milliseconds')
        actions = dict(reveal_actions or {})
        if actions.keys() - REVEAL_ACTIONS or any(not callable(value) for value in actions.values()):
            raise ValueError('trusted reveal hooks must use registered actions')
        if (manage_window is None) != (unmanage_window is None):
            raise ValueError('window management hooks must be paired')
        self.registry, self._canvas = registry, canvas
        self._prepare_fixture, self._prepare_step = prepare_fixture, prepare_step
        self._reveal_actions, self._available_geometry = actions, available_geometry
        self._manage_window, self._unmanage_window = manage_window, unmanage_window
        self._managed_windows: list[QWidget] = []
        self._closed = False
        self._starting = False
        self._generation = 0
        self._dialog_depth = 0
        self._missing = self._automatic_retry = self._resuming = False
        self._fixture: str | None = None
        self._chapter = None
        self.active_target_id: str | None = None
        self.controller = TutorialController(translate)
        self.highlight = HighlightOverlay()
        self.barrier = InputBarrier(owns, self)
        self.engine = TutorialEngine(catalog, session_id=session_id, on_step=self._present,
                                     on_sequence=self._sequence_changed, on_progress=on_progress,
                                     condition_reader=condition_reader)
        self.events = TeachingEventBus(self.engine)
        self.registry.failed.connect(self._target_failed)
        self._missing_timer = QTimer(self)
        self._missing_timer.setSingleShot(True)
        self._missing_timer.setInterval(missing_timeout_ms)
        self._missing_timer.timeout.connect(lambda: self._request(self._missing_expired))
        for signal, action in (
            (self.controller.previous_requested, self.engine.previous),
            (self.controller.next_requested, self.engine.next),
            (self.controller.pause_requested, self._toggle_pause),
            (self.controller.skip_requested, self.engine.skip_chapter),
            (self.controller.retry_requested, self.retry),
            (self.controller.exit_requested, self._exit),
        ):
            signal.connect(lambda action=action: self._request(action))

    def start(self, course_id: str, chapter_id: str) -> None:
        if self._closed:
            raise RuntimeError('teaching presentation is closed')
        if self._starting or self.engine.phase in ('running', 'paused'):
            raise RuntimeError('a teaching chapter is already active')
        course = self.engine.catalog.course_by_id(course_id)
        chapter = next((value for value in course.chapters if value.id == chapter_id), None)
        if chapter is None:
            raise KeyError(chapter_id)
        for step in chapter.steps:
            if set(step.reveal) - self._reveal_actions.keys() - {'scroll_target'}:
                raise ValueError('a required reveal action has no trusted hook')
            if step.allowed_targets and (step.wait is None or
                                         len(step.allowed_targets) != len(step.wait.clauses)):
                raise ValueError('allowed targets must map one-to-one to sequence stages')
        self._starting = True
        self._generation += 1
        generation = self._generation
        try:
            with self.events.suppress():
                self._prepare_fixture(chapter.fixture)
            if self._closed or generation != self._generation:
                return
            self._fixture, self._chapter = chapter.fixture, chapter
            if self._manage_window is not None and not self._managed_windows:
                try:
                    for window in (self.controller, self.highlight):
                        self._manage_window(window)
                        self._managed_windows.append(window)
                        if self._closed or generation != self._generation:
                            self._unregister_windows()
                            return
                except Exception:
                    self._unregister_windows()
                    raise
            self.engine.start(course_id, chapter_id)
        finally:
            self._starting = False

    def _snapshot(self) -> tuple:
        return (self._generation, self.engine.run_id, self.engine.step_epoch,
                self.engine.current_step_id, self.engine.sequence_index, self.engine.phase)

    def _still_current(self, snapshot: tuple) -> bool:
        return not self._closed and snapshot == self._snapshot()

    def _request(self, action: Callable[[], object]) -> None:
        if self._closed:
            return
        try:
            action()
        except Exception:
            self._fail_presentation()

    def _target_failed(self, code: str) -> None:
        if not self._closed:
            self._fail_presentation()

    def _fail_presentation(self) -> None:
        # Both direct and deferred Qt callbacks fail closed, never hidden-running.
        with suppress(Exception):
            self.engine.stop()
        self._release()
        if _live(self.controller):
            self.controller.hide()
        self.failed.emit('presentation_failed')

    def _release(self) -> None:
        self._missing_timer.stop()
        self._automatic_retry = False
        self.registry.unwatch()
        self.barrier.deactivate()
        if _live(self.highlight):
            self.highlight.highlight(None)

    def _present(self, step: TutorialStep | None) -> None:
        if step is None:
            self.barrier.deactivate()
            self.highlight.highlight(None)
            if self.engine.phase == 'paused' and not self._closed:
                if not self._missing:
                    self._release()
                self.controller.set_paused(not self._missing)
                self.controller.set_target_missing(self._missing)
                self._show_controller()
            else:
                self._release()
                self.controller.hide()
            return
        if self._closed:
            return
        self._release()
        self._missing = False
        snapshot = self._snapshot()
        if not self._resuming and self._prepare_step is not None:
            with self.events.suppress():
                self._prepare_step(self._fixture, step)
            if not self._still_current(snapshot):
                return
        with self.events.suppress():
            for action in step.reveal:
                if action != 'scroll_target':
                    self._reveal_actions[action]()
                    if not self._still_current(snapshot):
                        return
        self.controller.set_paused(False)
        self.controller.set_target_missing(False)
        self.controller.present(step, self._chapter.steps.index(step), len(self._chapter.steps),
                                self.engine.can_previous, step.kind == 'information')
        if self._still_current(snapshot):
            self._configure_target()

    def _sequence_changed(self, index: int) -> None:
        if not self._closed:
            self._configure_target()

    def _configure_target(self) -> None:
        step = self.engine.current_step
        if step is None or self._closed:
            return
        snapshot = self._snapshot()
        self.active_target_id = (step.allowed_targets[self.engine.sequence_index]
                                 if step.allowed_targets else step.target)
        with self.events.suppress():
            if self.active_target_id is not None:
                self.registry.reveal(self.active_target_id)
        if not self._still_current(snapshot):
            return
        self.registry.watch((self.active_target_id,) if self.active_target_id else (),
                            lambda: self._request(self._targets_changed),
                            extra_resolvers=(self._canvas,) if self.active_target_id is None
                            or step.input_policy == 'canvas' else ())
        if self._still_current(snapshot):
            self._targets_changed()

    def _target(self) -> QWidget | None:
        if self.active_target_id is not None:
            return self.registry.resolve(self.active_target_id)
        return self._canvas()

    def _targets_changed(self) -> None:
        if self._closed or self._dialog_depth:
            return
        step = self.engine.current_step
        if step is None or self.engine.phase not in ('running', 'paused'):
            return
        snapshot = self._snapshot()
        target = self._target()
        if not self._still_current(snapshot):
            return
        required = self.active_target_id is not None or step.input_policy == 'canvas'
        available = _live(target) and target.isVisible() and target.isEnabled()
        canvas = self._canvas()
        if not self._still_current(snapshot):
            return
        canvas_ready = _live(canvas) and canvas.isVisible() and canvas.isEnabled()
        if (required and not available) or (step.input_policy == 'canvas' and not canvas_ready):
            if self.engine.phase == 'running':
                self._missing = self._automatic_retry = True
                self._missing_timer.start()
                self.engine.pause()
            return
        if self.engine.phase == 'paused':
            if self._missing and self._automatic_retry:
                self._resume_current()
            return
        if not available:
            target = None
        anchor = QRect(target.mapToGlobal(QPoint()), target.size()) if target is not None else QRect()
        area = self._available_geometry(target)
        if not self._still_current(snapshot):
            return
        if not isinstance(area, QRect) or area.isEmpty():
            raise ValueError('a valid Qt logical screen work area is required')
        if anchor.isEmpty():
            anchor = QRect(area.center(), self.controller.size())
        self.controller.place(anchor, area)
        if not self._still_current(snapshot):
            return
        self.barrier.activate(step.input_policy, targets=(target,) if target else (),
                              canvas=canvas if _live(canvas) else None, controller=self.controller)
        self.highlight.highlight(anchor if self.active_target_id is not None else None)
        self._show_controller()

    def _show_controller(self) -> None:
        if not self._closed and not self._dialog_depth:
            self.controller.show()

    def _missing_expired(self) -> None:
        if not self._missing or not self._automatic_retry:
            return
        with self.events.suppress():
            if self.active_target_id is not None:
                self.registry.reveal(self.active_target_id)
        self._targets_changed()
        if self._missing:
            self._automatic_retry = False
            self.registry.unwatch()

    def _resume_current(self) -> None:
        self._missing = False
        self._resuming = True
        try:
            self.engine.resume()
        finally:
            self._resuming = False

    def pause(self) -> None:
        if not self._closed and self.engine.phase == 'running':
            self._missing = False
            self.engine.pause()

    def resume(self) -> None:
        if not self._closed and self.engine.phase == 'paused':
            self._resume_current()

    def _toggle_pause(self) -> None:
        if self.engine.phase == 'paused':
            self.resume()
        else:
            self.pause()

    def retry(self) -> None:
        if not self._closed and self._missing and self.engine.phase == 'paused':
            self._resume_current()

    @contextmanager
    def native_dialog(self) -> Iterator[None]:
        """Cover the whole native-file operation, including its terminal result.

        Consume success/cancel/failure inside the context, before target checks
        resume: the chooser can close the menu that originally owned the action.
        The native dialog itself and the rest of the real file operation belong
        inside the same with block. This does not invent a successful operation.
        """
        self._dialog_depth += 1
        self.barrier.suspend()
        if not self._closed:
            self.controller.hide()
            self.highlight.hide()
        try:
            yield
        finally:
            self._dialog_depth -= 1
            self.barrier.resume()
            if not self._closed and not self._dialog_depth:
                self._request(self._targets_changed)
                if self.engine.phase == 'paused':
                    self._show_controller()

    def _exit(self) -> None:
        self.close()
        self.exit_requested.emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        with suppress(TypeError, RuntimeError):
            self.registry.failed.disconnect(self._target_failed)
        try:
            self.engine.stop()
        finally:
            self._release()
            self.events.close()
            self.barrier.close()
            self._unregister_windows()
            for window in (self.controller, self.highlight):
                if _live(window):
                    window.hide()
                    window.deleteLater()

    def _unregister_windows(self) -> None:
        windows, self._managed_windows = self._managed_windows, []
        failed = False
        for window in windows:
            try:
                self._unmanage_window(window)
            except Exception:
                failed = True
        if failed:
            self.failed.emit('window_cleanup_failed')
