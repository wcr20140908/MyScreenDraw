# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in 6.2 native feature acceptance. NOT collected by pytest.

SAFE (no app, Qt, Win32, input or screenshots):
  python -B tests/real_features_620.py --list
  python -B tests/real_features_620.py --self-check
  python -B tests/real_features_620.py --all --plan

REAL DESKTOP -- run only when explicitly scheduled, never beside another driver:
  python -B tests/real_features_620.py --case thumbnails --output D:/private/.ccgui/features-thumbs
  python -B tests/real_features_620.py --case boxes --output D:/private/.ccgui/features-boxes
  python -B tests/real_features_620.py --chapter c05.reorder --output D:/private/.ccgui/features-reorder
  python -B tests/real_features_620.py --all --output D:/private/.ccgui/features-620

Every case gets a fresh private source-app process and RuntimePaths. Fixtures and
composition are initial setup only; subsequent actions use guarded Win32 input.
Only geometry/state/pixels are read for assertions. No QTest, Qt synthetic input,
replaced OLE loops, production renderer calls, or business-method lesson credit.
Screenshots are PRIVATE CAPTUREBLT evidence; do not upload/publish them. Physical
Escape aborts; do not use the desktop during a run. Before hard termination the
supervisor releases only a journaled mouse DOWN above a read-back, child-owned
native target; otherwise cleanup is explicitly unconfirmed. It then kills ONLY
our child and restores the cursor, never sends an UP over a foreign application.
The standalone host tests neither packaged startup nor IPC/parent restoration.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
from ctypes import wintypes
import json
import math
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

CASES = {
    'thumbnails': '13 default/renamed pages; pixels, before/after insertion cues, cross-row OLE, edge scroll, double-click, X',
    'boxes': 'native CUBE/CUBOID buttons and four drag directions; 3 hidden/9 solid CAPTUREBLT edge checks',
    'c05.reorder.direct': 'A/B/C -> C/A/B; native chapter completion and current-page identity',
    'c05.reorder.intermediate': 'A/B/C -> A/C/B (stays) -> C/A/B (advances)',
    'c05.reorder.wrong': 'A/B/C -> B/A/C -> C/B/A; wrong remaining order must stay at reorder',
}
EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6),
         (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))
HIDDEN = frozenset(((6, 7), (7, 4), (3, 7)))


def box_vertices(kind, rect):
    """Independent oracle: no production box_faces/bounds/rendering calls."""
    x, y, w, h = rect
    if kind not in ('CUBE', 'CUBOID') or w <= 0 or h <= 0:
        raise ValueError('invalid box oracle input')
    d = min(w, h) * (.18 if kind == 'CUBE' else .20)
    if kind == 'CUBE':
        front = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
        back = [(px+d, py-d) for px, py in front]
    else:
        front = [(x, y+d), (x+w-d, y+d), (x+w-d, y+h), (x, y+h)]
        back = [(x+d, y), (x+w, y), (x+w, y+h-d), (x+d, y+h-d)]
    return front + back


def longest_run(values, wanted):
    best = count = 0
    for value in values:
        count = count+1 if value == wanted else 0
        best = max(best, count)
    return best


def inspect_edges(rgb, width, height, vertices):
    """Read actual edge-center pixels. Solid underpainting cannot pass gaps.

    Sampling is in physical pixels, trimmed away from vertices/intersections.
    A dark fraction alone is insufficient: require genuine white gap runs and
    genuine dark ink on EACH hidden edge, and continuous ink on EACH solid edge.
    """
    rows = []
    for edge in EDGES:
        a, b = (vertices[i] for i in edge)
        length = math.dist(a, b)
        if length < 22:
            raise AssertionError(f'edge too small to judge real dash gaps: {edge}, {length}')
        trim = min(12.0, length*.20)
        samples = max(20, math.ceil(length-2*trim))
        dark, white = [], []
        for i in range(samples):
            t = (trim+(length-2*trim)*(i+.5)/samples)/length
            x, y = (round(a[j]+(b[j]-a[j])*t) for j in (0, 1))
            if not (0 <= x < width and 0 <= y < height):
                raise AssertionError(f'edge clipped outside capture: {edge}, {(x, y)}')
            r, g, blue = rgb(x, y)
            dark.append(max(r, g, blue) < 160)
            white.append(min(r, g, blue) > 235)
        ink, gaps = sum(dark)/samples, sum(white)/samples
        is_hidden = edge in HIDDEN
        checks = {
            'edge_ink': ink > .30,
            'hidden_gaps' if is_hidden else 'solid_continuity':
                (gaps > .05 and longest_run(white, True) >= 2) if is_hidden else
                (gaps < .02 and ink > .95),
        }
        rows.append({'edge': list(edge), 'hidden': is_hidden, 'dark_fraction': ink,
                     'white_fraction': gaps, 'longest_white_run': longest_run(white, True),
                     'checks': checks, 'passed': all(checks.values())})
    return rows


def inspect_thumbnail(rgb, width, height):
    """Both distant page extremes must survive in this one full item crop."""
    red, blue = [], []
    minimum_run = max(8, math.ceil(height*.10))
    # ClearType captions can contain red/blue fringes; the fixture ink is a
    # continuous vertical stroke, not a few coloured pixels along a glyph.
    for x in range(width):
        starts = [None, None]
        for y in range(height+1):
            if y < height:
                r, g, b = rgb(x, y)
                matches = (r > 120 and r > g*1.5 and r > b*1.5,
                           b > 120 and b > r*1.5 and b > g*1.2)
            else:
                matches = (False, False)
            for index, points in enumerate((red, blue)):
                if matches[index]:
                    if starts[index] is None: starts[index] = y
                elif starts[index] is not None:
                    if y-starts[index] >= minimum_run:
                        points.extend((x, yy) for yy in range(starts[index], y))
                    starts[index] = None
    def bounds(points):
        return [min(p[0] for p in points), min(p[1] for p in points),
                max(p[0] for p in points), max(p[1] for p in points)] if points else None
    left, right = bounds(red), bounds(blue)
    checks = {'left_ink': len(red) >= 8, 'right_ink': len(blue) >= 8}
    checks['full_left_right'] = bool(left and right and left[0] < width*.35
        and right[2] > width*.65 and left[2] < right[0]
        and left[3]-left[1] > height*.10 and right[3]-right[1] > height*.10)
    return {'checks': checks, 'passed': all(checks.values()), 'red_bounds': left,
            'blue_bounds': right, 'red_pixels': len(red), 'blue_pixels': len(blue)}


def inspect_insertion(rgb, width, height, a, b):
    """Require a continuous blue cue away from the top-edge drag cursor/image."""
    length = math.dist(a, b)
    if length < 20:
        raise AssertionError('insertion cue is too short to judge')
    nx, ny = -(b[1]-a[1])/length, (b[0]-a[0])/length
    samples = max(12, round(length*.35))
    hits = []
    for index in range(samples):
        t = .55 + .35*(index+.5)/samples
        x, y = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t
        blue = False
        for offset in (-2, -1, 0, 1, 2):
            xx, yy = round(x+nx*offset), round(y+ny*offset)
            if not (0 <= xx < width and 0 <= yy < height):
                continue
            r, g, b_value = rgb(xx, yy)
            blue |= r < 85 and 105 < g < 185 and b_value > 190
        hits.append(blue)
    coverage = sum(hits)/len(hits)
    return {'passed': coverage >= .85, 'blue_fraction': coverage, 'samples': samples}


