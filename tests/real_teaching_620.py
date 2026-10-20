# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in Windows native C01-C13 tutorial acceptance (NOT a pytest test).

Safe, non-GUI commands:
  python -B tests/real_teaching_620.py --list
  python -B tests/real_teaching_620.py --self-check
  python -B tests/real_teaching_620.py --chapter c07.formula --plan

REAL DESKTOP commands -- run only when explicitly scheduled:
  python -B tests/real_teaching_620.py --chapter c07.edit --output D:/private/.ccgui/c07
  python -B tests/real_teaching_620.py --chapter c07 --chapter c08 --output D:/private/.ccgui/text-files
  python -B tests/real_teaching_620.py --all --output D:/private/.ccgui/tutorials-620

Each chapter has its own source/native application process and owned RuntimePaths.
Only initial composition/fixtures and teardown call internal application methods.
The local pause/center bridge is setup wiring, NOT an IPC/parent-restoration test.
All lesson operations use Windows mouse/keyboard/wheel/drag input. Geometry and
assertions read Qt/host objects; no business calls, QTest, sendEvent, .click(),
setValue(), direct result emission or dialog-result substitution advance lessons.
C13 system/tray/update/autostart are information lessons, never actual OS changes.
The c05.roam chapter uses native pan, wheel zoom and real Fit/Home controls.
Screenshots are PRIVATE composed screen captures (CAPTUREBLT); never publish them.
Physical Escape aborts. Do not use the desktop while a native chapter is running.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Feature's teaching bridge import is worker-local: these pure helpers do not
# import this module, Qt, native_input_620 or the application at import time.
from real_features_620 import configure_cleanup_api, release_owned_mouse, write_json

# Explicit coverage, not a catch-all that silently blesses a newly added chapter.
SUPPORTED = {
    'c01': ('interface', 'ink', 'select', 'pages', 'files', 'finish'),
    'c02': ('styles', 'color_width', 'transient'),
    'c03': ('erase', 'history_clear'),
    'c04': ('select_move', 'transform', 'copy_delete'),
    'c05': ('board', 'add_switch', 'rename_delete', 'copy_position', 'reorder', 'roam'),
    'c06': ('plane', 'solid', 'points', 'recognition_snap'),
    'c07': ('edit', 'format', 'formula'),
    'c08': ('save', 'open_guard', 'recovery', 'interval'),
    'c09': ('image', 'pdf_pages'),
    'c10': ('formats', 'progress_cancel', 'result'),
    'c11': ('instruments', 'calibration'),
    'c12': ('calculator', 'roster', 'timer', 'magnifier', 'spotlight'),
    'c13': ('layout_theme', 'monitor_audio', 'lifecycle', 'system'),
}


def catalog_rows():
    result = {}
    for file in sorted((ROOT/'assets/tutorials/courses').glob('c[0-9][0-9].json')):
        course = json.loads(file.read_text(encoding='utf-8'))
        for chapter in course['chapters']:
            result[chapter['id']] = chapter
    return result


def classify(chapter, step):
    """Pure action plan: usable without Qt, Win32 or an active desktop."""
    course, suffix = chapter.split('.', 1)
    if suffix not in SUPPORTED.get(course, ()):
        raise ValueError(f'no native action implementation for chapter {chapter}')
    name, target = step['id'], step.get('target')
    if step.get('kind') == 'information': return 'next'
    if chapter.startswith('c07.'): return 'text'
    if chapter.startswith('c08.'): return 'files'
    if chapter.startswith('c09.'): return 'media'
    if chapter.startswith('c10.'): return 'export'
    if chapter.startswith('c11.'): return 'measure'
    if chapter.startswith('c12.'): return 'toolbox'
    if chapter.startswith('c13.'): return 'interface'
    if chapter.startswith('c06.'): return 'geometry'
    if chapter.startswith('c05.'): return 'pages'
    if chapter.startswith('c04.'): return 'selection'
    if chapter == 'c01.files': return 'files'
    if name in ('pause', 'center'): return 'session'
    if target == 'canvas.ink' or name == 'erase' or name == 'choose': return 'canvas'
    if target == 'pen.palette': return 'palette'
    if target in ('pen.width', 'eraser.size', 'pen.marker.width', 'pen.marker.alpha', 'pen.laser.width'):
        return 'slider'
    if target: return 'button'
    raise ValueError(f'unmapped operation: {chapter}/{name}')


def selected_chapters(args, rows):
    if args.all:
        selected = list(rows)
    else:
        selected = []
        for item in args.chapter or ():
            values = [item] if '.' in item else [key for key in rows if key.startswith(item+'.')]
            if not values or any(value not in rows for value in values):
                raise ValueError(f'unknown chapter/course: {item}')
            selected.extend(values)
    return list(dict.fromkeys(selected))


