# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in Win32 input/capture helpers. Importing this module sends no input.

Extends the 6.1 harness' PID guard, Qt/physical DPI conversion and OLE worker
pattern. Never use this module from normal pytest collection.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import time

from real_release_610 import NativeMouse, Harness


class NativeInput(NativeMouse):
    """Qt only supplies geometry; all buttons, keys, wheels and drags go to Win32."""

    def __init__(self, app, audit=None):
        super().__init__(app)
        self.audit = audit or (lambda row: None)
        self.cancelled = threading.Event()
        self.keys_down = set()
        self.workers = []
        self.errors = []
        self.deadline = float('inf')
        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user32.SetCursorPos.restype = wintypes.BOOL
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.restype = ctypes.c_int
        self.user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user32.GetAsyncKeyState.restype = ctypes.c_short
        self.user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostMessageW.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetAncestor.restype = wintypes.HWND
        self._expected_hwnd = None
        self.native_press = None
        self.press_hwnd = None
        self.physical_start = self.physical()

    def verify_position(self, x, y):
        actual = self.physical()
        if abs(actual.x-x) > 3 or abs(actual.y-y) > 3:
            raise RuntimeError(f'native cursor missed ({x},{y}): ({actual.x},{actual.y})')

    def verify_press_target(self):
        hwnd = self.point_hwnd()
        if not self.owner(hwnd):
            raise RuntimeError('refusing DOWN above foreign HWND')
        if self._expected_hwnd is not None:
            root = self.user32.GetAncestor(hwnd, 2)
            expected = self.user32.GetAncestor(self._expected_hwnd, 2)
            if not expected or root != expected:
                raise RuntimeError('native target changed/occluded after Qt hit test')
        point = self.physical()
        self.native_press = (point.x, point.y)
        self.press_hwnd = hwnd

    def physical(self):
        p = self.POINT()
        if not self.user32.GetCursorPos(ctypes.byref(p)):
            raise RuntimeError('GetCursorPos failed')
        return p

    def alive(self):
        # Physical Esc is an emergency stop; do not steal desktop input if the
        # user intervenes. Our own Escape is sent and released without pumping.
        if self.cancelled.is_set() or time.monotonic() > self.deadline:
            raise TimeoutError('native input deadline / cancellation')
        if self.user32.GetAsyncKeyState(0x1B) & 0x8000:
            self.cancelled.set()
            raise RuntimeError('physical Escape: native run aborted')
        if self.errors:
            raise RuntimeError(f'native worker failed: {self.errors[0]}')

    def pump(self, ms=50):
        deadline = time.monotonic() + ms / 1000
        while time.monotonic() < deadline:
            self.alive()
            self.app.processEvents()
            time.sleep(.005)

    def _log(self, kind, **values):
        p = self.physical()
        self.audit(dict(kind=kind, time=time.monotonic(), physical=[p.x, p.y],
                        hwnd=int(self.point_hwnd() or 0), **values))

    def move(self, point):
        self.alive()
        # QCursor.setPos performs per-monitor Qt logical -> Windows physical
        # conversion. NativeMouse verifies QCursor.pos; Win32 reads it back.
        super().move(point)
        p = self.physical()
        if not self.user32.SetCursorPos(p.x, p.y):
            raise RuntimeError('native pointer move failed')
        self.verify_position(p.x, p.y)
        self._log('move', logical=[point.x(), point.y()])

    def down_at(self, point):
        self.move(point)
        self.verify_press_target()
        self._log('left_down')
        self.user32.mouse_event(self.LEFTDOWN, 0, 0, 0, 0)
        self.down, self.press_point = True, point
        self.pump(35)

    def up(self):
        if self.down:
            # OLE may have transferred capture. Never drop over a foreign app:
            # return to the saved physical press position and verify it first.
            # All calls here are Win32 so this is safe from the OLE worker too.
            if not self.owner(self.point_hwnd()):
                if self.native_press is not None:
                    x, y = self.native_press
                    if not self.user32.SetCursorPos(x, y):
                        raise RuntimeError('cannot return to owned native press point')
                    self.verify_position(x, y)
                if not self.owner(self.point_hwnd()) and self.owner(self.press_hwnd):
                    # If the exact start is covered, try interior pixels of the
                    # original owned window; these are moves, never new presses.
                    rect = wintypes.RECT()
                    if self.user32.GetWindowRect(self.press_hwnd, ctypes.byref(rect)):
                        for fx, fy in ((.5,.5),(.25,.25),(.75,.25),(.25,.75),(.75,.75)):
                            x = round(rect.left+(rect.right-rect.left)*fx)
                            y = round(rect.top+(rect.bottom-rect.top)*fy)
                            if not self.user32.SetCursorPos(x,y): continue
                            self.verify_position(x,y)
                            if self.owner(self.point_hwnd()): break
                if not self.owner(self.point_hwnd()):
                    if self.owner(self.press_hwnd):
                        self.user32.PostMessageW(self.press_hwnd, 0x001F, 0, 0)  # teardown WM_CANCELMODE
                    self.cancelled.set()
                    self.errors.append('no owned release pixel; refusing foreign OLE drop')
                    raise RuntimeError(self.errors[-1])
            self.user32.mouse_event(self.LEFTUP, 0, 0, 0, 0)
            self.down = False
            self._log('left_up')

    def click_point(self, point):
        self.down_at(point)
        try:
            self.up()
            self.pump(90)
        finally:
            self.up()

    def _native_target_at(self, widget, point):
        """Read-only DPI-aware corroboration, without moving the real cursor."""
        window = widget.window()
        expected = int(window.winId())
        client = self.POINT(0, 0)
        user = self.user32
        user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(self.POINT)]
        user.ClientToScreen.restype = wintypes.BOOL
        if not user.ClientToScreen(expected, ctypes.byref(client)):
            raise RuntimeError('ClientToScreen failed during transparent-overlay hit test')
        local = window.mapFromGlobal(point)
        ratio = window.devicePixelRatioF()
        native = self.POINT(client.x+round(local.x()*ratio), client.y+round(local.y()*ratio))
        actual = user.WindowFromPoint(native)
        actual_root = user.GetAncestor(actual, 2) if actual else None
        expected_root = user.GetAncestor(expected, 2)
        detail = {'native_point': [native.x, native.y], 'native_hwnd': int(actual or 0),
                  'native_root': int(actual_root or 0), 'expected_root': int(expected_root or 0),
                  'dpr': ratio}
        return bool(self.owner(actual) and expected_root and actual_root == expected_root), detail

    def hit(self, widget, point):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        if not widget.isVisible() or not widget.isEnabled():
            raise RuntimeError(f'target hidden/disabled: {widget.objectName()} {type(widget).__name__}')
        hit = QApplication.widgetAt(point)
        matched = hit is widget or (hit is not None and widget.isAncestorOf(hit))
        native_detail = None
        if not matched:
            hit_window = hit.window() if hit is not None else None
            # QWidget.widgetAt can return None/the transparent top-level while
            # Win32 correctly routes through a border-only HighlightOverlay.
            # Never hide that overlay, modify flags or ignore an opaque blocker.
            transparent = (hit_window is not None
                and bool(hit_window.windowFlags() & Qt.WindowType.WindowTransparentForInput)
                and hit_window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
            if hit is None or transparent:
                window = widget.window()
                local = window.mapFromGlobal(point)
                within = window.rect().contains(local)
                child = window.childAt(local) if within else None
                if child is None and within: child = window
                child_matches = child is widget or (child is not None and widget.isAncestorOf(child))
                native_matches, native_detail = self._native_target_at(widget, point)
                if child_matches and native_matches:
                    matched = True
                    self.audit({'kind': 'transparent_qt_hit_corroborated', 'time': time.monotonic(),
                                'qt_hit': type(hit).__name__ if hit is not None else None,
                                'target': type(widget).__name__, **native_detail})
            if not matched:
                raise RuntimeError(f'Qt target occluded: wanted {type(widget).__name__}'
                    f'({widget.objectName()!r}) in {type(widget.window()).__name__}, '
                    f'hit {type(hit).__name__ if hit is not None else None}'
                    f'({hit.objectName() if hit is not None else ""!r}), '
                    f'input_transparent={transparent}, point=({point.x()},{point.y()}), '
                    f'native={native_detail}')
        # The worker still verifies the actual owned native root immediately
        # before DOWN. This fallback does not weaken that independent guard.
        self._expected_hwnd = int(widget.window().winId())

    def click(self, widget):
        from PyQt6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton
        rect = widget.rect()
        if isinstance(widget, QCheckBox):
            option = QStyleOptionButton(); widget.initStyleOption(option)
            rect = widget.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, widget)
        point = widget.mapToGlobal(rect.center())
        self.hit(widget, point)
        self.click_point(point)

    def foreground(self, expected=None):
        self.alive()
        hwnd = self.user32.GetForegroundWindow()
        if not self.owner(hwnd) or (expected is not None and hwnd != expected):
            raise RuntimeError(f'refusing key: foreground HWND {hwnd!r} is not expected owned window')
        return hwnd

    def focus_window(self, widget):
        """Activation is Win32, not QWidget.setFocus or a Qt keyboard event."""
        hwnd = int(widget.window().winId())
        if not self.owner(hwnd):
            raise RuntimeError('cannot activate a foreign window')
        self.user32.SetForegroundWindow(hwnd)
        self.pump(60)
        self.foreground()

    def chord(self, *keys, expected=None):
        """Virtual-key keyboard input, checked immediately before every DOWN."""
        try:
            for key in keys:
                self.foreground(expected)
                self.user32.keybd_event(key, 0, 0, 0)
                self.keys_down.add(key)
                self._log('key_down', vk=key)
                time.sleep(.008)
        finally:
            for key in reversed(keys):
                if key in self.keys_down:
                    self.user32.keybd_event(key, 0, 2, 0)
                    self.keys_down.discard(key)
                    self._log('key_up', vk=key)

    def text(self, text, expected=None):
        """SendInput Unicode, no clipboard mutation or direct editor assignment."""
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                        ('dwExtraInfo', ctypes.c_size_t)]
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                        ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                        ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class INPUTUNION(ctypes.Union):
            _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
        class INPUT(ctypes.Structure):
            _anonymous_ = ('u',)
            _fields_ = [('type', wintypes.DWORD), ('u', INPUTUNION)]
        send = self.user32.SendInput
        send.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        send.restype = wintypes.UINT
        units = text.encode('utf-16-le')
        for offset in range(0, len(units), 2):
            self.foreground(expected)
            code = int.from_bytes(units[offset:offset+2], 'little')
            pair = (INPUT * 2)()
            for index, flags in enumerate((4, 6)):
                pair[index].type = 1
                pair[index].ki = KEYBDINPUT(0, code, flags, 0, 0)
            if send(2, pair, ctypes.sizeof(INPUT)) != 2:
                # A partial SendInput must not leave a Unicode key pressed.
                release = INPUT(); release.type = 1; release.ki = KEYBDINPUT(0, code, 6, 0, 0)
                send(1, ctypes.byref(release), ctypes.sizeof(INPUT))
                raise RuntimeError('SendInput Unicode failed (possibly UIPI)')
            self._log('unicode_pair', unit=code)
            time.sleep(.008)

    def wheel(self, widget, ticks):
        point = widget.mapToGlobal(widget.rect().center())
        self.hit(widget, point)
        self.move(point)
        if not self.owner(self.point_hwnd()):
            raise RuntimeError('refusing wheel above foreign HWND')
        self.foreground()
        self.user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong(ticks * 120).value, 0)
        self._log('wheel', ticks=ticks)
        self.pump(140)

    def path(self, points, *, hold_ms=0, interval=.035):
        """True held mouse path, including OLE drag loops; no Qt in the worker."""
        points = list(points)
        if len(points) < 2 or hold_ms > 10000:
            raise ValueError('a bounded path with at least two points is required')
        # Convert before pressing, exactly as 6.1 NativeMouse.drag does. Only
        # endpoints need conversion; Qt documents use one monitor per gesture.
        native = []
        for point in (points[0], points[-1]):
            self.move(point)
            p = self.physical(); native.append((p.x, p.y))
        start, end = native
        logical_delta = points[-1] - points[0]
        # Use the current screen's devicePixelRatio for intermediate curve points;
        # calibrated endpoints detect a wrong scale instead of pressing blindly.
        screen = self.app.screenAt(points[0])
        scale = screen.devicePixelRatio() if screen is not None else 1.0
        if (abs(end[0]-start[0]-logical_delta.x()*scale) > 3
                or abs(end[1]-start[1]-logical_delta.y()*scale) > 3):
            raise RuntimeError('gesture crosses incompatible monitor DPI boundaries')
        physical = [(start[0]+round((p.x()-points[0].x())*scale),
                     start[1]+round((p.y()-points[0].y())*scale)) for p in points]
        self.move(points[0])
        done = threading.Event()
        def sequence():
            try:
                self.alive()
                self.verify_press_target()
                self._log('left_down', gesture=True)
                self.user32.mouse_event(self.LEFTDOWN, 0, 0, 0, 0)
                self.down = True
                time.sleep(.055)
                for x, y in physical[1:]:
                    self.alive()
                    if not self.user32.SetCursorPos(x, y):
                        raise RuntimeError('native path move failed')
                    self.verify_position(x, y)
                    time.sleep(interval)
                until = time.monotonic() + hold_ms/1000
                while time.monotonic() < until:
                    self.alive(); time.sleep(.015)
            except Exception as exc:
                self.errors.append(repr(exc))
            finally:
                # Always attempt release, even if OLE swallowed GUI timers.
                try: self.up()
                except Exception as exc: self.errors.append(repr(exc))
                finally: done.set()
        worker = threading.Thread(target=sequence, name='bounded-620-native-path', daemon=True)
        self.workers.append(worker); worker.start()
        try:
            while not done.is_set():
                self.pump(15)
        finally:
            if not done.is_set(): self.cancelled.set()
            worker.join(2)
            self.up()
        self.alive()
        self.pump(160)

    def drag(self, source, destination, hold_ms=0):
        points = [source + (destination-source)*i/20 for i in range(21)]
        self.path(points, hold_ms=hold_ms)

    @contextmanager
    def file_chooser(self, path, *, timeout=20):
        """Native Windows common dialog: Alt+N, select filename, type, Enter.

        The worker is armed BEFORE the toolbar click: Qt timers alone can starve
        inside IFileDialog/OLE. It only reads HWNDs and sends Win32 input. A Qt
        fallback is deliberately not faked; absence of the dialog fails closed.
        """
        done, stop = threading.Event(), threading.Event()
        failures = []
        path = str(Path(path).resolve())
        def answer():
            try:
                deadline = time.monotonic() + timeout
                hwnd = None
                while time.monotonic() < deadline and not stop.is_set():
                    self.alive()
                    candidate = self.user32.GetForegroundWindow()
                    name = ctypes.create_unicode_buffer(256)
                    if self.owner(candidate):
                        self.user32.GetClassNameW(candidate, name, len(name))
                        if name.value == '#32770':
                            hwnd = candidate; break
                    time.sleep(.03)
                if hwnd is None:
                    raise TimeoutError('native file chooser did not appear')
                time.sleep(.25)
                self.chord(0x12, 0x4E, expected=hwnd)  # Alt+N: File name (also zh-CN).
                time.sleep(.12)
                self.chord(0x11, 0x41, expected=hwnd)
                self.text(path, expected=hwnd)
                self.chord(0x0D, expected=hwnd)
                self._log('file_chooser_submitted', path=path)
            except Exception as exc:
                failures.append(exc)
                self.errors.append(repr(exc))
                # WM_CLOSE is cleanup only, never counted as an input operation.
                hwnd = self.user32.GetForegroundWindow()
                if self.owner(hwnd):
                    self.user32.PostMessageW(hwnd, 0x0010, 0, 0)
            finally:
                done.set()
        worker = threading.Thread(target=answer, name='bounded-620-file-chooser', daemon=True)
        self.workers.append(worker); worker.start()
        try:
            yield
            while not done.is_set(): self.pump(20)
            if failures: raise failures[0]
        finally:
            stop.set()
            worker.join(timeout+1)
            if worker.is_alive():
                self.cancelled.set()
                raise TimeoutError('file chooser worker did not stop')

    def release_all(self):
        try: self.up()
        except Exception as exc: self.errors.append(repr(exc))
        for key in tuple(self.keys_down):
            self.user32.keybd_event(key, 0, 2, 0)
            self.keys_down.discard(key)

    def restore(self):
        self.cancelled.set()
        self.release_all()
        for worker in self.workers:
            if worker is not threading.current_thread(): worker.join(1)
        self.user32.SetCursorPos(self.physical_start.x, self.physical_start.y)


