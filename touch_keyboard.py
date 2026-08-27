# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Show and hide an on-screen keyboard, so the text box can be filled without hardware keys.

Why use an OS keyboard rather than drawing our own alphanumeric pad: TabTip
already carries every IME, all 8 UI languages, handwriting recognition and emoji.
Re-implementing that would be strictly worse. We only add the part it lacks --
maths and Greek symbols -- in our own panel above it.

Two backends, because neither covers every machine:

* **TabTip** -- the modern touch keyboard. Preferred where it actually appears,
  which in practice means machines with a touch digitizer.
* **osk.exe** -- the classic On-Screen Keyboard. Ancient, but it shows up on any
  desktop and sends real WM_KEYDOWN/WM_CHAR to the focused window, which is all
  we need. Used when TabTip declines to appear.

Three Windows details drive the shape of this module; all three were found the
hard way, and getting any of them wrong makes the keyboard button do nothing:

1. **Neither exe can be started with CreateProcess.** Both TabTip.exe and osk.exe
   are marked as requiring elevation, so ``subprocess.Popen`` fails outright with
   ``WinError 740`` in a normal user session. ``ShellExecuteW`` is the launcher
   that works, because it goes through the shell's UAC path. 5.3.0 and 5.3.1 used
   Popen, so this half never worked at all.
2. **ITipInvocation is only registered while TabTip.exe is already running.**
   ``CoCreateInstance`` returns ``REGDB_E_CLASSNOTREG`` (0x80040154) otherwise. So
   the COM call cannot bootstrap the keyboard -- the process has to be up first.
   Combined with (1) this produced a deadlock that hid behind session state: if
   something else had started TabTip earlier in the login session the button
   worked, and after a reboot the identical build failed every time.
3. **On Windows 10 1809+ the visible keyboard is not the window you would guess.**
   ``IPTip_Main_Window`` still exists but is a stub with a ``0,0,0,0`` rect; the
   real surface belongs to ``TextInputHost.exe`` and is a ``CoreWindow`` that is
   *DWM-cloaked* rather than hidden when down. Checking ``IsWindowVisible`` on the
   stub therefore reports "not visible" forever, which also silently broke the
   panel's keep-clear-of-the-keyboard logic.

Everything here is best-effort: a classroom PC may have the tablet input service
disabled by policy, so every entry point reports success as a bool (or None) and
never raises.
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

TABTIP_PATHS = (
    r"C:\Program Files\Common Files\microsoft shared\ink\TabTip.exe",
    r"C:\Program Files\Common Files\Microsoft Shared\ink\TabTip.exe",
)
OSK_PATHS = (
    r"C:\Windows\System32\osk.exe",
    # A 32-bit process sees System32 redirected to SysWOW64, where osk.exe is
    # absent; Sysnative is the un-redirected door back to the real System32.
    r"C:\Windows\Sysnative\osk.exe",
)

TABTIP_WINDOW_CLASS = "IPTip_Main_Window"
TABTIP_CORE_CLASS = "Windows.UI.Core.CoreWindow"
TABTIP_CORE_TITLE = "Microsoft Text Input Application"
OSK_WINDOW_CLASS = "OSKMainClass"

# ITipInvocation: {4CE576FA-83DC-4F88-951C-9D0782B4E376}
# IID_ITipInvocation: {37c994e7-432b-4834-a2f7-dce1f13b834b}
_CLSID_UIHostNoLaunch = "{4CE576FA-83DC-4F88-951C-9D0782B4E376}"
_IID_ITipInvocation = "{37c994e7-432b-4834-a2f7-dce1f13b834b}"

CLSCTX_LOCAL_SERVER = 0x4
WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060
SW_SHOWNOACTIVATE = 4
DWMWA_CLOAKED = 14
SM_DIGITIZER = 94
SM_MAXIMUMTOUCHES = 95

# How long to let a freshly launched keyboard turn into a visible window.
LAUNCH_SETTLE_S = 0.6
VISIBLE_TIMEOUT_S = 2.5


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text):
    guid = _GUID()
    ole32 = ctypes.windll.ole32
    ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
    return guid