def reorder_goal(order, current, abc):
    a, b, c = abc
    return list(order) == [c, a, b] and current == c


class SyntheticImage:
    """Tiny pure-Python image for negative calibration; never paints the app."""
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.pixels = [(255, 255, 255)] * (width*height)

    def rgb(self, x, y):
        return self.pixels[y*self.width+x]

    def line(self, a, b, color=(0, 0, 0), dashed=False, radius=1.8):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        for y in range(max(0, math.floor(min(a[1], b[1])-radius)),
                       min(self.height, math.ceil(max(a[1], b[1])+radius)+1)):
            for x in range(max(0, math.floor(min(a[0], b[0])-radius)),
                           min(self.width, math.ceil(max(a[0], b[0])+radius)+1)):
                t = min(1., max(0., ((x-a[0])*dx+(y-a[1])*dy)/(length*length)))
                if math.hypot(x-a[0]-t*dx, y-a[1]-t*dy) <= radius:
                    if not dashed or (t*length) % 16 < 9:
                        self.pixels[y*self.width+x] = color


def calibrate_pixels():
    """Known-good + missing/solid-underpaint/visible-dashed negative pictures."""
    results = []
    for kind in ('CUBE', 'CUBOID'):
        points = box_vertices(kind, (90, 110, 250, 210))
        for mode in ('good', 'solid_underpaint', 'visible_dashed', 'blank'):
            image = SyntheticImage(450, 380)
            if mode != 'blank':
                for edge in EDGES:
                    a, b = (points[i] for i in edge)
                    if mode == 'solid_underpaint': image.line(a, b)
                    image.line(a, b, dashed=(edge in HIDDEN or mode == 'visible_dashed'))
            rows = inspect_edges(image.rgb, image.width, image.height, points)
            passed = all(row['passed'] for row in rows)
            if passed != (mode == 'good'):
                raise AssertionError(f'pixel calibration failed: {kind}/{mode}: {rows}')
            if mode == 'solid_underpaint' and not all(
                    not row['checks']['hidden_gaps'] for row in rows if row['hidden']):
                raise AssertionError('solid underpainting must fail EACH hidden-gap check')
            if mode == 'visible_dashed' and not all(
                    not row['checks']['solid_continuity'] for row in rows if not row['hidden']):
                raise AssertionError('dashed visible edges must fail EACH solid-continuity check')
            results.append({'kind': kind, 'image': mode, 'correct_verdict': True})
    for mode in ('good', 'left_only', 'right_only', 'swapped', 'blank',
                 'good_caption', 'left_only_caption', 'right_only_caption', 'blank_caption'):
        image = SyntheticImage(220, 150)
        content = mode.removesuffix('_caption')
        if content in ('good', 'left_only', 'swapped'):
            x = 200 if content == 'swapped' else 18
            image.line((x, 22), (x, 115), (238, 32, 32), radius=3)
        if content in ('good', 'right_only', 'swapped'):
            x = 18 if content == 'swapped' else 200
            image.line((x, 22), (x, 115), (32, 80, 238), radius=3)
        if mode.endswith('_caption'):
            for x in range(65, 155, 8):
                image.line((x, 132), (x, 139), (238, 32, 32), radius=.5)
                image.line((x+2, 132), (x+2, 139), (32, 80, 238), radius=.5)
        row = inspect_thumbnail(image.rgb, image.width, image.height)
        if row['passed'] != (content == 'good'):
            raise AssertionError(f'thumbnail calibration failed: {mode}: {row}')
        results.append({'thumbnail': mode, 'correct_verdict': True})
    for mode in ('good', 'blank', 'short', 'wrong_position', 'page_blue'):
        image = SyntheticImage(220, 220)
        a, b = (18, 15), (18, 205)
        if mode != 'blank':
            start = (40, 15) if mode == 'wrong_position' else a
            end = (40, 205) if mode == 'wrong_position' else (18, 80) if mode == 'short' else b
            color = (32, 80, 238) if mode == 'page_blue' else (22, 136, 255)
            image.line(start, end, color=color, radius=2)
        row = inspect_insertion(image.rgb, image.width, image.height, a, b)
        if row['passed'] != (mode == 'good'):
            raise AssertionError(f'insertion-cue calibration failed: {mode}: {row}')
        results.append({'insertion': mode, 'correct_verdict': True})
    if not reorder_goal('CAB', 'C', 'ABC') or any(
            reorder_goal(order, current, 'ABC') for order, current in
            (('CBA', 'C'), ('ACB', 'C'), ('CAB', 'A'), ('ABC', 'C'))):
        raise AssertionError('reorder positive/negative oracle calibration failed')
    return results


def write_json(path, payload):
    temporary = path.with_suffix('.pending.json')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


class Capture:
    """Convert read-only Qt geometry to physical CAPTUREBLT pixels, without moves."""
    def __init__(self, harness, name, widget):
        from PyQt6.QtGui import QImage
        self.meta = harness.capture(name+'.png', widget)
        self.image = QImage(str(harness.output/self.meta['file']))
        if self.image.isNull(): raise RuntimeError('private capture did not decode')
        self.window = widget.window()
        user = harness.mouse.user32
        user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user.GetClientRect.restype = wintypes.BOOL
        user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user.ClientToScreen.restype = wintypes.BOOL
        rect, origin = wintypes.RECT(), wintypes.POINT()
        hwnd = self.meta['hwnd']
        if not user.GetClientRect(hwnd, ctypes.byref(rect)) or not user.ClientToScreen(hwnd, ctypes.byref(origin)):
            raise RuntimeError('cannot map owned capture client geometry')
        self.sx = (rect.right-rect.left)/self.window.width()
        self.sy = (rect.bottom-rect.top)/self.window.height()
        if abs(self.sx-self.sy) > .03:
            raise RuntimeError('nonuniform capture DPI mapping')
        x, y, width, height = self.meta['physical_rect']
        if self.image.width() != width or self.image.height() != height:
            raise RuntimeError('capture dimensions differ from native rectangle')
        self.offset = (origin.x-x, origin.y-y)

    def point(self, widget, point):
        # mapTo accepts QWidget-local QPoint; never use guessed screen DPR alone.
        local = widget.mapTo(self.window, point)
        return (self.offset[0]+local.x()*self.sx, self.offset[1]+local.y()*self.sy)

    def crop(self, widget, rect):
        x, y = self.point(widget, rect.topLeft())
        width, height = round(rect.width()*self.sx), round(rect.height()*self.sy)
        x, y = round(x), round(y)
        if x < 0 or y < 0 or x+width > self.image.width() or y+height > self.image.height():
            raise AssertionError('full thumbnail rectangle is clipped in native capture')
        return self.image.copy(x, y, width, height)


def rgb_reader(image):
    def rgb(x, y):
        color = image.pixelColor(x, y)
        return color.red(), color.green(), color.blue()
    return rgb


