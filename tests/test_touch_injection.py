# SPDX-License-Identifier: GPL-3.0-or-later
"""Self-check for the touch injection harness itself.

This does not test MyScreenDraw. It pins the harness so that when multitouch
support lands, a failure here means "the test rig broke", not "the feature broke".

Needs a real desktop session -- injection is positional and the offscreen platform
has no window at any screen pixel. Skips instead of failing when unavailable.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.touch_inject import (TouchInjectionUnavailable, drag_two_fingers,
                                init_injection, owns_pixel, qt_sees_touchscreen,
                                raise_topmost)

# Must happen before QApplication is constructed, so it runs at import time.
try:
    init_injection()
    _INIT_ERROR = None
except TouchInjectionUnavailable as exc:
    _INIT_ERROR = str(exc)


class TouchInjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _INIT_ERROR:
            raise unittest.SkipTest(f"touch injection unavailable: {_INIT_ERROR}")
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtWidgets import QApplication, QWidget

        cls.app = QApplication.instance() or QApplication(sys.argv[:1])
        if not qt_sees_touchscreen():
            raise unittest.SkipTest(
                "Qt enumerated no touch device -- QApplication was built before "
                "init_injection(), or another test module created it first")

        class Probe(QWidget):
            def __init__(self):
                super().__init__()
                self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
                self.frames = []

            def event(self, ev):
                kinds = {QEvent.Type.TouchBegin: "BEGIN",
                         QEvent.Type.TouchUpdate: "UPDATE",
                         QEvent.Type.TouchEnd: "END"}
                if ev.type() in kinds:
                    self.frames.append((kinds[ev.type()], len(ev.points())))
                    return True
                return super().event(ev)

        cls.Probe = Probe

    def setUp(self):
        from PyQt6.QtCore import Qt

        self.probe = self.Probe()
        self.probe.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.probe.setGeometry(200, 200, 600, 400)
        self.probe.show()
        self.app.processEvents()
        raise_topmost(self.probe)
        self.app.processEvents()

    def tearDown(self):
        self.probe.close()
        self.app.processEvents()

    def gesture(self):
        """Pinch apart at the probe's real centre; returns collected frames."""
        centre = self.probe.frameGeometry().center()
        cx, cy = centre.x(), centre.y()
        if not owns_pixel(self.probe, cx, cy):
            self.skipTest("probe is not topmost at its own centre pixel")
        drag_two_fingers((cx - 80, cy), (cx + 80, cy),
                         (cx - 140, cy), (cx + 140, cy))
        for _ in range(20):
            self.app.processEvents()
        return self.probe.frames

    def test_injected_gesture_arrives_as_touch_not_mouse(self):
        frames = self.gesture()
        self.assertTrue(frames, "no QTouchEvent arrived -- injection was "
                                "downgraded to synthesized mouse input")
        self.assertEqual(frames[0][0], "BEGIN")

    def test_two_contacts_are_simultaneous(self):
        frames = self.gesture()
        # No frames at all means the gesture never reached us -- almost always a
        # Z-order steal between the owns_pixel() check and the injection. That is
        # "could not test", not "multitouch is broken", so skip with a real reason
        # rather than letting max() raise ValueError on an empty sequence.
        if not frames:
            self.skipTest("no touch frames arrived -- another window took the "
                          "Z order mid-gesture")
        self.assertGreaterEqual(max(n for _, n in frames), 2,
                                "only one contact reached Qt; multitouch not usable")

    def test_gesture_terminates_with_touch_end(self):
        frames = self.gesture()
        if not frames:
            self.skipTest("no touch frames arrived -- another window took the "
                          "Z order mid-gesture")
        self.assertEqual(frames[-1][0], "END",
                         "gesture left contacts stuck down")


if __name__ == "__main__":
    unittest.main()