def _first_existing(paths):
    for path in paths:
        try:
            if os.path.exists(path):
                return path
        except Exception:
            continue
    return None


def available():
    """True if some on-screen keyboard looks usable on this machine."""
    if not sys.platform.startswith("win"):
        return False
    return bool(_first_existing(TABTIP_PATHS) or _first_existing(OSK_PATHS))


def has_touch():
    """Whether this machine reports a touch digitizer.

    Windows suppresses TabTip on plain desktops, so this decides which backend to
    reach for first -- and lets the UI say *why* rather than just "unavailable".
    """
    try:
        user32 = ctypes.windll.user32
        if user32.GetSystemMetrics(SM_MAXIMUMTOUCHES) > 0:
            return True
        # 0x80 NID_READY | 0x40 NID_MULTI_INPUT | 0x02 NID_INTEGRATED_TOUCH
        return bool(user32.GetSystemMetrics(SM_DIGITIZER) & 0xC2)
    except Exception:
        return False


def _is_cloaked(hwnd):
    """DWM cloaking: the modern way a shell window is 'not really there'."""
    try:
        value = ctypes.c_int(0)
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(value), 4)
        if result != 0:
            return False
        return value.value != 0
    except Exception:
        return False


def _window_rect(hwnd):
    try:
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        return None


def _showing(hwnd):
    """A window counts as showing only if it is visible, uncloaked and has area.

    All three matter: the TabTip stub passes the first test but has no area, and
    the TextInputHost CoreWindow passes the first two while cloaked.
    """
    if not hwnd:
        return False
    try:
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return False
    except Exception:
        return False
    if _is_cloaked(hwnd):
        return False
    rect = _window_rect(hwnd)
    return bool(rect and rect[2] > 0 and rect[3] > 0)


def _find(window_class, title=None):
    try:
        return ctypes.windll.user32.FindWindowW(window_class, title) or 0
    except Exception:
        return 0


def _candidates():
    """(backend, hwnd) for every keyboard window that currently exists."""
    found = []
    for name, cls, title in (
        ("tabtip", TABTIP_CORE_CLASS, TABTIP_CORE_TITLE),
        ("tabtip", TABTIP_WINDOW_CLASS, None),
        ("osk", OSK_WINDOW_CLASS, None),
    ):
        hwnd = _find(cls, title)
        if hwnd:
            found.append((name, hwnd))
    return found


def backend():
    """Which keyboard is on screen right now: 'tabtip', 'osk' or None."""
    for name, hwnd in _candidates():
        if _showing(hwnd):
            return name
    return None


def is_visible():
    """Whether any on-screen keyboard is actually occupying screen space."""
    return backend() is not None


def tabtip_running():
    """Whether TabTip.exe is up -- the precondition for ITipInvocation existing."""
    return bool(_find(TABTIP_WINDOW_CLASS) or _find(TABTIP_CORE_CLASS, TABTIP_CORE_TITLE))


def launch_allowed():
    """Whether this process may spawn a keyboard onto the real screen.

    A keyboard is a system-wide window: it lands on the user's actual display no
    matter how headless *we* are. The test suite runs on the offscreen platform
    precisely so it cannot disturb the screen, so launching there would break that
    promise -- and a real keyboard's rect would also fight the fake ones the panel
    placement tests inject. MYSCREENDRAW_NO_KEYBOARD=1 is the explicit override.
    """
    if os.environ.get("MYSCREENDRAW_NO_KEYBOARD") == "1":
        return False
    return os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen"


def _shell_execute(path):
    """Launch via the shell, which is the only way these two exes will start.

    SW_SHOWNOACTIVATE keeps the keyboard from stealing activation from the panel
    that is about to receive its characters.
    """
    if not launch_allowed():
        return False
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", path, None, None, SW_SHOWNOACTIVATE)
        # ShellExecuteW returns >32 on success; anything else is an error code.
        return int(result) > 32
    except Exception:
        return False