class FeatureDriver:
    def __init__(self, host, harness, output, case, timeout, progress):
        self.host, self.h, self.output, self.case = host, harness, output, case
        self.panel, self.canvas = host.panel, host.panel.canvas
        self.timeout, self.progress = timeout, progress
        self.inputs, self.steps, self.captures = [], [], []
        self.started = time.monotonic()
        self.error = None
        self.input_lock = threading.Lock()
        self.input_state = {'pid': os.getpid(), 'left_down': False, 'sequence': 0}
        write_json(self.output/'input-state.json', self.input_state)
        self.h.mouse.audit = self.audit
        self.initial_ids = [p['page_id'] for p in self.canvas.pages]

    def audit(self, row):
        self.inputs.append(row)
        if row['kind'] in ('left_down', 'left_up'):
            # The helper logs DOWN before sending, UP after sending. Persisting
            # here is deliberately conservative and survives a wedged Qt loop.
            with self.input_lock:
                self.input_state.update(left_down=row['kind'] == 'left_down',
                                        sequence=self.input_state['sequence']+1)
                if row['kind'] == 'left_down':
                    self.input_state.update(press=list(row['physical']), hwnd=row['hwnd'])
                write_json(self.output/'input-state.json', self.input_state)

    def require(self, name, condition, detail=''):
        self.h.require(name, condition, detail)

    def persist(self, outcome='running', error=None):
        write_json(self.output/'report.json', {
            'schema': 1, 'case': self.case, 'pid': os.getpid(), 'outcome': outcome,
            'error': error, 'elapsed_seconds': time.monotonic()-self.started,
            'scope': 'private native source UI, not package/IPC/parent restoration',
            'capture_method': 'SRCCOPY|CAPTUREBLT', 'private': True,
            'initial_page_ids': self.initial_ids, 'checks': self.h.checks,
            'steps': self.steps, 'captures': self.captures, 'inputs': list(self.inputs),
            'progress': self.progress})

    def pump(self, ms=180):
        self.h.mouse.pump(ms)
        if self.error is not None: raise RuntimeError(str(self.error))

    def until(self, condition, description, timeout=None):
        deadline = time.monotonic()+(self.timeout if timeout is None else timeout)
        while not condition():
            if time.monotonic() > deadline: raise TimeoutError(description)
            self.pump(25)

    def action(self, name, fn):
        self.h.mouse.deadline = time.monotonic()+self.timeout
        row = {'name': name, 'outcome': 'running', 'input_start': len(self.inputs)}
        self.steps.append(row); self.persist()
        try:
            fn(); row['outcome'] = 'passed'
        except Exception:
            row['outcome'] = 'failed'; row['error'] = traceback.format_exc()
            raise
        finally:
            row['input_end'] = len(self.inputs); self.persist()

    def capture(self, name, widget):
        result = Capture(self.h, name, widget)
        self.captures.append(result.meta)
        return result

    def ids(self):
        return [page['page_id'] for page in self.canvas.pages]

    def contents(self):
        # The live page's view can legitimately change; compare content by ID.
        pages = [self.host.module.serialize_page(self.canvas.live_page() if index == self.canvas.current_page else page)
                 for index, page in enumerate(self.canvas.pages)]
        return {page['page_id']: {key: value for key, value in page.items() if key != 'view'}
                for page in pages}

    def click_point(self, widget, point):
        self.h.mouse.hit(widget, point)
        self.h.mouse.click_point(point)

    def drag(self, widget, source, destination, hold_ms=0):
        points = [source+(destination-source)*i/24 for i in range(25)]
        # Check every intended path point in GUI thread before native worker starts.
        for point in points: self.h.mouse.hit(widget, point)
        self.h.mouse.path(points, hold_ms=hold_ms)

    def reveal(self, index):
        listing = self.panel.thumbnail_list
        viewport = listing.viewport()
        for _ in range(40):
            rect = listing.visualItemRect(listing.item(index))
            if viewport.rect().contains(rect): return rect
            value = listing.verticalScrollBar().value()
            self.h.mouse.focus_window(self.panel.thumbnail_panel)
            self.h.mouse.wheel(viewport, 1 if rect.top() < 0 else -1)
            if listing.verticalScrollBar().value() == value:
                raise AssertionError(f'cannot reveal full thumbnail {index+1} with native wheel')
        raise TimeoutError('native thumbnail reveal bounded out')

    def select(self, index):
        rect = self.reveal(index)
        self.click_point(self.panel.thumbnail_list.viewport(),
                         self.panel.thumbnail_list.viewport().mapToGlobal(rect.center()))
        self.until(lambda: self.canvas.current_page == index, 'native page selection')
        self.require('selected page ID agrees with model', self.canvas._page_id == self.ids()[index])

    def page_names(self):
        from PyQt6.QtCore import Qt
        listing = self.panel.thumbnail_list
        return {listing.item(row).data(Qt.ItemDataRole.UserRole): listing.item(row).text()
                for row in range(listing.count())}

    def assert_page_names(self):
        self.require('default and renamed page captions follow page identities',
                     self.page_names() == self.original_names, self.page_names())

    def move_before(self, source_id, target_id, *, cross_row=False, after=False, cue=False):
        from PyQt6.QtCore import QPoint, QTimer
        from PyQt6.QtGui import QCursor
        listing, viewport = self.panel.thumbnail_list, self.panel.thumbnail_list.viewport()
        before = self.ids()
        source_index, target_index = before.index(source_id), before.index(target_id)
        self.select(source_index)
        source_rect = self.reveal(source_index)
        target_rect = listing.visualItemRect(listing.item(target_index))
        self.require('both drag items fully visible', viewport.rect().contains(target_rect))
        if cross_row:
            self.require('native OLE crosses thumbnail rows', source_rect.top() != target_rect.top())
        source = viewport.mapToGlobal(source_rect.center())
        target = viewport.mapToGlobal((target_rect.topRight()+QPoint(-5, 5)) if after
                                      else target_rect.topLeft()+QPoint(5, 5))
        evidence, failures = [], []
        timer = QTimer()
        side = 'after' if after else 'before'
        baseline = self.capture(f'thumbnail-cue-{side}-baseline', self.panel.thumbnail_panel) if cue else None
        ready_since = None

        def inspect_cue():
            nonlocal ready_since
            if evidence or failures:
                return
            try:
                if listing._drag_source_id != source_id or (QCursor.pos()-target).manhattanLength() > 3:
                    ready_since = None
                    return
                if ready_since is None:
                    ready_since = time.monotonic()
                    return
                if time.monotonic()-ready_since < .10:
                    return
                insertion, line = listing._drop_insertion, listing._drop_line
                if insertion != target_index+int(after) or line is None:
                    raise AssertionError(f'{side} cue has wrong insertion: {insertion}')
                if abs(line.x1()-line.x2()) > 1 or abs(line.y2()-line.y1()) < target_rect.height()*.6:
                    raise AssertionError(f'{side} cue is not a full vertical boundary')
                edge = target_rect.right() if after else target_rect.left()
                if abs(line.x1()-edge) > 12:
                    raise AssertionError(f'{side} cue does not match target boundary: {line.x1()}, {edge}')
                captured = self.capture(f'thumbnail-cue-{side}-dragging', self.panel.thumbnail_panel)
                a, b = (captured.point(viewport, point) for point in (line.p1(), line.p2()))
                if a[1] > b[1]: a, b = b, a
                metrics = inspect_insertion(rgb_reader(captured.image), captured.image.width(),
                                            captured.image.height(), a, b)
                absent = inspect_insertion(rgb_reader(baseline.image), baseline.image.width(),
                                           baseline.image.height(), a, b)
                evidence.append({'side': side, 'insertion': insertion, 'line': [a, b],
                                 'painted': metrics, 'baseline': absent})
            except Exception as exc:
                failures.append(repr(exc))

        if cue:
            timer.timeout.connect(inspect_cue)
            timer.start(40)
        try:
            self.drag(viewport, source, target, hold_ms=1000 if cue else 350)
        finally:
            timer.stop()
        if cue:
            self.require(f'native {side} insertion sampled during held OLE drag',
                         not failures and bool(evidence), failures)
            row = evidence[0]
            self.require(f'native {side} insertion has real visible blue pixels', row['painted']['passed'], row)
            self.require(f'native {side} insertion pixel oracle rejects no-drag baseline',
                         not row['baseline']['passed'], row)
            self.require('drop cue cleaned up after native release',
                         listing._drop_insertion is None and listing._drop_line is None)
        expected = list(before)
        expected.remove(source_id)
        expected.insert(expected.index(target_id)+int(after), source_id)
        self.until(lambda: self.ids() == expected, 'native OLE changed actual page order')
        self.require('drag preserves active page identity', self.canvas._page_id == source_id)
        self.require('selected row follows page identity', listing.currentRow() == expected.index(source_id))
        self.require('OLE source cleaned up', listing._drag_source_id is None)
        if self.case == 'thumbnails': self.assert_page_names()
        return expected

    def check_thumbnail_layout(self):
        listing = self.panel.thumbnail_list
        rects = [listing.visualItemRect(listing.item(i)) for i in range(listing.count())]
        viewport = listing.viewport().rect()
        columns = sum(rect.top() == rects[0].top() for rect in rects)
        self.require('13 thumbnails', listing.count() == 13)
        self.require('overview uses multiple complete columns', columns >= 2, columns)
        self.require('every item fits horizontally', all(0 <= r.left() <= r.right() < viewport.width() for r in rects))
        self.require('every full item can fit vertically', all(0 < r.height() <= viewport.height() for r in rects))
        self.require('no horizontal scrolling', listing.horizontalScrollBar().maximum() == 0
                     and not listing.horizontalScrollBar().isVisible())
        self.require('13 pages require vertical scrolling', listing.verticalScrollBar().maximum() > 0)
        return columns

    def thumbnail_pixels(self):
        listing = self.panel.thumbnail_list
        seen = set()
        # At one tick the production lazy renderer may complete only two icons.
        # Wait for cache population via normal timers, never call its renderer.
        for index in range(13):
            self.reveal(index)
            def icons_ready():
                viewport = listing.viewport().rect()
                return all(not listing.item(i).icon().isNull() for i in range(13)
                           if viewport.contains(listing.visualItemRect(listing.item(i))))
            self.until(icons_ready, 'lazy thumbnails render through live timers')
            self.pump(250)
            rect = listing.visualItemRect(listing.item(index))
            self.require('full thumbnail visible before capture', listing.viewport().rect().contains(rect), index+1)
            # Keep cursor off the item but on an owned control, avoiding hover/cursor contamination.
            park = self.panel.btn_close_thumbnails
            point = park.mapToGlobal(park.rect().center())
            self.h.mouse.hit(park, point); self.h.mouse.move(point); self.pump(80)
            capture = self.capture(f'thumbnail-{index+1:02}', self.panel.thumbnail_panel)
            image = capture.crop(listing.viewport(), rect)
            metrics = inspect_thumbnail(rgb_reader(image), image.width(), image.height())
            self.require(f'page {index+1:02} full left/right extreme ink pixels', metrics['passed'], metrics)
            seen.add(self.ids()[index])
            self.require('wheel leaves current page unchanged', self.canvas._page_id == self.initial_ids[0])
            self.require('no horizontal range while scrolling', listing.horizontalScrollBar().maximum() == 0)
        self.require('all 13 distinct page identities pixel-checked', seen == set(self.initial_ids))
        self.require('native wheel reached the full last page',
                     listing.viewport().rect().contains(listing.visualItemRect(listing.item(12))))
        self.require('actual native vertical wheel observed', any(r['kind'] == 'wheel' for r in self.inputs))

    def thumbnail_drags(self, columns):
        from PyQt6.QtCore import QPoint, QTimer
        listing = self.panel.thumbnail_list
        original_content = self.contents()
        self.reveal(0)
        source_id = self.ids()[columns]
        self.move_before(source_id, self.ids()[0], cross_row=True, cue=True)
        self.capture('thumbnail-cross-row', self.panel.thumbnail_panel)
        self.move_before(self.ids()[0], self.ids()[columns+1], cross_row=True, after=True, cue=True)
        self.capture('thumbnail-after-insertion', self.panel.thumbnail_panel)
        viewport = listing.viewport()
        self.select(0)
        before, active = self.ids(), self.canvas._page_id
        start_value = listing.verticalScrollBar().value()
        edge_values, drops, edge_cues, cue_failures = [], [], [], []
        def scrolled(value):
            if listing._drag_source_id is not None: edge_values.append(value)
        def dropped(source, destination): drops.append((source, destination))
        def read_edge_cue():
            try:
                if listing._drag_source_id is not None and listing._drop_insertion is not None:
                    edge_cues.append((listing.verticalScrollBar().value(), listing._drop_insertion))
            except Exception as exc:
                cue_failures.append(repr(exc))
        timer = QTimer()
        timer.timeout.connect(read_edge_cue)
        listing.verticalScrollBar().valueChanged.connect(scrolled)
        listing.reorder_requested.connect(dropped)
        try:
            source_rect = listing.visualItemRect(listing.currentItem())
            destination = QPoint(source_rect.center().x(), viewport.height()-3)
            timer.start(40)
            self.drag(viewport, viewport.mapToGlobal(source_rect.center()),
                      viewport.mapToGlobal(destination), hold_ms=2400)
        finally:
            timer.stop()
            listing.verticalScrollBar().valueChanged.disconnect(scrolled)
            listing.reorder_requested.disconnect(dropped)
        self.require('native OLE edge hold autoscrolled during drag',
                     bool(edge_values) and max(edge_values) > start_value, edge_values)
        self.require('edge OLE committed exactly one reorder', len(drops) == 1, drops)
        self.require('edge insertion cue tracks autoscroll', not cue_failures and bool(edge_cues)
                     and len({row[1] for row in edge_cues}) > 1, [cue_failures, edge_cues])
        expected = list(before)
        if drops:
            source, destination = drops[0]
            insertion = edge_cues[-1][1]
            self.require('edge release uses the final visible insertion cue',
                         destination == insertion-int(source < insertion), [drops[0], edge_cues[-1]])
            expected.insert(destination, expected.pop(source))
        self.require('edge drop changed real model order', self.ids() == expected and self.ids() != before)
        self.require('edge drag preserves active page identity', self.canvas._page_id == active)
        self.require('edge drag preserves all page contents', self.contents() == original_content)
        self.assert_page_names()
        self.require('edge release clears insertion feedback',
                     listing._drop_insertion is None and listing._drop_line is None)
        self.require('edge drag keeps 13 pages and matching selection',
                     listing.count() == 13 and listing.currentRow() == self.canvas.current_page)
        self.capture('thumbnail-edge-scroll', self.panel.thumbnail_panel)
        page_ids, current = self.ids(), self.canvas._page_id
        self.h.mouse.click(self.panel.btn_close_thumbnails)
        self.pump(800)  # Cover the ordinary heartbeat; hide() alone is not evidence.
        self.require('native X stays closed after heartbeat', not self.panel.thumbnail_panel.isVisible())
        self.require('X preserves order/current-page identity/content', self.ids() == page_ids
                     and self.canvas._page_id == current and self.contents() == original_content)
        self.capture('thumbnail-X-closed', self.canvas)

    def thumbnail_double_clicks(self):
        listing, viewport = self.panel.thumbnail_list, self.panel.thumbnail_list.viewport()
        original_content, order = self.contents(), self.ids()
        user = self.h.mouse.user32
        user.GetDoubleClickTime.restype = wintypes.UINT
        for already_selected in (True, False):
            self.h.mouse.click(self.panel.rail_count)
            self.until(lambda: self.panel.thumbnail_panel.isVisible(), 'overview reopens for double-click')
            index = self.canvas.current_page if already_selected else (0 if self.canvas.current_page else 1)
            target_id = order[index]
            rect = self.reveal(index)
            self.pump(int(user.GetDoubleClickTime())+60)
            point = viewport.mapToGlobal(rect.center())
            try:
                self.h.mouse.hit(viewport, point)
                self.h.mouse.down_at(point)
                self.h.mouse.up()
                self.pump(15)
                self.require('single native click selects and keeps overview open',
                             self.canvas._page_id == target_id and self.panel.thumbnail_panel.isVisible())
                self.h.mouse.hit(viewport, point)
                self.h.mouse.down_at(point)
                self.h.mouse.up()
            finally:
                self.h.mouse.up()
            self.pump(800)
            detail = 'selected' if already_selected else 'another'
            self.require(f'double-click on {detail} page closes overview past heartbeat',
                         not self.panel.thumbnail_panel.isVisible())
            self.require(f'double-click enters the exact {detail} page',
                         self.canvas._page_id == target_id and self.canvas.current_page == index)
            self.require('double-click preserves all pages and contents',
                         self.ids() == order and self.contents() == original_content)
            self.assert_page_names()
            self.capture(f'thumbnail-double-click-{detail}-closed', self.canvas)

    def thumbnails(self):
        self.action('native thumbnail entry', lambda: self.h.mouse.click(self.panel.rail_count))
        self.until(lambda: self.panel.thumbnail_panel.isVisible(), 'thumbnail overview opens')
        columns = self.check_thumbnail_layout()
        self.original_names = {page_id: ('Native renamed' if index == 2 else
                               self.host.module.trf('page_label', index=index+1))
                               for index, page_id in enumerate(self.initial_ids)}
        self.assert_page_names()
        self.action('13 full native thumbnail pixel checks and wheel', self.thumbnail_pixels)
        self.action('before/after insertion cues, cross-row OLE, edge autoscroll, native X',
                    lambda: self.thumbnail_drags(columns))
        self.action('native single-click and selected/other-page double-click', self.thumbnail_double_clicks)

    def box_area(self):
        from PyQt6.QtCore import QPoint
        # Find an unobstructed projected box region instead of relying on desktop size.
        c = self.canvas
        for y in range(130, max(131, c.height()-230), 70):
            for x in reversed(range(120, max(121, c.width()-340), 90)):
                try:
                    for yy in range(y-50, y+231, 14):
                        for xx in range(x, x+331, 14):
                            self.h.mouse.hit(c, c.mapToGlobal(QPoint(xx, yy)))
                    return x, y, 280, 210
                except RuntimeError:
                    pass
        raise RuntimeError('no fully owned unobstructed 330x280 canvas region; enlarge desktop')

    def draw_box(self, kind, direction, first):
        from PyQt6.QtCore import QPoint, QPointF
        p, c = self.panel, self.canvas
        if not first:
            previous_pages = len(c.pages)
            self.h.mouse.click(p.rail_new)
            self.require('native new page isolates next box', len(c.pages) == previous_pages+1 and not c.shape_items)
        shape_button = next(b for b in p.shape_buttons if b.property('shape_type') == kind)
        if not shape_button.isVisible(): self.h.mouse.click(p.icon_buttons['shape'])
        self.h.mouse.click(shape_button)
        self.require('native button chose box tool', c.draw_state == 'SHAPE' and c.shape_type == kind)
        x, y, w, h = self.box_area()
        corners = {'down_right': ((x, y), (x+w, y+h)), 'up_left': ((x+w, y+h), (x, y)),
                   'up_right': ((x, y+h), (x+w, y)), 'down_left': ((x+w, y), (x, y+h))}
        start, end = (c.mapToGlobal(QPoint(*point)) for point in corners[direction])
        self.drag(c, start, end)
        self.until(lambda: len(c.shape_items) == 1, 'native box committed exactly one shape')
        item = c.shape_items[0]
        self.require('native committed requested box', item['type'] == kind and c.preview_shape is None)
        a, b = (c.to_document(QPointF(*point)) for point in corners[direction])
        expected_rect = (min(a.x(), b.x()), min(a.y(), b.y()), abs(b.x()-a.x()), abs(b.y()-a.y()))
        self.require('box rectangle matches native drag endpoints in this direction',
                     all(abs(actual-expected) <= 3 for actual, expected in zip(item['rect'].getRect(), expected_rect)),
                     {'actual': item['rect'].getRect(), 'expected': expected_rect})
        self.require('unrotated drag box for independent oracle', item.get('rotation', 0) == 0)
        self.require('isolated box has no ink/text/image contamination',
                     not c.all_segments and not c.text_items and not c.image_items)
        content = self.contents()
        # A newly committed shape is selected. Use the real pen button to remove
        # handles; never mutate selected_ids or the renderer to make pixels pass.
        self.h.mouse.click(p.icon_buttons['pen'])
        self.require('native tool change removes selection decoration', not c.selected_ids)
        self.require('native deselection preserves shape content', self.contents() == content)
        park = p.rail_count  # Always-visible whiteboard control; shape submenus may collapse.
        point = park.mapToGlobal(park.rect().center())
        self.h.mouse.hit(park, point); self.h.mouse.move(point); self.pump(250)
        capture = self.capture(f'{kind.lower()}-{direction}', c)
        points = []
        for px, py in box_vertices(kind, item['rect'].getRect()):
            local = c.to_view(QPointF(px, py))
            self.h.mouse.hit(c, c.mapToGlobal(local.toPoint()))
            # Keep subpixel projection until final image sampling.
            origin = capture.point(c, QPoint(0, 0))
            points.append((origin[0]+local.x()*capture.sx, origin[1]+local.y()*capture.sy))
        metrics = inspect_edges(rgb_reader(capture.image), capture.image.width(), capture.image.height(), points)
        for row in metrics:
            self.require(f'{kind}/{direction} native edge {row["edge"]}', row['passed'], row)

    def boxes(self):
        self.require('image-only negative calibration', bool(calibrate_pixels()))
        first = True
        for kind in ('CUBE', 'CUBOID'):
            for direction in ('down_right', 'up_left', 'up_right', 'down_left'):
                self.action(f'native {kind} {direction}', lambda k=kind, d=direction, f=first: self.draw_box(k, d, f))
                first = False

    def lesson_state(self):
        engine = self.host.presenter.engine
        return engine.current_step_id, engine.sequence_index, engine.phase

    def step(self, expected):
        self.until(lambda: self.lesson_state() == (expected, 0, 'running'), f'lesson reaches {expected}')
        self.require('lesson target available', not self.host.presenter._missing)

    def remains_reorder(self, label):
        self.pump(650)
        self.require(label, self.lesson_state() == ('reorder', 0, 'running'), self.lesson_state())
        self.require('wrong/intermediate drag gives no completion credit',
                     not any(row[1] in ('completed', 'skipped') for row in self.progress))
        self.require('input barrier reinstalled after OLE', self.host.presenter.barrier.installed)
        self.require('native document batch closed', self.panel._teaching_document_batch is None)
        self.require('native dialog guard balanced', not self.host.presenter._dialog_depth)

    def reorder(self):
        p, c = self.panel, self.canvas
        abc = self.ids(); a, b, last = abc
        original_content = self.contents()
        self.step('intro')
        self.action('native intro next', lambda: self.h.mouse.click(self.host.presenter.controller.next_button))
        self.step('thumbnails')
        self.action('native thumbnail entry', lambda: self.h.mouse.click(p.rail_count))
        self.step('select_last')
        self.action('native select C', lambda: self.select(2))
        self.step('identity_info')
        self.action('native identity next', lambda: self.h.mouse.click(self.host.presenter.controller.next_button))
        self.step('reorder')
        if self.case.endswith('.intermediate'):
            self.action('native C before B intermediate', lambda: self.move_before(last, b))
            self.require('intermediate actual order is A/C/B', self.ids() == [a, last, b])
            self.remains_reorder('A/C/B must remain at reorder')
            self.capture('reorder-intermediate-ACB', p.thumbnail_panel)
        elif self.case.endswith('.wrong'):
            self.action('native B before A wrong preparation', lambda: self.move_before(b, a))
            self.require('native wrong preparation is B/A/C', self.ids() == [b, a, last])
            self.remains_reorder('B/A/C must remain at reorder')
        target = b if self.case.endswith('.wrong') else a
        self.action('native C to front', lambda: self.move_before(last, target))
        expected = [last, b, a] if self.case.endswith('.wrong') else [last, a, b]
        self.require('exact complete page order', self.ids() == expected, self.ids())
        self.require('C identity follows current row zero', c._page_id == last and c.current_page == 0
                     and p.thumbnail_list.currentRow() == 0 and p.rail_count.text() == '1/3')
        self.require('reorder preserves every page content', self.contents() == original_content)
        self.capture('reorder-final', p.thumbnail_panel)
        if self.case.endswith('.wrong'):
            self.require('wrong C/B/A rejected by independent order oracle', not reorder_goal(self.ids(), c._page_id, abc))
            self.remains_reorder('C/B/A with correct current page must NOT advance')
        else:
            self.require('correct C/A/B accepted by independent oracle', reorder_goal(self.ids(), c._page_id, abc))
            self.step('verify_info')
            self.action('native verification next', lambda: self.h.mouse.click(self.host.presenter.controller.next_button))
            self.step('done')
            self.action('native done next', lambda: self.h.mouse.click(self.host.presenter.controller.next_button))
            self.until(lambda: self.host.presenter.engine.phase == 'completed', 'formal chapter completion')
            self.require('completed callback observed', any(row[1] == 'completed' for row in self.progress))

    def run(self):
        self.h.mouse.deadline = time.monotonic()+self.timeout
        self.pump(800)
        if self.case == 'thumbnails': self.thumbnails()
        elif self.case == 'boxes': self.boxes()
        else: self.reorder()
        self.persist('passed')