class NativeHarness(Harness):
    """Keep 6.1 check reporting, replace every shortcut with genuine input."""

    def __init__(self, app, output, audit=None):
        self.app, self.output, self.checks = app, Path(output), []
        self.mouse = NativeInput(app, audit)

    def require(self, name, condition, detail=''):
        self.check(name, condition, detail)
        if not condition: raise AssertionError(f'{name}: {detail}')

    def scroll_to(self, panel, widget):
        # Unlike 6.1, NEVER setValue on the scroll bar. Native wheel is required.
        from PyQt6.QtWidgets import QAbstractScrollArea
        area = widget.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        last_error = None
        for _ in range(24):
            point = widget.mapToGlobal(widget.rect().center())
            try:
                self.mouse.hit(widget, point)
                if area is None or area.viewport().rect().contains(area.viewport().mapFromGlobal(point)):
                    return
            except RuntimeError as exc:
                last_error = exc
                if area is None:
                    raise RuntimeError(f'target has no scrollable ancestor; original hit error: {exc}') from exc
            if area is None:
                raise RuntimeError('target outside its available hit region with no scrollable ancestor')
            local = area.viewport().mapFromGlobal(point)
            self.mouse.wheel(area.viewport(), -2 if local.y() > area.viewport().height()/2 else 2)
        raise TimeoutError(f'native wheel could not reveal control; last hit error: {last_error}') from last_error

    def combo(self, combo, data):
        index = combo.findData(data)
        if index < 0: raise ValueError(f'combo data not found: {data}')
        self.mouse.click(combo)
        self.mouse.pump(200)
        # Keyboard navigation remains usable for rows outside the popup viewport.
        self.mouse.chord(0x24)  # Home
        for _ in range(index): self.mouse.chord(0x28)
        self.mouse.chord(0x0D)
        self.mouse.pump(150)
        self.require('native combo choice', combo.currentData() == data, data)

    def number(self, widget, value):
        self.mouse.click(widget)
        self.mouse.chord(0x11, 0x41)
        self.mouse.text(str(value))
        self.mouse.chord(0x0D)
        self.mouse.pump(100)

    def slider(self, slider, value, *, exact=False):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtWidgets import QStyle, QStyleOptionSlider
        option = QStyleOptionSlider(); slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                              QStyle.SubControl.SC_SliderHandle, slider)
        if exact:
            # Exact-value lessons cannot rely on pixel quantization of a narrow
            # slider. Real Home/arrow keys retain full numeric precision.
            point = slider.mapToGlobal(handle.center())
            self.mouse.hit(slider, point); self.mouse.click_point(point)
            self.mouse.chord(0x24)
            for _ in range((value-slider.minimum())//slider.singleStep()): self.mouse.chord(0x27)
            self.mouse.pump(120)
            self.require('exact native slider value', slider.value() == value, slider.value())
            return
        # Arrow keys avoid valueChanged committing an intermediate drag value,
        # while the initial real drag demonstrates the native slider path.
        lo, hi = slider.minimum(), slider.maximum()
        value = max(lo, min(hi, value))
        if slider.orientation() == Qt.Orientation.Horizontal:
            target = QPoint(round(handle.width()/2 + (slider.width()-handle.width())*(value-lo)/max(1,hi-lo)), handle.center().y())
        else:
            target = QPoint(handle.center().x(), round(handle.height()/2 + (slider.height()-handle.height())*(hi-value)/max(1,hi-lo)))
        start = slider.mapToGlobal(handle.center()); end = slider.mapToGlobal(target)
        self.mouse.hit(slider, start); self.mouse.hit(slider, end)
        self.mouse.drag(start, end)

    def capture(self, name, widget):
        """Real composed desktop pixels, including layered windows (CAPTUREBLT).

        Output is PRIVATE; no QWidget.grab/QScreen.grabWindow. The screenshot
        alone is evidence, not an automatic claim of no overlap.
        """
        from PyQt6.QtGui import QImage
        user, gdi = self.mouse.user32, ctypes.windll.gdi32
        user.GetDC.argtypes = [wintypes.HWND]; user.GetDC.restype = wintypes.HDC
        user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]; user.ReleaseDC.restype = ctypes.c_int
        gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]; gdi.CreateCompatibleDC.restype = wintypes.HDC
        gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]; gdi.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]; gdi.SelectObject.restype = wintypes.HGDIOBJ
        gdi.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
        gdi.BitBlt.restype = wintypes.BOOL
        gdi.DeleteDC.argtypes = [wintypes.HDC]; gdi.DeleteDC.restype = wintypes.BOOL
        gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]; gdi.DeleteObject.restype = wintypes.BOOL
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                        ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                        ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                        ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]
        gdi.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
        gdi.GetDIBits.restype = ctypes.c_int
        rect = wintypes.RECT()
        hwnd = int(widget.window().winId())
        if not self.mouse.owner(hwnd) or not user.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError('capture target is not an owned live native window')
        width, height = rect.right-rect.left, rect.bottom-rect.top
        if not 0 < width*height <= 50_000_000:
            raise RuntimeError('invalid capture size')
        screen = user.GetDC(None); memory = bitmap = previous = None
        try:
            memory = gdi.CreateCompatibleDC(screen)
            bitmap = gdi.CreateCompatibleBitmap(screen, width, height)
            if not memory or not bitmap: raise RuntimeError('GDI capture allocation failed')
            previous = gdi.SelectObject(memory, bitmap)
            if not gdi.BitBlt(memory, 0, 0, width, height, screen, rect.left, rect.top, 0x00CC0020 | 0x40000000):
                raise RuntimeError('CAPTUREBLT failed')
            gdi.SelectObject(memory, previous); previous = None
            header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
            pixels = ctypes.create_string_buffer(width*height*4)
            if gdi.GetDIBits(memory, bitmap, 0, height, pixels, ctypes.byref(header), 0) != height:
                raise RuntimeError('GetDIBits failed')
            image = QImage(pixels.raw, width, height, width*4, QImage.Format.Format_RGB32).copy()
            if image.isNull() or not image.save(str(self.output/name), 'PNG'):
                raise RuntimeError('private screenshot save failed')
        finally:
            if previous: gdi.SelectObject(memory, previous)
            if bitmap: gdi.DeleteObject(bitmap)
            if memory: gdi.DeleteDC(memory)
            if screen: user.ReleaseDC(None, screen)
        return {'file': name, 'physical_rect': [rect.left, rect.top, width, height],
                'capture': 'BitBlt(SRCCOPY|CAPTUREBLT)', 'hwnd': hwnd}
