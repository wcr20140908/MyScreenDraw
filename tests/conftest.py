# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests must never persist into the developer's data directory."""
import os
from pathlib import Path

import pytest


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
        yield