def initial_feature_setup(host, case):
    """Only initial fixture construction. This function is never called mid-case."""
    from PyQt6.QtCore import QLineF
    from PyQt6.QtGui import QColor, QPen
    p, c = host.panel, host.panel.canvas
    p.infinite_whiteboard = True
    p.whiteboard_auto_pen = False
    p.pen_defaults_enabled = False
    c.smart_shapes_enabled = False
    c.board_style = 'WHITE'
    c.pen_color, c.pen_width = QColor('black'), 3
    p.set_drawing_mode(True)
    c.enter_whiteboard()
    if case == 'thumbnails':
        for index in range(13):
            if index: c.new_page()
            c.all_segments = [
                {'id': f'extreme-left-{index}', 'line': QLineF(-900, -400, -900, 400),
                 'pen': QPen(QColor('#ee2020'), 60)},
                {'id': f'extreme-right-{index}', 'line': QLineF(900, -400, 900, 400),
                 'pen': QPen(QColor('#2050ee'), 60)}]
            c.mark_content_changed()
        c.rename_page(2, 'Native renamed')
        c.switch_page(-12)
        c.save_current_page()
    p.update_whiteboard_ui()
    c.show(); p.show()
    p.set_ui_mode('icon', persist=False)
    p.show_only_sub(None)
    p.resume_callbacks(); p.bind_topmost_stack()


