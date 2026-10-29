# SPDX-License-Identifier: GPL-3.0-or-later
"""Private calculator Qt trees must be destroyed before interpreter shutdown."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication, QWidget

from test_teaching_writing_courses import writing_host, next_info


@pytest.mark.parametrize('writing_host', ['c12.calculator', 'c12.scientific_calculator'], indirect=True)
def test_practice_entry_disposes_calculator_tree_after_event_loop(writing_host, monkeypatch):
    import main
    import teaching.application as application

    host, _ = writing_host
    next_info(host)
    host.panel.tool_menu_buttons['open_calculator'].click()
    host.pause(hidden=True)
    host.resume()
    app = QApplication.instance()
    windows = [window for window in app.topLevelWidgets()
               if host.panel.lifecycle._owns_window(window)]
    calculator = host.panel.calculator_widget
    stack, editor = calculator.stack, calculator.expression_edit
    unrelated_window = QWidget()
    unrelated_pending = QObject()
    unrelated_pending.deleteLater()

    class StoppedChild:
        def __init__(self, *_args, **_kwargs):
            self.host = host
            self.finished = SimpleNamespace(connect=Mock())
        def start(self):
            pass
        def stop(self, **_kwargs):
            self.host.close()

    socket = SimpleNamespace(connectToServer=Mock(), waitForConnected=Mock(return_value=True), abort=Mock())
    monkeypatch.setattr(application, 'QLocalSocket', lambda: socket)
    monkeypatch.setattr(application, 'TeachingConnection', Mock())
    monkeypatch.setattr(application, 'PracticeChild', StoppedChild)
    monkeypatch.setattr(application.QTimer, 'singleShot', Mock())
    monkeypatch.setattr(app, 'exec', lambda: 0)
    for name in ('initialize_interface_preferences', 'ensure_directories', 'setup_logging', 'install_qt_translations'):
        monkeypatch.setattr(main, name, Mock())
    host.context.ui_active = False

    try:
        assert application.run_practice_application(host.request, main) == 0
        assert all(sip.isdeleted(widget) for widget in (calculator, stack, editor))
        surviving = [type(window).__name__ for window in windows if not sip.isdeleted(window)]
        assert windows and not surviving, surviving
        assert not sip.isdeleted(unrelated_window)
        assert not sip.isdeleted(unrelated_pending)
    finally:
        unrelated_window.hide()
        unrelated_window.deleteLater()
