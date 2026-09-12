# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for a third-party "sprite ball" / floating widget.

Many desktop pets and floating launchers keep themselves on screen the crude way:
a timer that re-asserts HWND_TOPMOST every few hundred milliseconds. Each such
call moves the window to the *front* of the topmost band, i.e. above our canvas
and panel. This process reproduces that behaviour so the stacking heartbeat can
be checked against a real, actively-fighting competitor.

Usage:  python tests/_fake_floater.py [--period MS] [--title TITLE] [--under-classisland]
Runs until killed.

--under-classisland: instead of HWND_TOPMOST, re-insert directly below ClassIsland's
lowest visible topmost window each period -- the "floater between ClassIsland and the
canvas" case the heartbeat must resolve without touching ClassIsland.
"""
import argparse
import ctypes
import os
import sys
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

HWND_TOPMOST = ctypes.c_void_p(-1)
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", type=int, default=300, help="re-assert interval in ms")
    parser.add_argument("--title", default="FakeFloater")
    parser.add_argument("--under-classisland", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    win = QLabel(args.title)
    win.setWindowTitle(args.title)
    win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                       | Qt.WindowType.Tool)
    win.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.setStyleSheet("background:#ff00aa; color:white; font-weight:bold; border-radius:40px;")
    win.setFixedSize(80, 80)
    screen = app.primaryScreen().availableGeometry()
    win.move(screen.right() - 120, screen.center().y() - 40)
    win.show()

    u32 = ctypes.windll.user32
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_uint]

    def reassert():
        anchor = HWND_TOPMOST
        if args.under_classisland:
            import main as app_main
            islands = [h for h in app_main.topmost_band() if app_main.is_privileged_window(h)]
            if islands:
                anchor = ctypes.c_void_p(islands[-1])
        u32.SetWindowPos(ctypes.c_void_p(int(win.winId())), anchor, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    timer = QTimer()
    timer.timeout.connect(reassert)
    timer.start(args.period)
    print(f"floater hwnd={int(win.winId())} pid={os.getpid()} period={args.period}ms", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
