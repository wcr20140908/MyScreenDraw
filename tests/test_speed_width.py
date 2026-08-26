"""Speed-to-width: a real pen leaves a thin trail when moved fast.

Slow strokes come out thicker (ink has time to spread, the hand presses harder),
fast strokes thinner. This is the one part of "realistic ink" that needs no
hardware at all -- a mouse has velocity, and so does an injected contact, unlike
pressure and tilt which never reach Qt on this machine.

The case worth pinning hardest is the interaction with hold-to-shape: dwelling
drives velocity to zero, and "slow means thick" would grow a blob exactly where
the user is holding still watching the progress ring. The width must freeze
instead, and it must freeze whether or not smart shapes are enabled.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SpeedWidthTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        cls.canvas = main.DrawingCanvas(None)

    def setUp(self):
        c = self.canvas
        c.is_drawing_mode = True
        c.draw_state = "PEN"
        c.smart_shapes_enabled = False
        c.speed_width_enabled = True
        c.whiteboard_mode = False
        c.all_segments = []
        c.pen_width = 12
        c.current_pressure = 1.0
        c._speed_px_per_mm = 4.0        # fixed scale so tests do not depend on the screen
        c._speed_mm_s = None
        c._speed_at = None
        c._last_seg_width = None
        c.current_stroke_widths = []
        c.current_stroke_points = []
        c.last_point = None

    def widths(self):
        return [s["pen"].width() for s in self.canvas.all_segments]

    def factor_at(self, mm_per_s):
        self.canvas._speed_mm_s = mm_per_s
        return self.canvas._speed_width_factor()


class WidthFactorTests(SpeedWidthTestCase):
    def test_faster_is_thinner(self):
        fast = self.factor_at(self.canvas.SPEED_REF_MM_S * 4)
        slow = self.factor_at(self.canvas.SPEED_REF_MM_S / 4)
        self.assertLess(fast, slow, "快写必须比慢写细")

    def test_reference_speed_is_unchanged_width(self):
        self.assertAlmostEqual(self.factor_at(self.canvas.SPEED_REF_MM_S), 1.0, places=6)

    def test_the_factor_is_clamped_at_both_ends(self):
        c = self.canvas
        self.assertEqual(self.factor_at(100000.0), c.SPEED_WIDTH_MIN,
                         "再快也不能细到看不见")
        self.assertEqual(self.factor_at(0.001), c.SPEED_WIDTH_MAX,
                         "再慢也不能超过上限")

    def test_the_mapping_only_thins_never_thickens(self):
        """上限锁 1.0 是刻意的，不是随手填的数——它让墨疙瘩在结构上不可能出现。

        「慢＝粗」和停笔定形打架：停笔时手抖被读成极慢，笔尖会在用户盯着进度环
        的那一点涨成疙瘩。区分「抖」和「慢写」需要方向一致性分析，阈值还只能在
        真机上对真人的手调。锁住上限等于用放弃一半效果换掉整类 bug。
        """
        c = self.canvas
        self.assertEqual(c.SPEED_WIDTH_MAX, 1.0,
                         "上限必须是 1.0；放宽它会让停笔墨疙瘩重新变成可能")
        for speed in (0.001, 1.0, 20.0, 47.0, c.SPEED_REF_MM_S):
            self.assertLessEqual(self.factor_at(speed), 1.0,
                                 f"{speed}mm/s 下宽度系数不能超过 1.0")

    def test_an_unmeasured_stroke_uses_the_reference_width(self):
        self.canvas._speed_mm_s = None
        self.assertEqual(self.canvas._speed_width_factor(), 1.0,
                         "还没测到速度时不能瞎猜，按参考手速走")

    def test_the_factor_falls_monotonically_with_speed(self):
        speeds = [20, 60, 150, 400, 900]
        factors = [self.factor_at(s) for s in speeds]
        self.assertEqual(factors, sorted(factors, reverse=True),
                         "宽度系数必须随速度单调下降")


class DwellInteractionTests(SpeedWidthTestCase):
    """停笔定形时速度趋近 0——宽度必须冻住，不能涨成墨疙瘩。"""

    def test_a_pen_inside_the_anchor_slop_does_not_update_the_speed(self):
        from PyQt6.QtCore import QPoint, QPointF

        c = self.canvas
        c._speed_anchor = QPointF(100, 100)
        c._speed_at = 1.0
        c._speed_mm_s = 200.0
        # 离锚点 1px，在 SPEED_ANCHOR_SLOP_PX 之内
        c._track_stroke_speed(QPoint(101, 100))
        self.assertEqual(c._speed_mm_s, 200.0, "锚点附近的抖动不能更新笔速")

    def test_leaving_the_anchor_slop_does_update_the_speed(self):
        from PyQt6.QtCore import QPoint, QPointF

        c = self.canvas
        c._speed_anchor = QPointF(100, 100)
        c._speed_at = None          # 无时间基准：只挪锚点，不算速度
        c._speed_mm_s = None
        c._track_stroke_speed(QPoint(140, 100))
        self.assertIsNotNone(c._speed_anchor)
        self.assertEqual((c._speed_anchor.x(), c._speed_anchor.y()), (140.0, 100.0),
                         "真的移动后锚点必须跟上")

    def test_dwelling_does_not_inflate_the_width(self):
        """把「画一段 → 停住不动多次」走完，停住期间宽度不应持续变粗。"""
        from PyQt6.QtCore import QPoint

        c = self.canvas
        c.current_stroke_id = "s"
        c.last_point = QPoint(100, 100)
        last_x = 100
        for x in range(106, 160, 6):        # 正常速度画一段
            c.add_smooth_segments(QPoint(x, 100))
            last_x = x
        moving = self.widths()[-1]
        for _ in range(15):                 # 停在真正的落点上：位移 0
            c.add_smooth_segments(QPoint(last_x, 100))
        resting = self.widths()[-1]
        self.assertEqual(resting, moving, "停笔期间宽度必须冻住")

    def test_jittery_dwell_cannot_exceed_the_pen_width(self):
        """按住不动但手在抖：宽度不能超过笔宽本身。

        这才是 SPEED_WIDTH_MAX = 1.0 真正挡住的场景。零位移测不到东西——位置没变
        就不会新增线段；而真手一定会抖，实测 1~2px，会被读成「极慢」。
        与智能识别开关无关：两种情况都不能出疙瘩。
        """
        import random

        from PyQt6.QtCore import QPoint

        for smart_on in (True, False):
            with self.subTest(smart_shapes=smart_on):
                c = self.canvas
                c.smart_shapes_enabled = smart_on
                c.all_segments = []
                c.current_stroke_widths = []
                c._begin_stroke(QPoint(100, 100))
                x = 100
                for _ in range(20):
                    x += 10
                    c.add_smooth_segments(QPoint(x, 100))
                if smart_on:
                    c._start_smart_hold(QPoint(x, 100))
                rng = random.Random(7)
                for _ in range(40):
                    c.add_smooth_segments(QPoint(x + rng.randint(-2, 2),
                                                 100 + rng.randint(-2, 2)))
                self.assertLessEqual(max(self.widths()), c.pen_width,
                                     "停笔抖动不能让宽度超过笔宽")


class WidthDampingTests(SpeedWidthTestCase):
    def test_adjacent_widths_change_gradually(self):
        c = self.canvas
        c._last_seg_width = 10.0
        # 要求一个远超步长的宽度，必须被限幅
        got = c._damp_width(100.0)
        self.assertLessEqual(got, 10 + max(1.0, 10 * c.SPEED_WIDTH_STEP) + 1)

    def test_damping_works_downward_too(self):
        c = self.canvas
        c._last_seg_width = 40.0
        got = c._damp_width(1.0)
        self.assertGreater(got, 1, "宽度骤降也要限幅，否则线条断成串珠")

    def test_width_never_reaches_zero(self):
        c = self.canvas
        c._last_seg_width = None
        self.assertGreaterEqual(c._damp_width(0.0), 1, "宽度至少 1px，否则这一段看不见")


class StrokeIsolationTests(SpeedWidthTestCase):
    def test_a_new_stroke_starts_without_inherited_speed(self):
        from PyQt6.QtCore import QPoint

        c = self.canvas
        c._speed_mm_s = 900.0
        c._speed_at = 123.0
        c._last_seg_width = 3.0
        c._begin_stroke(QPoint(10, 10))
        self.assertIsNone(c._speed_mm_s, "新的一笔不能继承上一笔的末速")
        self.assertIsNone(c._speed_at)
        self.assertIsNone(c._last_seg_width)

    def test_speed_state_is_per_pointer(self):
        """两根手指的速度不能互相污染。"""
        c = self.canvas
        for name in ("_speed_mm_s", "_speed_at", "_speed_anchor", "_last_seg_width"):
            self.assertIn(name, c._POINTER_FIELDS,
                          f"{name} 必须是 per-pointer，否则两指速度互相干扰")

    def test_each_contact_keeps_its_own_speed(self):
        c = self.canvas
        c._speed_mm_s = 100.0
        with c._pointer_scope(7):
            c._speed_mm_s = 800.0
        self.assertEqual(c._speed_mm_s, 100.0, "手指的速度不能写回主指字段")
        self.assertEqual(c._pointer_slots[7]["_speed_mm_s"], 800.0)
        c._drop_pointer(7)


class ToggleTests(SpeedWidthTestCase):
    def test_disabling_restores_constant_width(self):
        from PyQt6.QtCore import QPoint

        c = self.canvas
        c.speed_width_enabled = False
        c._speed_mm_s = 20.0            # 很慢，开启时会明显变粗
        c.current_stroke_id = "s"
        c.last_point = QPoint(100, 100)
        for x in range(106, 200, 6):
            c.add_smooth_segments(QPoint(x, 100))
        widths = self.widths()
        # 关掉速度映射后，宽度只受起笔渐变影响，最终应稳定在 pen_width
        self.assertEqual(widths[-1], c.pen_width,
                         "关掉后必须回到 5.2.0 的恒定宽度")

    def test_the_toggle_is_persisted(self):
        """v5.2.0 漏过一次同类问题（多指开关没进配置，重启即复位），不能再犯。"""
        import main

        try:
            panel = main.ControlPanel()
        except Exception as exc:        # pragma: no cover - no display / no input hook
            self.skipTest(f"cannot build ControlPanel: {exc}")
        canvas = main.DrawingCanvas(panel)
        panel.canvas = canvas
        try:
            canvas.speed_width_enabled = False
            self.assertIs(panel.collect_settings().get("speed_width"), False)
            canvas.speed_width_enabled = True
            self.assertIs(panel.collect_settings().get("speed_width"), True)
        finally:
            for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
                try:
                    getattr(panel, name).stop()
                except Exception:
                    pass

    def test_marker_ignores_speed_entirely(self):
        from PyQt6.QtCore import QPoint

        c = self.canvas
        c.draw_state = "MARKER"
        c.marker_width = 24
        c._speed_mm_s = 20.0
        c.current_stroke_id = "s"
        c.last_point = QPoint(100, 100)
        for x in range(106, 180, 6):
            c.add_smooth_segments(QPoint(x, 100))
        self.assertEqual(set(self.widths()), {c.marker_pen().width()},
                         "荧光笔宽度恒定，不受速度影响")


if __name__ == "__main__":
    unittest.main(verbosity=2)
