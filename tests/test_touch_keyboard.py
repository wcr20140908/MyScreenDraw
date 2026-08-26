# SPDX-License-Identifier: GPL-3.0-or-later
"""The Windows touch keyboard wrapper.

These tests must not actually pop the keyboard onto the user's screen, so they
only exercise the pure/observational parts and check that every entry point is
total -- a classroom PC may have the tablet input service disabled by policy, and
the app must degrade to "no keyboard" rather than raise.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import touch_keyboard


class AvailabilityTests(unittest.TestCase):
    def test_available_returns_a_bool(self):
        self.assertIsInstance(touch_keyboard.available(), bool)

    def test_is_visible_returns_a_bool(self):
        self.assertIsInstance(touch_keyboard.is_visible(), bool)

    def test_keyboard_rect_is_none_or_a_four_tuple(self):
        rect = touch_keyboard.keyboard_rect()
        if rect is not None:
            self.assertEqual(len(rect), 4)
            for value in rect:
                self.assertIsInstance(value, int)

    def test_hide_is_safe_when_nothing_is_up(self):
        """没弹键盘时调 hide 不能抛异常。"""
        if not touch_keyboard.is_visible():
            self.assertFalse(touch_keyboard.hide())

    def test_paths_are_absolute(self):
        for path in touch_keyboard.TABTIP_PATHS:
            self.assertTrue(path[1:3] == ":\\", f"{path} 应是绝对路径")


class DegradationTests(unittest.TestCase):
    """Every entry point must be total, even with the platform pulled out."""

    def test_show_reports_false_when_unavailable(self):
        original = touch_keyboard.TABTIP_PATHS
        touch_keyboard.TABTIP_PATHS = ()
        try:
            self.assertFalse(touch_keyboard.show(),
                             "找不到 TabTip 时应返回 False 而不是抛异常")
        finally:
            touch_keyboard.TABTIP_PATHS = original

    def test_is_visible_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None            # 模拟调用失败
            self.assertFalse(touch_keyboard.is_visible())
        finally:
            ctypes.windll = original

    def test_keyboard_rect_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertIsNone(touch_keyboard.keyboard_rect())
        finally:
            ctypes.windll = original

    def test_hide_survives_a_broken_win32_call(self):
        import ctypes

        original = ctypes.windll
        try:
            ctypes.windll = None
            self.assertFalse(touch_keyboard.hide())
        finally:
            ctypes.windll = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
