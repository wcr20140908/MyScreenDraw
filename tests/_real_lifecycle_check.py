"""Authorized desktop lifecycle check; no mouse/touch injection or user settings writes."""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop("QT_QPA_PLATFORM", None)
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
import main

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
u32 = ctypes.windll.user32
u32.GetWindow.argtypes = [wt.HWND, wt.UINT]
u32.GetWindow.restype = wt.HWND
u32.IsWindowVisible.argtypes = [wt.HWND]
u32.IsWindowVisible.restype = wt.BOOL

def above(upper, lower):
    target = int(upper.winId())
    current = u32.GetWindow(int(lower.winId()), 3)  # GW_HWNDPREV
    visited = set()
    while current and current not in visited:
        if current == target:
            return True
        visited.add(current)
        current = u32.GetWindow(current, 3)
    return False

with tempfile.TemporaryDirectory(prefix="msd_lifecycle_") as root:
    with patch.object(main, "CONFIG_FILE", str(Path(root) / "config.json")), \
         patch.object(main.ControlPanel, "check_for_updates", lambda *a, **k: None):
        panel = main.ControlPanel()
        canvas = main.DrawingCanvas(panel)
        panel.canvas = canvas
        panel.load_settings()
        lifecycle = panel.lifecycle
        try:
            panel.show()
            panel.set_drawing_mode(True)
            panel.toggle_whiteboard()
            QTest.qWait(800)
            logo = panel.logo_window
            print("LOGO geometry", logo.geometry(), "toolbar", panel.toolbar_window.geometry(), flush=True)
            print("visibility", logo.isVisible(), u32.IsWindowVisible(int(logo.winId())), "panel", panel.isVisible(), "state", lifecycle.state, flush=True)
            assert logo.isVisible() and u32.IsWindowVisible(int(logo.winId()))
            assert above(logo, canvas), "LOGO is behind whiteboard"
            assert not logo.frameGeometry().intersects(panel.toolbar_window.frameGeometry()), "toolbar covers LOGO"
            print("PASS real whiteboard LOGO visible, above canvas and not covered by toolbar", flush=True)
            panel.toggle_thumbnail_panel()
            QTest.qWait(250)
            assert panel.thumbnail_panel.isVisible() and panel._thumbnail_live_timer.isActive()
            lifecycle.hide_to_background()
            QTest.qWait(800)
            assert not any(w.isVisible() for w in (logo, canvas, panel.toolbar_window, panel.thumbnail_panel, panel.page_rail))
            assert not panel._thumbnail_live_timer.isActive()
            print("PASS background hides preview, rail and main windows beyond delayed callbacks", flush=True)
            for _ in range(2):
                seen = []
                def cancel_dialog():
                    dialog = next((w for w in app.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()), None)
                    if dialog is not None:
                        seen.append(dialog)
                        dialog.close()
                QTimer.singleShot(150, cancel_dialog)
                lifecycle._quit_app()
                assert seen, "exit did not show a confirmation"
                assert lifecycle.state == "hidden"
                QTest.qWait(650)
                assert not logo.isVisible() and not canvas.isVisible()
            print("PASS repeated exit confirmation close keeps application hidden", flush=True)
            lifecycle.restore_from_background()
            QTest.qWait(650)
            assert logo.isVisible() and panel.page_rail.isVisible()
            assert not panel.thumbnail_panel.isVisible()
            panel.toggle_thumbnail_panel()
            lifecycle._do_quit(False)
            assert not panel.thumbnail_panel.isVisible() and not panel.page_rail.isVisible()
            print("PASS restore and quit clean all preview windows", flush=True)
        finally:
            panel.pause_callbacks()
            if hasattr(panel, "update_check_timer"):
                panel.update_check_timer.stop()
            panel.listener.stop()
            for widget in app.topLevelWidgets():
                widget.hide()
