"""Opt-in Windows real-input probe. Opens isolated windows and moves the cursor.

Run explicitly: python tests/manual_mouse_passthrough.py
The target is a separate process, so Qt-only/same-thread passthrough cannot pass.
"""
import ctypes
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

os.environ.pop("QT_QPA_PLATFORM", None)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest


def target(folder):
    app = QApplication([])
    path = Path(folder)

    class Receiver(QWidget):
        def __init__(self):
            super().__init__()
            self.clicks = 0
            self.keys = 0
            self.setWindowTitle("MyScreenDraw isolated click receiver")
            self.setGeometry(300, 220, 360, 250)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setStyleSheet("background: #eff7ec;")

        def save(self):
            (path / "receiver.json").write_text(json.dumps({"hwnd": int(self.winId()), "clicks": self.clicks, "keys": self.keys}), encoding="utf-8")

        def mousePressEvent(self, event):
            self.clicks += 1
            self.setFocus()
            self.save()

        def keyPressEvent(self, event):
            self.keys += 1
            self.save()

    widget = Receiver()
    widget.show()
    widget.save()
    QTimer.singleShot(40000, app.quit)
    app.exec()


def probe():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    work = Path(tempfile.mkdtemp(prefix="MyScreenDraw-pass-through-"))
    shutil.copy2(root / "main.py", work / "main.py")
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--target", str(work)])
    u = ctypes.windll.user32
    from ctypes import wintypes
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.WindowFromPoint.restype = wintypes.HWND
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    u.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    u.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_size_t]
    original_cursor = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(original_cursor))
    original_exec = QApplication.exec
    result = {"ok": False}

    def drive():
        app = QApplication.instance()
        native = None
        globals_ = None
        try:
            panel = next(w for w in app.topLevelWidgets() if type(w).__name__ == "ControlPanel")
            canvas = panel.canvas
            for _ in range(50):
                if (work / "receiver.json").exists():
                    break
                QTest.qWait(100)
            def state():
                return json.loads((work / "receiver.json").read_text(encoding="utf-8"))
            hwnd = state()["hwnd"]
            rect = wintypes.RECT()
            assert u.GetWindowRect(hwnd, ctypes.byref(rect))
            point = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
            canvas.whiteboard_mode = True  # opaque pixels: empty transparent canvas is not a valid test
            canvas.update()
            panel.set_drawing_mode(True)
            QTest.qWait(700)
            globals_ = panel.set_drawing_mode.__func__.__globals__
            native = globals_["set_canvas_passthrough"]

            def click(expected_hwnd):
                assert u.SetCursorPos(point.x, point.y)
                actual = wintypes.POINT()
                u.GetCursorPos(ctypes.byref(actual))
                assert (actual.x, actual.y) == (point.x, point.y), "Cursor conversion failed"
                assert int(u.WindowFromPoint(point)) == expected_hwnd, "Unexpected window under test point; refusing input"
                u.mouse_event(0x0002, 0, 0, 0, 0)
                u.mouse_event(0x0004, 0, 0, 0, 0)
                QTest.qWait(150)

            canvas_hwnd = int(canvas.winId())
            click(canvas_hwnd)
            assert state()["clicks"] == 0, "Drawing mode leaked input"

            # Reproduce the exact old bug: Qt transparency only, native helper disabled.
            globals_["set_canvas_passthrough"] = lambda *args: None
            panel.set_drawing_mode(False)
            QTest.qWait(650)
            click(canvas_hwnd)
            assert state()["clicks"] == 0, "Known-bad control unexpectedly passed"
            print("KNOWN_BAD_REPRODUCED: Qt-only mode blocks cross-process clicks", flush=True)
            globals_["set_canvas_passthrough"] = native

            # Re-selecting mouse mode also repairs a lost native style.
            panel.set_drawing_mode(False)
            QTest.qWait(650)
            assert int(canvas.winId()) == canvas_hwnd, "Mode switch recreated HWND"
            click(hwnd)
            assert state()["clicks"] == 1
            assert int(u.GetForegroundWindow()) == hwnd, "Receiver did not acquire keyboard focus"
            u.keybd_event(0x58, 0, 0, 0)
            u.keybd_event(0x58, 0, 2, 0)
            QTest.qWait(150)
            assert state()["keys"] == 1, "Keyboard did not reach underlying app"
            panel.set_drawing_mode(True)
            QTest.qWait(650)
            click(canvas_hwnd)
            assert state()["clicks"] == 1, "Drawing did not recover input"
            panel.set_drawing_mode(False)
            QTest.qWait(650)
            click(hwnd)
            assert state()["clicks"] == 2
            print("REAL_INPUT_OK: mouse, keyboard, heartbeat, repeated toggles; HWND unchanged", flush=True)
            result["ok"] = True
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            if native is not None:
                globals_["set_canvas_passthrough"] = native
            app.quit()

    def exec_with_probe():
        QTimer.singleShot(600, drive)
        QTimer.singleShot(25000, QApplication.instance().quit)
        return original_exec()

    QApplication.exec = staticmethod(exec_with_probe)
    sys.argv = [str(work / "main.py")]
    try:
        runpy.run_path(str(work / "main.py"), run_name="__main__")
    except SystemExit:
        pass
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        u.SetCursorPos(original_cursor.x, original_cursor.y)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    if "--target" in sys.argv:
        target(sys.argv[-1])
    else:
        raise SystemExit(probe())
