# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted application/IPC bridge. Offline course data never supplies callbacks."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
import shutil
import sys
import uuid
from types import ModuleType

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QRect, QRectF, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from runtime_paths import RuntimeContext, RuntimePaths
from .bootstrap import PracticeRequest, practice_arguments
from .catalog import CatalogLoader
from .presentation import TeachingPresenter
from .targets import TargetRegistry
from .transport import TeachingConnection
from .session_view import PracticeProgressView, require_transaction_id
from .toolbox_actions import (TOOLBOX_EVENTS, TOOLBOX_TARGETS, toolbox_bindings, reveal_toolbox_target)
from .interface_actions import (INTERFACE_EVENTS, INTERFACE_TARGETS, interface_bindings, reveal_interface_target)

# Grow this manifest only alongside a real, verified business adapter/target.
APPLICATION_TARGETS = frozenset({
    'aids.ruler', 'aids.protractor', 'aids.set_square_45', 'aids.set_square_30',
    'aids.clear', 'aids.calibrate', 'aids.reset',
    'canvas.ink', 'toolbar.mode', 'toolbar.pen', 'toolbar.eraser', 'toolbar.select',
    'toolbar.undo', 'toolbar.redo', 'toolbar.whiteboard', 'toolbar.file', 'toolbar.tools',
    'pen.palette', 'pen.width', 'pen.marker.width', 'pen.marker.alpha', 'pen.laser.width',
    'pen.defaults', 'pen.defaults.capture', 'pen.style.pen', 'pen.style.fountain',
    'pen.style.brush', 'pen.style.calligraphy', 'pen.style.pencil', 'pen.style.crayon',
    'pen.style.chalk', 'pen.style.neon', 'pen.style.dashed', 'pen.style.rainbow',
    'pen.style.arrow', 'pen.marker', 'pen.laser', 'eraser.type.circle',
    'eraser.type.stroke', 'eraser.size', 'toolbar.clear', 'file.save', 'file.save_as',
    'file.open', 'file.recovery', 'file.import', 'export.png', 'export.pdf', 'export.svg', 'export.eps',
    'pages.add', 'pages.previous', 'pages.next', 'tools.teaching',
    'selection.duplicate', 'selection.delete', 'toolbar.board_style',
    'pages.thumbnails_button', 'pages.thumbnail_list', 'pages.rename', 'pages.delete',
    'pages.copy', 'pages.copy_position', 'toolbar.shape', 'shape.cancel_points',
    'shape.type.line', 'shape.type.dashed_line', 'shape.type.triangle', 'shape.type.rect',
    'shape.type.parallelogram', 'shape.type.trapezoid', 'shape.type.diamond', 'shape.type.angle',
    'shape.type.circle', 'shape.type.ellipse', 'shape.type.cuboid', 'shape.type.cube',
    'shape.type.cylinder', 'shape.type.cone', 'settings.smart_shapes', 'selection.more',
    'toolbar.text', 'text.input', 'text.done', 'text.backspace', 'text.newline',
    'text.group.greek', 'text.group.structure', 'text.symbol.alpha', 'text.symbol.pm',
    'text.symbol.member', 'text.symbol.integral', 'text.structure.frac', 'text.structure.sup',
    'text.structure.sub', 'text.structure.sqrt', 'text.structure.sum', 'text.structure.int',
    'selection.width', 'selection.color', 'settings.autosave_preset', 'settings.autosave_custom',
    'settings.view_fit', 'settings.view_home',
}) | TOOLBOX_TARGETS | INTERFACE_TARGETS
APPLICATION_EVENTS = frozenset({
    'ink.committed', 'ink.erased', 'project.saved', 'mode.changed', 'tool.changed',
    'pen.color_changed', 'pen.width_changed', 'history.undone', 'history.redone',
    'selection.changed', 'selection.transformed', 'whiteboard.entered', 'whiteboard.exited',
    'page.created', 'page.changed', 'project.opened', 'recovery.previewed', 'recovery.applied', 'export.finished',
    'center.visited', 'practice.resumed', 'pen.style_changed', 'eraser.type_changed',
    'eraser.size_changed', 'history.cleared', 'laser.trace', 'pen.default_saved',
    'pen.defaults_changed', 'pen.default_applied', 'selection.duplicated', 'selection.deleted',
    'board.style_changed', 'board.view_changed', 'page.renamed', 'page.deleted', 'page.copied',
    'page.copy_placement_changed', 'page.reordered', 'thumbnails.opened',
    'shape.type_changed', 'shape.committed', 'shape.point_added', 'shape.points_cancelled',
    'shape.recognized', 'shape.recognition_changed', 'shape.constructed',
    'aid.added', 'aid.cleared', 'aid.transformed', 'aid.calibration_changed',
    'text.box_created', 'text.edit_started', 'text.changed', 'text.edit_finished',
    'text.formatted', 'formula.inserted', 'formula.slot_changed', 'formula.cursor_moved',
    'symbols.opened', 'media.imported', 'unsaved.decision', 'settings.autosave_changed', 'settings.autosave_custom_opened',
}) | TOOLBOX_EVENTS | INTERFACE_EVENTS


APPLICATION_HINT_TOPICS = {
    'toolbar.pen': ('c02', 'c02.styles'),
    'toolbar.eraser': ('c03', 'c03.erase'),
    'toolbar.select': ('c04', 'c04.select_move'),
    'whiteboard.pages': ('c05', 'c05.add_switch'),
    'shapes.create': ('c06', 'c06.plane'),
    'text.edit': ('c07', 'c07.edit'),
    'file.projects': ('c08', 'c08.save'),
    'file.recovery': ('c08', 'c08.recovery'),
    'file.import': ('c09', 'c09.image'),
    'file.export': ('c10', 'c10.formats'),
    'tools.measure': ('c11', 'c11.instruments'),
    'tools.timer': ('c12', 'c12.timer'),
    'interface.settings': ('c13', 'c13.layout_theme'),
}


