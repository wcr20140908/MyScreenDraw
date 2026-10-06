# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the existing native release scenarios with strict fixture/input isolation.

Usage: python tests/run_real_acceptance_isolated.py PRIVATE_EVIDENCE_DIR [dark|light]
Real-screen testing is opt-in. Never click an unrelated process or upload captures.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import tempfile


def execute(output, theme="dark"):
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
    os.environ["MYSCREENDRAW_TEST_THEME"] = theme
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "tests"))
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    # Bootstrap isolation precedes importing legacy helpers, which ensure data
    # directories and copy a config at module import time.
    import main
    with tempfile.TemporaryDirectory(prefix="msd-native-bootstrap-") as temporary:
        paths = {"DATA_DIR": ".", "CONFIG_FILE": "config.json", "ROSTER_FILE": "roster.json",
                 "AUTOSAVE_DIR": "autosave", "EXPORT_DIR": "exports",
                 "TELEMETRY_FILE": "events.jsonl", "LOG_FILE": "app.log"}
        for key, name in paths.items(): setattr(main, key, str(Path(temporary) / name))
        main.ControlPanel.check_for_updates = lambda self, *args, **kwargs: None
        old_args = sys.argv[:]
        sys.argv = [str(Path(__file__).resolve()), str(output)]
        import real_release_acceptance as acceptance
        user32 = ctypes.windll.user32
        user32.WindowFromPoint.argtypes = [wintypes.POINT]
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.GetCapture.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        pressed = [False]
        original_send = acceptance.probe._send
        def owns_window(handle):
            if not handle: return False
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            return pid.value == os.getpid()
        def guarded_send(flags, dx=0, dy=0):
            if flags & acceptance.probe.MOUSEEVENTF_LEFTDOWN:
                point = wintypes.POINT()
                if not user32.GetCursorPos(ctypes.byref(point)):
                    raise RuntimeError("Could not verify current input position")
                if not owns_window(user32.WindowFromPoint(point)):
                    raise RuntimeError("Refusing mouse down: another process owns the target pixel")
                original_send(flags, dx, dy)
                pressed[0] = True
                return
            if flags & acceptance.probe.MOUSEEVENTF_LEFTUP:
                if not pressed[0]: return
                original_send(flags, dx, dy)
                pressed[0] = False
                return
            original_send(flags, dx, dy)
        acceptance.probe._send = guarded_send
        original_exercise = acceptance.exercise
        def exercise(panel, canvas):
            try:
                return original_exercise(panel, canvas)
            finally:
                panel.shutdown_autosave()
        acceptance.exercise = exercise
        try:
            return acceptance.main_()
        finally:
            if pressed[0]: original_send(acceptance.probe.MOUSEEVENTF_LEFTUP)
            from PyQt6.QtWidgets import QApplication
            from conftest import _dispose_offscreen_widgets
            app = QApplication.instance()
            if app is not None: _dispose_offscreen_widgets(app)
            sys.argv = old_args


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "dark"))
