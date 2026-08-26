"""Two-finger writing: per-contact strokes, per-finger dwell, per-stroke undo.

These tests drive DrawingCanvas._handle_touch with duck-typed touch events. Qt
gives no way to set a synthetic QEventPoint's widget-local position -- only the
private QMutableEventPoint can, and PyQt6 does not expose it, so a constructed
QTouchEvent always arrives at (0, 0) and cannot express "two fingers at two
different places". Real QTouchEvent coverage lives in tests/run_touch_injection.py,
which injects genuine contacts through the Win32 digitizer path.

What is pinned here is the part that actually broke during design review:
  * two contacts must build two separate strokes, never one merged polyline
  * undo must remove the last stroke to FINISH, regardless of which finger
    started first (the whole-page snapshot model got this wrong -- a snapshot
    taken when B pressed already contains A's half-drawn ink)
  * each finger dwells on its own clock; A converting to a shape must not
    disturb B's in-flight stroke
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakePoint:
    """Duck-types the QEventPoint members DrawingCanvas._handle_touch reads."""

    def __init__(self, contact_id, state, x, y, pressure=1.0):
        self._id = contact_id
        self._state = state
        self._pos = (x, y)
        self._pressure = pressure

    def id(self):
        return self._id

    def state(self):
        return self._state

    def position(self):
        from PyQt6.QtCore import QPointF

        return QPointF(*self._pos)

    def pressure(self):
        return self._pressure


class FakeTouchEvent:
    """Duck-types QTouchEvent. type() is derived from the point states the way
    Qt does it: any Pressed -> TouchBegin, all Released -> TouchEnd, else Update."""

    def __init__(self, points):
        self._points = points

    def points(self):
        return self._points

    def type(self):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QEventPoint

        states = [p.state() for p in self._points]
        if any(s == QEventPoint.State.Pressed for s in states):
            return QEvent.Type.TouchBegin
        if states and all(s == QEventPoint.State.Released for s in states):
            return QEvent.Type.TouchEnd
        return QEvent.Type.TouchUpdate


class MultitouchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        cls.canvas = main.DrawingCanvas(None)

    @classmethod
    def tearDownClass(cls):
        canvas = getattr(cls, "canvas", None)
        if canvas is not None:
            canvas._cancel_all_pointers()
            canvas._cancel_smart_recognition(drop_pending=True)

    def setUp(self):
        from PyQt6.QtGui import QEventPoint

        self.State = QEventPoint.State
        c = self.canvas
        c._cancel_all_pointers()
        c._cancel_smart_recognition(drop_pending=True)
        c.is_drawing_mode = True
        c.draw_state = "PEN"
        c.smart_shapes_enabled = True
        c.smart_multitouch_enabled = True
        c.whiteboard_mode = False
        c.all_segments = []
        c.shape_items = []
        c.text_items = []
        c.image_items = []
        c.undo_stack = []
        c.redo_stack = []
        c.pending_undo = None
        c.selected_ids = set()
        c.last_point = None
        c.current_stroke_id = None
        c.current_stroke_points = []
        c._stroke_uses_delta = False

    # --- helpers ---
    def send(self, *points):
        return self.canvas._handle_touch(FakeTouchEvent(list(points)))

    def press(self, contact_id, x, y, other=()):
        pts = [FakePoint(contact_id, self.State.Pressed, x, y)]
        pts.extend(other)
        return self.send(*pts)

    def stationary(self, contact_id, x, y):
        return FakePoint(contact_id, self.State.Stationary, x, y)

    def two_finger_press(self, a=(100, 100), b=(400, 300)):
        return self.send(FakePoint(1, self.State.Pressed, *a),
                         FakePoint(2, self.State.Pressed, *b))

    def drag(self, contact_id, points, other=()):
        for x, y in points:
            pts = [FakePoint(contact_id, self.State.Updated, x, y)]
            pts.extend(other)
            self.send(*pts)

    def release(self, contact_id, x, y, other=()):
        pts = [FakePoint(contact_id, self.State.Released, x, y)]
        pts.extend(other)
        return self.send(*pts)

    def stroke_ids(self):
        seen = []
        for seg in self.canvas.all_segments:
            if seg["id"] not in seen:
                seen.append(seg["id"])
        return seen

    def expire_dwell(self, contact_id):
        """Push this finger's dwell start into the past and tick its own timer."""
        c = self.canvas
        slot = c._pointer_slots[contact_id]
        slot["_hold_since"] -= (c.SMART_HOLD_MS + 50) / 1000.0
        c._tick_pointer_hold(contact_id)