class ChapterDriver:
    def __init__(self, host, harness, output, timeout):
        self.host, self.h, self.output = host, harness, output
        self.panel, self.canvas = host.panel, host.panel.canvas
        self.engine = host.presenter.engine
        self.timeout = timeout
        self.rows, self.inputs, self.progress = [], [], []
        self.input_journal = install_input_journal(self.h.mouse, self.output, self.inputs)
        self.state = {}
        self.dialog_handler = None
        self.dialog_busy = False
        self.dialog_error = None
        self.closed = False
        self.started = time.monotonic()
        self.qt_input_observer = install_qt_input_observer(self)
        from PyQt6.QtCore import QTimer
        self.dialog_timer = QTimer()
        self.dialog_timer.setInterval(5)
        self.dialog_timer.timeout.connect(self.service_dialogs)
        self.dialog_timer.start()

    def current(self):
        return (self.engine.current_step_id, self.engine.sequence_index, self.engine.phase)

    def pump(self, ms=100):
        self.h.mouse.pump(ms)
        if self.dialog_error: raise self.dialog_error

    def until(self, predicate, timeout=8, description='condition'):
        end = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() >= end:
                raise TimeoutError(f'{description}; state={self.current()} missing={self.host.presenter._missing}')
            self.pump(25)

    def target(self):
        target = self.host.presenter.active_target_id
        widget = self.host.registry.resolve(target) if target else None
        if widget is None: raise RuntimeError(f'current target unavailable: {target}')
        if target == 'toolbar.logo': widget = self.panel.logo_window.logo_btn
        return widget

    def click_target(self):
        widget = self.target()
        self.h.scroll_to(self.panel, widget)
        self.h.mouse.click(widget)

    def point(self, x, y=None):
        from PyQt6.QtCore import QPointF
        doc = QPointF(x, y) if y is not None else QPointF(x)
        local = self.canvas.to_view(doc).toPoint()
        if not self.canvas.rect().contains(local):
            raise RuntimeError(f'document point outside canvas: {doc} -> {local}')
        return self.canvas.mapToGlobal(local)

    def click_canvas(self, x, y=None):
        point = self.point(x, y)
        self.h.mouse.hit(self.canvas, point)
        self.h.mouse.click_point(point)

    def free_document_path(self, coordinates):
        from PyQt6.QtCore import QPointF
        coordinates = [QPointF(x, y) for x, y in coordinates]
        left, top = min(p.x() for p in coordinates), min(p.y() for p in coordinates)
        width = max(p.x() for p in coordinates)-left
        height = max(p.y() for p in coordinates)-top
        view = self.canvas.to_document(self.canvas.rect().center())
        origins = [(view.x(), view.y()), (left, top)]
        origins.extend((x, y) for y in range(100, self.canvas.height()-int(height)-30, 70)
                       for x in range(120, self.canvas.width()-int(width)-30, 90))
        for x, y in origins:
            points = [p+QPointF(x-left, y-top) for p in coordinates]
            try:
                samples = [points[0]]
                for start, end in zip(points, points[1:]):
                    samples.extend(start+(end-start)*i/12 for i in range(1, 13))
                for point in samples: self.h.mouse.hit(self.canvas, self.point(point))
                return [(p.x(), p.y()) for p in points]
            except RuntimeError:
                continue
        raise RuntimeError('no unobstructed canvas region for a new drawing')

    def stroke(self, coordinates=None, *, hold_ms=0):
        if coordinates is None:
            coordinates = self.free_document_path([(420+i*5, 310+(i%6)*3) for i in range(27)])
        points = [self.point(x, y) for x, y in coordinates]
        for p in points: self.h.mouse.hit(self.canvas, p)
        self.h.mouse.path(points, hold_ms=hold_ms)

    def drag_canvas(self, start, end):
        a, b = self.point(start), self.point(end)
        self.h.mouse.hit(self.canvas, a); self.h.mouse.hit(self.canvas, b)
        self.h.mouse.drag(a, b)

    def text_input(self, text):
        self.h.mouse.click(self.panel.text_input)
        self.h.mouse.text(text)
        self.pump(100)

    def transform(self, action):
        from PyQt6.QtCore import QPointF
        c = self.canvas
        start = c.selection_bounds().center() if action == 'move' else c.selection_handles()[action].center()
        for dx, dy in ((70, 55 if action == 'rotate' else 30), (70, -55), (-70, 55), (-70, -55)):
            end = start+QPointF(dx, dy)
            try:
                for index in range(13):
                    self.h.mouse.hit(c, self.point(start+(end-start)*index/12))
            except RuntimeError:
                continue
            self.drag_canvas(start, end)
            return
        raise RuntimeError(f'no unobstructed native {action} handle path')

    def snapshot(self):
        c, p = self.canvas, self.panel
        return {'document': c.document_signature(), 'page': c.current_page,
                'page_ids': [page['page_id'] for page in c.pages],
                'segments': len(c.all_segments), 'shapes': len(c.shape_items),
                'texts': [{'id': str(t['id']), 'text': t.get('text', ''),
                           'size': t.get('size'), 'scale': t.get('scale'), 'rotation': t.get('rotation')} for t in c.text_items],
                'images': len(c.image_items), 'selected': sorted(map(str, c.selected_ids)),
                'aids': len(c.aids), 'project_path': p.project_path,
                'dirty': p.has_unsaved_changes(), 'tool': c.draw_state,
                'phase': self.engine.phase, 'step': self.engine.current_step_id,
                'sequence': self.engine.sequence_index, 'pending_operations': len(self.engine._issued),
                'theme': p.theme_name, 'orientation': p.orientation,
                'runtime_root': str(self.host.request.paths.runtime_root)}

    def capture(self, name):
        return self.h.capture(name+'.png', self.canvas)

    def persist(self, *, outcome='running', error=None):
        payload = {'schema': 1, 'chapter': self.host.request.chapter_id, 'pid': os.getpid(),
                   'scope': 'native source UI; isolated chapter; not IPC or parent restoration',
                   'outcome': outcome, 'error': error, 'elapsed_seconds': time.monotonic()-self.started,
                   'capture_method': 'SRCCOPY|CAPTUREBLT', 'steps': self.rows,
                   'inputs': list(self.inputs), 'checks': self.h.checks, 'progress': self.progress}
        temporary = self.output/'report.pending.json'
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        temporary.replace(self.output/'report.json')

    def service_dialogs(self):
        if self.dialog_busy or self.closed: return
        from PyQt6.QtWidgets import QApplication, QMessageBox
        self.dialog_busy = True
        try:
            if self.dialog_handler is not None:
                self.dialog_handler()
            # Export/import notifications are real widgets and real native clicks.
            # Never auto-accept a question or an unexpected failure notification.
            for box in QApplication.topLevelWidgets():
                if not isinstance(box, QMessageBox) or not box.isVisible(): continue
                if box.icon() not in (QMessageBox.Icon.Information, QMessageBox.Icon.Warning): continue
                allowed = self.state.get('notice_allowed', False)
                if not allowed: raise AssertionError(f'unexpected application notice: {box.text()}')
                button = box.button(QMessageBox.StandardButton.Ok)
                if button is None: continue
                self.state.setdefault('notices', []).append({'title': box.windowTitle(), 'text': box.text(),
                    'info': box.informativeText(), 'details': box.detailedText(), 'icon': str(box.icon())})
                self.h.capture(f'notice-{len(self.state["notices"]):03}.png', box)
                self.h.mouse.click(button)
        except Exception as exc:
            self.dialog_error = exc
            self.h.mouse.release_all()
            # Teardown only: dismiss a stuck modal so the outer finally runs.
            modal = QApplication.activeModalWidget()
            if modal is not None: modal.close()
        finally:
            self.dialog_busy = False

    @contextmanager
    def dialog(self, kind, responder, *, required=True):
        from PyQt6.QtWidgets import QApplication
        seen = []
        old = self.dialog_handler
        def poll():
            if seen: return
            dialogs = [w for w in QApplication.topLevelWidgets() if isinstance(w, kind) and w.isVisible()]
            if not dialogs: return
            if len(dialogs) != 1: raise AssertionError(f'ambiguous {kind.__name__}: {len(dialogs)}')
            seen.append(True)
            self.h.capture(f'dialog-{len(self.rows):03}-{kind.__name__}.png', dialogs[0])
            responder(dialogs[0])
        self.dialog_handler = poll
        try:
            yield seen
            if required: self.until(lambda: bool(seen), description=f'native {kind.__name__}')
            if self.dialog_error: raise self.dialog_error
        finally:
            self.dialog_handler = old

    def file_action(self, button, path, *, use_default=False):
        paths = self.host.request.paths
        # A chooser can never type an ordinary user-data or exports destination.
        if not Path(path).resolve().is_relative_to(paths.runtime_root):
            raise ValueError('chooser path outside this private chapter')
        with self.h.mouse.file_chooser(path, use_default=use_default): self.h.mouse.click(button)
        self.pump(150)

    def message_choice(self, choice, *, required=True):
        from PyQt6.QtWidgets import QMessageBox
        return self.dialog(QMessageBox, lambda box: self.h.mouse.click(box.button(choice)), required=required)

    def execute_files(self, chapter, name):
        from PyQt6.QtWidgets import QMessageBox
        from recovery_dialog import RecoveryDialog
        p, c, paths = self.panel, self.canvas, self.host.request.paths
        if name in ('edit', 'make_dirty', 'make_dirty_again'):
            self.stroke(); self.state['edited_document'] = c.serialized_document_pages()
            return
        if name in ('preview', 'restore'):
            before = c.document_signature()
            with self.dialog(RecoveryDialog, lambda d: self.h.mouse.click(
                    d.not_now_button if name == 'preview' else d.restore_button)):
                self.h.mouse.click(p.btn_recovery)
            self.h.require('recovery document effect', (c.document_signature() == before) == (name == 'preview'))
            return
        if name in ('save', 'save_first', 'save_again', 'save_as', 'save_restored'):
            filename = {'save': '1.msd', 'save_first': 'c08-first.msd', 'save_again': 'c08-first.msd',
                        'save_as': 'c08-copy.msd', 'save_restored': 'c08-restored.msd'}[name]
            destination = paths.data_dir/filename
            if name == 'save_again': self.h.mouse.click(p.btn_save_project)
            else: self.file_action(p.btn_save_project_as if name == 'save_as' else p.btn_save_project, destination)
            self.h.require('saved private project file', destination.is_file() and destination.stat().st_size > 0)
            self.state['last_project'] = destination
            return
        if name in ('open', 'reopen'):
            destination = self.state.get('last_project', paths.data_dir/'1.msd')
            with self.message_choice(QMessageBox.StandardButton.Discard, required=False):
                # Prompt is optional for a clean saved document.
                self.file_action(p.btn_open_project, destination)
            return
        if name in ('cancel_open', 'discard_open', 'save_then_open'):
            destination = Path(p._teaching_file_open_path)
            choice = {'cancel_open': QMessageBox.StandardButton.Cancel,
                      'discard_open': QMessageBox.StandardButton.Discard,
                      'save_then_open': QMessageBox.StandardButton.Save}[name]
            before = c.document_signature()
            expected_pages = c.serialized_document_pages()
            self.h.require('chapter sample exists', destination.is_file())
            with self.message_choice(choice): self.file_action(p.btn_open_project, destination, use_default=True)
            if name == 'save_then_open':
                from persistence import normalize_project_data, PROJECT_KIND, read_json_maybe_gz
                saved = normalize_project_data(read_json_maybe_gz(str(destination)), kind=PROJECT_KIND)
                self.h.require('saved and reopened page content',
                               c.serialized_document_pages() == expected_pages == saved['pages'])
                self.h.require('reopened saved project is clean',
                               Path(p.project_path).resolve() == destination.resolve() and not p.has_unsaved_changes())
            else:
                self.h.require('unsaved guard result',
                               (c.document_signature() == before) == (name == 'cancel_open'))
            return
        if chapter == 'c08.interval':
            ui = p.document_preferences
            if name == 'custom_75': self.h.number(ui.interval_custom, 75)
            else: self.h.combo(ui.interval_combo, {'custom': -1, 'preset_60': 60, 'preset_30': 30}[name])
            return
        if name == 'png': self.execute_export(chapter, name); return
        raise ValueError(f'unimplemented file step: {chapter}/{name}')

    def execute_text(self, chapter, name):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtWidgets import QColorDialog, QDialogButtonBox, QLineEdit
        c, p = self.canvas, self.panel
        if name in ('choose_text', 'choose_select', 'backspace', 'newline', 'finish', 'finish_again',
                    'copy', 'delete_copy', 'structure', 'greek', 'operator', 'relation', 'calculus'):
            self.click_target(); return
        if chapter == 'c07.edit':
            if name == 'create_box':
                points = self.free_document_path([(300,240), (560,380)])
                self.drag_canvas(QPointF(*points[0]), QPointF(*points[1]))
                self.state['edit_id'] = str(c.editing_text_id)
            elif name == 'type_text': self.text_input('AB')
            elif name == 'insert_middle':
                item = c.editing_text_item(); rect = c.text_local_rect(item)
                metrics = c.text_metrics(c.text_font(item))
                point = c.text_transform(item).map(QPointF(rect.left()+c.TEXT_PAD+metrics.horizontalAdvance('A'),
                                                         rect.top()+c.TEXT_PAD+metrics.lineSpacing()/2))
                self.click_canvas(point)
                self.h.require('native middle caret', c.caret_offset == 1, c.caret_offset)
                # Canvas click refocuses the production input; don't click the
                # editor here (that would move the caret we are testing).
                self.h.mouse.text('C'); self.pump(80)
            elif name == 'reedit':
                if self.engine.sequence_index == 0:
                    item = next(t for t in c.text_items if str(t['id']) == self.state['edit_id'])
                    self.click_canvas(item['pos']+QPointF(8,20))
                else: self.text_input('C')
            else: raise ValueError(f'unimplemented text edit: {name}')
            return
        if chapter == 'c07.format':
            if name == 'select_box': self.click_canvas(c.text_items[0]['pos']+QPointF(8,20))
            elif name == 'size': self.h.slider(p.select_width_slider, 6)
            elif name == 'color':
                def choose(d):
                    edit = next((w for w in d.findChildren(QLineEdit) if w.objectName() == 'qt_colorname_lineedit'), None)
                    if edit is None: raise RuntimeError('QColorDialog HTML field not found')
                    self.h.mouse.click(edit); self.h.mouse.chord(0x11,0x41); self.h.mouse.text('#aa2255')
                    box = d.findChild(QDialogButtonBox)
                    self.h.mouse.click(box.button(QDialogButtonBox.StandardButton.Ok))
                with self.dialog(QColorDialog, choose): self.click_target()
            elif name in ('move', 'scale', 'rotate'): self.transform(name)
            else: raise ValueError(f'unimplemented text format: {name}')
            return
        if name in ('open_symbols', 'open_formula'):
            item = next(t for t in c.text_items if t.get('text') == ('Symbols: ' if name == 'open_symbols' else 'F = '))
            self.click_canvas(item['pos']+QPointF(8,20)); return
        if name in ('frac', 'sup', 'sub', 'sqrt', 'sqrt_frac', 'sum', 'integral'):
            self.click_target(); self.state['formula_prefix'] = tuple(c.editing_slot[:-1]); return
        if name == 'frac_edit':
            self.h.mouse.chord(0x24); self.h.mouse.chord(0x27); self.h.mouse.text('Z'); self.pump(80); return
        if name.startswith('root_after_'):
            stage = self.engine.sequence_index
            if stage == 0:
                self.formula_slot(())
            elif stage == 1:
                self.formula_slot((), at_end=True)
                self.h.require('native root-end caret', c.caret_offset == c.caret_limit(c.editing_text_item()))
            else:
                self.h.mouse.text('+'); self.pump(80)
            return
        slot = name.rsplit('_',1)[-1]
        if slot not in ('num','den','base','exp','sub','lo','hi','arg'):
            raise ValueError(f'unimplemented formula step: {name}')
        path = self.state['formula_prefix']+(slot,)
        if tuple(c.editing_slot or ()) != path: self.formula_slot(path)
        self.h.mouse.text('xy' if name == 'frac_den' else 'x'); self.pump(80)

    def formula_slot(self, path, *, at_end=False):
        from PyQt6.QtCore import QPointF
        import formula
        c = self.canvas; item = c.editing_text_item(); box = c.formula_box(item); rect = c.text_local_rect(item)
        if path:
            _, x, y, w, h = next(row for row in formula.slot_rects(box) if row[0] == path)
            x += w/2; y += h/2
        else:
            # Just beyond the final atom, inside the text box's padding: don't
            # accidentally enter the last structure's nested field.
            x, y = (box.w+2 if at_end else 2), -box.ascent/2
        point = c.text_transform(item).map(QPointF(rect.left()+c.TEXT_PAD+x, rect.top()+c.TEXT_PAD+box.ascent+y))
        self.click_canvas(point)
        self.h.require('native formula slot', tuple(c.editing_slot or ()) == path, path)

    def execute_media(self, chapter, name):
        p, c = self.panel, self.canvas
        if name in ('import_image','import_pdf'):
            self.state['notice_allowed'] = True
            self.file_action(p.btn_import_media, p._teaching_media_source_path)
            self.h.require('private import loaded', bool(c.image_items))
            self.state['import_page_ids'] = [page['page_id'] for page in c.pages]
        elif name == 'resize_image':
            before = c.image_items[0]['size']; before = (before.width(), before.height())
            self.transform('scale')
            after = c.image_items[0]['size']
            self.h.require('native image size changed', before != (after.width(), after.height()))
        elif name == 'annotate': self.stroke()
        else: self.click_target()
        if name == 'previous_page':
            self.h.require('PDF page ink remains isolated', not c.all_segments and bool(c.pages[2]['segments']) and not c.pages[0]['segments'])

    def execute_export(self, chapter, name):
        from PyQt6.QtWidgets import QApplication, QProgressDialog, QProgressBar, QPushButton
        before = self.canvas.document_signature()
        self.state['notice_allowed'] = True
        cancelled = []
        def cancel():
            if cancelled: return
            for dialog in QApplication.topLevelWidgets():
                if not isinstance(dialog, QProgressDialog) or not dialog.isVisible(): continue
                progress = dialog.findChild(QProgressBar)
                if progress is None or progress.value() < 1: continue
                button = dialog.findChild(QPushButton)
                if button is None: raise AssertionError('export cancellation has no button')
                cancelled.append(True)
                self.h.capture('export-before-native-cancel.png', dialog)
                self.h.mouse.click(button)
                self.h.require('native cancellation registered', dialog.wasCanceled())
        previous = self.dialog_handler
        self.dialog_handler = cancel if name == 'cancel_png' else None
        try: self.click_target()
        finally: self.dialog_handler = previous
        self.h.require('export preserved document', self.canvas.document_signature() == before)
        if name == 'cancel_png': self.h.require('cancelled via visible progress button', bool(cancelled))
        self.verify_exports(chapter, name)

    def verify_exports(self, chapter, name):
        from PyQt6.QtGui import QImageReader
        from PyQt6.QtPdf import QPdfDocument
        from PyQt6.QtSvg import QSvgRenderer
        directory = self.host.request.paths.export_dir
        fmt = name if chapter == 'c10.formats' else 'png'
        prefix = 'c10_'+chapter.split('.')[1] if chapter.startswith('c10.') else 'Export_'
        files = sorted(p for p in directory.glob(prefix+'*.'+fmt) if p.is_file())
        self.h.require('private export output exists', bool(files), files)
        expected = 1 if fmt == 'pdf' or name == 'cancel_png' else 2 if name == 'partial_png' else 3
        if chapter.startswith('c10.'):
            self.h.require('export page/file count', len(files) == expected, (len(files), expected))
        for file in files:
            self.h.require('export stays private', file.resolve().is_relative_to(directory.resolve()))
            if fmt == 'png': valid = QImageReader(str(file)).canRead()
            elif fmt == 'svg': valid = QSvgRenderer(str(file)).isValid()
            elif fmt == 'eps': valid = file.read_bytes().startswith(b'%!PS-Adobe')
            else:
                document = QPdfDocument(None)
                try: valid = document.load(str(file)) == QPdfDocument.Error.None_ and document.pageCount() == 3
                finally: document.close()
            self.h.require('export decodes: '+file.name, valid)
        self.h.require('export temporary files cleaned', not list(directory.glob('.msd-export-*')))

    def execute_measure(self, chapter, name):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtWidgets import QPushButton
        c, p = self.canvas, self.panel
        if chapter == 'c11.calibration' and name == 'calibrate':
            def apply(d):
                button = next(b for b in d.findChildren(QPushButton) if b.text() == self.host.module.tr('calibration_apply'))
                self.h.mouse.click(button)
            with self.dialog(self.host.module.RulerCalibrationDialog, apply): self.click_target()
            self.h.require('calibration saved privately', bool(c.ruler_calibrations) and self.host.request.paths.config_file.is_file())
        elif name.startswith(('move_', 'rotate_', 'scale_', 'width_')):
            aid = c.aids[-1]; mode = name.split('_',1)[0]
            if mode == 'move': start, end = aid['pos'], aid['pos']+QPointF(70,60)
            else:
                local = (c._aid_width_handle_local(aid) if mode == 'width' else
                         c._aid_rotate_handle_local(aid) if mode == 'rotate' else c._aid_scale_handle_local(aid))
                start = c.aid_transform(aid).map(local); delta = start-aid['pos']
                end = aid['pos']+(QPointF(-delta.y(),delta.x()) if mode == 'rotate' else delta*1.2)
                if mode == 'width': end = start+QPointF(0,20)
            self.drag_canvas(start,end)
        else: self.click_target()

    def execute_toolbox(self, chapter, name):
        if chapter == 'c12.timer' and name == 'pause_up':
            self.until(lambda: self.panel.timer_left > 0, description='real count-up tick')
        if chapter == 'c12.magnifier' and name == 'size': self.h.slider(self.panel.mag_size_slider,320)
        elif chapter == 'c12.magnifier' and name == 'move':
            for x, y in ((220, 210), (260, 225)):
                point = self.point(x, y)
                self.h.mouse.hit(self.canvas, point)
                self.h.mouse.move(point)
                self.pump(80)
        elif chapter == 'c12.spotlight' and name == 'move':
            point = self.point(210,160); self.h.mouse.hit(self.canvas,point); self.h.mouse.move(point)
        else: self.click_target()
        if chapter == 'c12.calculator' and name == 'equals':
            self.h.require('calculator native 2+3', self.panel._calc_display.text() == '5')
        if chapter == 'c12.magnifier' and name == 'open':
            self.h.require('magnifier never captures desktop', self.panel._teaching_magnifier_source == 'private_canvas'
                           and self.canvas.magnifier_pixmap is not None and not self.canvas.magnifier_pixmap.isNull())
        if chapter == 'c12.roster':
            self.h.require('roster uses only fictional private names', set(self.panel.roster) == set(self.panel._teaching_fictional_roster))

    def execute_interface(self, chapter, name):
        if name == 'pause_resume': self.execute_session(name); return
        target = self.target()
        if name in ('graphite','slate','warm','classic'):
            self.h.combo(target, {'graphite':'graphite_teal','slate':'slate_blue','warm':'warm_indigo','classic':'classic'}[name])
        elif name == 'select_monitor':
            values = [target.itemData(i) for i in range(target.count())]
            choice = next(value for value in values if value and value != target.currentData())
            self.h.combo(target,choice)
        elif name in ('opacity','volume'): self.h.slider(target,65 if name == 'opacity' else 40)
        else: self.click_target()
        self.h.require('interface configuration remains private', self.host.request.paths.config_file.is_file())

    def execute_session(self, name):
        from PyQt6.QtWidgets import QDialogButtonBox
        if name in ('pause','pause_resume'):
            self.h.mouse.click(self.host.presenter.controller.pause_button)
            self.until(lambda: self.engine.phase == 'paused', description='native pause')
            self.h.mouse.click(self.host.presenter.controller.pause_button)
        else:
            self.click_target()
            self.until(lambda: self.host.center is not None and self.host.center.isVisible(), description='native center open')
            center = self.host.center
            self.h.capture('teaching-center.png',center)
            # Native Escape closes a QDialog; no center.close() or direct signal.
            self.h.mouse.focus_window(center)
            self.h.mouse.chord(0x1B)
            self.pump(100)

    def execute_geometry(self, chapter, name):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtWidgets import QMenu, QApplication
        if name.startswith('draw_'):
            kind = name.removeprefix('draw_')
            points = {'line':((100,160),(360,160)), 'dashed_line':((100,160),(360,160)),
                'triangle':((100,160),(360,160),(240,340)), 'rect':((100,160),(360,340)),
                'parallelogram':((100,160),(300,160),(360,340)),
                'trapezoid':((100,340),(360,340),(320,160),(140,160)),
                'diamond':((100,250),(360,250),(240,340)), 'angle':((240,240),(100,240),(240,360)),
                'circle':((240,240),(340,240)), 'ellipse':((100,160),(360,340))}.get(kind)
            if points:
                for point in points: self.click_canvas(*point)
            else: self.drag_canvas(QPointF(100,160),QPointF(360,340))
        elif name == 'recognize_line':
            started = time.monotonic()
            self.stroke([(x,460+(x%3)) for x in range(100,365,12)],hold_ms=1000)
            self.h.require('recognition used actual dwell', time.monotonic()-started >= self.canvas.SMART_HOLD_MS/1000)
        elif name in ('point1','point2','restart1','restart2','finish3'):
            self.click_canvas(*{'point1':(120,160),'restart1':(120,160),'point2':(360,160),
                                'restart2':(360,160),'finish3':(240,340)}[name])
        elif name == 'snap_line':
            # Snap near the designated source endpoint; being near a different
            # line endpoint must not satisfy the lesson's specific identity.
            clause = self.engine.current_step.wait.clauses[0]
            target_id = clause.equals.get('snap_target_id')
            shape = next(s for s in self.canvas.shape_items if str(s['id']) == target_id)
            endpoint = shape['points'][clause.equals['snap_target_endpoint']]
            self.click_canvas(240,340)
            self.click_canvas(endpoint.x()+3,endpoint.y()-3)
        elif name in ('midpoint','perp_bisector'):
            shape = self.canvas.single_flat_shape(); label = dict(self.canvas.shape_op_list(shape))[name]
            def pick(menu):
                action = next(a for a in menu.actions() if a.text() == label)
                point = menu.mapToGlobal(menu.actionGeometry(action).center())
                self.h.mouse.hit(menu,point); self.h.mouse.click_point(point)
            with self.dialog(QMenu,pick): self.click_target()
        else: self.click_target()

    def execute_pages(self, chapter, name):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QInputDialog, QLineEdit, QDialogButtonBox, QMessageBox
        p, c = self.panel,self.canvas
        if chapter == 'c05.roam':
            from PyQt6.QtCore import QPointF
            def content_history():
                return ([{key:value for key,value in page.items() if key != 'view'}
                         for page in c.serialized_document_pages()],len(c.undo_stack),len(c.redo_stack))
            before = content_history()
            if name == 'pan': self.drag_canvas(QPointF(430,310),QPointF(510,365))
            elif name in ('zoom_in','zoom_out'):
                self.h.mouse.wheel(c,1 if name == 'zoom_in' else -1)
            elif name == 'ink': self.stroke()
            else: self.click_target()
            if name != 'ink':
                self.h.require('roaming preserves document/history',
                    content_history() == before)
            return
        if name == 'rename':
            def rename(dialog):
                editor = dialog.findChild(QLineEdit)
                self.h.mouse.click(editor); self.h.mouse.chord(0x11,0x41); self.h.mouse.text('Practice')
                self.h.mouse.click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok))
            with self.dialog(QInputDialog,rename): self.click_target()
        elif name in ('cancel_delete','delete'):
            choice = QMessageBox.StandardButton.Cancel if name == 'cancel_delete' else QMessageBox.StandardButton.Yes
            with self.message_choice(choice): self.click_target()
        elif name in ('before','after','first','last'): self.h.combo(self.target(),name)
        elif name == 'select_last':
            listing = p.thumbnail_list
            for _ in range(20):
                rect = listing.visualItemRect(listing.item(listing.count()-1))
                if listing.viewport().rect().contains(rect.center()): break
                self.h.mouse.wheel(listing.viewport(),-2)
            else: raise RuntimeError('native wheel failed to show last thumbnail')
            point = listing.viewport().mapToGlobal(rect.center()); self.h.mouse.hit(listing.viewport(),point)
            self.h.mouse.click_point(point)
            self.state['reorder_id'] = c.pages[-1]['page_id']
        elif name == 'reorder':
            listing = p.thumbnail_list
            viewport = listing.viewport()
            # A multi-column viewport's midpoint can be a gap (drop-to-end),
            # never assume it denotes the first page. Reveal actual item rects.
            for _ in range(20):
                source_rect = listing.visualItemRect(listing.currentItem())
                first_rect = listing.visualItemRect(listing.item(0))
                destination = first_rect.topLeft()+QPoint(5,5)
                if viewport.rect().contains(source_rect.center()) and viewport.rect().contains(destination): break
                if not viewport.rect().contains(destination): self.h.mouse.wheel(viewport,2)
                else: self.h.mouse.wheel(viewport,-2)
            else: raise RuntimeError('first and selected thumbnail cannot both be reached in the native viewport')
            source = viewport.mapToGlobal(source_rect.center())
            dest = viewport.mapToGlobal(destination)
            self.h.mouse.hit(viewport,source); self.h.mouse.hit(viewport,dest)
            self.h.mouse.drag(source,dest,hold_ms=500)
            self.h.require('native OLE moved last page to first', c.pages[0]['page_id'] == self.state['reorder_id'])
        else: self.click_target()

    def execute_selection(self, chapter, name):
        from PyQt6.QtCore import QPointF
        if name in ('move','scale','rotate'): self.transform(name)
        elif name in ('select','choose'):
            segment = self.canvas.all_segments[0]
            self.click_canvas(segment['line'].p1())
        elif name == 'box': self.drag_canvas(QPointF(90,100),QPointF(460,450))
        else: self.click_target()

    def execute_canvas(self, chapter, name):
        # Sequence targets can be controls before the canvas gesture.
        if self.host.presenter.active_target_id != 'canvas.ink': self.click_target(); return
        if name in ('choose','select'):
            self.click_canvas(self.canvas.all_segments[0]['line'].p1())
        elif name == 'move': self.transform('move')
        elif name in ('erase','circle_erase','stroke_erase'):
            segments = self.canvas.all_segments
            if not segments: raise AssertionError('eraser fixture contains no ink')
            # Choose the intended row, retaining other stroke IDs for stroke mode.
            expected_id = self.engine.current_step.wait.clauses[self.engine.sequence_index].equals.get('stroke_id')
            candidates = [s for s in segments if expected_id is None or str(s['id']) == expected_id]
            if not candidates: raise AssertionError('designated eraser stroke is missing')
            segment = min(candidates,key=lambda s: abs(s['line'].y1()-(390 if name == 'stroke_erase' else 150)))
            line = segment['line']; a,b = line.p1(),line.p2()
            if a == b: raise RuntimeError('zero length eraser fixture segment')
            self.drag_canvas(a,b)
        else: self.stroke(hold_ms=850 if name == 'stroke' and self.canvas.smart_shapes_enabled else 0)

    def execute(self):
        step = self.engine.current_step; chapter,name = self.engine.chapter_id,step.id
        raw = {'id':name,'kind':step.kind,'target':step.target}
        action = classify(chapter,raw)
        if action == 'next': self.h.mouse.click(self.host.presenter.controller.next_button)
        elif action == 'text': self.execute_text(chapter,name)
        elif action == 'files': self.execute_files(chapter,name)
        elif action == 'media': self.execute_media(chapter,name)
        elif action == 'export': self.execute_export(chapter,name)
        elif action == 'measure': self.execute_measure(chapter,name)
        elif action == 'toolbox': self.execute_toolbox(chapter,name)
        elif action == 'interface': self.execute_interface(chapter,name)
        elif action == 'session': self.execute_session(name)
        elif action == 'geometry': self.execute_geometry(chapter,name)
        elif action == 'pages': self.execute_pages(chapter,name)
        elif action == 'selection': self.execute_selection(chapter,name)
        elif action == 'canvas': self.execute_canvas(chapter,name)
        elif action == 'palette':
            from PyQt6.QtGui import QColor
            button = next(b for b in self.panel.color_buttons if b.property('color_val')
                          and QColor(b.property('color_val')) != self.canvas.pen_color)
            self.h.mouse.click(button)
        elif action == 'slider':
            target = self.host.presenter.active_target_id
            widget = self.panel.pen_slider if target == 'pen.width' else self.target()
            self.h.slider(widget,60 if target == 'eraser.size' else 12,exact=target == 'eraser.size')
        else: self.click_target()

    def run(self):
        self.pump(800)
        while self.engine.phase in ('running','paused'):
            self.h.mouse.deadline = time.monotonic()+self.timeout
            self.until(lambda: not self.host.presenter._missing,description='lesson target available')
            current = self.current()
            step = self.engine.current_step
            row = {'step':step.id,'sequence':self.engine.sequence_index,'kind':step.kind,
                   'target':self.host.presenter.active_target_id,'outcome':'running',
                   'before':self.snapshot(),'input_start':len(self.inputs)}
            self.rows.append(row)
            started = time.monotonic()
            self.persist()
            try:
                row['before_capture'] = self.capture(f'{len(self.rows):03}-{step.id}-before')
                self.execute()
                self.until(lambda: self.current() != current,timeout=self.timeout,description='native step advance')
                self.pump(220)
                self.h.require('no retry/skip/error completion', self.engine.phase not in ('error','skipped','stopped'), self.current())
                row['after'] = self.snapshot()
                row['after_capture'] = self.capture(f'{len(self.rows):03}-{step.id}-after')
                row['outcome'] = 'passed'
            except Exception:
                row['outcome']='failed'; row['error']=traceback.format_exc()
                try: row['failure_capture']=self.capture(f'{len(self.rows):03}-{step.id}-FAILED')
                except Exception as exc: row['capture_error']=repr(exc)
                raise
            finally:
                row['elapsed_seconds']=time.monotonic()-started
                row['input_end']=len(self.inputs)
                self.persist()
        self.h.require('chapter genuinely completed', self.engine.phase == 'completed',self.engine.phase)
        self.h.require('completion callback observed', any(x[1] == 'completed' for x in self.progress))
        self.persist(outcome='passed')


