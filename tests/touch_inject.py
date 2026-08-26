# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Windows multitouch on a machine with no touch screen.

Wraps the Win32 Touch Injection API (InitializeTouchInjection / InjectTouchInput,
Windows 8+). Injected contacts travel the same path as a physical digitizer --
HID -> WM_POINTER -> Qt -> QTouchEvent -- so this exercises the production input
path rather than faking events at the Qt layer.

Two hard requirements, both learned the hard way:

1. init_injection() MUST run before QApplication is constructed. Qt enumerates
   input devices exactly once, at QApplication construction. InitializeTouchInjection
   is what makes Windows report a digitizer (SM_DIGITIZER gains NID_MULTI_INPUT).
   Initialize after QApplication and Qt permanently routes WM_POINTER through mouse
   synthesis -- you get mousePressEvent, never QTouchEvent, no matter what you inject.

2. Injection is positional, not focus-based. It hits whichever window owns that
   screen pixel, so the target must genuinely be topmost there. Use
   raise_topmost(widget) and aim at the widget's real frameGeometry.
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

PT_TOUCH = 2
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000
TOUCH_MASK_CONTACTAREA = 0x00000001
TOUCH_MASK_PRESSURE = 0x00000004
TOUCH_FEEDBACK_INDIRECT = 0x2

DOWN = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
MOVE = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
UP = POINTER_FLAG_UP

HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x0040


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", wintypes.DWORD),
        ("pointerId", wintypes.UINT),
        ("frameId", wintypes.UINT),
        ("pointerFlags", wintypes.UINT),
        ("sourceDevice", wintypes.HANDLE),
        ("hwndTarget", wintypes.HWND),
        ("ptPixelLocation", wintypes.POINT),
        ("ptHimetricLocation", wintypes.POINT),
        ("ptPixelLocationRaw", wintypes.POINT),
        ("ptHimetricLocationRaw", wintypes.POINT),
        ("dwTime", wintypes.DWORD),
        ("historyCount", wintypes.UINT),
        ("InputData", ctypes.c_int32),
        ("dwKeyStates", wintypes.DWORD),
        ("PerformanceCount", ctypes.c_uint64),
        ("ButtonChangeType", ctypes.c_int),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO),
        ("touchFlags", wintypes.UINT),
        ("touchMask", wintypes.UINT),
        ("rcContact", wintypes.RECT),
        ("rcContactRaw", wintypes.RECT),
        ("orientation", wintypes.UINT),
        ("pressure", wintypes.UINT),
    ]


class TouchInjectionUnavailable(RuntimeError):
    """Raised when this machine or session cannot inject touch."""


def init_injection(max_contacts=10):
    """Call BEFORE QApplication() exists. Safe to call once per process."""
    if not hasattr(user32, "InitializeTouchInjection"):
        raise TouchInjectionUnavailable("InitializeTouchInjection missing (pre-Win8)")
    if not user32.InitializeTouchInjection(max_contacts, TOUCH_FEEDBACK_INDIRECT):
        raise TouchInjectionUnavailable(ctypes.WinError(ctypes.GetLastError()))


def qt_sees_touchscreen():
    """True if Qt enumerated a touch device. Requires QApplication to exist."""
    from PyQt6.QtGui import QInputDevice

    return any(d.type() == QInputDevice.DeviceType.TouchScreen
               for d in QInputDevice.devices())


def make_contact(contact_id, x, y, flags, radius=4, pressure=32000):
    """One finger at a screen pixel."""
    touch = POINTER_TOUCH_INFO()
    touch.pointerInfo.pointerType = PT_TOUCH
    touch.pointerInfo.pointerId = contact_id
    touch.pointerInfo.pointerFlags = flags
    touch.pointerInfo.ptPixelLocation.x = int(x)
    touch.pointerInfo.ptPixelLocation.y = int(y)
    touch.touchFlags = 0
    touch.touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_PRESSURE
    touch.pressure = pressure
    touch.rcContact.left = int(x) - radius
    touch.rcContact.right = int(x) + radius
    touch.rcContact.top = int(y) - radius
    touch.rcContact.bottom = int(y) + radius
    return touch


def _inject_once(contacts):
    array = (POINTER_TOUCH_INFO * len(contacts))(*contacts)
    if not user32.InjectTouchInput(len(contacts), array):
        raise TouchInjectionUnavailable(ctypes.WinError(ctypes.GetLastError()))


def inject(contacts, retry=True):
    """Send one frame. Every contact still down must appear in every frame.

    Two transient failures are worth retrying rather than surfacing:

    * ERROR_TIMEOUT (1460) on the very first frame after InitializeTouchInjection
      -- the injection device needs a moment to come up.
    * ERROR_INVALID_PARAMETER (87) when a previous gesture died between its DOWN
      and UP frames: Windows still believes those contacts are down, and a fresh
      DOWN for the same ids is then rejected.

    Both clear once the stuck contacts are lifted and the device settles.
    """
    try:
        _inject_once(contacts)
        return
    except TouchInjectionUnavailable:
        if not retry:
            raise
    # Settle and try once more. Do NOT try to "reset" by injecting UP for ids
    # that are not down -- InjectTouchInput rejects that, and issuing those
    # rejected frames is itself enough to make the next legitimate DOWN fail.
    time.sleep(0.12)
    _inject_once(contacts)


def raise_topmost(widget):
    """Put widget at the top of the OS Z order so injected pixels reach it."""
    geo = widget.frameGeometry()
    user32.SetWindowPos(int(widget.winId()), HWND_TOPMOST,
                        geo.x(), geo.y(), geo.width(), geo.height(),
                        SWP_SHOWWINDOW)


def owns_pixel(widget, x, y):
    """True if widget's native window is the one at that screen pixel."""
    return user32.WindowFromPoint(wintypes.POINT(int(x), int(y))) == int(widget.winId())


def drag_two_fingers(a_start, b_start, a_end, b_end, steps=5, pump=None):
    """Inject a full two-finger gesture: down, interpolated moves, up.

    pump: optional callable invoked after every frame (pass app.processEvents).
    Without it Windows and Qt coalesce the MOVE frames into a single
    TouchUpdate, so the widget sees one big jump instead of a path.
    """
    (ax, ay), (bx, by) = a_start, b_start
    (ax2, ay2), (bx2, by2) = a_end, b_end

    def frame(contacts):
        inject(contacts)
        if pump is not None:
            pump()

    frame([make_contact(0, ax, ay, DOWN), make_contact(1, bx, by, DOWN)])
    try:
        for i in range(1, steps + 1):
            t = i / steps
            frame([make_contact(0, ax + (ax2 - ax) * t, ay + (ay2 - ay) * t, MOVE),
                   make_contact(1, bx + (bx2 - bx) * t, by + (by2 - by) * t, MOVE)])
    finally:
        # Always lift. Leaving contacts down makes every later DOWN fail with 87.
        frame([make_contact(0, ax2, ay2, UP), make_contact(1, bx2, by2, UP)])


def drag_one_finger(start, end, steps=5, pump=None, contact_id=0):
    """Inject a single-contact gesture: down, interpolated moves, up."""
    (x, y), (x2, y2) = start, end

    def frame(contacts):
        inject(contacts)
        if pump is not None:
            pump()

    frame([make_contact(contact_id, x, y, DOWN)])
    try:
        for i in range(1, steps + 1):
            t = i / steps
            frame([make_contact(contact_id, x + (x2 - x) * t, y + (y2 - y) * t, MOVE)])
    finally:
        frame([make_contact(contact_id, x2, y2, UP)])