class ConcurrentStrokeTests(MultitouchTestCase):
    def test_two_contacts_build_two_separate_strokes(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100), (130, 100)],
                  other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320), (400, 330)],
                  other=[self.stationary(1, 130, 100)])
        ids = self.stroke_ids()
        self.assertEqual(len(ids), 2, "两根手指必须产生两笔，不能并成一笔")
        self.assertEqual(len(self.canvas._pointer_slots), 2)

    def test_each_contact_keeps_its_own_point_list(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 120, 100)])
        a = self.canvas._pointer_slots[1]
        b = self.canvas._pointer_slots[2]
        self.assertNotEqual(a["current_stroke_id"], b["current_stroke_id"])
        # A 走的是水平线，B 走的是竖直线：点列混在一起就说明上下文串了
        self.assertTrue(all(p.y() == 100 for p in a["current_stroke_points"]))
        self.assertTrue(all(p.x() == 400 for p in b["current_stroke_points"]))

    def test_ink_from_both_fingers_lands_on_the_page(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320)], other=[self.stationary(1, 120, 100)])
        self.assertTrue(self.canvas.all_segments)
        ids = set(self.stroke_ids())
        self.assertEqual(ids, {self.canvas._pointer_slots[1]["current_stroke_id"],
                               self.canvas._pointer_slots[2]["current_stroke_id"]})

    def test_releasing_one_finger_leaves_the_other_writing(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 120, 100)])
        b_id = self.canvas._pointer_slots[2]["current_stroke_id"]
        self.release(1, 120, 100, other=[self.stationary(2, 400, 310)])
        self.assertNotIn(1, self.canvas._pointer_slots)
        self.assertIn(2, self.canvas._pointer_slots, "B 指还按着，上下文不能被清掉")
        self.drag(2, [(400, 330), (400, 340)])
        self.assertEqual(self.canvas._pointer_slots[2]["current_stroke_id"], b_id,
                         "B 的笔画不能被 A 抬指打断")

    def test_a_third_press_does_not_discard_the_earlier_strokes(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 120, 100)])
        before = len(self.canvas.all_segments)
        self.assertTrue(before)
        self.press(3, 600, 200, other=[self.stationary(1, 120, 100),
                                       self.stationary(2, 400, 310)])
        self.assertGreaterEqual(len(self.canvas.all_segments), before,
                                "第三根手指落笔不能抹掉前两根已落的墨")
        self.assertEqual(len(self.canvas._pointer_slots), 3)