def install_qt_input_observer(driver):
    """Read-only diagnostic setup; never consumes, synthesizes or forwards input."""
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtWidgets import QApplication
    class Observer(QObject):
        def eventFilter(self, receiver, event):
            if driver.closed or event.type() not in (QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
                return False
            try:
                target_id = driver.host.presenter.active_target_id
                target = driver.host.registry.resolve(target_id) if target_id else None
                focus = QApplication.focusWidget()
                def describe(widget):
                    if widget is None: return None
                    text = getattr(widget, 'text', None)
                    return {'class': type(widget).__name__, 'object_name': widget.objectName(),
                            'text': text() if callable(text) else None,
                            'teaching_symbol': widget.property('teaching_symbol')}
                driver.inputs.append({'kind': 'qt_mouse_observed', 'time': time.monotonic(),
                    'event': event.type().name, 'receiver': describe(receiver),
                    'is_current_target': receiver is target, 'target': target_id,
                    'local': [event.position().x(), event.position().y()],
                    'global': [event.globalPosition().x(), event.globalPosition().y()],
                    'focus': describe(focus), 'editing_text_id': driver.canvas.editing_text_id,
                    'step': driver.engine.current_step_id, 'sequence': driver.engine.sequence_index})
            except Exception as exc:
                driver.inputs.append({'kind': 'qt_mouse_observer_error', 'error': repr(exc)})
            return False
    observer = Observer(QApplication.instance())
    QApplication.instance().installEventFilter(observer)
    return observer


def owned_key_target(user, child_pid, entry):
    """A key UP goes only to the still-live original owned foreground root."""
    if not isinstance(entry, dict): return False
    hwnd, root = entry.get('hwnd'), entry.get('root')
    if type(hwnd) is not int or type(root) is not int or not hwnd or not root: return False
    def owned(handle):
        pid = wintypes.DWORD()
        if not handle: return False
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        return pid.value == child_pid
    foreground = user.GetForegroundWindow()
    return (owned(hwnd) and owned(root) and user.GetAncestor(hwnd, 2) == root
            and owned(foreground) and user.GetAncestor(foreground, 2) == root)


class InputJournal:
    """Setup adapter: durable DOWN-before-send / UP-after-send, without Qt.

    NativeInput's key audit happens AFTER DOWN and records the cursor HWND,
    not keyboard focus. Wrap only its Win32 keyboard endpoint to close that
    gap, keeping lesson actions and the input helper itself unchanged.
    """
    def __init__(self, mouse, output, inputs):
        self.user, self.output, self.inputs = mouse.user32, output, inputs
        self.lock = threading.RLock()
        self.state = {'pid': os.getpid(), 'left_down': False, 'keys_down': {}, 'sequence': 0}
        write_json(self.output/'input-state.json', self.state)

    def save(self):
        self.state['sequence'] += 1
        write_json(self.output/'input-state.json', self.state)

    def audit(self, row):
        with self.lock:
            self.inputs.append(row)
            if row['kind'] in ('left_down', 'left_up'):
                self.state['left_down'] = row['kind'] == 'left_down'
                if self.state['left_down']:
                    self.state.update(press=list(row['physical']), hwnd=row['hwnd'])
                self.save()

    def keybd_event(self, key, scan, flags, extra):
        with self.lock:
            identifier = str(key)
            if flags == 0:
                hwnd = self.user.GetForegroundWindow()
                entry = {'hwnd': int(hwnd or 0), 'root': int(self.user.GetAncestor(hwnd, 2) or 0)}
                if not owned_key_target(self.user, self.state['pid'], entry):
                    raise RuntimeError('refusing key DOWN without an owned foreground')
                self.state['keys_down'][identifier] = entry
                self.save()  # Conservative even if the following native call fails.
            elif flags == 2:
                # Enter can close a native dialog before its ordinary UP. That
                # paired UP may follow focus to another live window of THIS
                # child, but never a foreign foreground or an untracked key.
                # Hard-timeout cleanup below still requires the original root.
                hwnd = self.user.GetForegroundWindow()
                entry = {'hwnd': int(hwnd or 0), 'root': int(self.user.GetAncestor(hwnd, 2) or 0)}
                if identifier not in self.state['keys_down'] or not owned_key_target(self.user, self.state['pid'], entry):
                    raise RuntimeError('refusing untracked/foreign key UP; residual input possible')
            else:
                raise RuntimeError('unexpected native keyboard flags in teaching driver')
            self.user.keybd_event(key, scan, flags, extra)
            if flags == 2:
                del self.state['keys_down'][identifier]
                self.save()


def install_input_journal(mouse, output, inputs):
    journal = InputJournal(mouse, output, inputs)
    class KeyboardJournalAPI:
        def __getattr__(self, name): return getattr(journal.user, name)
        def keybd_event(self, *args): return journal.keybd_event(*args)
    mouse.user32 = KeyboardJournalAPI()
    mouse.audit = journal.audit
    return journal


def release_owned_keys(user, child_pid, state):
    """No activation, new DOWN or blanket modifier UP, including on timeout."""
    if (not isinstance(state, dict) or state.get('pid') != child_pid
            or not isinstance(state.get('keys_down'), dict)):
        return {'confirmed': False, 'released': False, 'reason': 'missing/foreign keyboard journal'}
    results = []
    for identifier, entry in reversed(list(state['keys_down'].items())):
        row = {'key': identifier, 'confirmed': False, 'released': False}
        results.append(row)
        if not isinstance(identifier, str) or not identifier.isascii() or not identifier.isdecimal() or not 8 <= int(identifier) <= 254:
            row['reason'] = 'invalid tracked virtual key'; continue
        key = int(identifier)
        if not user.GetAsyncKeyState(key)&0x8000:
            row.update(confirmed=True, reason='tracked key already physically released'); continue
        if not owned_key_target(user, child_pid, entry):
            row['reason'] = 'original keyboard HWND/root is gone or foreground changed; refused foreign UP'; continue
        user.keybd_event(key, 0, 2, 0)
        end = time.monotonic()+.2
        while user.GetAsyncKeyState(key)&0x8000 and time.monotonic() < end: time.sleep(.005)
        row.update(confirmed=not bool(user.GetAsyncKeyState(key)&0x8000), released=True,
                   reason='owned tracked key UP; physical state checked')
    return {'confirmed': all(row['confirmed'] for row in results),
            'released': any(row['released'] for row in results), 'keys': results,
            'reason': 'tracked keyboard cleanup' if results else 'no tracked keyboard DOWN'}


def release_owned_inputs(user, child_pid, state):
    results = {}
    for name, release in (('mouse', release_owned_mouse), ('keyboard', release_owned_keys)):
        try: results[name] = release(user, child_pid, state)
        except Exception as exc:
            results[name] = {'confirmed': False, 'released': False, 'reason': str(exc)}
    return {'confirmed': all(row['confirmed'] for row in results.values()),
            'released': any(row['released'] for row in results.values()), **results}


def terminate_owned_child(user, child, output):
    """Try tracked cleanup BEFORE killing only our child, even on cleanup error."""
    try:
        if child.poll() is not None:
            return exited_input_cleanup(child.pid, output)
        try: state = json.loads((output/'input-state.json').read_text(encoding='utf-8'))
        except (ValueError, OSError): state = None
        cleanup = release_owned_inputs(user, child.pid, state)
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=10)
    write_json(output.parent/(output.name+'.cleanup.json'), cleanup)
    return cleanup


