# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-screen capture that includes layered (WS_EX_LAYERED) windows. Manual tool.

QScreen.grabWindow(0) omits every translucent window this app owns; BitBlt needs
CAPTUREBLT. Usage:

    python tests/_grab.py out.png [x y w h]
"""
import ctypes
import sys
from ctypes import wintypes

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79

u32.GetDC.argtypes = [wintypes.HWND]
u32.GetDC.restype = wintypes.HDC
u32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
u32.GetSystemMetrics.argtypes = [ctypes.c_int]
g32.CreateCompatibleDC.argtypes = [wintypes.HDC]
g32.CreateCompatibleDC.restype = wintypes.HDC
g32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
g32.CreateDIBSection.restype = wintypes.HBITMAP
g32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
g32.SelectObject.restype = wintypes.HGDIOBJ
g32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
g32.BitBlt.restype = wintypes.BOOL
g32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
g32.DeleteDC.argtypes = [wintypes.HDC]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def grab(x=None, y=None, w=None, h=None):
    """Return (width, height, bytes BGRA top-down) of the screen region."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    if x is None:
        x, y = u32.GetSystemMetrics(SM_XVIRTUALSCREEN), u32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w, h = u32.GetSystemMetrics(SM_CXVIRTUALSCREEN), u32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    hdc = u32.GetDC(None)
    mem = g32.CreateCompatibleDC(hdc)
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth, bmi.biHeight = w, -h
    bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
    bits = ctypes.c_void_p()
    hbm = g32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old = g32.SelectObject(mem, hbm)
    ok = g32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRCCOPY | CAPTUREBLT)
    data = ctypes.string_at(bits, w * h * 4) if ok else b""
    g32.SelectObject(mem, old)
    g32.DeleteObject(hbm)
    g32.DeleteDC(mem)
    u32.ReleaseDC(None, hdc)
    return w, h, data


def save_png(path, x=None, y=None, w=None, h=None):
    from PyQt6.QtGui import QImage, QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])
    w, h, data = grab(x, y, w, h)
    img = QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
    img.save(path)
    return w, h


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "screen.png"
    region = [int(v) for v in sys.argv[2:6]] if len(sys.argv) >= 6 else [None] * 4
    print(save_png(out, *region))