def worker(args):
    worker_started = time.monotonic()
    if sys.platform != 'win32' or os.environ.get('QT_QPA_PLATFORM') not in (None, 'windows'):
        raise RuntimeError('real worker requires Windows QPA, never offscreen')
    # Reject manual --worker invocations: the supervisor owns the scratch lifetime.
    temporary = os.environ.get('MYSCREENDRAW_FEATURE_PARENT_TEMP')
    if not temporary or not Path(temporary).is_dir():
        raise RuntimeError('worker must be started by this driver supervisor')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    os.environ['MYSCREENDRAW_NO_KEYBOARD'] = '1'
    from runtime_paths import RuntimePaths
    from teaching.bootstrap import PracticeRequest, practice_arguments
    paths = RuntimePaths.create_practice(ROOT, ROOT, temp_root=Path(temporary))
    chapter = 'c05.reorder'
    channel = 'myscreendraw-teaching-'+paths.session_id
    request = PracticeRequest(paths, channel, 'c05', chapter)
    os.environ['MYSCREENDRAW_PRACTICE_NONCE'] = paths.nonce
    os.environ['MYSCREENDRAW_PRACTICE_TEMP_ROOT'] = str(paths.temp_root)
    # Must bind practice paths before importing main or constructing application UI.
    sys.argv = [str(ROOT/'main.py'), *practice_arguments(paths, channel, 'c05', chapter)]
    import main
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QWidget
    from teaching.application import ApplicationTeachingHost
    from native_input_620 import NativeHarness
    from real_teaching_620 import local_host_bridge
    app = QApplication(sys.argv[:1]); app.setQuitOnLastWindowClosed(False)
    if app.platformName() != 'windows': raise RuntimeError('not a native Windows application')
    context = main.RUNTIME_CONTEXT
    if context.paths != paths or not paths.practice or context.ui_active:
        raise AssertionError('private runtime binding failed')
    if any((context.updates, context.autostart, context.global_keyboard, context.tray,
            context.usage_tracking, context.ordinary_recovery, context.desktop_capture)):
        raise AssertionError('ordinary process services leaked into native feature acceptance')
    if not all(Path(getattr(main, name)).resolve().is_relative_to(paths.runtime_root.resolve())
               for name in paths.module_aliases()):
        raise AssertionError('module data path escaped private runtime')
    import socket
    def no_network(*_args, **_kwargs): raise RuntimeError('network forbidden in native feature acceptance')
    socket.socket.connect = no_network
    socket.create_connection = no_network
    main.ensure_directories(); main.setup_logging(); main.install_qt_translations(app)
    backdrop = QWidget(); backdrop.setWindowTitle('Private native feature backdrop')
    backdrop.setStyleSheet('background: #db23bd;')
    backdrop.setGeometry(app.primaryScreen().geometry())
    result = 1
    host = h = driver = None
    guard = None
    try:
        h = NativeHarness(app, output)
        progress = []
        host = ApplicationTeachingHost(main, request, on_progress=lambda *row: progress.append(row))
        local_host_bridge(host)
        context.activate(); backdrop.show()
        if args.case[0].startswith('c05.'):
            host.activate()
        else:
            # Same private host, but no tutorial/presenter start or lesson credit.
            initial_feature_setup(host, args.case[0])
        driver = FeatureDriver(host, h, output, args.case[0], args.step_timeout, progress)
        host.failed.connect(lambda detail: setattr(driver, 'error', detail))
        host.exit_requested.connect(lambda: setattr(driver, 'error', 'practice exited early'))
        # Independent of Qt/OLE: cancellation gets to the bounded native worker
        # even when Windows' modal drag loop stops processing Qt timers.
        def cancel():
            driver.error = 'case wall-clock timeout'
            h.mouse.cancelled.set()
        remaining = max(0., args.case_timeout-(time.monotonic()-worker_started))
        guard = threading.Timer(remaining, cancel); guard.daemon = True; guard.start()
        def run():
            nonlocal result
            try:
                driver.run(); result = 0
            except Exception:
                detail = traceback.format_exc(); print(detail, file=sys.stderr, flush=True)
                driver.persist('failed', detail)
            finally:
                try: h.mouse.restore()
                finally: app.quit()
        QTimer.singleShot(600, run)
        app.exec()
    finally:
        if guard is not None: guard.cancel()
        if h is not None:
            h.mouse.restore()
            if h.mouse.errors or h.mouse.down or h.mouse.keys_down or any(w.is_alive() for w in h.mouse.workers):
                result = 1
                if driver is not None: driver.error = f'native cleanup incomplete: {h.mouse.errors}'
        if host is not None:
            try: host.close()
            except Exception as exc:
                result = 1
                if driver is not None: driver.error = f'private host cleanup failed: {exc}'
        backdrop.hide()
        for handler in list(main.LOGGER.handlers):
            handler.flush(); handler.close(); main.LOGGER.removeHandler(handler)
        if driver is not None and result:
            driver.persist('failed', driver.error or 'case did not finish; inspect step error/log')
    return result


