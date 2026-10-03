# SPDX-License-Identifier: GPL-3.0-or-later
"""Test the spec's DLL lookup isolation without running PyInstaller or an EXE."""
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != "nt", reason="Windows system DLL search policy")
@pytest.mark.parametrize("inherited", [None, r"C:\foreign-tools\bin;C:\Python"])
@pytest.mark.parametrize("fails", [False, True])
def test_analysis_prefers_system_dlls_and_restores_path(monkeypatch, inherited, fails):
    system_dir = os.path.join(os.environ["SystemRoot"], "System32")
    if inherited is None:
        monkeypatch.delenv("PATH", raising=False)
    else:
        monkeypatch.setenv("PATH", inherited)
    calls = []

    def analyze(*args, **kwargs):
        search_path = os.environ["PATH"].split(os.pathsep)
        assert search_path[0].casefold() == system_dir.casefold()
        if inherited:
            assert search_path[1:] == inherited.split(os.pathsep)
        calls.append(True)
        if fails:
            raise RuntimeError("analysis failed")
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

    globals_ = {"Analysis": analyze, "PYZ": lambda *a, **k: object(),
                "EXE": lambda *a, **k: object(), "COLLECT": lambda *a, **k: object()}
    with patch("PyInstaller.utils.hooks.collect_submodules", return_value=[]):
        if fails:
            with pytest.raises(RuntimeError, match="analysis failed"):
                runpy.run_path(str(ROOT / "MyScreenDraw.spec"), init_globals=globals_)
        else:
            runpy.run_path(str(ROOT / "MyScreenDraw.spec"), init_globals=globals_)
    assert calls == [True]
    assert os.environ.get("PATH") == inherited
