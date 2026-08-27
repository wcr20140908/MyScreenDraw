# SPDX-License-Identifier: GPL-3.0-or-later
"""Does a character from an external on-screen keyboard reach the text box?

Skipped by default, and deliberately so: this needs the real Windows platform
plugin, because osk.exe posts WM_CHAR to whatever window holds *Win32* focus, and
the offscreen platform has no real focus to inspect. Everything else about the
text panel is covered offscreen in test_text_workflow.py.

Run it when touching the focus path::

    set MYSCREENDRAW_REAL_KEYBOARD=1
    python -m unittest tests.test_keyboard_delivery

It opens a panel on the real screen for a moment. It does *not* pop a keyboard --
the character is posted directly, which is exactly what osk.exe does.

Why it exists: 5.3.0/5.3.1 shipped a keyboard button that could not work, and the
offscreen suite could not have caught it. The check that matters is the one made
here -- Win32 focus lands inside our panel, and a posted WM_CHAR arrives in the
canvas object.
"""
import ctypes
import os
import sys
import time
import unittest
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REASON = ("需要真实 Windows 平台插件与真实焦点；设 MYSCREENDRAW_REAL_KEYBOARD=1 才跑")
ENABLED = os.environ.get("MYSCREENDRAW_REAL_KEYBOARD") == "1"

WM_CHAR = 0x0102


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


def focus_hwnd():
    """Win32 focus inside our own GUI thread.

    Passing 0 would ask about the *foreground* thread -- when run from a terminal
    that is the terminal, which says nothing about our widget.
    """
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(info)
    tid = ctypes.windll.kernel32.GetCurrentThreadId()
    if not ctypes.windll.user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return 0
    return int(info.hwndFocus or 0)


@unittest.skipUnless(ENABLED, REASON)
@unittest.skipUnless(sys.platform.startswith("win"), "Windows only")
class RealKeyboardDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "windows"
        # The panel is what we are testing; no need to disturb the screen with a
        # real keyboard, since the character is posted by hand below.
        os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.canvas.show()
        cls.canvas.is_drawing_mode = True
        cls.pump(cls)

    @classmethod
    def tearDownClass(cls):
        for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
            try:
                getattr(cls.panel, name).stop()
            except Exception:
                pass
        os.environ.pop("MYSCREENDRAW_NO_KEYBOARD", None)

    def pump(self, times=15):
        for _ in range(times):
            self.app.processEvents()
            time.sleep(0.03)

    def open_box(self):
        from PyQt6.QtCore import QRectF

        self.canvas.draw_state = "TEXT"
        item = self.canvas.finish_text_box(QRectF(300, 300, 260, 120))
        self.assertIsNotNone(item, "建框失败，后面的检查无意义")
        self.pump(25)
        return item

    def test_win32_focus_lands_inside_our_panel(self):
        """外部键盘把字符投给持有 Win32 焦点的窗口，所以焦点必须在我们的面板里。"""
        self.open_box()
        self.assertTrue(self.panel.text_input.hasFocus(), "Qt 层没有焦点")
        win32 = focus_hwnd()
        ours = (int(self.panel.text_input.winId()), int(self.panel.text_panel.winId()))
        self.assertIn(win32, ours,
                      f"Win32 焦点在 {win32}，不在我们的面板里，外部键盘的字符会送到别处")

    def test_a_posted_character_reaches_the_canvas_object(self):
        """osk.exe 就是这么送字符的：WM_CHAR 投给焦点窗口。"""
        item = self.open_box()
        before = item.get("text", "")
        target = focus_hwnd() or int(self.panel.text_input.winId())
        ctypes.windll.user32.PostMessageW(
            wintypes.HWND(target), WM_CHAR, ord("Q"), 0)
        self.pump(30)
        self.assertEqual(item.get("text", ""), before + "Q",
                         "字符没有落进画布对象——键盘按了也不会显示")


if __name__ == "__main__":
    unittest.main(verbosity=2)