def private_output(path):
    path = path.resolve()
    if '.ccgui' not in path.parts:
        raise ValueError('--output must name a NEW directory inside private .ccgui')
    if any(path.is_relative_to(ROOT/name) for name in ('data', 'exports', 'assets', 'tests')):
        raise ValueError('ordinary data/exports/source directories are forbidden output roots')
    if path.exists(): raise ValueError('refusing to reuse an output directory')
    return path


def configure_cleanup_api(user):
    user.WindowFromPoint.argtypes = [wintypes.POINT]; user.WindowFromPoint.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]; user.GetAncestor.restype = wintypes.HWND
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowRect.restype = wintypes.BOOL
    user.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]


def release_owned_mouse(user, child_pid, state):
    """Cleanup only, before killing child. No input without a tracked DOWN.

    The captured original HWND/root and physical press position are journaled by
    the child's audited native helper. No blind global UP; another PID (including
    this supervisor) is not an acceptable recipient. Injectable user API allows
    non-Windows/pure fake-Win32 negative calibration without any actual input.
    """
    if not isinstance(state, dict) or state.get('pid') != child_pid or type(state.get('left_down')) is not bool:
        return {'confirmed': False, 'released': False, 'reason': 'missing/foreign input journal; residual input unknown'}
    if not state['left_down']:
        return {'confirmed': True, 'released': False, 'reason': 'child journal has no tracked DOWN'}
    if not user.GetAsyncKeyState(1)&0x8000:
        return {'confirmed': True, 'released': False, 'reason': 'tracked DOWN already physically released'}
    hwnd, press = state.get('hwnd'), state.get('press')
    def owned(handle):
        pid = wintypes.DWORD()
        if not handle: return False
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        return pid.value == child_pid
    if not owned(hwnd) or not isinstance(press, list) or len(press) != 2:
        return {'confirmed': False, 'released': False, 'reason': 'saved press window is no longer owned/live'}
    root = user.GetAncestor(hwnd, 2)
    if not root or not owned(root):
        return {'confirmed': False, 'released': False, 'reason': 'saved native root is no longer owned/live'}
    def hit(x, y):
        actual = user.WindowFromPoint(wintypes.POINT(x, y))
        return owned(actual) and user.GetAncestor(actual, 2) == root
    candidates = [tuple(map(int, press))]
    rect = wintypes.RECT()
    if user.GetWindowRect(root, ctypes.byref(rect)):
        for fx, fy in ((.5, .5), (.25, .25), (.75, .25), (.25, .75), (.75, .75)):
            candidates.append((round(rect.left+(rect.right-rect.left)*fx),
                               round(rect.top+(rect.bottom-rect.top)*fy)))
    for x, y in candidates:
        # Native hit check before move and immediately again before release.
        if not hit(x, y): continue
        if not user.SetCursorPos(x, y): continue
        actual = wintypes.POINT()
        if not user.GetCursorPos(ctypes.byref(actual)) or abs(actual.x-x) > 3 or abs(actual.y-y) > 3:
            continue
        if not hit(actual.x, actual.y): continue
        if not user.GetAsyncKeyState(1)&0x8000:
            return {'confirmed': True, 'released': False, 'reason': 'tracked DOWN released during cleanup'}
        user.mouse_event(0x0004, 0, 0, 0, 0)  # ONLY tracked LEFTUP, never a new press.
        end = time.monotonic()+.2
        while user.GetAsyncKeyState(1)&0x8000 and time.monotonic() < end: time.sleep(.005)
        confirmed = not bool(user.GetAsyncKeyState(1)&0x8000)
        return {'confirmed': confirmed, 'released': True, 'physical': [actual.x, actual.y],
                'root': int(root), 'reason': 'owned tracked LEFTUP' if confirmed else 'LEFTUP sent; release not confirmed'}
    return {'confirmed': False, 'released': False, 'reason': 'no owned release pixel/readback; refused foreign drop; residual DOWN possible'}


