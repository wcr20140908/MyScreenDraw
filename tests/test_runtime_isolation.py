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