def exited_input_cleanup(child_pid, output):
    # No native input after process exit: the former HWND might already be reused.
    try:
        state = json.loads((output/'input-state.json').read_text(encoding='utf-8'))
        confirmed = (isinstance(state, dict) and state.get('pid') == child_pid
                     and state.get('left_down') is False and state.get('keys_down') == {})
        return {'confirmed': confirmed, 'released': False, 'reason': 'child exit journal; no post-exit input'}
    except (ValueError, OSError) as exc:
        return {'confirmed': False, 'released': False, 'reason': f'missing exit journal: {exc}'}


def restore_worker_inputs(mouse, journal):
    try: mouse.restore()
    except Exception as exc: mouse.errors.append(f'input restore failed: {exc}')
    residual = journal is not None and (journal.state['left_down'] or journal.state['keys_down'])
    return not (mouse.errors or mouse.down or mouse.keys_down or residual
                or any(worker.is_alive() for worker in mouse.workers))


def local_host_bridge(host):
    """Initial app composition only. Native buttons invoke the real host routes.

    A standalone per-chapter driver has no ordinary parent or user-progress file.
    This is explicitly not evidence about authenticated IPC or parent restore.
    """
    def toggle_pause():
        if host.presenter.engine.phase == 'paused': host.resume()
        else: host.pause()
    def open_center():
        view = {'records':{chapter.id:host.view.chapter_record(chapter.id)
                           for course in host.catalog.courses for chapter in course.chapters},
                'last_started':None,'read_only':True,'context_hints_enabled':False}
        host.accept_center(view)
    host.pause_requested.connect(toggle_pause)
    host.center_requested.connect(open_center)
    host.center_closed.connect(lambda: host.finish_center(resume=True))


