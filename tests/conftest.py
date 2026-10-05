# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests must never persist into the developer's data directory."""
import os
from pathlib import Path

import pytest


def _dispose_offscreen_widgets(app):
    """Dispose Qt trees while Python/SIP and isolated runtime paths are alive."""
    import gc
    import main
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication, QEvent, QTimer

    windows = list(app.topLevelWidgets())
    for window in windows:
        if sip.isdeleted(window):
            continue
        for timer in window.findChildren(QTimer):
            timer.stop()
        if isinstance(window, main.ControlPanel):
            window.stop_update_worker()
            listener = getattr(window, "listener", None)
            if listener is not None:
                listener.stop()
                try:
                    listener.join(timeout=1)
                except RuntimeError:
                    pass  # A constructor may not have started the listener.
        # closeEvent may prompt or hide to tray: deferred deletion is non-interactive.
        window.hide()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    windows.clear()
    gc.collect()
    assert not app.topLevelWidgets(), "Offscreen test windows survived session teardown"


@pytest.fixture(scope="session", autouse=True)
def isolated_offscreen_runtime(tmp_path_factory):
    if os.environ.get("QT_QPA_PLATFORM", "").split(":", 1)[0] != "offscreen":
        yield
        return

    import main

    root = tmp_path_factory.mktemp("myscreendraw-runtime")
    data = root / "data"
    paths = {
        "DATA_DIR": data,
        "EXPORT_DIR": root / "exports",
        "AUTOSAVE_DIR": data / "autosave",
        "CONFIG_FILE": data / "config.json",
        "ROSTER_FILE": data / "roster.json",
        "TELEMETRY_FILE": data / "events.jsonl",
        "LOG_FILE": data / "app.log",
    }
    checkout = Path(__file__).resolve().parents[1]
    if root.resolve().is_relative_to(checkout):
        raise RuntimeError("Offscreen runtime must be outside the checkout")
    for name in ("DATA_DIR", "EXPORT_DIR", "AUTOSAVE_DIR"):
        paths[name].mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as patch:
        for name, path in paths.items():
            patch.setattr(main, name, str(path))
        from PyQt6.QtWidgets import QApplication
        # Test classes retain widget/app references; own one app for the session.
        app = QApplication.instance() or QApplication([])
        try:
            yield
        finally:
            _dispose_offscreen_widgets(app)
