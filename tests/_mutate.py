"""Mutation check for the topmost-order tests. Manual tool.

Applies one text substitution to main.py at a time, runs the stacking tests, restores
the file, and reports which mutations were caught. A mutation that survives means the
tests would stay green with that bug live.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
MUTATIONS = [
    ("ceiling ignored (old behaviour: always HWND_TOPMOST)",
     "anchor = ctypes.c_void_p(int(ceiling)) if ceiling else HWND_TOPMOST\n    for hwnd in chain:",
     "anchor = HWND_TOPMOST\n    for hwnd in chain:"),
    ("audit always says rewrite",
     "    return False, ceiling, []\n\n\ndef apply_topmost_order",
     "    return True, ceiling, []\n\n\ndef apply_topmost_order"),
    ("foreign windows never flagged",
     "    if foreign:\n        return True, ceiling, foreign",
     "    if False:\n        return True, ceiling, foreign"),
    ("ceiling is the highest privileged window, not the lowest",
     "ceiling = privileged[-1] if privileged else None",
     "ceiling = privileged[0] if privileged else None"),
    ("ignore set never pruned",
     "        ignore.intersection_update(above)",
     "        pass"),
    ("unreachable windows never remembered",
     "    if still and unreachable:\n        ignore.update(unreachable)",
     "    if False:\n        ignore.update(unreachable)"),
    ("chain order not audited",
     "    if [h for h in zone if h in chain_set] != chain:\n        return True, ceiling, []",
     "    if False:\n        return True, ceiling, []"),
    ("zero-size windows count as covering",
     "    return rect.right > rect.left and rect.bottom > rect.top",
     "    return True"),
    ("band walk does not stop at non-topmost windows",
     "            if not ex_style & WS_EX_TOPMOST:\n                break",
     "            if not ex_style & WS_EX_TOPMOST:\n                pass"),
]


def run_tests():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, "-m", "unittest", "tests.test_window_stacking"],
                          cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode == 0


def main():
    original = MAIN.read_text(encoding="utf-8")
    backup = MAIN.with_suffix(".py.mutbak")
    shutil.copy(MAIN, backup)
    survived = []
    try:
        for label, old, new in MUTATIONS:
            if original.count(old) != 1:
                print(f"?? cannot apply ({original.count(old)} matches): {label}")
                survived.append(label)
                continue
            MAIN.write_text(original.replace(old, new), encoding="utf-8")
            green = run_tests()
            print(("SURVIVED " if green else "caught   ") + label, flush=True)
            if green:
                survived.append(label)
    finally:
        shutil.copy(backup, MAIN)
        backup.unlink()
    assert MAIN.read_text(encoding="utf-8") == original
    print(f"\n{len(MUTATIONS) - len(survived)}/{len(MUTATIONS)} mutations caught")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