def _canvas_region(canvas, bounds):
    """Map bounded document content to the visible Qt logical/global workspace."""
    viewport = QRectF(canvas.rect())
    region = QRectF()
    for rect in bounds:
        if rect.isEmpty():
            continue
        view_rect = QRectF(canvas.to_view(rect.topLeft()), canvas.to_view(rect.bottomRight()))
        # Logical-pixel clearance, independent of document zoom and OS DPR.
        visible = view_rect.adjusted(-20, -20, 20, 20).intersected(viewport)
        if not visible.isEmpty():
            region = region.united(visible)
    return region.toAlignedRect().translated(canvas.mapToGlobal(QPoint())) if not region.isEmpty() else QRect()


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
        self._active_course_id, self._active_chapter_id = request.course_id, request.chapter_id
        self._center_id = None
        self._center_action = None
        self._center_open = False
        self._center_hidden = False
        self._have_view = False
        self._desired_chapter = None
        self._switch_id = None
        self._center_timer = QTimer(self)
        self._center_timer.setSingleShot(True)
        self._center_timer.setInterval(5000)
        self._center_timer.timeout.connect(self._fail)
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
            for name, callback in (('center_requested',self._request_center),
                                   ('center_closed',self._request_center_close),
                                   ('chapter_requested',self._request_chapter)):
                signal=getattr(host,name,None)
                if signal is not None:
                    signal.connect(callback)
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
            if kind in ('center_state','center_closed','chapter_offer','chapter_commit'):
                self._receive_center(kind,payload)
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
                if payload.get('hidden',False):
                    self._center_hidden=True
                self.host.pause(hidden=payload.get('hidden', False))
                if self.phase not in ('stopping', 'stopped'):
                    self.phase = 'paused'
            elif action == 'resume' and self.phase in ('paused', 'running') and set(payload) == {'action'}:
                if self.phase == 'paused':
                    self._center_hidden=False
                    self.host.resume()
                if self.phase not in ('stopping', 'stopped'):
                    self.phase = 'paused' if self._center_open else 'running'
            else:
                raise ValueError('invalid practice transition')
            if action in ('pause', 'resume'):
                self._pending_control = None
                self._control_timer.stop()
                self._drain_center_request()
        except Exception:
            self._fail()

    def _request_center(self):
        if self.phase not in ('running','paused') or self._center_id is not None:
            return
        self._center_id=uuid.uuid4().hex
        self._center_action='opening'
        self._center_timer.start()
        self._drain_center_request()

    def _request_center_close(self):
        if not self._center_open or self.phase!='paused' or self._center_action is not None:
            return
        self._center_action='closing'
        self._center_timer.start()
        self._drain_center_request()

    def _request_chapter(self, course_id, chapter_id):
        if (not self._center_open or self._center_hidden or self.phase!='paused'
                or self._center_action is not None or self._pending_control is not None):
            return
        try:
            course=self.host.catalog.course_by_id(course_id)
            if not any(chapter.id==chapter_id for chapter in course.chapters):
                raise ValueError('unknown requested chapter')
            self._switch_id=uuid.uuid4().hex
            self._desired_chapter=(course_id,chapter_id)
            self._center_action='switch_wait'
            self._center_timer.start()
            self.host.prepare_chapter_change()
            self._drain_center_request()
        except Exception:
            self._fail()

    def _drain_center_request(self):
        if self._pending or self._pending_control is not None or self.phase not in ('running','paused'):
            return
        try:
            action=self._center_action
            if action=='opening':
                self._center_action='open_sent'
                self.peer.send('center_request',{'center_id':self._center_id})
            elif action=='closing':
                self._center_action='close_sent'
                self.peer.send('center_close',{'center_id':self._center_id})
            elif action=='switch_wait':
                self._center_action='offer_wait'
                course,chapter=self._desired_chapter
                self.peer.send('chapter_request',{'center_id':self._center_id,'switch_id':self._switch_id,
                    'from_chapter_id':self._active_chapter_id,'course_id':course,'chapter_id':chapter})
        except Exception:
            self._fail()

    def _receive_center(self, kind, payload):
        if not isinstance(payload,dict):
            raise ValueError('invalid center response')
        if kind=='center_state':
            if (self._center_action!='open_sent' or self.phase not in ('running','paused')
                    or set(payload)!={'center_id','view','resume_on_close','hidden'}
                    or payload['center_id']!=self._center_id
                    or type(payload['resume_on_close']) is not bool or type(payload['hidden']) is not bool):
                raise ValueError('unexpected center state')
            require_transaction_id(payload['center_id'])
            PracticeProgressView(self.host.catalog).replace(payload['view'])
            self._have_view=True;self._center_open=True;self._center_action=None
            self._center_hidden=self._center_hidden or payload['hidden']
            self.phase='paused';self._center_timer.stop()
            self.host.accept_center(payload['view'],hidden=self._center_hidden)
        elif kind=='center_closed':
            if (self._center_action!='close_sent' or not self._center_open
                    or set(payload)!={'center_id','resume','hidden'} or payload['center_id']!=self._center_id
                    or type(payload['resume']) is not bool or type(payload['hidden']) is not bool
                    or payload['hidden'] and payload['resume']):
                raise ValueError('unexpected center close')
            self._center_open=False;self._center_id=None;self._center_action=None
            self._center_hidden=payload['hidden'];self._center_timer.stop()
            self.phase='running' if payload['resume'] else 'paused'
            self.host.finish_center(resume=payload['resume'],hidden=payload['hidden'])
        elif kind=='chapter_offer':
            if (self._center_action!='offer_wait' or self.phase!='paused'
                    or set(payload)!={'center_id','switch_id','course_id','chapter_id','revision','compat_revision'}
                    or payload['center_id']!=self._center_id or payload['switch_id']!=self._switch_id
                    or (payload['course_id'],payload['chapter_id'])!=self._desired_chapter):
                raise ValueError('unexpected chapter offer')
            course=self.host.catalog.course_by_id(payload['course_id'])
            if (type(payload['revision']) is not int or type(payload['compat_revision']) is not int
                    or payload['revision']!=course.revision or payload['compat_revision']!=course.compat_revision):
                raise ValueError('chapter revision mismatch')
            self.phase='switching';self._center_action='commit_wait'
            self._active_course_id,self._active_chapter_id=self._desired_chapter
            self.host.prepare_chapter(*self._desired_chapter)
            ready={key:payload[key] for key in ('center_id','switch_id','course_id','chapter_id')}
            self._center_timer.start()
            self.peer.send('chapter_ready',ready)
        else:
            expected={'center_id':self._center_id,'switch_id':self._switch_id,
                      'course_id':self._active_course_id,'chapter_id':self._active_chapter_id}
            if self.phase!='switching' or self._center_action!='commit_wait' or payload!=expected:
                raise ValueError('unexpected chapter commit')
            self._center_timer.stop();self._center_open=False;self._center_id=None
            self._center_action=None;self._switch_id=None;self._desired_chapter=None
            self.phase='running'
            self.host.commit_chapter()
            queued,self._queued_progress=self._queued_progress,[]
            for progress in queued:
                self.record_progress(*progress)

    def _request_pause_control(self):
        if self._center_id is not None or self.phase not in ('running', 'paused') or self._pending_control is not None:
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
        if (chapter_id != self._active_chapter_id or status not in ('in_progress', 'completed', 'skipped')
                or type(compat_revision) is not int or compat_revision < 1):
            raise ValueError('invalid application progress')
        if self.phase in ('activating','switching'):
            if len(self._queued_progress) >= 8:
                raise RuntimeError('practice progress budget exceeded')
            self._queued_progress.append((chapter_id, status, compat_revision))
            return
        if self.phase != 'running' and not (self.phase == 'paused' and (status == 'skipped'
                or status == 'in_progress' and self._center_action=='switch_wait')):
            return  # Explicit Skip is allowed while paused; async completion is not.
        if len(self._pending) >= 32:
            raise RuntimeError('practice acknowledgement budget exceeded')
        message_id = self.peer.send('chapter_state', {
            'chapter_id': chapter_id, 'status': status, 'compat_revision': compat_revision})
        self._pending[message_id] = (chapter_id, status)

    def _ack(self, payload):
        expected={'message_id','chapter_id','persisted'} | ({'view'} if self._have_view else set())
        if (not isinstance(payload,dict) or set(payload)!=expected
                or not isinstance(payload['message_id'],str) or payload['message_id'] not in self._pending
                or type(payload['persisted']) is not bool):
            raise ValueError('invalid progress acknowledgement')
        chapter_id,status=self._pending[payload['message_id']]
        if payload['chapter_id']!=chapter_id:
            raise ValueError('progress acknowledgement does not match')
        if self._have_view:
            PracticeProgressView(self.host.catalog).replace(payload['view'])
            self.host.update_parent_view(payload['view'])
        del self._pending[payload['message_id']]
        self.host.progress_ack(chapter_id,status,payload['persisted'])
        self._drain_center_request()

    def _fail(self):
        with suppress(Exception):
            self.peer.send('error', {})
        self.stop(exit_code=3)

    def stop(self, *, send=True, exit_code=0):
        if self.phase in ('stopping', 'stopped'):
            return
        self.phase = 'stopping'
        self._center_timer.stop()
        self._center_action=None;self._center_id=None;self._center_open=False
        self._desired_chapter=None;self._switch_id=None
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
    center_requested = pyqtSignal()
    center_closed = pyqtSignal()
    chapter_requested = pyqtSignal(str, str)

    def __init__(self, module, request, *, on_progress):
        super().__init__()
        self.module, self.request, self.context = module, request, module.RUNTIME_CONTEXT
        if not self.context.paths.practice or self.context.ui_active or self.context.paths != request.paths:
            raise ValueError('application must be bound to the hidden private runtime')
        self._closed, self._hidden_token = False, None
        self._example_ids = {}
        self._example_snapshot, self._example_bounds = None, ()
        self._obstacle_snapshot, self._obstacle_rects = None, ()
        self._on_progress, self._progress_warning_shown = on_progress, False
        self.center = None
        self._center_token = None
        self._center_native = None
        self._center_batch = None
        self._center_visited = False
        self._center_hidden = False
        self._switch_pending = False
        self._chapter_confirming = False
        self._center_ending = False
        self._center_end_control = None
        self._center_windows = set()
        self.current_course_id, self.current_chapter_id = request.course_id, request.chapter_id
        self.catalog, self.loader = application_catalog(module, request.paths.resource_dir)
        course = self.catalog.course_by_id(request.course_id)
        if not any(chapter.id == request.chapter_id for chapter in course.chapters):
            raise ValueError('unknown practice chapter')
        self.panel = module.ControlPanel(runtime=self.context)
        self.panel.canvas = module.DrawingCanvas(self.panel, runtime=self.context)
        self.panel.teaching_host = self
        self.view = PracticeProgressView(self.catalog)
        self.panel.apply_theme()
        self.panel.load_settings()
        self.registry = TargetRegistry()
        bindings = {
            'canvas.ink': lambda: self.panel.canvas,
            'toolbar.mode': lambda: self.panel.icon_buttons.get('mode'),
            'toolbar.pen': lambda: self.panel.icon_buttons.get('pen'),
            'toolbar.eraser': lambda: self.panel.icon_buttons.get('eraser'),
            'toolbar.select': lambda: self.panel.icon_buttons.get('select'),
            'toolbar.undo': lambda: self.panel.icon_buttons.get('undo'),
            'toolbar.redo': lambda: self.panel.icon_buttons.get('redo'),
            'toolbar.whiteboard': lambda: self.panel.icon_buttons.get('whiteboard'),
            'toolbar.file': lambda: self.panel.icon_buttons.get('folder'),
            'toolbar.tools': lambda: self.panel.icon_buttons.get('tools'),
            'tools.teaching': lambda: self.panel.btn_teaching,
            'pen.palette': lambda: self.panel.pen_palette,
            'pen.width': lambda: self.panel.pen_width_row,
            'pen.marker.width': lambda: self.panel.marker_width_slider,
            'pen.marker.alpha': lambda: self.panel.marker_alpha_slider,
            'pen.laser.width': lambda: self.panel.laser_width_slider,
            'pen.defaults': lambda: self.panel.pen_defaults_checkbox,
            'pen.defaults.capture': lambda: getattr(getattr(self.panel, 'pen_defaults_editor', None), 'capture_button', None),
            'pen.style.pen': lambda: self.panel.pen_style_buttons.get('pen'),
            'pen.style.fountain': lambda: self.panel.pen_style_buttons.get('fountain'),
            'pen.style.brush': lambda: self.panel.pen_style_buttons.get('brush'),
            'pen.style.calligraphy': lambda: self.panel.pen_style_buttons.get('calligraphy'),
            'pen.style.pencil': lambda: self.panel.pen_style_buttons.get('pencil'),
            'pen.style.crayon': lambda: self.panel.pen_style_buttons.get('crayon'),
            'pen.style.chalk': lambda: self.panel.pen_style_buttons.get('chalk'),
            'pen.style.neon': lambda: self.panel.pen_style_buttons.get('neon'),
            'pen.style.dashed': lambda: self.panel.pen_style_buttons.get('dashed'),
            'pen.style.rainbow': lambda: self.panel.pen_style_buttons.get('rainbow'),
            'pen.style.arrow': lambda: self.panel.pen_style_buttons.get('arrow'),
            'pen.marker': lambda: self.panel.btn_ann_marker,
            'pen.laser': lambda: self.panel.btn_ann_laser,
            'eraser.type.circle': lambda: self.panel.btn_circ,
            'eraser.type.stroke': lambda: self.panel.btn_stroke,
            'eraser.size': lambda: self.panel.e_slider,
            'toolbar.clear': lambda: self.panel.icon_buttons.get('clear'),
            'selection.duplicate': lambda: self.panel.btn_dup,
            'selection.delete': lambda: self.panel.btn_del,
            'selection.more': lambda: self.panel.btn_more,
            'toolbar.shape': lambda: self.panel.icon_buttons.get('shape'),
            'toolbar.text': lambda: self.panel.icon_buttons.get('text'),
            'text.input': lambda: getattr(self.panel, 'text_input', None),
            'selection.width': lambda: self.panel.select_width_slider,
            'selection.color': lambda: self.panel.selection_color_button,
            'shape.cancel_points': lambda: self.panel.btn_cancel_points,
            'settings.smart_shapes': lambda: getattr(self.panel, 'btn_settings_smart', None),
            'settings.view_fit': lambda: getattr(self.panel, 'btn_view_fit', None),
            'settings.view_home': lambda: getattr(self.panel, 'btn_view_home', None),
            'toolbar.board_style': lambda: self.panel.icon_buttons.get('board_style'),
            'pages.thumbnails_button': lambda: self.panel.rail_count,
            'pages.thumbnail_list': lambda: self.panel.thumbnail_list,
            'pages.rename': lambda: self.panel.btn_rename_page,
            'pages.delete': lambda: self.panel.btn_delete_page,
            'pages.copy': lambda: self.panel.btn_copy_page,
            'pages.copy_position': lambda: getattr(getattr(self.panel, 'document_preferences', None), 'copy_combo', None),
            'settings.autosave_preset': lambda: getattr(getattr(self.panel, 'document_preferences', None), 'interval_combo', None),
            'settings.autosave_custom': lambda: getattr(getattr(self.panel, 'document_preferences', None), 'interval_custom', None),
            'file.import': lambda: self.panel.btn_import_media,
            'file.save': lambda: self.panel.btn_save_project,
            'file.save_as': lambda: self.panel.btn_save_project_as,
            'file.open': lambda: self.panel.btn_open_project,
            'file.recovery': lambda: self.panel.btn_recovery,
            'export.png': lambda: self.panel.btn_export_png,
            'export.pdf': lambda: self.panel.btn_export_pdf,
            'export.svg': lambda: self.panel.btn_export_svg,
            'export.eps': lambda: self.panel.btn_export_eps,
            'pages.add': lambda: self.panel.rail_new,
            'pages.previous': lambda: self.panel.rail_prev,
            'pages.next': lambda: self.panel.rail_next,
        }
        for kind in ('LINE', 'DASHED_LINE', 'TRIANGLE', 'RECT', 'PARALLELOGRAM', 'TRAPEZOID',
                     'DIAMOND', 'ANGLE', 'CIRCLE', 'ELLIPSE', 'CUBOID', 'CUBE', 'CYLINDER', 'CONE'):
            bindings['shape.type.'+kind.lower()] = lambda kind=kind: next(
                (button for button in self.panel.shape_buttons if button.property('shape_type') == kind), None)
        for action in ('done', 'backspace', 'newline'):
            bindings['text.'+action] = lambda action=action: getattr(
                self.panel, 'text_action_buttons', {}).get('text_'+action)
        for group in ('greek', 'structure'):
            bindings['text.group.'+group] = lambda group=group: getattr(
                self.panel, '_symbol_group_buttons', {}).get(group)
        symbols = {'alpha': ('greek', 'α'), 'pm': ('operator', '±'),
                   'member': ('relation', '∈'), 'integral': ('calculus', '∫')}
        for key, (group, entry) in symbols.items():
            bindings['text.symbol.'+key] = lambda entry=entry: self._symbol_target(entry)
        for kind in ('frac', 'sup', 'sub', 'sqrt', 'sum', 'int'):
            bindings['text.structure.'+kind] = lambda kind=kind: self._symbol_target(kind)
        for kind in ('ruler', 'protractor', 'set_square_45', 'set_square_30'):
            bindings['aids.'+kind] = lambda kind=kind: self.panel.aid_buttons[kind]
        bindings.update({'aids.clear': lambda: self.panel.btn_aid_clear,
                         'aids.calibrate': lambda: self.panel.btn_aid_calibrate,
                         'aids.reset': lambda: self.panel.btn_aid_reset})
        bindings.update(toolbox_bindings(self.panel))
        bindings.update(interface_bindings(self.panel))
        for target_id, resolver in bindings.items():
            if target_id in TOOLBOX_TARGETS:
                reveal = lambda target_id=target_id: reveal_toolbox_target(self.panel, target_id)
            elif target_id in INTERFACE_TARGETS:
                reveal = lambda target_id=target_id: reveal_interface_target(self.panel, target_id)
            elif target_id.startswith('aids.'):
                reveal = self.panel.open_aid_menu
            elif target_id in {'pen.palette', 'pen.width'}:
                reveal = self._reveal_pen
            elif target_id.startswith('pen.style.') or target_id in {'pen.marker', 'pen.laser'}:
                reveal = self._reveal_annotations
            elif target_id in {'pen.marker.width', 'pen.marker.alpha'}:
                reveal = self._reveal_marker
            elif target_id == 'pen.laser.width':
                reveal = self._reveal_laser
            elif target_id in {'pen.defaults', 'pen.defaults.capture'}:
                reveal = self._reveal_settings
            elif target_id.startswith('shape.type.') or target_id == 'shape.cancel_points':
                reveal = self._reveal_shapes
            elif target_id == 'settings.smart_shapes':
                reveal = self._reveal_geometry_settings
            elif target_id in {'settings.view_fit', 'settings.view_home'}:
                reveal = lambda target_id=target_id: self._reveal_board_view(target_id)
            elif target_id in {'toolbar.pen', 'toolbar.mode', 'canvas.ink'}:
                reveal = self._leave_board_view_settings
            elif target_id == 'pages.thumbnails_button':
                reveal = self._reveal_thumbnail_button
            elif target_id in {'pages.add', 'pages.previous', 'pages.next'}:
                reveal = self._reveal_page_rail
            elif target_id in {'pages.thumbnail_list', 'pages.rename', 'pages.delete', 'pages.copy'}:
                reveal = self._reveal_thumbnails
            elif target_id.startswith('settings.autosave_'):
                custom = target_id.endswith('custom')
                reveal = lambda custom=custom: self._reveal_autosave_settings(custom)
            elif target_id == 'pages.copy_position':
                reveal = self._reveal_page_settings
            elif target_id.startswith('text.symbol.'):
                group = symbols[target_id.rsplit('.', 1)[1]][0]
                reveal = lambda group=group: self._reveal_symbols(group)
            elif target_id.startswith('text.structure.'):
                reveal = lambda: self._reveal_symbols('structure')
            elif target_id.startswith('text.'):
                reveal = self._reveal_text_input
            elif target_id in {'selection.duplicate', 'selection.delete', 'selection.more',
                               'selection.width', 'selection.color'}:
                reveal = self._reveal_selection
            elif target_id in {'eraser.type.circle', 'eraser.type.stroke', 'eraser.size'}:
                reveal = self._reveal_eraser
            elif target_id in {'file.save', 'file.save_as', 'file.open', 'file.recovery', 'file.import', 'export.png', 'export.pdf', 'export.svg', 'export.eps'}:
                reveal = self._reveal_file
            else:
                reveal = None
            self.registry.register(target_id, resolver, reveal=reveal)
        self.presenter = TeachingPresenter(
            self.catalog, session_id=request.paths.session_id, registry=self.registry,
            owns=self.panel.lifecycle._owns_window, canvas=lambda: self.panel.canvas, translate=module.tr,
            prepare_fixture=self._prepare_fixture,
            reveal_actions={'open_file_panel': self._reveal_file, 'open_pen_panel': self._reveal_pen,
                            'open_eraser_panel': self._reveal_eraser, 'open_settings': self._reveal_settings,
                            'open_tools_panel': self._reveal_tools},
            on_progress=self._record_progress,
            condition_reader=lambda name, argument: name == 'multiple_monitors' and len(QApplication.screens()) > 1,
            pause_action=self.pause_requested.emit,
            layout_obstacles=self._placement_obstacles, interaction_region=self._interaction_region,
            input_helpers=self._input_helpers,
            restack_window=self.panel.raise_floating,
            manage_window=self.panel.lifecycle.register_teaching_window,
            unmanage_window=self.panel.lifecycle.unregister_tool_window)
        self.presenter.controller.setStyleSheet(self.panel.styleSheet())
        self.presenter.controller.setPalette(self.panel.palette())
        self.presenter.controller.set_practice_session(True)
        self.panel.teaching_events = self.presenter.events
        self.panel.teaching_presenter = self.presenter
        self.panel.teaching_text_region = self._text_region
        self.presenter.exit_requested.connect(self.exit_requested)
        self.presenter.failed.connect(self.failed)
        self.panel.exit_requested.disconnect(module.QApplication.quit)
        self.panel.exit_requested.connect(self.exit_requested)

    def _layout_obstacles(self):
        names = ('toolbar_window', 'logo_window', 'menu_panel', 'select_panel', 'page_rail',
                 'settings_panel', 'text_panel', 'calc_panel', 'roster_panel',
                 'thumbnail_panel', 'mini_timer')
        windows = [getattr(self.panel, name, None) for name in names]
        if self.panel.main_frame.isVisible():
            windows.append(self.panel)
        return tuple(window.frameGeometry() for window in windows
                     if window is not None and not sip.isdeleted(window)
                     and window.isWindow() and window.isVisible()
                     and not window.frameGeometry().isEmpty())

    def _text_region(self):
        canvas = self.panel.canvas
        if (self.presenter.engine.phase not in ('running', 'paused') or not canvas.isVisible()
                or canvas.editing_text_item() is None):
            return QRect()
        return _canvas_region(canvas, (canvas.text_bounds(item) for item in canvas.text_items))

    def place_aid(self, aid):
        if self.request.course_id == 'c11':
            from .measurement_layout import place_aid
            place_aid(self, aid)

    def _aid_regions(self):
        canvas = self.panel.canvas
        if self.request.course_id != 'c11':
            return ()
        return tuple(_canvas_region(canvas, (canvas.aid_bounds(aid),)) for aid in canvas.aids)

    def _placement_obstacles(self):
        canvas, engine = self.panel.canvas, self.presenter.engine
        editor = getattr(self.panel, 'text_panel', None)
        if editor is not None and editor.isVisible() and editor.frameGeometry().intersects(self._text_region()):
            self.panel._position_text_panel()
        key = (engine.run_id, engine.step_epoch, canvas._page_id)
        # A pen press closes temporary menus. Defer that placement opportunity
        # until release, rather than move the instruction card during a stroke.
        # Selection keeps its live layout, including marquee/handle movement.
        drawing = canvas.draw_state != 'SELECT' and (canvas.last_point is not None or canvas._pointer_slots)
        if key != self._obstacle_snapshot or not drawing:
            self._obstacle_snapshot = key
            self._obstacle_rects = self._layout_obstacles()
        return self._obstacle_rects + self._aid_regions()

    def _selection_region(self):
        """Protect the live selection workspace, not a course-specific sample box.

        Object/handle/marquee bounds are document coordinates. Convert each to
        the current view before clipping and uniting: offscreen objects must not
        reserve the whole infinite board. The union also keeps the blank space
        between objects available for a mandatory rectangle-selection gesture.
        """
        canvas = self.panel.canvas
        step = self.presenter.engine.current_step
        if step is None or not canvas.isVisible():
            return QRect()
        events = {clause.event for clause in step.wait.clauses} if step.wait else set()
        if canvas.draw_state != 'SELECT' and not any(event.startswith('selection.') for event in events):
            return QRect()
        choosing = 'selection.changed' in events
        ids = (set(canvas.selected_ids) if canvas.selected_ids and not choosing else
               {item['id'] for items in (canvas.all_segments, canvas.shape_items,
                                        canvas.text_items, canvas.image_items) for item in items})
        bounds = [canvas.object_bounds(object_id) for object_id in ids]
        bounds.extend(canvas.selection_handles().values())
        if canvas.selection_rect is not None:
            bounds.append(canvas.selection_rect.normalized())
        return _canvas_region(canvas, bounds)

    def _interaction_region(self):
        canvas = self.panel.canvas
        if self.request.course_id == 'c11' and canvas.aids:
            aid = canvas.find_aid(canvas.active_aid_id) or canvas.aids[-1]
            return _canvas_region(canvas, (canvas.aid_bounds(aid),))
        text = self._text_region()
        if not text.isEmpty():
            return text
        selection = self._selection_region()
        canvas, engine = self.panel.canvas, self.presenter.engine
        step = engine.current_step
        if (not selection.isEmpty() or step is None or not canvas.isVisible()
                or canvas.draw_state == 'SELECT' or step.input_policy != 'canvas'):
            return selection
        # Capture existing examples once, before the user can start this step.
        # Epoch changes also cover Previous, Retry and resume; a page switch or
        # new run cannot reuse another document's protected rectangle.
        key = (engine.run_id, engine.step_epoch, canvas._page_id)
        if key != self._example_snapshot:
            ids = {item['id'] for items in (canvas.all_segments, canvas.shape_items,
                                           canvas.text_items, canvas.image_items) for item in items}
            examples = self._example_ids.get(canvas._page_id, set()) & ids
            if not examples:
                examples = ids
                self._example_ids[canvas._page_id] = set(examples)
            # Prefer the original examples over accumulating new practice ink.
            # Copy bounds, not mutable objects: even a partial erase or an
            # uncommitted stroke must not make the card chase the user's pen.
            self._example_bounds = tuple(QRectF(canvas.object_bounds(object_id)) for object_id in examples)
            self._example_snapshot = key
        region = _canvas_region(canvas, self._example_bounds)
        if step.target == 'magnifier.practice' and not region.isEmpty():
            # Protect the whole lens sweep over the fixed sample, including its
            # zoom badge. View-pixel padding stays correct under zoom/DPR and
            # does not chase the pointer as the user practices.
            radius = int(canvas.magnifier_size / 2) + 4
            viewport = canvas.rect().translated(canvas.mapToGlobal(QPoint()))
            return region.adjusted(-radius, -radius, radius, radius + 30).intersected(viewport)
        return region

    def _reveal_tools(self):
        self.panel.show_only_sub(self.panel.tools_sub)

    def _reveal_annotations(self):
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is not None and not sip.isdeleted(settings):
            settings.hide()
        self.panel.show_only_sub(self.panel.annotate_sub)

    def _reveal_marker(self):
        self.panel.show_only_sub(self.panel.marker_sub)

    def _reveal_laser(self):
        self.panel.show_only_sub(self.panel.laser_sub)

    def _reveal_eraser(self):
        self.panel.show_only_sub(self.panel.eraser_sub)

    def _reveal_shapes(self):
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is not None and not sip.isdeleted(settings):
            settings.hide()
        self.panel.show_only_sub(self.panel.shape_sub)

    def _reveal_board_view(self, target_id):
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is None or sip.isdeleted(settings) or not settings.isVisible():
            self.panel.open_settings_panel()
        self._board_view_settings_revealed = True
        widget = getattr(self.panel, 'btn_' + target_id.split('.', 1)[1])
        self.panel.settings_scroll.ensureWidgetVisible(widget)

    def _leave_board_view_settings(self):
        if not getattr(self, '_board_view_settings_revealed', False):
            return
        self._board_view_settings_revealed = False
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is not None and not sip.isdeleted(settings):
            settings.hide()

    def _reveal_geometry_settings(self):
        self.panel.close_thumbnail_panel()
        self.panel.open_settings_panel()

    def _reveal_page_rail(self):
        self.panel.update_whiteboard_ui()

    def _reveal_thumbnail_button(self):
        self.panel.close_thumbnail_panel()
        self._reveal_page_rail()

    def _reveal_thumbnails(self):
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is not None and not sip.isdeleted(settings):
            settings.hide()
        if not self.panel.thumbnail_panel.isVisible():
            self.panel.toggle_thumbnail_panel()

    def _reveal_page_settings(self):
        self.panel.close_thumbnail_panel()
        self.panel.open_settings_panel()

    def _reveal_autosave_settings(self, custom=False):
        self.panel.close_thumbnail_panel()
        settings = getattr(self.panel, 'settings_panel', None)
        if settings is None or sip.isdeleted(settings) or not settings.isVisible():
            self.panel.open_settings_panel()
        preferences = self.panel.document_preferences
        widget = preferences.interval_custom if custom else preferences.interval_combo
        self.panel.settings_scroll.ensureWidgetVisible(widget)

    def _symbol_target(self, entry):
        layout = getattr(self.panel, 'symbol_grid_layout', None)
        if layout is None:
            return None
        for index in range(layout.count()):
            button = layout.itemAt(index).widget()
            if button is not None and button.property('teaching_symbol') == entry:
                return button
        return None

    def _input_helpers(self, target_id):
        # Launching the keyboard is an input aid, not a completed lesson action.
        # Permit only that button, never the whole text panel or its Done action.
        if (not target_id or not (target_id.startswith('text.') or target_id == 'canvas.ink')
                or self.panel.canvas.editing_text_item() is None):
            return ()
        button = getattr(self.panel, 'text_action_buttons', {}).get('text_keyboard')
        if button is None or sip.isdeleted(button) or not button.isVisible():
            return ()
        return (button,)

    def _reveal_text_input(self):
        if self.panel.canvas.editing_text_item() is None:
            return
        panel = getattr(self.panel, 'text_panel', None)
        if panel is not None and panel.isVisible():
            self.panel._position_text_panel()

    def _reveal_symbols(self, group):
        self._reveal_text_input()
        if (self.panel.canvas.editing_text_item() is not None
                and getattr(self.panel, '_open_symbol_group', None) != group):
            self.panel._toggle_symbol_group(group)

    def _reveal_selection(self):
        self.panel.sync_selection_controls()
        self.panel.position_selection_panel(self.panel.canvas.selection_bounds())

    def _reveal_settings(self):
        self.panel.open_settings_panel()
        self.panel.pen_defaults_editor.set_current_key('pen')

    def _busy(self):
        canvas = self.panel.canvas
        editor = getattr(self.panel, 'text_panel', None)
        return bool(self._closed or self._center_ending or not self.context.ui_active or self._hidden_token is not None
            or self._center_hidden or self.panel._document_transition_active or self.panel._unsaved_prompt_active
            or self.panel._autosave_future is not None or getattr(self.panel, '_teaching_document_batch', None)
            or QApplication.activeModalWidget() is not None
            or editor is not None and editor.isVisible()
            or canvas is None or canvas._pointer_slots or any(getattr(canvas, name, None) is not None for name in (
                'last_point','shape_start','selection_start','drag_start','drag_action','text_drag_start',
                'transform_start_distance','transform_start_angle','aid_drag')))

    def request_center(self):
        if self._busy() or self._center_token is not None:
            return False
        from .events import TeachingOperationBatch
        batch = TeachingOperationBatch(self.panel.teaching_events, ('center.visited',))
        native = self.presenter.native_dialog(before_refresh=batch.flush)
        try:
            native.__enter__()
            self._center_native = native
            self._center_batch = batch
            self._center_token = self.panel.lifecycle.suspend_for_teaching()
            self._center_visited = False
            self.center_requested.emit()
            return True
        except Exception:
            batch.close()
            if self._center_native is not None:
                self._center_native = None
                native.__exit__(*sys.exc_info())
            raise

    def update_parent_view(self, view):
        self.view.replace(view)
        if self.center is not None and not sip.isdeleted(self.center):
            self.center.refresh()

    def accept_center(self, view, *, hidden=False):
        if self._closed or self._center_token is None or self.center is not None:
            raise ValueError('no pending private center request')
        from .widgets import TeachingCenter
        self.update_parent_view(view)
        center = TeachingCenter(self.catalog, self.view, self.module.tr, self.panel)
        self.center = center
        self._center_hidden = hidden
        center.set_mutations_allowed(False)
        center.select_chapter(self.current_course_id, self.current_chapter_id)
        center.start_requested.connect(self._select_chapter)
        center.finished.connect(lambda _: self._center_view_closed(center))
        self.panel.lifecycle.allow_practice_teaching_window(center)
        self._center_windows.add(center)
        if not hidden:
            center.show()
            self._center_visited = center.isVisible()

    def _center_view_closed(self, center):
        if self._closed or self.center is not center:
            return
        self.center = None
        self.panel.lifecycle.unregister_tool_window(center)
        self._center_windows.discard(center)
        self.center_closed.emit()

    def _select_chapter(self, course_id, chapter_id):
        center = self.center
        if (self._busy() or self._switch_pending or self._chapter_confirming or center is None or sip.isdeleted(center)
                or not center.isVisible() or not center.isEnabled()):
            return False
        course = self.catalog.course_by_id(course_id)
        if not any(chapter.id == chapter_id for chapter in course.chapters):
            return False
        box = QMessageBox(center)
        box.setWindowTitle(self.module.tr('teaching_center_title'))
        box.setText(self.module.tr('teaching_chapter_switch_confirm'))
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        self.panel.lifecycle.allow_practice_teaching_window(box)
        self._center_windows.add(box)
        self._chapter_confirming = True
        try:
            accepted = box.exec() == QMessageBox.StandardButton.Yes
        finally:
            self._chapter_confirming = False
            self._center_windows.discard(box)
            self.panel.lifecycle.unregister_tool_window(box)
            if not sip.isdeleted(box):
                box.hide()
                box.deleteLater()
        if (not accepted or self._busy() or self._closed or self._switch_pending
                or self.center is not center or sip.isdeleted(center) or not center.isEnabled()):
            return False
        self._switch_pending = True
        center.setEnabled(False)
        self.chapter_requested.emit(course_id, chapter_id)
        return True

    def prepare_chapter_change(self):
        if self._closed or self._center_token is None:
            raise ValueError('no private center session')
        self._switch_pending = True
        self._cancel_roaming_gesture()
        if self._center_batch is not None: self._center_batch.close()
        self.presenter.engine.stop()

    def prepare_chapter(self, course_id, chapter_id):
        if self._closed or self._center_token is None or not self._switch_pending:
            raise ValueError('no accepted chapter change')
        self.current_course_id, self.current_chapter_id = course_id, chapter_id
        self.presenter.start(course_id, chapter_id)
        self.presenter.pause()

    def commit_chapter(self):
        if not self._switch_pending:
            raise ValueError('no prepared private chapter')
        self._end_center(resume=True, hidden=False, publish=False)

    def finish_center(self, *, resume, hidden=False):
        self._end_center(resume=resume, hidden=hidden, publish=resume and not hidden)

    def _end_center(self, *, resume, hidden, publish):
        if self._center_ending:
            return
        self._center_ending = True
        self._center_end_control = None
        batch, native = self._center_batch, self._center_native
        error = (None, None, None)
        try:
            center, self.center = self.center, None
            if center is not None and not sip.isdeleted(center):
                self.panel.lifecycle.unregister_tool_window(center)
                self._center_windows.discard(center)
                center.close()
            token = self._center_token
            if token is not None:
                if self._closed:
                    # An exiting private process only tears down; it need not show its scene.
                    self._center_token = None
                elif hidden:
                    self._hidden_token, self._center_token = token, None
                    self.presenter.pause()
                else:
                    if self._switch_pending:
                        self.panel.lifecycle.restore_practice_after_chapter_change(token)
                        if not self._closed and self._center_end_control not in ('pause', 'hide'):
                            self.panel.show_only_sub(None)
                            self.panel.close_thumbnail_panel()
                            settings = getattr(self.panel, 'settings_panel', None)
                            if settings is not None and not sip.isdeleted(settings):
                                settings.hide()
                            calculator = getattr(self.panel, 'calc_panel', None)
                            if calculator is not None and not sip.isdeleted(calculator):
                                calculator.hide()
                            self.panel.update_whiteboard_ui()
                    else:
                        self.panel.lifecycle.restore_after_teaching(token)
                    self._center_token = None
                    control = self._center_end_control
                    if self._closed:
                        self.panel._teaching_suspended = True
                        self.panel.pause_callbacks()
                        self._hide_owned_windows()
                    elif control == 'hide':
                        self._hidden_token = self.panel.lifecycle.suspend_for_teaching()
                        if self._hidden_token is None:
                            raise RuntimeError('cannot keep private practice hidden')
                        self.presenter.pause()
                    elif control == 'pause' or not resume:
                        self.presenter.pause()
                    else:
                        self.presenter.resume()
            if (publish and not self._closed and not hidden and self._hidden_token is None
                    and self._center_end_control not in ('pause', 'hide')
                    and self._center_visited and batch is not None):
                batch.emit_result(batch.operation('center.visited'), 'center.visited', 'success',
                    {'course_id': self.current_course_id, 'chapter_id': self.current_chapter_id})
        except Exception:
            error = sys.exc_info()
            with suppress(Exception):
                self.presenter.pause()
            raise
        finally:
            self._center_batch = None
            self._center_native = None
            self._center_hidden = False
            self._switch_pending = False
            try:
                if native is not None:
                    native.__exit__(*error)
            finally:
                if batch is not None:
                    batch.close()
                self._center_visited = False
                self._center_ending = False
                self._center_end_control = None

    def _reveal_pen(self):
        # Revealing settings cannot select a tool or satisfy a business wait.
        self.panel.show_only_sub(self.panel.draw_sub)

    def _reveal_file(self):
        if not self.panel.file_sub.isVisible():
            self.panel.handle_file_click()

    def _prepare_fixture(self, fixture):
        self._example_ids.clear()
        self._example_snapshot, self._example_bounds = None, ()
        self._obstacle_snapshot, self._obstacle_rects = None, ()
        # The catalog maps IDs to bounded bundled data only, never executable code.
        source = self.loader.asset_path(self.loader.fixtures[fixture])
        directory = self.request.paths.require_directory_path(self.request.paths.data_dir / 'fixtures')
        directory.mkdir(parents=True, exist_ok=True)
        destination = self.request.paths.require_write_path(directory / (fixture + '.msd'))
        shutil.copyfile(source, destination)
        if not self.panel.load_teaching_fixture(str(destination)):
            raise ValueError('practice fixture could not be prepared')
        self.panel.project_path = None
        self.panel.project_dirty = False
        self.panel._teaching_file_open_path = None
        self.panel._teaching_last_saved_project = None
        self.panel._teaching_export_fixture = None
        self.panel._teaching_media_original_id = None
        self.panel._teaching_media_source_path = None
        from .core_fixtures import prepare_core_fixture
        prepare_core_fixture(self.panel, self.loader, fixture, self.request.paths)
        from .writing_fixtures import prepare_writing_fixture
        prepare_writing_fixture(self.panel, fixture, self.request.paths)
        from .selection_fixtures import prepare_selection_fixture
        prepare_selection_fixture(self.panel, fixture, self.request.paths)
        from .pages_fixtures import prepare_pages_fixture
        prepare_pages_fixture(self.panel, fixture, self.request.paths)
        from .geometry_fixtures import prepare_geometry_fixture
        prepare_geometry_fixture(self.panel, fixture, self.request.paths)
        from .text_fixtures import prepare_text_fixture
        prepare_text_fixture(self.panel, fixture, self.request.paths)
        from .file_fixtures import prepare_file_fixture
        prepare_file_fixture(self.panel, self.loader, fixture, self.request.paths)
        from .media_fixtures import prepare_media_fixture
        prepare_media_fixture(self.panel, self.loader, fixture, self.request.paths)
        from .export_fixtures import prepare_export_fixture
        prepare_export_fixture(self.panel, fixture, self.request.paths)
        from .measurement_fixtures import prepare_measurement_fixture
        prepare_measurement_fixture(self.panel, fixture, self.request.paths)
        from .toolbox_fixtures import prepare_toolbox_fixture
        prepare_toolbox_fixture(self.panel, fixture, self.request.paths)
        from .interface_fixtures import prepare_interface_fixture
        prepare_interface_fixture(self.panel, fixture, self.request.paths)

    def activate(self):
        if self._closed or not self.context.ui_active:
            raise RuntimeError('practice has not been activated')
        self.panel.canvas.show()
        self.panel.show()
        self.panel.set_ui_mode('icon', persist=False)
        self.panel.btn_teaching.setEnabled(True)
        self.presenter.start(self.request.course_id, self.request.chapter_id)
        self.panel.resume_callbacks()
        self.panel.bind_topmost_stack()

    def _cancel_roaming_gesture(self):
        canvas = self.panel.canvas
        canvas._cancel_teaching_roam()
        canvas._pan_point = None
        canvas._board_gesture.clear()

    def pause(self, *, hidden=False):
        self._cancel_roaming_gesture()
        self.presenter.pause()
        if self._center_ending:
            self._center_end_control = 'hide' if hidden else 'pause'
            return
        if self._center_token is not None:
            if hidden:
                self._center_hidden = True
                for window in tuple(self._center_windows):
                    if not sip.isdeleted(window): window.hide()
            return
        if hidden and self._hidden_token is None:
            self._hidden_token = self.panel.lifecycle.suspend_for_teaching()

    def resume(self):
        if self._center_ending:
            self._center_end_control = 'resume'
            return
        if self._center_token is not None:
            self._center_hidden = False
            for window in tuple(self._center_windows):
                if not sip.isdeleted(window): window.show()
            return
        was_paused = self.presenter.engine.phase == 'paused'
        prior_step = (self.presenter.engine.chapter_id, self.presenter.engine.current_step_id)
        if self._hidden_token is not None:
            self.panel.lifecycle.restore_after_teaching(self._hidden_token)
            self._hidden_token = None
        self.presenter.resume()
        if (was_paused and self.presenter.engine.phase == 'running'
                and prior_step == (self.presenter.engine.chapter_id, self.presenter.engine.current_step_id)):
            events = self.presenter.events
            operation = events.begin_operation('practice.resumed')
            if operation is not None:
                QTimer.singleShot(0, lambda: not self._closed and events.emit_result(
                    operation, 'practice.resumed', 'success', {}))

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

    def _hide_owned_windows(self):
        for window in QApplication.topLevelWidgets():
            if not sip.isdeleted(window) and self.panel.lifecycle._owns_window(window):
                for timer in window.findChildren(QTimer):
                    timer.stop()
                window.hide()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._cancel_roaming_gesture()
        failure = None
        if not self._center_ending and (self._center_token is not None or self._center_native is not None):
            if self._center_batch is not None:
                self._center_batch.close()
            try:
                self._end_center(resume=False, hidden=False, publish=False)
            except Exception as exc:
                failure = exc
        self.panel.btn_teaching.setEnabled(False)
        self.panel.teaching_host = None
        self.panel.teaching_events = None
        self.panel.teaching_presenter = None
        self.panel.teaching_text_region = None
        self.panel._teaching_suspended = True
        for cleanup in (self.presenter.close, self.registry.close, self.panel.pause_callbacks,
                        self.panel.stop_update_worker, self.panel.shutdown_autosave,
                        self._hide_owned_windows):
            try:
                cleanup()
            except Exception as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise RuntimeError('private teaching cleanup failed') from failure


