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
@pytest.mark.parametrize("loader", ["runpy", "pyinstaller"])
def test_analysis_prefers_system_dlls_and_restores_path(monkeypatch, inherited, fails, loader):
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
    def run_spec():
        path = ROOT / "MyScreenDraw.spec"
        if loader == "runpy":
            return runpy.run_path(str(path), init_globals=globals_)
        namespace = dict(globals_, SPEC=str(path))
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)

    with patch("PyInstaller.utils.hooks.collect_submodules", return_value=[]):
        if fails:
            with pytest.raises(RuntimeError, match="analysis failed"):
                run_spec()
        else:
            run_spec()
    assert calls == [True]
    assert os.environ.get("PATH") == inherited