def worker(args):
    """Private child. Called only by the real-run supervisor, never by self-check."""
    worker_started = time.monotonic()
    if sys.platform != 'win32': raise RuntimeError('Windows native UI required')
    if os.environ.get('QT_QPA_PLATFORM') not in (None,'windows'):
        raise RuntimeError('refusing real run on a non-Windows/offscreen QPA backend')
    parent_temp = os.environ.get('MYSCREENDRAW_NATIVE_PARENT_TEMP')
    if not parent_temp or not Path(parent_temp).is_dir():
        raise RuntimeError('worker must be started by this driver supervisor')
    os.environ['MYSCREENDRAW_NO_KEYBOARD']='1'
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    from runtime_paths import RuntimePaths
    from teaching.bootstrap import PracticeRequest, practice_arguments
    chapter=args.chapter[0]
    result=1; host=driver=h=None
    with tempfile.TemporaryDirectory(prefix='msd-native-620-', dir=parent_temp) as temporary:
        paths=RuntimePaths.create_practice(ROOT,ROOT,temp_root=Path(temporary))
        channel='myscreendraw-teaching-'+paths.session_id
        request=PracticeRequest(paths,channel,chapter.split('.')[0],chapter)
        os.environ['MYSCREENDRAW_PRACTICE_NONCE']=paths.nonce
        os.environ['MYSCREENDRAW_PRACTICE_TEMP_ROOT']=str(paths.temp_root)
        # Bind before importing main, logging, helpers, or constructing any UI.
        sys.argv=[str(ROOT/'main.py'),*practice_arguments(paths,channel,request.course_id,chapter)]
        import main
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QWidget
        from teaching.application import ApplicationTeachingHost
        from native_input_620 import NativeHarness
        app=QApplication(sys.argv[:1]); app.setQuitOnLastWindowClosed(False)
        if app.platformName() != 'windows': raise RuntimeError('native platform validation failed')
        context=main.RUNTIME_CONTEXT
        assert context.paths==paths and paths.practice and not context.ui_active
        assert not any((context.updates,context.autostart,context.global_keyboard,context.tray,
                        context.usage_tracking,context.ordinary_recovery,context.desktop_capture))
        assert all(Path(getattr(main,name)).is_relative_to(paths.runtime_root) for name in paths.module_aliases())
        # A network operation here is an isolation bug, not something to mock as
        # success. There is no network service in these source/private lessons.
        import socket
        def forbidden_network(*_args,**_kwargs): raise RuntimeError('network disabled in native teaching acceptance')
        socket.socket.connect=forbidden_network
        socket.create_connection=forbidden_network
        main.ensure_directories(); main.setup_logging(); main.install_qt_translations(app)
        backdrop=QWidget(); backdrop.setWindowTitle('Private native tutorial backdrop')
        backdrop.setStyleSheet('background: #db23bd;')
        backdrop.setGeometry(app.primaryScreen().geometry())
        watchdog=QTimer(); watchdog.setSingleShot(True)
        guard = None
        try:
            h=NativeHarness(app,output)
            progress=[]
            host=ApplicationTeachingHost(main,request,on_progress=lambda *event: progress.append(event))
            local_host_bridge(host)
            driver=ChapterDriver(host,h,output,args.step_timeout); driver.progress=progress
            host.failed.connect(lambda detail: setattr(driver,'dialog_error',RuntimeError(str(detail))))
            host.exit_requested.connect(lambda: setattr(driver,'dialog_error',RuntimeError('practice exited early')))
            context.activate()
            backdrop.show()
            host.activate()
            # The app itself performs chapter fixture preparation; no lesson
            # has been credited yet. This is the end of initial setup.
            def run():
                nonlocal result
                try: driver.run(); result=0
                except Exception:
                    detail=traceback.format_exc(); print(detail,file=sys.stderr,flush=True)
                    driver.persist(outcome='failed',error=detail)
                finally:
                    driver.closed=True; driver.dialog_timer.stop()
                    if not restore_worker_inputs(h.mouse, driver.input_journal):
                        result=1; driver.dialog_error=RuntimeError(f'native cleanup incomplete: {h.mouse.errors}')
                    app.quit()
            def cancel():
                driver.dialog_error=TimeoutError('chapter deadline')
                h.mouse.cancelled.set()
            def deadline():
                cancel()
                modal=QApplication.activeModalWidget()
                if modal is not None: modal.close()  # cleanup, never a passed action
                app.quit()
            # OLE/common dialogs can starve Qt timers; native workers must still
            # see cancellation before the supervisor's bounded hard timeout.
            remaining=max(0., args.chapter_timeout-(time.monotonic()-worker_started))
            guard=threading.Timer(remaining,cancel); guard.daemon=True; guard.start()
            watchdog.timeout.connect(deadline); watchdog.start(int(remaining*1000))
            QTimer.singleShot(600,run)
            app.exec()
        finally:
            watchdog.stop()
            if guard is not None: guard.cancel()
            if driver is not None: driver.closed=True; driver.dialog_timer.stop()
            if h is not None and not restore_worker_inputs(h.mouse, driver.input_journal if driver else None):
                result=1
                if driver is not None: driver.dialog_error=RuntimeError(f'native cleanup incomplete: {h.mouse.errors}')
            if host is not None:
                try: host.close()
                except Exception as exc:
                    result=1
                    if driver is not None: driver.dialog_error=RuntimeError(f'host cleanup failed: {exc}')
            backdrop.hide()
            for handler in list(main.LOGGER.handlers):
                handler.flush(); handler.close(); main.LOGGER.removeHandler(handler)
            if driver is not None and result:
                driver.persist(outcome='failed',error=driver.dialog_error or 'chapter did not finish successfully')
    return result