def _invoke_com():
    """Ask the shell to toggle the touch keyboard through ITipInvocation."""
    if not launch_allowed():
        return False
    try:
        ole32 = ctypes.windll.ole32
    except Exception:
        return False
    try:
        if ole32.CoInitialize(None) < 0:
            return False
    except Exception:
        return False
    try:
        interface = ctypes.c_void_p()
        result = ole32.CoCreateInstance(
            ctypes.byref(_guid(_CLSID_UIHostNoLaunch)), None, CLSCTX_LOCAL_SERVER,
            ctypes.byref(_guid(_IID_ITipInvocation)), ctypes.byref(interface))
        if result < 0 or not interface:
            return False
        # vtable slot 3 is Toggle(HWND) -- slots 0..2 are the IUnknown methods.
        vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        toggle_address = vtable[0][3]
        toggle = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(toggle_address)
        desktop = ctypes.windll.user32.GetDesktopWindow()
        return toggle(interface, ctypes.c_void_p(desktop)) >= 0
    except Exception:
        return False
    finally:
        try:
            ole32.CoUninitialize()
        except Exception:
            pass


def _wait_showing(timeout=LAUNCH_SETTLE_S):
    """Poll briefly for a keyboard window to appear. Returns the backend or None."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        name = backend()
        if name:
            return name
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.05)


def show_tabtip():
    """Best effort at raising TabTip. Returns True if the attempt was made.

    Order matters and is not obvious: the process must exist before the COM class
    is registered, so a cold machine needs the exe launched *first* and the COM
    toggle issued after. Conversely the toggle is a *toggle*, so it must not be
    fired when the keyboard is already showing.
    """
    if backend() == "tabtip":
        return True
    launched = False
    if not tabtip_running():
        path = _first_existing(TABTIP_PATHS)
        if path and _shell_execute(path):
            launched = True
            # Give the process time to register ITipInvocation before toggling.
            _wait_showing(LAUNCH_SETTLE_S)
    if backend() == "tabtip":
        return True
    return _invoke_com() or launched


def show_osk():
    """Raise the classic On-Screen Keyboard. Returns True if the attempt was made."""
    if backend() == "osk":
        return True
    path = _first_existing(OSK_PATHS)
    if not path:
        return False
    return _shell_execute(path)


def show(prefer=None):
    """Bring some on-screen keyboard up. Returns True if an attempt succeeded.

    A True result means "a keyboard was asked to appear", not "a keyboard is on
    screen" -- the shell takes a moment, and callers should re-check
    :func:`is_visible` on a timer rather than block the UI thread here.

    TabTip is tried first on touch machines and skipped on plain desktops, where
    it reliably reports success and then stays cloaked; osk.exe is the backend
    that actually shows up there.
    """
    if not available() or not launch_allowed():
        return False
    if is_visible():
        return True
    first = prefer or ("tabtip" if has_touch() else "osk")
    order = ("tabtip", "osk") if first == "tabtip" else ("osk", "tabtip")
    attempted = False
    for name in order:
        started = show_tabtip() if name == "tabtip" else show_osk()
        attempted = attempted or started
        if not started:
            continue
        if _wait_showing(LAUNCH_SETTLE_S):
            return True
        # The attempt was accepted but nothing appeared. Fall through to the other
        # backend: on a non-touch desktop TabTip reports success every time and
        # then stays cloaked forever, which is exactly the case that must not end
        # the search here.
    return attempted


def hide():
    """Close whichever on-screen keyboard is up."""
    closed = False
    for _name, hwnd in _candidates():
        if not _showing(hwnd):
            continue
        try:
            ctypes.windll.user32.PostMessageW(
                wintypes.HWND(hwnd), WM_SYSCOMMAND, SC_CLOSE, 0)
            closed = True
        except Exception:
            continue
    return closed


def keyboard_rect():
    """Screen rect the keyboard occupies, or None.

    The symbol panel has to sit above the keyboard rather than under it, and the
    text box being edited must not end up hidden behind either.
    """
    for _name, hwnd in _candidates():
        if _showing(hwnd):
            rect = _window_rect(hwnd)
            if rect:
                return rect
    return None