def terminate_owned_child(user, child, output):
    """Always terminate our subprocess, even if safe release cannot be confirmed."""
    try:
        state = json.loads((output/'input-state.json').read_text(encoding='utf-8'))
        cleanup = release_owned_mouse(user, child.pid, state)
    except Exception as exc:
        cleanup = {'confirmed': False, 'released': False, 'reason': f'input cleanup unconfirmed: {exc}'}
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=10)
    write_json(output.parent/(output.name+'.cleanup.json'), cleanup)
    return cleanup


def calibrate_cleanup():
    class FakeUser:
        def __init__(self, mode):
            self.mode, self.position, self.down, self.ups = mode, (9, 9), True, 0
        def GetAsyncKeyState(self, key): return 0x8000 if self.down else 0
        def GetWindowThreadProcessId(self, hwnd, pid): pid._obj.value = 42 if hwnd == 10 else 99
        def GetAncestor(self, hwnd, mode): return hwnd
        def WindowFromPoint(self, point):
            return 20 if self.mode == 'foreign' or (self.mode == 'covered_press' and point.x == 100) else 10
        def GetWindowRect(self, hwnd, rect):
            rect._obj.left = rect._obj.top = 200
            rect._obj.right = rect._obj.bottom = 600
            return True
        def SetCursorPos(self, x, y): self.position = (x, y); return True
        def GetCursorPos(self, point):
            point._obj.x, point._obj.y = self.position
            if self.mode == 'miss': point._obj.x += 20
            return True
        def mouse_event(self, flags, *_args):
            assert flags == 4
            assert self.WindowFromPoint(wintypes.POINT(*self.position)) == 10
            self.ups += 1; self.down = False
    for mode in ('owned', 'covered_press', 'foreign', 'miss', 'untracked', 'wrong_pid', 'missing'):
        user = FakeUser(mode)
        state = {'pid': 42, 'left_down': mode != 'untracked', 'hwnd': 10, 'press': [100, 100]}
        if mode == 'wrong_pid': state['pid'] = 99
        if mode == 'missing': state = None
        result = release_owned_mouse(user, 42, state)
        if user.ups != int(mode in ('owned', 'covered_press')):
            raise AssertionError(f'cleanup injected unsafe/missing UP: {mode}, {result}')
        if result['confirmed'] != (mode in ('owned', 'covered_press', 'untracked')):
            raise AssertionError(f'cleanup falsely claimed release confirmation: {mode}, {result}')
    return 7


