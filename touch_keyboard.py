# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Show and hide the Windows touch keyboard (TabTip).

Why use the OS keyboard rather than drawing our own alphanumeric pad: TabTip
already carries every IME, all 8 UI languages, handwriting recognition and emoji.
Re-implementing that would be strictly worse. We only add the part it lacks --
maths and Greek symbols -- in our own panel above it.

Two mechanisms, in order of preference:

1. ITipInvocation, the documented COM interface. Works on Windows 8+ and is what
   the shell itself calls.
2. Launching TabTip.exe. Needed because ITipInvocation silently does nothing when
   the tablet input service is not already running -- starting the exe brings the
   service up, after which the COM path works.

Everything here is best-effort: a classroom PC may have the service disabled by
policy, so every entry point reports success as a bool and never raises.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

TABTIP_PATHS = (
    r"C:\Program Files\Common Files\microsoft shared\ink\TabTip.exe",
    r"C:\Program Files\Common Files\Microsoft Shared\ink\TabTip.exe",
)
TABTIP_WINDOW_CLASS = "IPTip_Main_Window"

# ITipInvocation: {4CE576FA-83DC-4F88-951C-9D0782B4E376}
# IID_ITipInvocation: {37c994e7-432b-4834-a2f7-dce1f13b834b}
_CLSID_UIHostNoLaunch = "{4CE576FA-83DC-4F88-951C-9D0782B4E376}"
_IID_ITipInvocation = "{37c994e7-432b-4834-a2f7-dce1f13b834b}"

CLSCTX_LOCAL_SERVER = 0x4
SW_HIDE = 0
WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text):
    guid = _GUID()
    ole32 = ctypes.windll.ole32
    ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
    return guid


def available():
    """True if the touch keyboard looks usable on this machine."""
    if not sys.platform.startswith("win"):
        return False
    return any(os.path.exists(path) for path in TABTIP_PATHS)


def is_visible():
    """Whether TabTip currently has a visible window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(TABTIP_WINDOW_CLASS, None)
        if not hwnd:
            return False
        return bool(user32.IsWindowVisible(hwnd))
    except Exception:
        return False


def _invoke_com():
    """Ask the shell to show the keyboard through ITipInvocation."""
    ole32 = ctypes.windll.ole32
    if ole32.CoInitialize(None) < 0:
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
        toggle(interface, ctypes.c_void_p(desktop))
        return True
    except Exception:
        return False
    finally:
        try:
            ole32.CoUninitialize()
        except Exception:
            pass


def _launch_exe():
    for path in TABTIP_PATHS:
        if not os.path.exists(path):
            continue
        try:
            # DETACHED_PROCESS so the keyboard outlives whatever spawned it and
            # never inherits our console.
            subprocess.Popen([path], creationflags=0x00000008,
                             close_fds=True)
            return True
        except Exception:
            continue
    return False


def show():
    """Bring the touch keyboard up. Returns True if something was attempted.

    Launching the exe first is deliberate: ITipInvocation.Toggle does nothing at
    all when the tablet input service is not running, and it also *toggles*, so
    calling it while the keyboard is already up would hide it -- the opposite of
    what a caller asking to "show" wants.
    """
    if not available():
        return False
    if is_visible():
        return True
    if _launch_exe():
        return True
    return _invoke_com()


def hide():
    """Close the touch keyboard if it is up."""
    if not is_visible():
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(TABTIP_WINDOW_CLASS, None)
        if not hwnd:
            return False
        user32.PostMessageW(wintypes.HWND(hwnd), WM_SYSCOMMAND, SC_CLOSE, 0)
        return True
    except Exception:
        return False


def keyboard_rect():
    """Screen rect the keyboard occupies, or None.

    The symbol panel has to sit above the keyboard rather than under it, and the
    text box being edited must not end up hidden behind either.
    """
    if not is_visible():
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(TABTIP_WINDOW_CLASS, None)
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        return None
