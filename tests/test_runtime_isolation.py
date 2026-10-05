# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep offscreen tests away from the developer's actual runtime data."""
from pathlib import Path


def test_offscreen_runtime_paths_do_not_point_into_checkout():
    import main
    root = Path(__file__).resolve().parents[1]
    for name in ("DATA_DIR", "EXPORT_DIR", "AUTOSAVE_DIR", "CONFIG_FILE",
                 "ROSTER_FILE", "TELEMETRY_FILE", "LOG_FILE"):
        path = Path(getattr(main, name)).resolve()
        assert not path.is_relative_to(root), (name, str(path))


def test_config_and_autosave_are_inside_isolated_data_directory():
    import main
    data = Path(main.DATA_DIR).resolve()
    assert Path(main.CONFIG_FILE).resolve().parent == data
    assert Path(main.AUTOSAVE_DIR).resolve().parent == data
    assert data.is_dir()


def test_real_settings_writer_uses_isolated_config(monkeypatch):
    import main
    from types import SimpleNamespace
    from unittest.mock import Mock
    root = Path(__file__).resolve().parents[1]
    config = Path(main.CONFIG_FILE).resolve()
    # Fail before any write if the suite isolation is missing.
    assert not config.is_relative_to(root)
    monkeypatch.setattr(main, "track_event", Mock())
    panel = SimpleNamespace(collect_settings=lambda: {"isolated_test": True})
    previous = config.read_bytes() if config.exists() else None
    try:
        main.ControlPanel.save_settings(panel)
        import json
        assert json.loads(config.read_text(encoding="utf-8")) == {"isolated_test": True}
    finally:
        if previous is None:
            config.unlink(missing_ok=True)
        else:
            config.write_bytes(previous)


def test_session_teardown_deletes_widgets_before_interpreter_shutdown():
    import os
    import subprocess
    import sys
    script = r"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tests'))
from PyQt6.QtWidgets import QApplication, QWidget, QProgressBar
from PyQt6.QtCore import QTimer
from PyQt6 import sip
from conftest import _dispose_offscreen_widgets
app = QApplication([])
retained = []
for _ in range(12):
    parent = QWidget()
    progress = QProgressBar(parent)
    progress.setRange(0, 0)
    timer = QTimer(parent)
    timer.start(100)
    retained.append((parent, progress, timer))
_dispose_offscreen_widgets(app)
assert all(sip.isdeleted(value) for tree in retained for value in tree)
assert QApplication.instance() is app
assert not sip.isdeleted(app)
print('Qt widget trees disposed before shutdown')
"""
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", MYSCREENDRAW_NO_KEYBOARD="1")
    for _ in range(3):
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
                                env=environment, capture_output=True, timeout=30)
        assert result.returncode == 0, (result.returncode, result.stderr)
        assert b"disposed before shutdown" in result.stdout