def supervise(args,chapters):
    """One owned child at a time; journaled, target-checked cleanup before kill."""
    if sys.platform != 'win32': raise ValueError('real native acceptance requires Windows')
    if os.environ.get('QT_QPA_PLATFORM') not in (None, 'windows'):
        raise RuntimeError('native acceptance refuses an offscreen/non-Windows backend')
    output=args.output.resolve()
    if '.ccgui' not in output.parts: raise ValueError('--output must be inside a private .ccgui directory')
    if any(output.is_relative_to(ROOT/name) for name in ('data','exports','assets','tests')):
        raise ValueError('ordinary data/exports/source directories are forbidden')
    if output.exists(): raise ValueError('refusing to reuse an output directory')
    user=ctypes.windll.user32
    user.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]; user.GetCursorPos.restype=wintypes.BOOL
    user.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]; user.SetCursorPos.restype=wintypes.BOOL
    user.GetForegroundWindow.restype=wintypes.HWND
    user.keybd_event.argtypes=[wintypes.BYTE,wintypes.BYTE,wintypes.DWORD,ctypes.c_size_t]
    user.GetAsyncKeyState.argtypes=[ctypes.c_int]; user.GetAsyncKeyState.restype=ctypes.c_short
    configure_cleanup_api(user)
    if any(user.GetAsyncKeyState(key)&0x8000 for key in (1,2,4,0x10,0x11,0x12,0x1B)):
        raise RuntimeError('release mouse buttons, modifier keys and Escape before native acceptance')
    start=wintypes.POINT()
    if not user.GetCursorPos(ctypes.byref(start)): raise RuntimeError('could not save physical pointer position')
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    child=None
    try:
        for chapter in chapters:
            command=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--chapter',chapter,
                     '--output',str(output/chapter),'--step-timeout',str(args.step_timeout),
                     '--chapter-timeout',str(args.chapter_timeout)]
            print('NATIVE CHAPTER '+chapter,flush=True)
            error=cleanup=None
            with (output/(chapter+'.stdout.log')).open('w',encoding='utf-8') as stdout, \
                 (output/(chapter+'.stderr.log')).open('w',encoding='utf-8') as stderr:
                with tempfile.TemporaryDirectory(prefix='msd-native-supervised-620-') as scratch:
                    environment=dict(os.environ,MYSCREENDRAW_NATIVE_PARENT_TEMP=scratch)
                    child=subprocess.Popen(command,cwd=str(ROOT),stdout=stdout,stderr=stderr,env=environment)
                    child_pid=child.pid
                    try: code=child.wait(timeout=args.chapter_timeout+20)
                    except subprocess.TimeoutExpired:
                        cleanup=terminate_owned_child(user,child,output/chapter)
                        code=124; error='owned child hard timeout; inspect cleanup confirmation and partial report'
                    finally:
                        if child.poll() is None: cleanup=terminate_owned_child(user,child,output/chapter)
                    child=None
            if cleanup is None: cleanup=exited_input_cleanup(child_pid,output/chapter)
            if not cleanup['confirmed']:
                print('INPUT CLEANUP UNCONFIRMED: '+json.dumps(cleanup),file=sys.stderr,flush=True)
            report=output/chapter/'report.json'
            try: payload=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
            except (ValueError,OSError) as exc: payload={}; error=f'invalid child report: {exc}'
            passed=code==0 and payload.get('outcome')=='passed' and cleanup['confirmed']
            results.append({'chapter':chapter,'passed':passed,'exit_code':code,'error':error,
                            'cleanup':cleanup,'report':str(report),'native_steps':len(payload.get('steps',()))})
            write_json(output/'summary.json',{'results':results,
                'passed':len(results)==len(chapters) and all(r['passed'] for r in results),
                'requested':chapters,'scope':'native chapter UI, not IPC; no OS update/autostart actions'})
            # Stop on obstruction, user intervention OR unconfirmed cleanup.
            if not passed: break
    finally:
        if child is not None and child.poll() is None:
            terminate_owned_child(user,child,output/chapter)
        # Only cursor restoration remains after child exit. Never global UPs.
        if not user.SetCursorPos(start.x,start.y): raise RuntimeError('physical cursor restore failed')
        actual=wintypes.POINT()
        if not user.GetCursorPos(ctypes.byref(actual)) or abs(actual.x-start.x)>3 or abs(actual.y-start.y)>3:
            raise RuntimeError('physical cursor restore readback failed')
    return 0 if len(results)==len(chapters) and all(r['passed'] for r in results) else 1


