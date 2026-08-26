"""Hold-to-shape must give up immediately on strokes that cannot become a shape.

Reported behaviour: writing a character, then resting the pen, produced the full
650ms progress ring and then nothing happened -- the ink never changed. Every
handwriting stroke is an open curve, which the recogniser rejects in its first few
lines, so the wait was pure noise.

The verdict is deliberately conservative: it may only answer "impossible" when
StrokeShapeRecognizer.recognize would certainly return None. A false "impossible"
would silently break shape recognition, which is far worse than a needless ring,
so the tests below pin both directions.
"""
import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def line_points(n=40, length=200.0):
    return [(100.0 + length * i / (n - 1), 300.0 + (i % 2) * 0.4) for i in range(n)]


def square_points(side=140.0, per_side=14):
    pts = []
    corners = [(100.0, 100.0), (100.0 + side, 100.0),
               (100.0 + side, 100.0 + side), (100.0, 100.0 + side), (100.0, 100.0)]
    for a, b in zip(corners, corners[1:]):
        for i in range(per_side):
            t = i / per_side
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    pts.append(corners[0])
    return pts


def circle_points(n=60, r=70.0):
    return [(300.0 + r * math.cos(2 * math.pi * i / n),
             300.0 + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def handwriting_points():
    """An open, wandering curve -- what a written character stroke looks like."""
    pts = []
    for i in range(60):
        t = i / 59.0
        pts.append((100.0 + 160.0 * t,
                    300.0 + 40.0 * math.sin(t * 5.0) + 25.0 * t))
    return pts


class VerdictAgreesWithRecogniserTests(unittest.TestCase):
    """can_form_shape must never veto something recognize would accept."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.rec = main.StrokeShapeRecognizer

    def test_a_line_is_possible(self):
        self.assertTrue(self.rec.can_form_shape(line_points()))

    def test_a_square_is_possible(self):
        self.assertTrue(self.rec.can_form_shape(square_points()))

    def test_a_circle_is_possible(self):
        self.assertTrue(self.rec.can_form_shape(circle_points()))

    def test_an_open_squiggle_is_impossible(self):
        self.assertFalse(self.rec.can_form_shape(handwriting_points()),
                         "开放的手写笔迹必须立刻判定为不可能")

    def test_too_few_points_is_impossible(self):
        self.assertFalse(self.rec.can_form_shape([(0.0, 0.0), (5.0, 5.0)]))

    def test_a_tiny_stroke_is_impossible(self):
        tiny = [(100.0 + i * 0.9, 100.0 + i * 0.4) for i in range(12)]
        self.assertFalse(self.rec.can_form_shape(tiny))

    def test_anything_recognised_is_never_vetoed(self):
        """核心不变量：识别器能认出来的，判据一律不能否掉。"""
        for name, pts in (("line", line_points()), ("square", square_points()),
                          ("circle", circle_points()),
                          ("short_line", line_points(n=20, length=90.0))):
            with self.subTest(shape=name):
                if self.rec.recognize(pts) is not None:
                    self.assertTrue(self.rec.can_form_shape(pts),
                                    f"{name} 能被识别，却被判据否掉了")

    def test_whatever_the_verdict_rejects_the_recogniser_also_rejects(self):
        """反向不变量：判据说不可能的，识别器必须也返回 None。"""
        for name, pts in (("squiggle", handwriting_points()),
                          ("two_points", [(0.0, 0.0), (5.0, 5.0)]),
                          ("tiny", [(100.0 + i * 0.9, 100.0) for i in range(12)])):
            with self.subTest(shape=name):
                if not self.rec.can_form_shape(pts):
                    self.assertIsNone(self.rec.recognize(pts),
                                      f"{name} 被判据否掉，但识别器其实认得出来")


class RingSuppressionTests(unittest.TestCase):
    """The ring must not appear at all for an impossible stroke."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        cls.canvas = main.DrawingCanvas(None)

    def setUp(self):
        from PyQt6.QtCore import QPointF

        c = self.canvas
        c._cancel_smart_recognition(drop_pending=True)
        c.is_drawing_mode = True
        c.draw_state = "PEN"
        c.smart_shapes_enabled = True
        c.all_segments = []
        c.shape_items = []
        c.undo_stack = []
        c.pending_undo = None
        c.current_stroke_id = "s"
        c.current_stroke_points = []
        self.QPointF = QPointF

    def load(self, points):
        self.canvas.current_stroke_points = [self.QPointF(x, y) for x, y in points]

    def dwell_once(self):
        """Fire one tick as if the pen had just come to rest."""
        self.canvas._start_smart_hold(self.canvas.current_stroke_points[-1])
        self.canvas._tick_smart_hold()

    def test_an_impossible_stroke_stops_the_timer_at_once(self):
        self.load(handwriting_points())
        self.dwell_once()
        self.assertFalse(self.canvas._hold_active,
                         "判定不可能后必须立刻停止停笔判定")
        self.assertFalse(self.canvas._smart_recognize_timer.isActive(),
                         "计时器必须停掉，否则会一直空转")

    def test_an_impossible_stroke_shows_no_ring(self):
        self.load(handwriting_points())
        self.dwell_once()
        self.assertEqual(self.canvas._hold_progress, 0.0,
                         "不可能成形时一圈光环都不该画")
        self.assertFalse(self.canvas.any_hold_in_progress())

    def test_an_impossible_stroke_keeps_the_ink_untouched(self):
        """判定不可能后，无论停多久笔迹都保持原样。"""
        self.load(handwriting_points())
        before = list(self.canvas.current_stroke_points)
        self.dwell_once()
        # 再跑很多拍，模拟「一直按着不动」
        for _ in range(50):
            self.canvas._tick_smart_hold()
        self.assertEqual(len(self.canvas.current_stroke_points), len(before))
        self.assertFalse(self.canvas.shape_items, "不该凭空产生标准图形")
        self.assertEqual(self.canvas._hold_progress, 0.0)

    def test_a_possible_stroke_still_arms_the_ring(self):
        self.load(line_points())
        self.dwell_once()
        self.assertTrue(self.canvas._hold_active,
                        "能成形的笔迹必须照常进入停笔判定")
        self.assertTrue(self.canvas._smart_recognize_timer.isActive())

    def test_the_verdict_is_cached_within_one_dwell(self):
        self.load(line_points())
        self.dwell_once()
        self.assertIs(self.canvas._hold_can_form, True)

    def test_moving_the_pen_re_evaluates(self):
        """先画一段开放曲线被否掉，继续画成闭合图形后必须能重新判定。"""
        self.load(handwriting_points())
        self.dwell_once()
        self.assertFalse(self.canvas._hold_active)
        self.load(square_points())                  # 笔迹变了
        self.canvas._track_smart_hold(self.canvas.current_stroke_points[-1])
        self.assertIsNone(self.canvas._hold_can_form, "移动后必须重置判定")
        self.canvas._tick_smart_hold()
        self.assertTrue(self.canvas._hold_active, "新笔迹能成形，应重新进入判定")

    def test_a_rejected_dwell_does_not_drop_the_pending_undo(self):
        """这一笔还在写，待提交的撤销快照不能被顺手丢掉。"""
        self.canvas.pending_undo = self.canvas.capture_page()
        snapshot = self.canvas.pending_undo
        self.load(handwriting_points())
        self.dwell_once()
        self.assertIs(self.canvas.pending_undo, snapshot)

    def tearDown(self):
        self.canvas._cancel_smart_recognition(drop_pending=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