class StrokeCompletionUndoTests(MultitouchTestCase):
    """决策三：按 stroke 完成时间入栈，撤销撤最后完成的一笔。"""

    def test_each_finished_stroke_is_one_undo_step(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320)], other=[self.stationary(1, 120, 100)])
        self.release(1, 120, 100, other=[self.stationary(2, 400, 320)])
        self.assertEqual(len(self.canvas.undo_stack), 1)
        self.release(2, 400, 320)
        self.assertEqual(len(self.canvas.undo_stack), 2)

    def test_undo_removes_the_last_stroke_to_finish_not_the_last_to_start(self):
        """A 先落笔、B 后落笔，但 B 先抬指——撤销必须撤 B。"""
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320)], other=[self.stationary(1, 120, 100)])
        a_id = self.canvas._pointer_slots[1]["current_stroke_id"]
        b_id = self.canvas._pointer_slots[2]["current_stroke_id"]
        self.release(2, 400, 320, other=[self.stationary(1, 120, 100)])   # B 先完成
        self.release(1, 120, 100)                                         # A 后完成
        self.canvas.undo()
        remaining = set(self.stroke_ids())
        self.assertIn(b_id, remaining, "B 先完成，不该被第一次撤销撤掉")
        self.assertNotIn(a_id, remaining, "A 最后完成，第一次撤销应撤 A")
        self.canvas.undo()
        self.assertNotIn(b_id, set(self.stroke_ids()))

    def test_undo_of_one_stroke_leaves_the_other_intact(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320)], other=[self.stationary(1, 120, 100)])
        a_id = self.canvas._pointer_slots[1]["current_stroke_id"]
        self.release(1, 120, 100, other=[self.stationary(2, 400, 320)])
        self.release(2, 400, 320)
        self.canvas.undo()
        self.assertTrue(self.canvas.all_segments, "另一笔必须完整留下")
        self.assertIn(a_id, set(self.stroke_ids()))

    def test_undo_while_the_other_finger_is_still_writing_keeps_its_ink(self):
        """增量撤销不走整页快照，正在写的那一笔不能被截断。"""
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.release(1, 120, 100, other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310), (400, 320)])
        b_id = self.canvas._pointer_slots[2]["current_stroke_id"]
        b_before = len([s for s in self.canvas.all_segments if s["id"] == b_id])
        self.assertTrue(b_before)
        self.canvas.undo()                      # 撤掉已完成的 A
        b_after = len([s for s in self.canvas.all_segments if s["id"] == b_id])
        self.assertEqual(b_after, b_before, "撤销 A 不能动 B 正在写的墨")
        self.assertIsNotNone(self.canvas._pointer_slots[2]["current_stroke_id"],
                             "B 的笔画上下文必须还活着")
        self.drag(2, [(400, 330)])
        self.assertEqual(self.canvas._pointer_slots[2]["current_stroke_id"], b_id,
                         "B 撤销后应能继续画同一笔")

    def test_redo_restores_the_undone_stroke(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 120, 100)])
        b_id = self.canvas._pointer_slots[2]["current_stroke_id"]
        self.release(1, 120, 100, other=[self.stationary(2, 400, 310)])
        self.release(2, 400, 310)          # B 最后完成 → 第一次撤销撤 B
        self.canvas.undo()
        self.assertNotIn(b_id, set(self.stroke_ids()))
        self.canvas.redo()
        self.assertIn(b_id, set(self.stroke_ids()), "重做应把这一笔放回来")

    def test_a_tap_that_leaves_no_ink_costs_no_undo_step(self):
        """两指同时点一下就抬起：没有墨，就不该占撤销步骤。"""
        self.two_finger_press()
        self.release(1, 100, 100, other=[self.stationary(2, 400, 300)])
        self.release(2, 400, 300)
        self.assertEqual(self.canvas.undo_stack, [])

    def test_touch_cancel_commits_the_ink_already_drawn(self):
        self.two_finger_press()
        self.drag(1, [(110, 100), (120, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 120, 100)])
        self.canvas._cancel_all_pointers()
        self.assertFalse(self.canvas._pointer_slots)
        self.assertTrue(self.canvas.all_segments, "系统抢走触控序列不应静默抹掉已画的墨")
        self.assertEqual(len(self.canvas.undo_stack), 2, "两笔各占一个撤销步骤")


