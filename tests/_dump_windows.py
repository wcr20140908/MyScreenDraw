# SPDX-License-Identifier: GPL-3.0-or-later
"""Dump the visible top-level windows of a process, in z-order. Manual tool.

Usage:  python tests/_dump_windows.py ClassIsland
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zorder_probe import describe, visible_zorder, u32, wt  # noqa: E402
import ctypes  # noqa: E402

needle = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
pids = {}
try:
    import psutil  # type: ignore
    for p in psutil.process_iter(["pid", "name"]):
        if needle in (p.info["name"] or "").lower():
            pids[p.info["pid"]] = p.info["name"]
except ImportError:
    pass

for i, hwnd in enumerate(visible_zorder(0)):
    pid = wt.DWORD(0)
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not needle or pid.value in pids:
        print(i, describe(hwnd))
