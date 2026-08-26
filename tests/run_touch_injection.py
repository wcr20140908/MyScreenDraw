# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the touch-injection tier in its own process.

Kept out of `unittest discover` on purpose. Two reasons:

- init_injection() must run before QApplication exists, and discovery lets whichever
  module imports first build QApplication -- usually with QT_QPA_PLATFORM=offscreen.
- Injection is positional, so it needs a real desktop session with real windows.
  Offscreen has no window at any screen pixel.

Usage:  python tests/run_touch_injection.py
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Injection needs a real window on a real desktop; offscreen cannot work.
os.environ.pop("QT_QPA_PLATFORM", None)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([
        loader.loadTestsFromName("tests.test_touch_injection"),      # harness self-check
        loader.loadTestsFromName("tests.test_multitouch_injection"),  # canvas end-to-end
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