class PerFingerDwellTests(MultitouchTestCase):
    """决策二：每指一个独立停笔计时器，互不干扰。"""

    def test_each_finger_gets_its_own_timer(self):
        self.two_finger_press()
        self.assertIn(1, self.canvas._pointer_timers)
        self.assertIn(2, self.canvas._pointer_timers)
        self.assertIsNot(self.canvas._pointer_timers[1], self.canvas._pointer_timers[2])

    def test_both_fingers_can_dwell_at_once(self):
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        self.assertTrue(self.canvas._pointer_slots[1]["_hold_active"])
        self.assertTrue(self.canvas._pointer_slots[2]["_hold_active"])

    def test_one_finger_moving_does_not_reset_the_others_dwell(self):
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        b_since = self.canvas._pointer_slots[2]["_hold_since"]
        self.drag(1, [(200, 100), (260, 100)], other=[self.stationary(2, 400, 310)])
        self.assertEqual(self.canvas._pointer_slots[2]["_hold_since"], b_since,
                         "A 在动不能把 B 的停笔计时清零")

    def test_conversion_replaces_only_the_converting_fingers_stroke(self):
        self.two_finger_press(a=(100, 300), b=(100, 500))
        self.drag(1, [(100 + i * 6, 300 + (i % 2)) for i in range(1, 46)],
                  other=[self.stationary(2, 100, 500)])
        self.drag(2, [(100 + i * 6, 500 + (i % 2)) for i in range(1, 46)],
                  other=[self.stationary(1, 370, 301)])
        a_id = self.canvas._pointer_slots[1]["current_stroke_id"]
        b_id = self.canvas._pointer_slots[2]["current_stroke_id"]
        b_before = len([s for s in self.canvas.all_segments if s["id"] == b_id])
        self.expire_dwell(1)
        self.assertEqual([i["type"] for i in self.canvas.shape_items], ["LINE"],
                         "A 停笔应定形为直线")
        self.assertFalse([s for s in self.canvas.all_segments if s["id"] == a_id],
                         "A 的原笔迹应被替换")
        self.assertEqual(len([s for s in self.canvas.all_segments if s["id"] == b_id]),
                         b_before, "B 的笔迹不能受 A 定形影响")
        self.assertIsNotNone(self.canvas._pointer_slots[2]["current_stroke_id"],
                             "B 还在写，上下文必须活着")

    def test_conversion_is_undoable_in_two_steps_per_finger(self):
        # 第二根手指只负责让事件流进入多指路径，自己不落墨（按下即抬起）
        self.two_finger_press(a=(100, 300), b=(700, 700))
        self.release(2, 700, 700, other=[self.stationary(1, 100, 300)])
        self.drag(1, [(100 + i * 6, 300 + (i % 2)) for i in range(1, 46)])
        self.expire_dwell(1)
        self.release(1, 370, 301)
        self.assertEqual([i["type"] for i in self.canvas.shape_items], ["LINE"])
        self.canvas.undo()
        self.assertTrue(self.canvas.all_segments, "第一次撤销应找回原手绘笔迹")
        self.assertFalse(self.canvas.shape_items)
        self.canvas.undo()
        self.assertFalse(self.canvas.all_segments, "第二次撤销应回到落笔之前")

    def test_dwell_conversion_lets_the_same_finger_keep_writing(self):
        self.two_finger_press(a=(100, 300), b=(700, 700))
        self.release(2, 700, 700, other=[self.stationary(1, 100, 300)])
        self.drag(1, [(100 + i * 6, 300 + (i % 2)) for i in range(1, 46)])
        self.expire_dwell(1)
        self.assertIsNone(self.canvas._pointer_slots[1]["current_stroke_id"])
        self.drag(1, [(380, 380), (390, 400)])
        self.assertIsNotNone(self.canvas._pointer_slots[1]["current_stroke_id"],
                             "手指没抬，应就地另起一笔")
        self.assertEqual(len(self.canvas.shape_items), 1, "已定形的直线不应受影响")

    def test_release_leaves_no_timer_behind(self):
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.release(1, 110, 100, other=[self.stationary(2, 400, 300)])
        self.assertNotIn(1, self.canvas._pointer_timers)
        self.release(2, 400, 300)
        self.assertFalse(self.canvas._pointer_timers)
        self.assertFalse(self.canvas._pointer_slots)

    def test_switching_tool_stops_every_fingers_dwell(self):
        """切成橡皮后，还按在屏上的手指不能在 650ms 后突然定形。"""
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        self.canvas.draw_state = "ERASER"
        self.canvas._cancel_smart_recognition(drop_pending=True)
        for key in (1, 2):
            self.assertFalse(self.canvas._pointer_slots[key]["_hold_active"])
            self.assertFalse(self.canvas._pointer_timers[key].isActive())


