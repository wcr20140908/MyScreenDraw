# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end multitouch against a real DrawingCanvas, via real QTouchEvents.

tests/test_multitouch.py drives _handle_touch with duck-typed events because Qt
exposes no way to place a synthetic QEventPoint at a chosen position. This module
closes that gap: it injects genuine contacts through the Win32 digitizer path
(HID -> WM_POINTER -> Qt -> QTouchEvent), so what reaches the canvas is
indistinguishable from a physical touch screen.

Needs a real desktop session, and init_injection() must run before QApplication
exists -- see tests/run_touch_injection.py. Skips rather than fails otherwise.

Everything runs inside ONE test method on purpose. Injection is positional, so it
depends on the canvas genuinely owning its centre pixel, and that is real desktop
state any window can take away. A per-test setUp that re-shows and re-raises the
canvas was observed to shrink it (836 -> 478 -> 273 px at devicePixelRatio 1.75,
because showFullScreen recomputes geometry from already-scaled logical pixels)
and to lose topmost, so later gestures injected at negative coordinates and got
ERROR_INVALID_PARAMETER. One window, shown once, one gesture sequence.

This tier is not deterministic the way the offscreen suite is: any window that
takes the Z order mid-run (a notification, an installer, a focus steal) makes the
injected pixels land elsewhere. Those cases skip with a clear reason rather than
failing. Treat a skip as "could not test", not as "passed".
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.touch_inject import (TouchInjectionUnavailable, drag_one_finger,
                                drag_two_fingers, init_injection, owns_pixel,
                                qt_sees_touchscreen, raise_topmost)

# Must precede QApplication construction, so it runs at import time.
try:
    init_injection()
    _INIT_ERROR = None
except TouchInjectionUnavailable as exc:
    _INIT_ERROR = str(exc)


class CanvasInjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _INIT_ERROR:
            raise unittest.SkipTest(f"touch injection unavailable: {_INIT_ERROR}")
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv[:1])
        if not qt_sees_touchscreen():
            raise unittest.SkipTest(
                "Qt enumerated no touch device -- QApplication was built before "
                "init_injection(), or another test module created it first")
        import main

        cls.main = main
        cls.canvas = main.DrawingCanvas(None)
        cls.canvas.is_drawing_mode = True
        cls.canvas.draw_state = "PEN"
        # Off: a dwell mid-gesture would convert a stroke to a shape and change
        # the segment ids asserted on here. Dwell has its own tests.
        cls.canvas.smart_shapes_enabled = False
        cls.canvas.smart_multitouch_enabled = True
        cls.canvas.whiteboard_mode = False
        cls.canvas.showFullScreen()
        cls.pump(12)
        raise_topmost(cls.canvas)
        cls.pump(12)

    @classmethod
    def tearDownClass(cls):
        canvas = getattr(cls, "canvas", None)
        if canvas is not None:
            canvas._cancel_all_pointers()
            canvas._cancel_smart_recognition(drop_pending=True)
            canvas.hide()
            cls.pump()

    @classmethod
    def pump(cls, n=8):
        for _ in range(n):
            cls.app.processEvents()

    # --- helpers ---
    def reset_page(self):
        c = self.canvas
        c._cancel_all_pointers()
        c.all_segments = []
        c.shape_items = []
        c.undo_stack = []
        c.redo_stack = []
        c.pending_undo = None
        # _touch_owns_input is deliberately left alone: it clears itself when a
        # genuine (non-touch) mouse event arrives. Forcing it False lets a
        # leftover synthesized press start a phantom mouse-path stroke.

    def stroke_ids(self):
        seen = []
        for seg in self.canvas.all_segments:
            if seg["id"] not in seen:
                seen.append(seg["id"])
        return seen

    def aim(self):
        geo = self.canvas.frameGeometry()
        centre = geo.center()
        cx, cy = centre.x(), centre.y()
        if not owns_pixel(self.canvas, cx, cy):
            self.skipTest("canvas is not topmost at its own centre pixel -- "
                          "another window owns it, injection cannot reach us")
        reach_x = max(40, min(200, geo.width() // 4))
        reach_y = max(20, min(60, geo.height() // 6))
        return cx, cy, reach_x, reach_y

    def two_finger_write(self):
        cx, cy, rx, ry = self.aim()
        drag_two_fingers((cx - rx, cy - ry), (cx - rx, cy + ry),
                         (cx + rx, cy - ry), (cx + rx, cy + ry),
                         steps=8, pump=self.pump)
        self.pump(10)

    def one_finger_write(self):
        cx, cy, rx, _ry = self.aim()
        drag_one_finger((cx - rx, cy), (cx + rx, cy), steps=8, pump=self.pump)
        self.pump(10)

    # --- the whole story, in order ---
    def test_real_injected_multitouch(self):
        c = self.canvas

        # 1. Two contacts must build two separate strokes.
        self.reset_page()
        self.two_finger_write()
        self.assertTrue(c.all_segments,
                        "no ink -- touch never reached the canvas as QTouchEvent")
        self.assertEqual(len(self.stroke_ids()), 2,
                         "two contacts must produce two strokes, not one merged "
                         "line (and not three: Windows also emits legacy mouse "
                         "messages for the primary contact, which must be filtered)")

        # 2. Each finished stroke is its own undo step, and undo removes one.
        self.assertEqual(len(c.undo_stack), 2, "each finished stroke is one undo step")
        c.undo()
        self.assertEqual(len(self.stroke_ids()), 1, "undo must remove exactly one stroke")
        self.assertTrue(c.all_segments, "the other stroke must survive")
        c.undo()
        self.assertFalse(c.all_segments, "second undo clears the page")

        # 3. No contact or timer may be left behind.
        self.assertFalse(c._pointer_slots, "contacts left stuck down")
        self.assertFalse(c._pointer_timers, "dwell timers leaked")

        # 4. Repeat: a second gesture must behave identically, with no phantom
        #    stroke carried over from the first.
        self.reset_page()
        self.two_finger_write()
        self.assertEqual(len(self.stroke_ids()), 2, "second gesture drew a phantom stroke")
        self.assertEqual(len(c.undo_stack), 2)

        # 5. A single contact must still go down the mouse path, exactly as it
        #    did before multitouch existed -- no per-pointer slot allocated.
        self.reset_page()
        self.one_finger_write()
        self.assertTrue(c.all_segments, "single-finger ink missing -- the "
                                        "mouse-synthesis fallback is broken")
        self.assertEqual(len(self.stroke_ids()), 1)
        self.assertFalse(c._pointer_slots,
                         "single contact should stay on the mouse path, "
                         "allocating no per-pointer slot")
        self.assertEqual(len(c.undo_stack), 1)

        # 6. And multitouch must still work after a single-finger stroke.
        self.reset_page()
        self.two_finger_write()
        self.assertEqual(len(self.stroke_ids()), 2,
                         "multitouch broke after a single-finger stroke")


if __name__ == "__main__":
    unittest.main(verbosity=2)