def calibrate_input_cleanup():
    """Pure fake Win32 + in-memory journal; no native API or application import."""
    from unittest.mock import patch
    from real_features_620 import calibrate_cleanup
    count = calibrate_cleanup()
    class FakeUser:
        def __init__(self, mode='owned', pid=42):
            self.mode, self.pid, self.foreground = mode, pid, 10
            self.down, self.events = {0x11, 0x41, 0x10}, []
            self.before_send = lambda *_: None
        def GetForegroundWindow(self): return self.foreground
        def GetWindowThreadProcessId(self, hwnd, pid):
            pid._obj.value = self.pid if hwnd in (10, 11) and not (hwnd == 10 and self.mode == 'stale') else 99
        def GetAncestor(self, hwnd, _mode): return 11 if self.mode == 'changed_root' else hwnd
        def GetAsyncKeyState(self, key): return 0x8000 if key in self.down else 0
        def keybd_event(self, key, scan, flags, extra):
            self.before_send(key, flags)
            self.events.append((key, flags))
            if flags == 0: self.down.add(key)
            elif self.mode != 'stuck': self.down.discard(key)
    for mode in ('owned','foreign','other_owned_root','stale','changed_root','untracked',
                 'wrong_pid','missing','bad_key','already_up','stuck'):
        user = FakeUser(mode)
        state = {'pid': 42, 'keys_down': {'17': {'hwnd': 10, 'root': 10}}}
        if mode == 'foreign': user.foreground = 20
        if mode == 'other_owned_root': user.foreground = 11
        if mode == 'untracked': state['keys_down'] = {}
        if mode == 'wrong_pid': state['pid'] = 99
        if mode == 'missing': state = None
        if mode == 'bad_key': state['keys_down'] = {'1': {'hwnd': 10, 'root': 10}}
        if mode == 'already_up': user.down.discard(0x11)
        result = release_owned_keys(user, 42, state)
        expected = [(0x11, 2)] if mode in ('owned','stuck') else []
        assert user.events == expected, (mode, result, user.events)
        assert result['confirmed'] == (mode in ('owned','untracked','already_up')), (mode, result)
        assert 0x10 in user.down and 0x41 in user.down, 'untracked physical keys must not be touched'
        count += 1
    user = FakeUser(pid=os.getpid())
    mouse = type('Mouse', (), {'user32': user})()
    snapshots = []
    def save(_path, state): snapshots.append(json.loads(json.dumps(state)))
    with patch.dict(globals(), write_json=save):
        journal = install_input_journal(mouse, Path('unused'), [])
        def before_send(key, flags):
            assert str(key) in snapshots[-1]['keys_down'], 'DOWN must be journaled before native send; UP cleared only afterwards'
        user.before_send = before_send
        mouse.user32.keybd_event(0x11, 0, 0, 0)
        assert snapshots[-1]['keys_down']['17'] == {'hwnd': 10, 'root': 10}
        user.foreground = 20
        try: mouse.user32.keybd_event(0x11, 0, 2, 0)
        except RuntimeError: pass
        else: raise AssertionError('worker must refuse foreign foreground UP')
        assert user.events == [(0x11, 0)] and '17' in snapshots[-1]['keys_down']
        user.foreground = 10
        mouse.user32.keybd_event(0x11, 0, 2, 0)
        assert snapshots[-1]['keys_down'] == {}
        try: mouse.user32.keybd_event(0x10, 0, 2, 0)
        except RuntimeError: pass
        else: raise AssertionError('worker must refuse untracked UP')
        assert user.events == [(0x11, 0), (0x11, 2)]
        # Ordinary paired UP may follow an Enter-closed dialog to another owned
        # root; the timeout path must still refuse this original-window loss.
        mouse.user32.keybd_event(0x0D, 0, 0, 0)
        original_press = json.loads(json.dumps(journal.state))
        user.mode, user.foreground = 'stale', 11
        timeout_result = release_owned_keys(user, os.getpid(), original_press)
        assert not timeout_result['confirmed'] and not timeout_result['released']
        mouse.user32.keybd_event(0x0D, 0, 2, 0)
        assert snapshots[-1]['keys_down'] == {} and user.events[-1] == (0x0D, 2)
        mouse.audit({'kind': 'left_down', 'physical': [100, 200], 'hwnd': 10})
        assert snapshots[-1]['left_down'] is True and snapshots[-1]['press'] == [100, 200]
        mouse.audit({'kind': 'left_up'})
        assert snapshots[-1]['left_down'] is False
        count += 5
    # Simulate a wedged owned child: release must precede kill, a malformed or
    # missing journal must still kill, and an already-exited child receives no UP.
    class FakeChild:
        pid = 42
        def __init__(self, events, exited=False): self.events, self.exited = events, exited
        def poll(self): return 0 if self.exited else None
        def kill(self): self.events.append('kill'); self.exited = True
        def wait(self, timeout): self.events.append('wait'); return 0
    with tempfile.TemporaryDirectory(prefix='msd-cleanup-selfcheck-') as scratch:
        output = Path(scratch)
        for mode in ('tracked','empty','missing','foreign_pid','exited','release_error'):
            events = []
            child = FakeChild(events, exited=mode == 'exited')
            state = {'pid': 99 if mode == 'foreign_pid' else 42, 'left_down': False,
                     'keys_down': {'17': {'hwnd': 10, 'root': 10}} if mode == 'tracked' else {}}
            if mode != 'missing': write_json(output/'input-state.json', state)
            else: (output/'input-state.json').unlink(missing_ok=True)
            user = FakeUser()
            if mode == 'release_error':
                def broken(*_args): raise RuntimeError('fake release failure')
                user.GetAsyncKeyState = broken
                state['keys_down'] = {'17': {'hwnd': 10, 'root': 10}}
                write_json(output/'input-state.json', state)
            user.before_send = lambda *_args: events.append('release')
            with patch.dict(globals(), write_json=lambda *_args: None):
                result = terminate_owned_child(user, child, output)
            assert child.exited
            assert events == (['wait'] if mode == 'exited' else
                              ['release','kill','wait'] if mode == 'tracked' else ['kill','wait']), (mode, events)
            assert result['confirmed'] == (mode in ('tracked','empty','exited')), (mode, result)
            count += 1
    return count