class ToolScopeTests(MultitouchTestCase):
    """决策一：两指共用一个工具；非书写工具交回 Qt 的鼠标合成。"""

    def test_marker_also_supports_two_fingers(self):
        self.canvas.draw_state = "MARKER"
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        self.assertEqual(len(self.canvas._pointer_slots), 2)
        self.assertTrue(all(s.get("marker") for s in self.canvas.all_segments))

    def test_both_fingers_share_one_tool(self):
        """draw_state 是全局的：两指不可能各用一个工具。"""
        self.canvas.draw_state = "MARKER"
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.canvas.draw_state = "PEN"
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        kinds = {s.get("marker", False) for s in self.canvas.all_segments}
        self.assertEqual(kinds, {True, False},
                         "切工具后新落的墨用新工具，这是共用一个 draw_state 的预期结果")

    def test_non_drawing_tools_fall_back_to_mouse_synthesis(self):
        for tool in ("ERASER", "SELECT", "SHAPE", "TEXT", "LASER"):
            with self.subTest(tool=tool):
                self.canvas.draw_state = tool
                self.assertFalse(self.send(FakePoint(1, self.State.Pressed, 10, 10),
                                           FakePoint(2, self.State.Pressed, 20, 20)),
                                 f"{tool} 应交回 Qt 由主接触点合成鼠标事件")
        self.canvas.draw_state = "PEN"

    def test_single_contact_falls_back_to_mouse_synthesis(self):
        """单指必须走与改造前完全相同的鼠标路径。"""
        self.assertFalse(self.send(FakePoint(1, self.State.Pressed, 10, 10)))
        self.assertFalse(self.canvas._pointer_slots)

    def test_disabling_multitouch_falls_back_to_one_pointer(self):
        self.canvas.smart_multitouch_enabled = False
        try:
            self.assertFalse(self.two_finger_press())
            self.assertFalse(self.canvas._pointer_slots)
        finally:
            self.canvas.smart_multitouch_enabled = True

    def test_touch_is_ignored_outside_drawing_mode(self):
        self.canvas.is_drawing_mode = False
        try:
            self.assertFalse(self.two_finger_press())
        finally:
            self.canvas.is_drawing_mode = True


