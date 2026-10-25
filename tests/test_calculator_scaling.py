# SPDX-License-Identifier: GPL-3.0-or-later
"""Scaled calculator modes use the current page and remain within the screen."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''
import json, sys
from pathlib import Path
import main, i18n
from runtime_paths import RuntimePaths, RuntimeContext
from PyQt6.QtCore import QCoreApplication, QEvent, QRect, QTimer
from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton
root = Path(sys.argv[1])
context = RuntimeContext(RuntimePaths.for_normal(root, Path.cwd()))
context.activate()
main.RUNTIME_CONTEXT = context
for name, value in context.paths.module_aliases().items(): setattr(main, name, value)
main.track_event = lambda *a, **kw: None
main.AppLifecycleManager._setup_tray = lambda self: None
main.ControlPanel.check_for_updates = lambda self: None
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
factor = float(sys.argv[2])
checks = 0
for language in i18n._LANGS:
    i18n.set_language(language)
    panel = main.ControlPanel(runtime=context)
    panel.canvas = main.DrawingCanvas(panel, runtime=context)
    panel.apply_theme()
    panel.open_calculator()
    widget = panel.calculator_widget
    for physical_width, physical_height in ((1920,1080), (1080,1920)):
        area = QRect(0,0,round(physical_width/factor),round(physical_height/factor))
        panel._calculator_available_geometry = lambda: QRect(area)
        for mode in ('statistics','base','scientific','unit','basic'):
            widget.set_mode(mode)
            for history in (True,False):
                widget.history_toggle.setChecked(history)
                panel._fit_calculator_window()
                for _ in range(5): app.processEvents()
                assert area.contains(panel.calc_panel.frameGeometry()), (language,mode,history,area,panel.calc_panel.geometry())
                assert widget.history_frame.geometry().right() <= widget.width() or not history
                assert not history or not widget.history_frame.geometry().intersects(widget.stack.geometry())
                assert panel.calculator_scroll.horizontalScrollBar().maximum() == 0, (language,mode,history,area,panel.calc_panel.size(),widget.size(),widget.minimumSizeHint(),widget.stack.minimumSizeHint(),widget.body_layout.direction().name,widget.history_frame.geometry(),panel.calculator_scroll.viewport().size(),panel.calculator_scroll.horizontalScrollBar().maximum())
                if not history:
                    assert widget.stack.height() <= widget.stack.sizeHint().height() + 4, (language,mode)
                for button in widget.findChildren((QPushButton,QToolButton)):
                    if button.isVisible(): assert button.height() >= 32, (language,mode,button.text(),button.height())
                checks += 1
    panel.shutdown_autosave()
    panel.stop_update_worker()
    for window in list(app.topLevelWidgets()):
        for timer in window.findChildren(QTimer): timer.stop()
        window.hide(); window.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
print(json.dumps({'checks':checks,'dpr':app.primaryScreen().devicePixelRatio()}))
'''


@pytest.mark.parametrize('percentage', (75, 100, 125, 150, 175, 200))
def test_calculator_fits_modes_history_languages_and_screen_orientations(tmp_path, percentage):
    factor = percentage / 100
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=str(factor),
                       MYSCREENDRAW_NO_KEYBOARD='1', PYNPUT_BACKEND='dummy', PYTHONUTF8='1')
    result = subprocess.run([sys.executable, '-c', PROBE, str(tmp_path), str(factor)], cwd=ROOT,
                            env=environment, capture_output=True, text=True, encoding='utf-8', timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout.splitlines()[-1])
    assert record['checks'] == 160
    assert record['dpr'] == pytest.approx(factor)