def self_check(rows):
    """Static coverage + negative calibration. Never imports main/Qt or Win32."""
    count=0
    for chapter,record in rows.items():
        for step in record['steps']:
            classify(chapter,step); count+=1
    try: classify('c05.future_unimplemented',{'id':'pan','target':'canvas.ink'})
    except ValueError: pass
    else: raise AssertionError('unknown future chapter must fail closed')
    try: classify('c01.interface',{'id':'unmapped'})
    except ValueError: pass
    else: raise AssertionError('unknown operation must fail closed')
    import ast
    for file in (Path(__file__),Path(__file__).with_name('native_input_620.py')):
        compile(file.read_text(encoding='utf-8'),str(file),'exec')
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    supervisor = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'supervise')
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in ('mouse_event','keybd_event') for node in ast.walk(supervisor)), 'supervisor must never send blanket UPs'
    cleanup_cases = calibrate_input_cleanup()
    assert 'main' not in sys.modules and 'PyQt6.QtWidgets' not in sys.modules
    print(f'STATIC ONLY: {len(rows)} chapters / {count} catalog steps classified; syntax, negative calibration and {cleanup_cases} fake-Win32 cleanup checks passed.')
    print('No native chapter, screenshot, or business acceptance has been run.')
    return 0


def main_():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--chapter',action='append',help='chapter id or course id; repeatable')
    parser.add_argument('--all',action='store_true',help='run all current chapters serially')
    parser.add_argument('--output',type=Path,help='NEW private .ccgui directory')
    parser.add_argument('--list',action='store_true',help='list only, no Qt/Win32')
    parser.add_argument('--plan',action='store_true',help='print action plan only, no Qt/Win32')
    parser.add_argument('--self-check',action='store_true',help='static checks only, no Qt/Win32')
    parser.add_argument('--step-timeout',type=float,default=30)
    parser.add_argument('--chapter-timeout',type=float,default=300)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(); rows=catalog_rows()
    try:
        if args.self_check: return self_check(rows)
        if args.list:
            for chapter,record in rows.items(): print(f'{chapter:24} {len(record["steps"]):3} steps')
            return 0
        if args.all and args.chapter: parser.error('choose --all OR --chapter')
        chapters=selected_chapters(args,rows)
        if not chapters: parser.error('choose --chapter, --all, --list or --self-check')
        for chapter in chapters:
            for step in rows[chapter]['steps']: classify(chapter,step)
        if args.plan:
            for chapter in chapters:
                for step in rows[chapter]['steps']:
                    print(f'{chapter}/{step["id"]}: {classify(chapter,step)} -> {step.get("target","controller.next")}')
            return 0
        if args.output is None: parser.error('real run requires --output')
        if not 5 <= args.step_timeout <= 120 or not 30 <= args.chapter_timeout <= 1800:
            parser.error('step timeout must be 5..120; chapter timeout 30..1800 seconds')
        if args.worker:
            if len(chapters)!=1 or '.ccgui' not in args.output.resolve().parts:
                parser.error('worker requires one private chapter')
            return worker(args)
        return supervise(args,chapters)
    except (ValueError,RuntimeError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    raise SystemExit(main_())