def run_practice_application(request: PracticeRequest, module: ModuleType) -> int:
    """Private startup branch: connect first; never fall through to normal startup."""
    context = module.RUNTIME_CONTEXT
    if not context.paths.practice or context.ui_active or context.paths != request.paths:
        return 2
    module.initialize_interface_preferences()
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
        self._welcome_deferred_to_next_start = False
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
        from .context_hints import ContextHintPolicy
        self._hint_topics = {}
        for context_id, (course_id, chapter_id) in APPLICATION_HINT_TOPICS.items():
            with suppress(KeyError):
                course = self.catalog.course_by_id(course_id)
                if any(chapter.id == chapter_id for chapter in course.chapters):
                    self._hint_topics[context_id] = (course_id, chapter_id)
        hint_context = TeachingStartupContext.from_arguments(
            sys.argv[1:], automated=QApplication.platformName() == 'offscreen')
        self.hint_policy = ContextHintPolicy(self.state_store, self._hint_topics,
                                             context=hint_context, warn=self._notice)
        self.context_hint = None
        self._hint_offer = None
        self._pending_hint = None
        self._hint_timer = QTimer(self)
        self._hint_timer.setInterval(200)
        self._hint_timer.timeout.connect(self._show_pending_context_hint)

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

    def _hint_entry_allowed(self, context_id):
        return (not self._closed and context_id in self._hint_topics and not self.active
                and self.hint_policy.context.automatic_allowed
                and self.state_store.welcome != 'unseen'
                and self.state_store.should_offer_context_hint(context_id)
                and not (self.center is not None and not sip.isdeleted(self.center)
                         and self.center.isVisible())
                and not (self.welcome.dialog is not None and not sip.isdeleted(self.welcome.dialog)
                         and self.welcome.dialog.isVisible()))

    def request_context_hint(self, context_id):
        """Queue one trusted feature visit; never finish or cancel the user's work."""
        if (not self._hint_entry_allowed(context_id) or self.context_hint is not None
                or self._pending_hint is not None):
            return False
        self._pending_hint = context_id
        self._hint_timer.start()
        return True

    def _show_pending_context_hint(self):
        context_id = self._pending_hint
        if context_id is None or not self._hint_entry_allowed(context_id):
            self._pending_hint = None
            self._hint_timer.stop()
            return False
        ready = self.readiness()
        if not ready.safe:
            return False
        self._pending_hint = None
        self._hint_timer.stop()
        offer = self.hint_policy.try_offer(context_id, ready, self._display_context_hint)
        if offer is None:
            self._retire_context_hint()
        return offer is not None

    def _display_context_hint(self, offer):
        from .hint_widget import ContextTeachingHint
        chapter = self.catalog.chapter_by_id(offer.chapter_id)
        hint = ContextTeachingHint(self.module.tr('teaching_context_hint_title'),
            self.module.trf('teaching_context_hint_body', chapter=self.module.tr(chapter.title_key)),
            self.module.tr('teaching_start'), self.module.tr('teaching_context_hint_later'), self.panel)
        self.context_hint, self._hint_offer = hint, offer
        hint.start_requested.connect(lambda: self._start_context_hint(offer))
        hint.dismissed.connect(lambda: self._dismiss_context_hint(offer))
        hint.destroyed.connect(lambda: self._context_hint_destroyed(hint, offer))
        self.panel.lifecycle.register_teaching_window(hint)
        hint.show()
        return not sip.isdeleted(hint) and hint.isVisible() and self._hint_offer is offer

    def _context_hint_destroyed(self, hint, offer):
        if self.context_hint is hint:
            self.context_hint, self._hint_offer = None, None
            self.hint_policy.dismiss(offer)
            self.panel.lifecycle.unregister_tool_window(hint)

    def _dismiss_context_hint(self, offer):
        if self._hint_offer is not offer:
            return False
        self.hint_policy.dismiss(offer)
        self._retire_context_hint()
        return True

    def _start_context_hint(self, offer):
        if self._closed or self._hint_offer is not offer:
            return False
        allowed = self.hint_policy.consume(offer, self.readiness())
        self._retire_context_hint()
        if not allowed:
            self._notice('teaching_waiting_operation')
            return False
        return self.start(offer.course_id, offer.chapter_id)

    def _retire_context_hint(self):
        self._hint_timer.stop()
        self._pending_hint = None
        self.hint_policy.invalidate()
        hint, self.context_hint, self._hint_offer = self.context_hint, None, None
        if hint is not None and not sip.isdeleted(hint):
            self.panel.lifecycle.unregister_tool_window(hint)
            hint.hide()
            hint.close()

    def open_center(self):
        from .widgets import TeachingCenter
        if self._closed or not self.policy.can_open_center(self.readiness()):
            self._notice('teaching_waiting_operation')
            return False
        self._retire_context_hint()
        if self.center is None or sip.isdeleted(self.center):
            self.center = TeachingCenter(self.catalog, self.state_store, self.module.tr, self.panel)
            self.center.start_requested.connect(self.start)
            self.center.context_hints_requested.connect(self.set_context_hints_enabled)
            self.center.reset_requested.connect(self.reset_progress)
            self.panel.lifecycle.register_teaching_window(self.center)
        self._refresh_center()
        self.center.show()
        return True

    def _can_change_learning_settings(self):
        if self._closed:
            self._refresh_center()
            return False
        if self.active or not self.readiness().safe:
            self._notice('teaching_waiting_operation')
            self._refresh_center()
            return False
        if self.state_store.read_only:
            self._notice('teaching_progress_save_failed')
            self._refresh_center()
            return False
        return True

    def set_context_hints_enabled(self, enabled):
        if not self._can_change_learning_settings():
            return False
        persisted = self.state_store.set_context_hints_enabled(enabled, require_persistence=True)
        if persisted:
            self._retire_context_hint()
        self._refresh_center()
        if not persisted:
            self._notice('teaching_progress_save_failed')
        return persisted

    def reset_progress(self, show_welcome=False):
        if not self._can_change_learning_settings():
            return False
        persisted = self.state_store.reset(show_welcome=show_welcome, require_persistence=True)
        if persisted:
            self._retire_context_hint()
            self._welcome_timer.stop()
            self._welcome_deferred_to_next_start = True
            self.welcome.close(record_decision=False)
        self._refresh_center()
        if not persisted:
            self._notice('teaching_progress_save_failed')
        return persisted

    def maybe_show_welcome(self):
        if self._closed or self._welcome_deferred_to_next_start:
            return False
        shown = self.welcome.maybe_show(self.readiness())
        if shown and self.welcome.dialog is not None and not sip.isdeleted(self.welcome.dialog):
            self.panel.lifecycle.register_teaching_window(self.welcome.dialog)
        return shown

    def request_startup_welcome(self):
        if (self._closed or self._welcome_deferred_to_next_start
                or not self.policy.context.automatic_allowed or self.state_store.read_only
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
        self._retire_context_hint()
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
        self._retire_context_hint()
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
            if self.session.request_resume():
                self._practice_hidden = False
                self._sync_background_action()
            return True
        if self.session.phase == 'restore_failed':
            self._notice('teaching_session_restore_failed', recovery=True)
            return True
        return self.session.phase not in ('idle', 'stopped')

    def _refresh_center(self, _=None):
        if self.center is not None and not sip.isdeleted(self.center):
            self.center.set_mutations_allowed(not self._closed and not self.active)
            self.center.refresh()

    def _phase_changed(self, phase):
        if phase not in ('idle', 'stopped'):
            self._retire_context_hint()
        self._refresh_center()
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
        self.panel.lifecycle.register_teaching_window(box)
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
        self._retire_context_hint()
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
