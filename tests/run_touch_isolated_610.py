# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in native touch-injection tier with isolated files and owned-pixel guard."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


def execute(output):
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    import main
    with tempfile.TemporaryDirectory(prefix="msd610-native-touch-") as temporary:
        for key, name in {"DATA_DIR": ".", "CONFIG_FILE": "config.json", "ROSTER_FILE": "roster.json",
                          "AUTOSAVE_DIR": "autosave", "EXPORT_DIR": "exports",
                          "TELEMETRY_FILE": "events.jsonl", "LOG_FILE": "app.log"}.items():
            setattr(main, key, str(Path(temporary) / name))
        main.ensure_directories()
        from tests import touch_inject as touch
        user32 = ctypes.windll.user32
        user32.WindowFromPoint.argtypes = [wintypes.POINT]
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        starting_cursor = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(starting_cursor))
        original_inject = touch.inject
        def inject(contacts, retry=True):
            for contact in contacts:
                if contact.pointerInfo.pointerFlags & touch.POINTER_FLAG_DOWN:
                    point = contact.pointerInfo.ptPixelLocation
                    handle = user32.WindowFromPoint(point)
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
                    if pid.value != os.getpid():
                        raise touch.TouchInjectionUnavailable("Refusing touch DOWN on unrelated process")
            return original_inject(contacts, retry=retry)
        touch.inject = inject
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromName("tests.test_touch_injection"),
            unittest.defaultTestLoader.loadTestsFromName("tests.test_multitouch_injection"),
        ])
        try:
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            summary = {"version": main.APP_VERSION, "native_windows_injection": True,
                       "physical_touchscreen": False, "tests": result.testsRun,
                       "failures": len(result.failures), "errors": len(result.errors),
                       "skipped": [(str(test), reason) for test, reason in result.skipped],
                       "successful": result.wasSuccessful()}
            (destination / "touch-results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 0 if result.wasSuccessful() else 1
        finally:
            from PyQt6.QtWidgets import QApplication
            sys.path.insert(0, str(root / "tests"))
            from conftest import _dispose_offscreen_widgets
            app = QApplication.instance()
            if app is not None: _dispose_offscreen_widgets(app)
            user32.SetCursorPos(starting_cursor.x, starting_cursor.y)


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1]))