class SynthesizedMouseFilterTests(MultitouchTestCase):
    """Windows 为触控主接触点【另发】一套传统鼠标消息。

    它们在 Qt 里是 pointingDevice().type() == TouchScreen 的 QMouseEvent。多指接管
    后必须挡掉，否则第一根手指被画两次（触控一次、鼠标一次），凭空多出一笔；
    但单指书写正是靠这套合成事件驱动的，不能无条件丢弃。
    """

    def test_taking_over_sets_the_ownership_flag(self):
        self.assertFalse(self.canvas._touch_owns_input)
        self.two_finger_press()
        self.assertTrue(self.canvas._touch_owns_input, "多指接管后必须挡住合成鼠标事件")

    def test_single_contact_releases_ownership(self):
        """单指必须把控制权交回鼠标合成，否则单指彻底画不出来。"""
        self.two_finger_press()
        self.release(1, 100, 100, other=[self.stationary(2, 400, 300)])
        self.release(2, 400, 300)
        self.assertFalse(self.send(FakePoint(9, self.State.Pressed, 50, 50)))
        self.assertFalse(self.canvas._touch_owns_input)

    def test_a_real_mouse_event_reclaims_control(self):
        from PyQt6.QtCore import QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent

        self.two_finger_press()
        self.assertTrue(self.canvas._touch_owns_input)
        # 真鼠标事件（离屏平台上 pointingDevice 是 Mouse）应当交还控制权
        ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(10, 10), QPointF(10, 10),
                         self.main.Qt.MouseButton.NoButton,
                         self.main.Qt.MouseButton.NoButton,
                         self.main.Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.canvas._touch_synthesized(ev),
                         "真鼠标事件不能被当成触控合成事件挡掉")
        self.assertFalse(self.canvas._touch_owns_input)

    def test_an_unrelated_earlier_mouse_stroke_is_never_discarded(self):
        """接管时只能丢「本次触控第一根手指画的」那一笔。

        用户可能刚用真鼠标画完一笔就立刻上手触屏——那一笔必须留下。
        判据是时间加位置：合成笔的落点压在接触点上，鼠标笔不会。
        """
        from PyQt6.QtCore import QPointF

        self.canvas.current_stroke_id = "mouse-stroke"
        self.canvas.last_point = QPointF(900, 700)      # 离两个接触点都很远
        self.canvas._mouse_stroke_since = None
        self.assertFalse(self.canvas._mouse_stroke_belongs_to_touch(
            [FakePoint(1, self.State.Pressed, 100, 100)]))

    def test_a_stroke_far_from_every_contact_is_not_a_synthesized_one(self):
        import time

        from PyQt6.QtCore import QPointF

        self.canvas._touch_sequence_since = time.perf_counter()
        self.canvas._mouse_stroke_since = self.canvas._touch_sequence_since + 0.001
        self.canvas.last_point = QPointF(900, 700)
        self.assertFalse(self.canvas._mouse_stroke_belongs_to_touch(
            [FakePoint(1, self.State.Pressed, 100, 100)]),
            "时间对得上但位置差很远，不能当成合成笔丢掉")

    def test_a_stroke_sitting_on_a_contact_is_a_synthesized_one(self):
        import time

        from PyQt6.QtCore import QPointF

        self.canvas._touch_sequence_since = time.perf_counter()
        self.canvas._mouse_stroke_since = self.canvas._touch_sequence_since + 0.001
        self.canvas.last_point = QPointF(102, 103)      # 压在接触点上
        self.assertTrue(self.canvas._mouse_stroke_belongs_to_touch(
            [FakePoint(1, self.State.Pressed, 100, 100)]))


class MousePathRegressionTests(MultitouchTestCase):
    """单指/鼠标路径不能被多指改造影响。"""

    def event(self, kind, x, y, buttons, button=None):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QMouseEvent

        if button is None:
            button = self.main.Qt.MouseButton.LeftButton
        return QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons,
                           self.main.Qt.KeyboardModifier.NoModifier)

    def mouse_stroke(self):
        from PyQt6.QtCore import QEvent

        self.canvas.mousePressEvent(self.event(QEvent.Type.MouseButtonPress, 100, 300,
                                               self.main.Qt.MouseButton.LeftButton))
        for i in range(1, 20):
            self.canvas.mouseMoveEvent(self.event(QEvent.Type.MouseMove, 100 + i * 6, 340 + i * 3,
                                                  self.main.Qt.MouseButton.LeftButton))
        self.canvas.mouseReleaseEvent(self.event(QEvent.Type.MouseButtonRelease, 214, 397,
                                                 self.main.Qt.MouseButton.NoButton))

    def test_mouse_stroke_is_one_undo_step(self):
        self.mouse_stroke()
        self.assertEqual(len(self.canvas.undo_stack), 1)
        self.assertTrue(self.canvas.all_segments)

    def test_mouse_stroke_undo_clears_only_that_stroke(self):
        self.mouse_stroke()
        self.canvas.undo()
        self.assertFalse(self.canvas.all_segments)

    def test_mouse_path_does_not_allocate_pointer_slots(self):
        self.mouse_stroke()
        self.assertFalse(self.canvas._pointer_slots,
                         "鼠标走的是原字段，不应占用 per-pointer 槽位")

    def test_mouse_and_touch_can_coexist_in_one_page(self):
        self.mouse_stroke()
        mouse_ids = set(self.stroke_ids())
        self.two_finger_press()
        self.drag(1, [(110, 100)], other=[self.stationary(2, 400, 300)])
        self.drag(2, [(400, 310)], other=[self.stationary(1, 110, 100)])
        self.assertTrue(mouse_ids <= set(self.stroke_ids()),
                        "触控落笔不能抹掉鼠标画的笔迹")


if __name__ == "__main__":
    unittest.main(verbosity=2)