def supervise(args, cases):
    if sys.platform != 'win32': raise RuntimeError('native acceptance requires Windows')
    if os.environ.get('QT_QPA_PLATFORM') not in (None, 'windows'):
        raise RuntimeError('native acceptance refuses an offscreen/non-Windows backend')
    output = private_output(args.output)
    user = ctypes.windll.user32
    user.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]; user.GetCursorPos.restype = wintypes.BOOL
    user.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]; user.SetCursorPos.restype = wintypes.BOOL
    user.GetAsyncKeyState.argtypes = [ctypes.c_int]; user.GetAsyncKeyState.restype = ctypes.c_short
    configure_cleanup_api(user)
    if any(user.GetAsyncKeyState(key)&0x8000 for key in (1, 2, 4, 0x10, 0x11, 0x12, 0x1B)):
        raise RuntimeError('release buttons/modifiers/Escape before native acceptance')
    start = wintypes.POINT()
    if not user.GetCursorPos(ctypes.byref(start)): raise RuntimeError('cannot save physical cursor')
    output.mkdir(parents=True, exist_ok=False)
    results = []
    child = None
    try:
        for case in cases:
            print('NATIVE FEATURE '+case, flush=True)
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--case', case,
                       '--output', str(output/case), '--step-timeout', str(args.step_timeout),
                       '--case-timeout', str(args.case_timeout)]
            error = cleanup = None
            with tempfile.TemporaryDirectory(prefix='msd-native-features-620-') as scratch:
                environment = dict(os.environ, MYSCREENDRAW_FEATURE_PARENT_TEMP=scratch)
                with (output/(case+'.stdout.log')).open('w', encoding='utf-8') as stdout, \
                     (output/(case+'.stderr.log')).open('w', encoding='utf-8') as stderr:
                    child = subprocess.Popen(command, cwd=str(ROOT), stdout=stdout, stderr=stderr, env=environment)
                    child_pid = child.pid
                    try:
                        code = child.wait(timeout=args.case_timeout+20)
                    except subprocess.TimeoutExpired:
                        cleanup = terminate_owned_child(user, child, output/case)
                        code, error = 124, 'owned child hard timeout; inspect cleanup confirmation and partial evidence'
                    finally:
                        if child.poll() is None:
                            cleanup = terminate_owned_child(user, child, output/case)
                    child = None
            if cleanup is None:
                try:
                    state = json.loads((output/case/'input-state.json').read_text(encoding='utf-8'))
                    confirmed = state.get('pid') == child_pid and state.get('left_down') is False
                    cleanup = {'confirmed': confirmed, 'released': False,
                               'reason': 'child exit journal; no supervisor input after process exit'}
                except (ValueError, OSError) as exc:
                    cleanup = {'confirmed': False, 'released': False, 'reason': f'missing exit journal: {exc}'}
            if not cleanup['confirmed']:
                print('INPUT CLEANUP UNCONFIRMED: '+cleanup['reason'], file=sys.stderr, flush=True)
            report = output/case/'report.json'
            try: payload = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
            except (ValueError, OSError) as exc: payload = {}; error = f'invalid child report: {exc}'
            passed = code == 0 and payload.get('outcome') == 'passed' and cleanup['confirmed']
            results.append({'case': case, 'passed': passed, 'exit_code': code, 'error': error,
                            'cleanup': cleanup, 'report': str(report)})
            write_json(output/'summary.json', {'requested': cases, 'results': results,
                'passed': len(results) == len(cases) and all(row['passed'] for row in results),
                'private': True, 'scope': 'native source UI; no package, IPC, exports or OS integration acceptance'})
            if not passed: break  # Never blindly continue after obstruction/user intervention.
    finally:
        if child is not None and child.poll() is None:
            terminate_owned_child(user, child, output/case)
        # Restore only once the owned child has stopped. Never send untracked UPs.
        if not user.SetCursorPos(start.x, start.y):
            raise RuntimeError('failed to restore physical cursor after child exit')
        actual = wintypes.POINT()
        if not user.GetCursorPos(ctypes.byref(actual)) or abs(actual.x-start.x) > 3 or abs(actual.y-start.y) > 3:
            raise RuntimeError('physical cursor restore readback failed')
    return 0 if len(results) == len(cases) and all(row['passed'] for row in results) else 1


def self_check():
    source = Path(__file__).read_text(encoding='utf-8')
    tree = ast.parse(source); compile(tree, str(Path(__file__)), 'exec')
    for sibling in ('native_input_620.py', 'real_teaching_620.py'):
        path = Path(__file__).with_name(sibling)
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    forbidden = {'QTest', 'QMouseEvent', 'QWheelEvent', 'QDragEnterEvent', 'QDropEvent',
                 'sendEvent', 'postEvent', 'startDrag', 'dropEvent', 'render_page_pixmap',
                 'setCurrentRow', 'setCurrentIndex', 'setValue', 'scrollToItem', 'scrollToTop', 'grab'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name in forbidden: raise AssertionError(f'forbidden shortcut: {name}:{node.lineno}')
    results = calibrate_pixels()
    cleanup_cases = calibrate_cleanup()
    assert list(CASES) == ['thumbnails', 'boxes', 'c05.reorder.direct', 'c05.reorder.intermediate', 'c05.reorder.wrong']
    assert 'main' not in sys.modules and 'PyQt6.QtWidgets' not in sys.modules
    print(f'STATIC/IMAGE ONLY: syntax + forbidden-input audit + {len(results)} known-good/bad image checks + {cleanup_cases} fake-Win32 cleanup cases passed.')
    print('No Qt application, Win32 input, screenshot or real-screen acceptance ran.')
    return 0


def main_():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--case', action='append', choices=tuple(CASES))
    parser.add_argument('--chapter', choices=('c05.reorder',), help='all three independent reorder paths')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--step-timeout', type=float, default=90)
    parser.add_argument('--case-timeout', type=float, default=360)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.self_check: return self_check()
        if args.list:
            for case, detail in CASES.items(): print(f'{case}: {detail}')
            return 0
        if sum(bool(v) for v in (args.all, args.chapter, args.case)) != 1:
            parser.error('choose exactly one of --all, --chapter, --case (repeatable)')
        cases = list(CASES) if args.all else ([key for key in CASES if key.startswith(args.chapter+'.')]
                                            if args.chapter else list(dict.fromkeys(args.case)))
        if args.plan:
            for case in cases: print(f'{case}: {CASES[case]}')
            print('PLAN ONLY. Initial fixture setup allowed; all subsequent gestures are native. New private process per case.')
            return 0
        if args.output is None: parser.error('real runs require --output')
        if not math.isfinite(args.step_timeout) or not 10 <= args.step_timeout <= 180:
            parser.error('--step-timeout must be 10..180 seconds')
        if not math.isfinite(args.case_timeout) or not 30 <= args.case_timeout <= 1800:
            parser.error('--case-timeout must be 30..1800 seconds')
        private_output(args.output)
        if args.worker:
            if len(cases) != 1: parser.error('one case per private worker')
            return worker(args)
        return supervise(args, cases)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main_())
