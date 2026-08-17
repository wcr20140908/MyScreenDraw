"""Headless smoke check: build ControlPanel + DrawingCanvas offscreen."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402
import main  # noqa: E402

app = QApplication([])
panel = main.ControlPanel()
canvas = main.DrawingCanvas(panel)
panel.canvas = canvas
panel.apply_theme()
panel.update_whiteboard_ui()
panel.update_history_ui()
print("panel ok", panel.orientation, panel.size())
panel.set_orientation("landscape")
print("landscape ok", panel.size())
panel.set_orientation("portrait")
print("portrait ok", panel.size())
