# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end text and formula workflows, driven the way a user drives them.

Why this file exists: 5.3.0 shipped with ten reported bugs while 381 unit tests
passed. Every one of those tests called a method directly. None of them pressed a
mouse, typed a key, or opened the panel -- so nothing noticed that there was no
path at all for a keystroke to reach the canvas, that a plain click created a box,
or that switching tools left the keyboard up.

The rule here: touch nothing but real entry points. Mouse events go through
mousePressEvent/mouseMoveEvent/mouseReleaseEvent. Keystrokes go to whatever widget
actually holds focus, exactly as the touch keyboard delivers them. Panel buttons are
pressed through their handlers. If a test needs to reach past those, that is a sign
the feature is not reachable by a user either.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import formula


class WorkflowCase(unittest.TestCase):
    """Shared harness. Not a test collection itself."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        try:
            cls.panel = main.ControlPanel()
        except Exception as exc:        # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas

    @classmethod
    def tearDownClass(cls):
        for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
            try:
                getattr(getattr(cls, "panel", None), name).stop()
            except Exception:
                pass

    def setUp(self):
        c = self.canvas
        if c.whiteboard_mode:
            c.exit_whiteboard()
        c.is_drawing_mode = True
        c.all_segments = []
        c.shape_items = []
        c.text_items = []
        c.image_items = []
        c.undo_stack = []
        c.redo_stack = []
        c.pending_undo = None
        c.selected_ids = set()
        c.editing_text_id = None
        c.editing_slot = None
        c.caret_offset = 0
        c.stop_caret_blink()
        c.text_drag_start = None
        c.text_drag_rect = None
        self.panel.close_text_input()
        self.pump()
        # 真机上永远有一个前台窗口；离屏平台在隐藏活动窗口后会留下「无活动窗口」的
        # 状态，而 activateWindow() 无法从那个状态恢复激活。先把画布激活，重建
        # Qt 转移激活所需的起点，否则测的是平台限制而不是被测代码。
        self.canvas.activateWindow()
        self.pump()

    def tearDown(self):
        if self.canvas.editing_text_id is not None:
            self.canvas.end_text_edit()
        self.panel.close_text_input()

    # --- real entry points only ---
    def pump(self, times=3):
        for _ in range(times):
            self.app.processEvents()

    def _mouse(self, kind, x, y, buttons, button):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QMouseEvent

        return QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons,
                           self.main.Qt.KeyboardModifier.NoModifier)

    def press(self, x, y):
        from PyQt6.QtCore import QEvent

        left = self.main.Qt.MouseButton.LeftButton
        self.canvas.mousePressEvent(
            self._mouse(QEvent.Type.MouseButtonPress, x, y, left, left))

    def move(self, x, y):
        from PyQt6.QtCore import QEvent

        left = self.main.Qt.MouseButton.LeftButton
        self.canvas.mouseMoveEvent(self._mouse(QEvent.Type.MouseMove, x, y, left, left))

    def release(self, x, y):
        from PyQt6.QtCore import QEvent

        self.canvas.mouseReleaseEvent(
            self._mouse(QEvent.Type.MouseButtonRelease, x, y,
                        self.main.Qt.MouseButton.NoButton,
                        self.main.Qt.MouseButton.LeftButton))

    def click(self, x, y):
        self.press(x, y)
        self.release(x, y)

    def drag(self, x1, y1, x2, y2):
        self.press(x1, y1)
        self.move((x1 + x2) // 2, (y1 + y2) // 2)
        self.move(x2, y2)
        self.release(x2, y2)

    def keyboard_target(self):
        """Where the touch keyboard would deliver a character.

        QApplication.focusWidget() only reports the focus widget of the ACTIVE
        window, so it goes None whenever the platform has no active window -- an
        offscreen artefact that says nothing about our code. The invariant that
        actually matters is "within the text panel, the input widget is the one
        holding focus", so ask the panel.
        """
        from PyQt6.QtWidgets import QApplication

        panel = getattr(self.panel, "text_panel", None)
        if panel is not None and panel.isVisible():
            inside = panel.focusWidget()
            if inside is not None:
                return inside
        return QApplication.focusWidget()

    def type_text(self, text):
        """Deliver characters the way the touch keyboard does: to the focus widget."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication

        for char in text:
            widget = self.keyboard_target()
            self.assertIsNotNone(widget, "没有任何控件持有焦点，触摸键盘无处送字符")
            QApplication.sendEvent(widget, QKeyEvent(
                QEvent.Type.KeyPress, self.main.Qt.Key.Key_unknown,
                self.main.Qt.KeyboardModifier.NoModifier, char))
        self.pump()

    def type_key(self, key):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication

        widget = self.keyboard_target()
        self.assertIsNotNone(widget, "没有任何控件持有焦点")
        QApplication.sendEvent(widget, QKeyEvent(
            QEvent.Type.KeyPress, key, self.main.Qt.KeyboardModifier.NoModifier, ""))
        self.pump()

    def select_tool(self, state):
        button = {"TEXT": self.panel.btn_text, "PEN": self.panel.btn_pen,
                  "ERASER": self.panel.btn_eraser,
                  "SELECT": self.panel.btn_select}[state]
        self.panel.set_tool(state, button)
        self.pump()

    def make_box(self, x1=300, y1=300, x2=560, y2=420):
        self.select_tool("TEXT")
        self.drag(x1, y1, x2, y2)
        self.pump()
        return self.canvas.text_items[-1] if self.canvas.text_items else None

    def focus_name(self):
        widget = self.keyboard_target()
        return type(widget).__name__ if widget else None

    def texts(self):
        return [t.get("text", "") for t in self.canvas.text_items]

    def record_repaints(self, action):
        """Run `action` and return the argument tuples passed to canvas.update().

        Patched on the instance, not the class: QWidget.update is a C++ slot wrapper,
        and assigning it back onto the class leaves an unbound descriptor that every
        later test trips over.
        """
        areas = []
        self.canvas.update = lambda *a: areas.append(a)
        try:
            action()
        finally:
            del self.canvas.update
        return areas


class KeyboardInputTests(WorkflowCase):
    """Bug 1 & 6: the touch keyboard could not put a single character on the canvas."""

    def test_the_text_input_holds_focus_after_opening(self):
        """键盘把 WM_CHAR 发给有焦点的窗口；画布 NoFocus，必须有别的控件替它收。"""
        self.make_box()
        self.assertEqual(self.focus_name(), "_TextInputEdit",
                         f"焦点在 {self.focus_name()}，触摸键盘无处送字符")

    def test_typing_reaches_the_canvas(self):
        item = self.make_box()
        self.type_text("AB")
        self.assertEqual(item["text"], "AB")

    def test_typing_chinese_reaches_the_canvas(self):
        item = self.make_box()
        self.type_text("你好")
        self.assertEqual(item["text"], "你好")

    def test_no_panel_button_can_hold_focus(self):
        """按钮持有焦点就等于键盘失效——按一下退格键盘就再也打不出字。"""
        from PyQt6.QtWidgets import QPushButton

        self.make_box()
        for button in self.panel.text_panel.findChildren(QPushButton):
            with self.subTest(button=button.text()[:12]):
                self.assertEqual(button.focusPolicy(),
                                 self.main.Qt.FocusPolicy.NoFocus)

    def test_backspace_key_deletes_a_character(self):
        item = self.make_box()
        self.type_text("abc")
        self.type_key(self.main.Qt.Key.Key_Backspace)
        self.assertEqual(item["text"], "ab")

    def test_typing_still_works_after_pressing_backspace_button(self):
        """报告里的「退格键无法使用」：按钮改了画布但控件没同步，下次打字整体回写旧值。"""
        item = self.make_box()
        self.type_text("abc")
        self.panel._text_backspace()
        self.pump()
        self.type_text("Z")
        self.assertEqual(item["text"], "abZ")

    def test_typing_still_works_after_pressing_a_symbol(self):
        item = self.make_box()
        self.type_text("x")
        self.panel._symbol_pressed("α")
        self.pump()
        self.type_text("y")
        self.assertEqual(item["text"], "xαy")

    def test_escape_leaves_edit_mode(self):
        self.make_box()
        self.type_text("x")
        self.type_key(self.main.Qt.Key.Key_Escape)
        self.assertIsNone(self.canvas.editing_text_id)


class ButtonActionTests(WorkflowCase):
    """Bug 6: backspace and newline buttons did nothing usable."""

    def test_the_backspace_button_deletes(self):
        item = self.make_box()
        self.type_text("abc")
        self.panel._text_backspace()
        self.assertEqual(item["text"], "ab")

    def test_the_newline_button_inserts_a_line_break(self):
        item = self.make_box()
        self.type_text("a")
        self.panel._text_newline()
        self.type_text("b")
        self.assertEqual(item["text"], "a\nb")
        self.assertEqual(len(self.canvas.text_lines(item)), 2)

    def test_backspace_on_an_empty_box_is_harmless(self):
        item = self.make_box()
        self.panel._text_backspace()
        self.assertEqual(item["text"], "")

    def test_the_done_button_leaves_edit_mode(self):
        self.make_box()
        self.type_text("keep me")
        self.panel._text_done()
        self.assertIsNone(self.canvas.editing_text_id)
        self.assertEqual(self.texts(), ["keep me"])

    def test_every_symbol_group_button_opens_its_grid(self):
        self.make_box()
        for key in formula.group_keys():
            with self.subTest(group=key):
                self.panel._toggle_symbol_group(key)
                self.pump()
                self.assertEqual(self.panel._open_symbol_group, key)
                self.assertTrue(self.panel.symbol_grid_host.isVisible())

    def test_toggling_the_same_group_closes_it(self):
        self.make_box()
        self.panel._toggle_symbol_group("greek")
        self.panel._toggle_symbol_group("greek")
        self.assertIsNone(self.panel._open_symbol_group)

    def test_every_symbol_in_every_group_inserts_something(self):
        """全部符号逐个按一遍：只要有一个按钮插不进东西就该失败。"""
        for key in formula.group_keys():
            for entry in formula.group_entries(key):
                with self.subTest(group=key, entry=formula.entry_label(entry)):
                    self.setUp()
                    item = self.make_box()
                    self.panel._symbol_pressed(entry)
                    self.pump()
                    produced = bool(item.get("text")) or bool(item.get("formula"))
                    self.assertTrue(produced, "按下后画布内容没有任何变化")


class ClickVersusDragTests(WorkflowCase):
    """Bug 7: a plain tap conjured a box the user never asked for."""

    def test_a_plain_click_creates_nothing(self):
        self.select_tool("TEXT")
        self.click(200, 200)
        self.assertEqual(self.canvas.text_items, [],
                         "点一下不该出现文本框，用户要的是拖拽定框")

    def test_a_tiny_jitter_creates_nothing(self):
        """触屏上手指落下时总会抖几像素，那仍然是点击。"""
        self.select_tool("TEXT")
        self.press(200, 200)
        self.move(203, 202)
        self.release(203, 202)
        self.assertEqual(self.canvas.text_items, [])

    def test_a_real_drag_creates_a_box(self):
        item = self.make_box(300, 300, 520, 400)
        self.assertIsNotNone(item)
        self.assertEqual([round(v) for v in item["box"]], [220, 100])

    def test_a_drag_just_over_the_threshold_creates_a_box(self):
        self.select_tool("TEXT")
        span = self.canvas.TEXT_DRAG_MIN_PX + 2
        self.drag(200, 200, int(200 + span), int(200 + span))
        self.assertEqual(len(self.canvas.text_items), 1)

    def test_clicking_an_existing_box_edits_it(self):
        item = self.make_box(300, 300, 560, 420)
        self.type_text("hi")
        self.panel._text_done()
        self.click(400, 350)
        self.assertEqual(self.canvas.editing_text_id, item["id"])

    def test_clicking_empty_space_does_not_create_while_editing(self):
        self.make_box(300, 300, 560, 420)
        self.type_text("hi")
        self.click(900, 700)
        self.assertEqual(len(self.canvas.text_items), 1,
                         "点空白只收束当前编辑，不该再建一个框")


class PhantomBoxTests(WorkflowCase):
    """Bug 4: an uneditable box appeared out of nowhere and would not go away."""

    def test_passthrough_then_click_then_drawing_leaves_nothing(self):
        """报告里的复现路径：穿透模式选文本框 → 点一下 → 回绘图模式。"""
        self.panel.set_drawing_mode(False)
        self.select_tool("TEXT")             # set_tool 会自动切回绘图模式
        self.click(400, 400)
        self.panel.set_drawing_mode(True)
        self.pump()
        self.assertEqual(self.canvas.text_items, [],
                         "不该凭空出现文本框")

    def test_an_empty_box_never_survives_a_tool_switch(self):
        self.make_box()
        self.select_tool("PEN")
        self.assertEqual(self.canvas.text_items, [])

    def test_an_empty_box_never_survives_an_undo(self):
        self.make_box()
        self.canvas.commit_undo(self.canvas.capture_page())
        self.canvas.undo()
        self.assertIsNone(self.canvas.editing_text_id,
                          "整页替换后编辑态必须作废")

    def test_no_editing_frame_without_an_edit_target(self):
        """编辑虚线框只在真的有编辑目标时画；否则就是「无法编辑的文本框」。"""
        self.make_box()
        self.type_text("x")
        self.panel._text_done()
        self.assertIsNone(self.canvas.editing_text_item())

    def test_discarding_empty_boxes_keeps_real_ones(self):
        keeper = self.make_box(100, 100, 300, 200)
        self.type_text("real")
        self.panel._text_done()
        self.make_box(400, 400, 600, 500)       # 留空
        self.canvas.discard_empty_text_items()
        self.assertEqual([t["id"] for t in self.canvas.text_items], [keeper["id"]])


class PanelPlacementTests(WorkflowCase):
    """Bugs 2, 3, 5, 9: the panel covered the taskbar, jumped, and sat wrongly."""

    def available(self):
        from PyQt6.QtWidgets import QApplication

        screen = self.panel.screen_geometry(self.panel.text_panel, self.panel) \
            or QApplication.primaryScreen().availableGeometry()
        return screen

    def panel_rect(self):
        return self.panel.text_panel.frameGeometry()

    def test_the_panel_stays_inside_the_available_area(self):
        """可用区已排除任务栏；越界就是压住了任务栏。"""
        self.make_box()
        screen = self.available()
        rect = self.panel_rect()
        self.assertGreaterEqual(rect.left(), screen.left())
        self.assertGreaterEqual(rect.top(), screen.top())
        self.assertLessEqual(rect.right(), screen.right() + 1)
        self.assertLessEqual(rect.bottom(), screen.bottom() + 1,
                             "面板下沿越过可用区，会压住任务栏")

    def test_switching_symbol_groups_does_not_move_the_panel(self):
        """报告里的「菜单位置乱跳」：内容变化不该重算锚点。"""
        self.make_box()
        before = self.panel_rect().topLeft()
        for key in ("greek", "operator", "calculus"):
            self.panel._toggle_symbol_group(key)
            self.pump()
            self.assertEqual(self.panel_rect().topLeft(), before,
                             f"展开 {key} 后面板左上角移动了")

    def test_pressing_backspace_does_not_move_the_panel(self):
        self.make_box()
        self.type_text("abc")
        before = self.panel_rect().topLeft()
        self.panel._text_backspace()
        self.pump()
        self.assertEqual(self.panel_rect().topLeft(), before)

    def test_inserting_a_symbol_does_not_move_the_panel(self):
        self.make_box()
        before = self.panel_rect().topLeft()
        self.panel._symbol_pressed("π")
        self.pump()
        self.assertEqual(self.panel_rect().topLeft(), before)

    def test_the_panel_stays_put_across_many_actions(self):
        self.make_box()
        before = self.panel_rect().topLeft()
        self.panel._toggle_symbol_group("greek")
        self.panel._symbol_pressed("α")
        self.panel._toggle_symbol_group("structure")
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.panel._text_backspace()
        self.pump()
        self.assertEqual(self.panel_rect().topLeft(), before)

    def test_the_panel_is_not_a_child_of_the_canvas_stack(self):
        """必须是独立浮窗，否则会被全屏画布压住而点不动。"""
        self.make_box()
        self.assertIsNone(self.panel.text_panel.parent())

    def test_the_panel_moves_out_from_under_the_keyboard(self):
        """Bug 3：键盘盖住面板时必须翻走，而不是任由符号按钮被挡住。

        离屏平台起不了真键盘，所以把 keyboard_rect 换成一个假矩形，直接检验避让逻辑。
        """
        self.make_box()
        rect = self.panel.text_panel.frameGeometry()
        fake = (rect.left() - 20, rect.top() - 20, rect.width() + 40, rect.height() + 40)
        original = self.main.touch_keyboard.keyboard_rect
        self.main.touch_keyboard.keyboard_rect = lambda: fake
        try:
            self.panel._position_text_panel()
            self.pump()
            moved = self.panel.text_panel.frameGeometry()
            overlaps = (moved.left() < fake[0] + fake[2] and moved.right() > fake[0]
                        and moved.top() < fake[1] + fake[3] and moved.bottom() > fake[1])
            self.assertFalse(overlaps, "面板仍与键盘重叠，符号按钮会被挡住点不到")
        finally:
            self.main.touch_keyboard.keyboard_rect = original

    def test_the_panel_stays_on_screen_when_dodging_the_keyboard(self):
        """避让不能把面板推出屏幕——那比被挡住更糟。"""
        self.make_box()
        screen = self.available()
        fake = (screen.left(), screen.top(), screen.width(), screen.height() - 10)
        original = self.main.touch_keyboard.keyboard_rect
        self.main.touch_keyboard.keyboard_rect = lambda: fake
        try:
            self.panel._position_text_panel()
            self.pump()
            rect = self.panel.text_panel.frameGeometry()
            self.assertGreaterEqual(rect.top(), screen.top())
            self.assertLessEqual(rect.bottom(), screen.bottom() + 1)
        finally:
            self.main.touch_keyboard.keyboard_rect = original


class KeyboardRequestTests(WorkflowCase):
    """5.3.2: the app must not claim success just because a launch was accepted.

    The 5.3.1 bug: on a desktop with no digitizer, TabTip's COM toggle returns
    success every single time and the window then stays DWM-cloaked, so the old
    code silently believed a keyboard was up. Worse, the launcher it used could
    never start the process at all, so whether the button worked depended on
    whether something else had started TabTip earlier in the login session --
    which is why the identical build worked one day and failed after a reboot.
    """

    def setUp(self):
        super().setUp()
        self.kb = self.main.touch_keyboard
        self._saved = {name: getattr(self.kb, name) for name in
                       ("available", "show", "is_visible", "has_touch", "keyboard_rect",
                        "escalate", "enforce_single", "backend", "preferred_backend")}
        self.show_calls = []
        self.kb.show = lambda prefer=None: (self.show_calls.append(prefer), True)[1]

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(self.kb, name, value)
        super().tearDown()

    def hint(self):
        return self.panel.text_hint_label.text()

    def test_opening_a_box_asks_for_a_keyboard(self):
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: False
        self.make_box()
        self.assertTrue(self.show_calls, "打开文本框没有请求键盘")

    def test_no_keyboard_on_the_machine_says_so_immediately(self):
        self.kb.available = lambda: False
        self.make_box()
        self.assertEqual(self.hint(), self.main.tr("text_keyboard_missing"))
        self.assertEqual(self.show_calls, [], "机器上没有键盘时不该还去启动")

    def test_a_launch_that_never_appears_is_reported_not_ignored(self):
        """报成功但没出现，必须说出来——沉默地假装成功是 5.3.1 的行为。"""
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: False
        self.kb.has_touch = lambda: False
        self.make_box()
        self.panel._keyboard_confirm()
        self.pump()
        self.assertEqual(self.hint(), self.main.tr("text_keyboard_no_touch"))

    def test_a_touch_machine_with_the_service_off_gets_the_generic_message(self):
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: False
        self.kb.has_touch = lambda: True
        self.make_box()
        self.panel._keyboard_confirm()
        self.pump()
        self.assertEqual(self.hint(), self.main.tr("text_keyboard_missing"))

    def test_a_keyboard_that_does_appear_clears_the_hint(self):
        self.kb.available = lambda: True
        self.kb.has_touch = lambda: True
        self.kb.is_visible = lambda: False
        self.make_box()
        self.panel._keyboard_confirm()
        self.pump()
        self.assertNotEqual(self.hint(), "")
        self.kb.is_visible = lambda: True
        self.kb.backend = lambda: "osk"
        self.kb.enforce_single = lambda keep: []
        self.panel._keyboard_confirm()
        self.pump()
        self.assertEqual(self.hint(), "", "键盘出现后提示没有清掉")

    def test_the_settle_check_keeps_the_input_focused(self):
        """复查会重排面板，重排会抢激活——焦点必须还回输入控件。"""
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: True
        self.make_box()
        self.panel._keyboard_confirm()
        self.pump()
        self.assertEqual(self.focus_name(), "_TextInputEdit")

    def test_the_settle_check_is_harmless_after_the_panel_closes(self):
        """定时器可能在面板关闭之后才到——那时不能抛异常，也不该改任何东西。"""
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: False
        self.make_box()
        self.panel.close_text_input()
        self.pump()
        self.panel._keyboard_confirm()          # 不该抛
        self.pump()

    def test_a_dismissed_keyboard_is_not_dragged_back(self):
        """出现过又不见了＝用户自己关的。硬拉回来最惹人烦，讲课中途更是如此。"""
        self.kb.available = lambda: True
        self.kb.has_touch = lambda: False
        self.kb.is_visible = lambda: True
        self.kb.backend = lambda: "osk"
        self.kb.enforce_single = lambda keep: []
        self.make_box()
        self.panel._keyboard_watch_tick()        # 观察到键盘在屏上
        self.pump()
        self.assertTrue(self.panel._keyboard_was_seen)
        self.kb.is_visible = lambda: False       # 用户关掉
        self.kb.backend = lambda: None
        escalations = []
        self.kb.escalate = lambda tried=(): (escalations.append(tried), None)[1]
        self.panel._keyboard_escalate()
        self.pump()
        self.assertEqual(escalations, [], "用户关掉键盘后又被硬拉回来")

    def test_a_dismissed_keyboard_is_not_reported_as_unavailable(self):
        """用户关掉键盘不等于键盘弹不出来，报「不可用」是彻底的误导。"""
        self.kb.available = lambda: True
        self.kb.has_touch = lambda: False
        self.kb.is_visible = lambda: True
        self.kb.backend = lambda: "osk"
        self.kb.enforce_single = lambda keep: []
        self.make_box()
        self.panel._keyboard_watch_tick()
        self.pump()
        self.kb.is_visible = lambda: False
        self.kb.backend = lambda: None
        self.panel._keyboard_confirm()
        self.pump()
        self.assertEqual(self.hint(), "", "把用户主动关闭误报成了「弹不出来」")

    def test_the_watch_timer_stops_when_the_panel_closes(self):
        """面板关了还在轮询就是白烧 CPU。"""
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: False
        self.make_box()
        self.assertTrue(self.panel._keyboard_watch.isActive())
        self.panel.close_text_input()
        self.pump()
        self.assertFalse(self.panel._keyboard_watch.isActive())

    def test_only_one_keyboard_is_left_on_screen(self):
        """两个键盘同时在屏上，教室里没法用。"""
        self.kb.available = lambda: True
        self.kb.is_visible = lambda: True
        kept = []
        self.kb.enforce_single = lambda keep: (kept.append(keep), [])[1]
        self.kb.backend = lambda: "osk"
        self.make_box()
        self.panel._keyboard_watch_tick()
        self.pump()
        self.assertIn("osk", kept, "没有强制只保留一个键盘")

    def test_the_no_touch_message_exists_in_all_eight_languages(self):
        import i18n

        self.assertEqual(len(i18n._LANGS), 8)
        for lang in i18n._LANGS:
            table = i18n.TEXT.get(lang, {})
            self.assertIn("text_keyboard_no_touch", table, f"{lang} 缺新提示语")
            self.assertTrue(table["text_keyboard_no_touch"].strip(),
                            f"{lang} 的新提示语是空的")


class ImeCompositionTests(WorkflowCase):
    """5.3.3: the soft keyboard must not fight the hardware keyboard's IME.

    Reported as "both keyboards conflict with the physical keyboard and the IME,
    input goes haywire, neither side can type". Two distinct causes:

    * A raw printable key arriving mid-composition was inserted as a character. A
      soft keyboard injects keys that do not go through the IME, so they interleave
      with a composition in progress: typing "ni" and tapping a soft key produced
      "z你" in the formula cell instead of "你".
    * _refocus_input() called activateWindow() unconditionally -- even when the
      input already had focus. activateWindow() posts WM_ACTIVATE, and Windows
      cancels the composition of a window losing focus. It ran six times in the
      first three seconds a box was open, right when the user is typing their first
      word, so CJK input could not commit anything at all.
    """

    def widget(self):
        return self.panel.text_input

    def preedit(self, text):
        from PyQt6.QtGui import QInputMethodEvent
        from PyQt6.QtWidgets import QApplication

        QApplication.sendEvent(self.widget(), QInputMethodEvent(text, []))
        self.pump()

    def commit(self, text):
        from PyQt6.QtGui import QInputMethodEvent
        from PyQt6.QtWidgets import QApplication

        event = QInputMethodEvent("", [])
        event.setCommitString(text)
        QApplication.sendEvent(self.widget(), event)
        self.pump()

    def raw_key(self, ch):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication

        QApplication.sendEvent(self.widget(), QKeyEvent(
            QEvent.Type.KeyPress, ord(ch.upper()),
            self.main.Qt.KeyboardModifier.NoModifier, ch))
        self.pump()

    def formula_box(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_backspace()
        self.panel.text_input.load_from(item)
        self.pump()
        return item

    def test_composition_state_is_tracked(self):
        """Qt 不提供「是否正在组字」的查询，必须自己跟。"""
        self.make_box()
        self.assertFalse(self.widget().composing())
        self.preedit("ni")
        self.assertTrue(self.widget().composing())
        self.commit("你")
        self.assertFalse(self.widget().composing())

    def test_a_soft_key_during_composition_is_not_inserted_in_a_formula(self):
        """软键盘按键不走输入法，与组字同时到达就会串成「z你」。"""
        item = self.formula_box()
        self.preedit("ni")
        self.raw_key("z")
        self.commit("你")
        text = formula.plain_text(item.get("formula"))
        self.assertNotIn("z", text, f"组字期间的原始按键被插进了公式：{text}")
        self.assertIn("你", text)

    def test_typing_still_works_after_a_composition_ends(self):
        """修组字串味不能把普通打字也一起挡掉。"""
        item = self.formula_box()
        self.preedit("ni")
        self.commit("你")
        self.raw_key("p")
        self.raw_key("q")
        text = formula.plain_text(item.get("formula"))
        self.assertIn("pq", text, f"组字结束后打不出字了：{text}")

    def test_losing_focus_clears_composition(self):
        """失焦时 Windows 已取消组字，状态不清会让下次按键被误当成组字期间。"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QFocusEvent
        from PyQt6.QtWidgets import QApplication

        self.make_box()
        self.preedit("ni")
        self.assertTrue(self.widget().composing())
        # 直接送 FocusOut：离屏平台上没有别的窗口可接焦点时 clearFocus() 不一定发出
        # 这个事件，那是平台限制，测的应该是我们的处理。
        QApplication.sendEvent(self.widget(), QFocusEvent(QEvent.Type.FocusOut))
        self.pump()
        self.assertFalse(self.widget().composing())

    def test_opening_a_box_clears_stale_composition(self):
        """新开的框不该继承上一个框的组字状态，否则第一下按键会被丢掉。"""
        self.make_box()
        self.preedit("ni")
        self.assertTrue(self.widget().composing())
        item = self.make_box(x1=100, y1=100, x2=300, y2=200)
        self.assertFalse(self.widget().composing(),
                         "新框继承了上一个框的组字状态，第一个字会打不出来")
        self.raw_key("a")
        self.assertIn("a", item.get("text", ""), "新框第一下按键被丢掉了")

    def require_focus(self):
        """确保输入控件真的持有焦点，否则跳过。

        离屏平台在隐藏过活动窗口之后会留下「无活动窗口」状态，activateWindow() 无法
        恢复，焦点于是留在主面板的按钮上——那是平台限制，不是被测代码的问题。这两个
        用例检验的是「焦点已正确时不许抢激活」，前提不成立就没什么可测的。
        """
        self.canvas.activateWindow()
        self.pump()
        self.panel.text_panel.activateWindow()
        self.pump()
        self.widget().setFocus(self.main.Qt.FocusReason.OtherFocusReason)
        self.pump()
        if not self.widget().hasFocus():
            self.skipTest("离屏平台无法把焦点交给文字面板")

    def count_activations(self, action):
        calls = []
        original = self.panel.text_panel.activateWindow
        self.panel.text_panel.activateWindow = lambda: (calls.append(1), original())[1]
        try:
            action()
            self.pump()
        finally:
            self.panel.text_panel.activateWindow = original
        return calls

    def test_refocus_does_nothing_when_focus_is_already_correct(self):
        """无条件抢激活会取消组字——焦点本来就对时必须一步都不做。"""
        self.make_box()
        self.require_focus()
        result = []
        calls = self.count_activations(
            lambda: result.append(self.panel._refocus_input()))
        self.assertEqual(result, [True])
        self.assertEqual(calls, [], "焦点已正确却还抢了一次激活，会毁掉组字")

    def test_pressing_panel_buttons_never_steals_activation(self):
        """按钮全是 NoFocus，焦点不会跑掉，所以按它们不该触发任何激活动作。"""
        self.make_box()
        self.require_focus()

        def press_everything():
            self.panel._text_backspace()
            self.panel._text_newline()
            self.panel._symbol_pressed("π")
            self.panel._toggle_symbol_group("greek")
            self.panel._symbol_pressed("α")

        calls = self.count_activations(press_everything)
        self.assertEqual(calls, [], f"按面板按钮抢了 {len(calls)} 次激活，组字会被取消")
        self.assertTrue(self.widget().hasFocus())


class RestackTests(WorkflowCase):
    """5.3.4: the main panel must never end up above the formula panel.

    bind_topmost_stack pinned each window above the *canvas*, which says nothing
    about the panels' order relative to each other -- whoever Windows happened to
    raise last won. A real click activates a window and Windows re-stacks the other
    windows owned by the same owner, so the main panel could land on top of the
    symbol panel; force_topmost cannot pull it back, because for a window already
    in the topmost band HWND_TOPMOST does not change sibling order.
    """

    def test_the_stack_puts_the_text_panel_first(self):
        self.make_box()
        stack = self.panel.floating_stack()
        self.assertIs(stack[0], self.panel.text_panel,
                      "文字/公式面板不在最上，符号按钮会被压住点不到")

    def test_the_main_panel_is_last_in_the_stack(self):
        self.make_box()
        stack = self.panel.floating_stack()
        self.assertIs(stack[-1], self.panel,
                      "主面板不在最下，任何临时浮窗都会被它压住")

    def test_the_text_panel_outranks_the_select_panel(self):
        self.make_box()
        self.type_text("x")
        self.panel.position_selection_panel(self.canvas.selection_bounds())
        self.pump()
        stack = self.panel.floating_stack()
        if self.panel.select_panel not in stack:
            self.skipTest("选中面板未显示")
        self.assertLess(stack.index(self.panel.text_panel),
                        stack.index(self.panel.select_panel))

    def test_hidden_panels_are_not_in_the_stack(self):
        """隐藏的窗口排进去会白费 SetWindowPos，也会打乱可见窗口的相对顺序。"""
        self.make_box()
        for widget in self.panel.floating_stack():
            self.assertTrue(widget.isVisible())

    def test_restacking_orders_every_adjacent_pair(self):
        """必须逐对 force_above，只把每个窗口钉到画布之上决定不了彼此高低。"""
        self.make_box()
        calls = []
        original = self.main.force_above
        self.main.force_above = lambda a, b: calls.append((a, b))
        try:
            self.panel.restack_floatings()
        finally:
            self.main.force_above = original
        stack = self.panel.floating_stack()
        self.assertEqual(len(calls), max(0, len(stack) - 1),
                         "相邻对数与调用次数不符，链没排全")

    def test_restacking_survives_a_dead_window(self):
        """浮窗可能刚被销毁；排链不能因此抛异常打断心跳。"""
        self.make_box()
        original = self.panel.floating_stack
        self.panel.floating_stack = lambda: [None]
        try:
            self.panel.restack_floatings()      # 不该抛
        finally:
            self.panel.floating_stack = original

    def test_ownership_is_chained_through_the_stack(self):
        """归属链是结构保证：Windows 保证被归属窗口永远在其 owner 之上。

        只靠事后 restack 不够——真实点击引发的重排是异步的，矫正总晚一步，那一步就是
        用户看到的「主面板闪到符号面板上面」。把顺序写进归属关系，就没有需要矫正的时刻。
        """
        self.make_box()
        pairs = []
        original = self.main.set_window_owner
        self.main.set_window_owner = lambda a, b: pairs.append((a, b))
        try:
            self.panel.chain_floating_owners()
        finally:
            self.main.set_window_owner = original
        stack = self.panel.floating_stack()
        # 相邻对 + 链尾归属画布
        self.assertEqual(len(pairs), max(0, len(stack) - 1) + 1,
                         "归属链没有串全")

    def test_the_chain_tail_still_belongs_to_the_canvas(self):
        """链尾脱离画布的话，整条链会跌出置顶层、被普通窗口盖住。"""
        self.make_box()
        pairs = []
        original = self.main.set_window_owner
        self.main.set_window_owner = lambda a, b: pairs.append((a, b))
        try:
            self.panel.chain_floating_owners()
        finally:
            self.main.set_window_owner = original
        self.assertEqual(pairs[-1][1], int(self.canvas.winId()),
                         "链尾没有归属画布")

    def test_chaining_survives_a_dead_window(self):
        self.make_box()
        original = self.panel.floating_stack
        self.panel.floating_stack = lambda: [None, None]
        try:
            self.panel.chain_floating_owners()      # 不该抛
        finally:
            self.panel.floating_stack = original

    def test_opening_the_panel_rebuilds_the_chain(self):
        """归属链随可见集合变化，而 _bound_key 只在 winId 变化时重绑。"""
        called = []
        original = self.panel.chain_floating_owners
        self.panel.chain_floating_owners = lambda: called.append(1)
        try:
            self.make_box()
        finally:
            self.panel.chain_floating_owners = original
        self.assertTrue(called, "打开文字面板没有重建归属链")

    def test_the_heartbeat_restacks(self):
        self.make_box()
        called = []
        original = self.panel.restack_floatings
        self.panel.restack_floatings = lambda: called.append(1)
        try:
            self.panel.heartbeat_refresh()
        finally:
            self.panel.restack_floatings = original
        self.assertTrue(called, "心跳没有排链，被点乱的层级要等到下次操作才恢复")

    def test_clicking_a_symbol_group_restacks_immediately(self):
        """等下一拍心跳就是用户看到的那一下「闪」。"""
        self.make_box()
        called = []
        original = self.panel.restack_floatings
        self.panel.restack_floatings = lambda: called.append(1)
        try:
            self.panel._toggle_symbol_group("greek")
            self.pump()
        finally:
            self.panel.restack_floatings = original
        self.assertTrue(called, "点符号分组后没有立即排链")


class ImeDigitTests(WorkflowCase):
    """5.3.4: digits must be typeable, including as the first keystroke.

    Reported as "the keyboard cannot type digits first, only letters". Cause: a
    dangling IME composition leaves the candidate window open, and a digit then
    selects candidate N instead of inserting a digit. Verified against the real
    Chinese IME: pressing 'a' then '5' produced 阿, not "a5". So the IME's own
    composition state -- not just our flag -- has to be cleared when a box opens.
    """

    def test_opening_a_box_resets_the_ime(self):
        called = []
        original = self.main.cancel_ime_composition
        self.main.cancel_ime_composition = lambda hwnd: called.append(hwnd)
        try:
            self.make_box()
        finally:
            self.main.cancel_ime_composition = original
        self.assertTrue(called, "开框没有清输入法组字，数字键会被候选选择吃掉")

    def test_reset_ime_clears_the_composition_flag(self):
        from PyQt6.QtGui import QInputMethodEvent
        from PyQt6.QtWidgets import QApplication

        self.make_box()
        widget = self.panel.text_input
        QApplication.sendEvent(widget, QInputMethodEvent("ni", []))
        self.pump()
        self.assertTrue(widget.composing())
        widget.reset_ime()
        self.assertFalse(widget.composing())

    def test_reset_ime_never_raises(self):
        """输入法上下文可能拿不到（无 IME、策略限制）；不能因此抛异常。"""
        self.make_box()
        self.assertIsNone(self.panel.text_input.reset_ime())

    def test_cancel_ime_composition_is_total(self):
        self.assertFalse(self.main.cancel_ime_composition(0))
        self.assertIsInstance(self.main.cancel_ime_composition(
            int(self.panel.text_input.winId())), bool)

    def test_a_digit_is_accepted_as_the_first_character(self):
        item = self.make_box()
        self.type_text("5")
        self.assertEqual(item.get("text", ""), "5", "数字打不进去")

    def test_a_whole_number_types_correctly(self):
        item = self.make_box()
        self.type_text("2026")
        self.assertEqual(item.get("text", ""), "2026")

    def test_digits_work_in_formula_mode(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_backspace()
        self.panel.text_input.load_from(item)
        self.pump()
        self.type_text("7")
        self.assertIn("7", formula.plain_text(item.get("formula")))


class LayeringTests(WorkflowCase):
    """Bug 9: the formula panel must sit above the select panel, below the main menu."""

    def test_the_select_panel_does_not_steal_focus(self):
        """选中面板被顶上来时会抢走激活，键盘焦点随之丢失——这正是 bug 1 的一条来源。"""
        self.make_box()
        self.type_text("x")
        self.panel.position_selection_panel(self.canvas.selection_bounds())
        self.pump()
        self.assertEqual(self.focus_name(), "_TextInputEdit",
                         "选中面板顶上来后键盘焦点丢了")

    def test_both_panels_can_be_visible_at_once(self):
        self.make_box()
        self.type_text("x")
        self.panel.position_selection_panel(self.canvas.selection_bounds())
        self.pump()
        self.assertTrue(self.panel.text_panel.isVisible())

    def test_typing_still_works_after_the_select_panel_appears(self):
        item = self.make_box()
        self.type_text("a")
        self.panel.position_selection_panel(self.canvas.selection_bounds())
        self.pump()
        self.type_text("b")
        self.assertEqual(item["text"], "ab")

    def test_the_heartbeat_does_not_steal_focus(self):
        """心跳每 500ms 重排置顶，原先会把焦点抢走，键盘不到半秒就失效。"""
        item = self.make_box()
        self.type_text("a")
        for _ in range(3):
            self.panel.heartbeat_refresh()
            self.pump()
        self.assertEqual(self.focus_name(), "_TextInputEdit",
                         "心跳重排后键盘焦点丢了")
        self.type_text("b")
        self.assertEqual(item["text"], "ab")


class ToolSwitchTests(WorkflowCase):
    """Bug 8: the keyboard stayed up after switching away from the text tool."""

    def test_switching_tools_hides_the_panel(self):
        self.make_box()
        self.type_text("x")
        self.select_tool("PEN")
        self.assertFalse(self.panel.text_panel.isVisible())

    def test_switching_tools_leaves_edit_mode(self):
        self.make_box()
        self.type_text("x")
        self.select_tool("ERASER")
        self.assertIsNone(self.canvas.editing_text_id)

    def test_the_panel_closes_even_when_nothing_is_being_edited(self):
        """原先收键盘藏在 editing_text_id 判断里，编辑态已结束就收不掉。"""
        self.make_box()
        self.type_text("x")
        self.panel._text_done()             # 编辑结束，但面板可能还开着
        self.panel.open_text_input(self.canvas.text_items[0])
        self.canvas.editing_text_id = None  # 模拟编辑态先结束
        self.select_tool("PEN")
        self.assertFalse(self.panel.text_panel.isVisible())

    def test_text_content_survives_a_tool_switch(self):
        self.make_box()
        self.type_text("keep me")
        self.select_tool("PEN")
        self.assertEqual(self.texts(), ["keep me"])

    def test_returning_to_the_text_tool_works_again(self):
        self.make_box()
        self.type_text("first")
        self.select_tool("PEN")
        second = self.make_box(600, 300, 820, 400)
        self.assertIsNotNone(second)
        self.type_text("second")
        self.assertEqual(sorted(self.texts()), ["first", "second"])


class WhiteboardModeTests(WorkflowCase):
    """Bug 10: text boxes were reported as completely unusable on the whiteboard."""

    def setUp(self):
        super().setUp()
        if not self.canvas.whiteboard_mode:
            self.canvas.enter_whiteboard()
        self.canvas.text_items = []
        self.canvas.editing_text_id = None
        self.pump()

    def test_a_drag_creates_a_box_on_the_whiteboard(self):
        item = self.make_box()
        self.assertIsNotNone(item, "白板模式下拖拽应能建框")

    def test_typing_works_on_the_whiteboard(self):
        item = self.make_box()
        self.type_text("白板文字")
        self.assertEqual(item["text"], "白板文字")

    def test_the_box_survives_being_written_into_the_page(self):
        """白板每次内容变化都会 save_current_page()，不能把正在编辑的框写丢。"""
        item = self.make_box()
        self.type_text("abc")
        self.canvas.save_current_page()
        self.assertEqual(len(self.canvas.text_items), 1)
        self.assertEqual(self.canvas.text_items[0]["text"], "abc")

    def test_a_formula_works_on_the_whiteboard(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1")
        self.assertEqual(formula.plain_text(item["formula"]), "(1)/()")

    def test_the_box_survives_a_page_round_trip(self):
        self.make_box()
        self.type_text("page text")
        self.panel._text_done()
        page = self.canvas.capture_page()
        self.canvas.text_items = []
        self.canvas.load_page(page)
        self.assertEqual(self.texts(), ["page text"])

    def test_switching_pages_does_not_strand_an_edit(self):
        self.make_box()
        self.type_text("x")
        self.canvas.save_current_page()
        self.canvas.new_page()
        self.pump()
        self.assertIsNone(self.canvas.editing_text_id,
                          "翻页后不该还挂着上一页的编辑态")

    def test_editing_then_leaving_whiteboard_keeps_the_text(self):
        self.make_box()
        self.type_text("kept")
        self.panel._text_done()
        self.canvas.save_current_page()
        pages = len(self.canvas.pages)
        self.assertGreaterEqual(pages, 1)
        self.assertEqual(self.texts(), ["kept"])


class FormulaWorkflowTests(WorkflowCase):
    """Typing a real formula the way a teacher would, through the panel only."""

    def test_build_a_fraction_by_tapping(self):
        item = self.make_box()
        self.panel._toggle_symbol_group("structure")
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1")
        self.canvas.editing_slot = (0, "den")
        self.type_text("2")
        self.assertEqual(formula.plain_text(item["formula"]), "(1)/(2)")

    def test_build_a_square_root_of_a_fraction(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!sqrt", "√‾"))
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("3")
        self.assertEqual(formula.plain_text(item["formula"]), "sqrt((3)/())")

    def test_greek_letters_land_in_the_active_slot(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.panel._symbol_pressed("π")
        self.assertEqual(formula.plain_text(item["formula"]), "(π)/()")

    def test_a_formula_renders_without_raising(self):
        """排版 + 绘制整条链路跑一遍：抛异常会在 paintEvent 里直接终止进程。"""
        from PyQt6.QtGui import QPixmap, QPainter

        item = self.make_box()
        self.panel._symbol_pressed(("!sum", "∑"))
        self.type_text("n")
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1")
        pixmap = QPixmap(600, 400)
        painter = QPainter(pixmap)
        try:
            self.canvas.draw_text_item(painter, item, editing=True)
        finally:
            painter.end()

    def test_the_whole_canvas_paints_with_a_formula_present(self):
        from PyQt6.QtGui import QPixmap, QPainter

        item = self.make_box()
        self.panel._symbol_pressed(("!int", "∫"))
        self.type_text("x")
        pixmap = QPixmap(800, 600)
        painter = QPainter(pixmap)
        try:
            self.canvas.draw_content(painter)
        finally:
            painter.end()

    def test_deeply_nested_formulas_still_render(self):
        from PyQt6.QtGui import QPixmap, QPainter

        item = self.make_box()
        for _ in range(6):
            self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1")
        pixmap = QPixmap(800, 600)
        painter = QPainter(pixmap)
        try:
            self.canvas.draw_text_item(painter, item, editing=True)
        finally:
            painter.end()


class CaretEditingTests(WorkflowCase):
    """5.4.0 request: "符号面板上的文字应该光标点在哪就编辑哪".

    Before this, every keystroke appended and backspace always removed the last
    character, no matter where the user had clicked. These drive it the way a user
    does -- click on the canvas, type on the keyboard -- rather than calling
    set_caret directly, because the click-to-offset mapping is the part that breaks.
    """

    def caret_x(self, item, offset):
        """Canvas x of the caret at `offset`, for aiming a click."""
        self.canvas.caret_offset = offset
        rect = self.canvas.caret_rect(item)
        self.assertIsNotNone(rect, "拿不到插入点矩形")
        return rect.center().x(), rect.center().y()

    def test_a_new_box_starts_with_the_caret_at_the_end(self):
        item = self.make_box()
        self.type_text("abc")
        self.assertEqual(self.canvas.caret_offset, 3)

    def test_clicking_mid_text_then_typing_inserts_there(self):
        item = self.make_box()
        self.type_text("abd")
        x, y = self.caret_x(item, 2)
        self.click(int(round(x)), int(round(y)))
        self.type_text("c")
        self.assertEqual(item["text"], "abcd")

    def test_clicking_mid_text_then_backspacing_deletes_there(self):
        item = self.make_box()
        self.type_text("abxc")
        x, y = self.caret_x(item, 3)
        self.click(int(round(x)), int(round(y)))
        self.type_key(self.main.Qt.Key.Key_Backspace)
        self.assertEqual(item["text"], "abc")

    def test_clicking_before_the_first_character_puts_the_caret_at_zero(self):
        item = self.make_box(300, 300, 560, 420)
        self.type_text("abc")
        self.click(302, 306)
        self.assertEqual(self.canvas.caret_offset, 0)
        self.type_text("Z")
        self.assertEqual(item["text"], "Zabc")

    def test_clicking_past_the_last_character_puts_the_caret_at_the_end(self):
        item = self.make_box(300, 300, 560, 420)
        self.type_text("ab")
        self.click(550, 306)
        self.assertEqual(self.canvas.caret_offset, 2)

    def test_the_caret_lands_on_the_line_that_was_clicked(self):
        """自动换行让行号不能从 text 里数出来——软换行在原文里没有字符。"""
        item = self.make_box(300, 300, 420, 460)
        self.type_text("一二三四五六七八九十")
        lines = self.canvas.text_lines(item)
        self.assertGreater(len(lines), 1, "没有发生换行，这个用例没测到东西")
        metrics = self.canvas.text_metrics(self.canvas.text_font(item))
        y = 300 + self.canvas.TEXT_PAD + metrics.lineSpacing() * 1.5
        self.click(305, int(round(y)))
        row, _column = self.canvas.caret_line_column(item)
        self.assertEqual(row, 1)

    def test_delete_removes_the_character_after_the_caret(self):
        item = self.make_box()
        self.type_text("abxc")
        x, y = self.caret_x(item, 2)
        self.click(int(round(x)), int(round(y)))
        self.type_key(self.main.Qt.Key.Key_Delete)
        self.assertEqual(item["text"], "abc")

    def test_arrow_keys_move_the_caret(self):
        item = self.make_box()
        self.type_text("abc")
        self.type_key(self.main.Qt.Key.Key_Left)
        self.type_key(self.main.Qt.Key.Key_Left)
        self.type_text("Z")
        self.assertEqual(item["text"], "aZbc")

    def test_typing_in_a_formula_inserts_at_the_caret(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("13")
        self.type_key(self.main.Qt.Key.Key_Left)
        self.type_text("2")
        self.assertEqual(formula.plain_text(item["formula"]), "(123)/()")

    def test_backspace_in_a_formula_deletes_at_the_caret(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1x2")
        self.type_key(self.main.Qt.Key.Key_Left)
        self.type_key(self.main.Qt.Key.Key_Backspace)
        self.assertEqual(formula.plain_text(item["formula"]), "(12)/()")

    def test_a_structure_lands_at_the_caret_inside_a_slot(self):
        """光标停在 "ab|c" 中间时，分数要落在 ab 和 c 之间，不是追加到最后。"""
        item = self.make_box()
        self.panel._symbol_pressed(("!sqrt", "√‾"))
        self.type_text("ac")
        self.type_key(self.main.Qt.Key.Key_Left)
        self.panel._symbol_pressed(("!frac", "x/y"))
        self.assertEqual(formula.plain_text(item["formula"]), "sqrt(a()/()c)")

    def test_clicking_a_formula_slot_moves_the_caret_into_it(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("12")
        box = self.canvas.formula_box(item)
        rect = self.canvas.text_local_rect(item)
        found = None
        for path, x, y, w, h in formula.slot_rects(box):
            if path == (0, "den"):
                found = (x + w / 2.0, y + h / 2.0)
        self.assertIsNotNone(found, "排版里没有分母这个槽")
        self.click(int(round(item["pos"].x() + rect.left() + self.canvas.TEXT_PAD + found[0])),
                   int(round(item["pos"].y() + rect.top() + self.canvas.TEXT_PAD
                             + box.ascent + found[1])))
        self.assertEqual(self.canvas.editing_slot, (0, "den"))
        self.type_text("3")
        self.assertEqual(formula.plain_text(item["formula"]), "(12)/(3)")

    def test_a_stale_caret_never_drops_a_character(self):
        """撤销/翻页会让插入点指向已经不存在的位置，此时也不能吞掉用户敲的字。"""
        item = self.make_box()
        self.type_text("ab")
        self.canvas.caret_offset = 999
        self.type_text("c")
        self.assertEqual(item["text"], "abc")

    def test_the_caret_survives_a_stale_formula_slot(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.canvas.editing_slot = (7, "num")       # 不存在的路径
        self.type_text("z")
        self.assertIn("z", formula.plain_text(item["formula"]))

    def test_home_and_end_reach_both_ends(self):
        item = self.make_box()
        self.type_text("abc")
        self.canvas.caret_to_line_edge(home=True)
        self.assertEqual(self.canvas.caret_offset, 0)
        self.canvas.caret_to_line_edge(home=False)
        self.assertEqual(self.canvas.caret_offset, 3)

    def test_the_caret_cannot_leave_the_content(self):
        item = self.make_box()
        self.type_text("ab")
        self.assertFalse(self.canvas.move_caret(+5))
        self.canvas.set_caret(0)
        self.assertFalse(self.canvas.move_caret(-1))
        self.assertEqual(self.canvas.caret_offset, 0)


class CaretBlinkTests(WorkflowCase):
    """5.4.0 request: "光标应该闪烁，不该静止"."""

    def test_editing_starts_the_blink(self):
        self.make_box()
        self.assertTrue(self.canvas._caret_timer is not None
                        and self.canvas._caret_timer.isActive(),
                        "进入编辑态没有起闪烁计时器，光标是静止的")

    def test_the_phase_actually_toggles(self):
        item = self.make_box()
        self.type_text("a")
        first = self.canvas.caret_visible
        self.canvas._caret_tick()
        self.assertNotEqual(self.canvas.caret_visible, first)
        self.canvas._caret_tick()
        self.assertEqual(self.canvas.caret_visible, first)

    def test_leaving_edit_mode_stops_the_blink(self):
        self.make_box()
        self.type_text("x")
        self.panel._text_done()
        self.assertFalse(self.canvas._caret_timer.isActive(),
                         "退出编辑后计时器还在跑，等于每半秒白刷一次屏")

    def test_typing_shows_the_caret_immediately(self):
        """刚敲完/刚点过必须看得见光标，否则正好落在熄灭那半拍会以为没生效。"""
        item = self.make_box()
        self.type_text("a")
        self.canvas.caret_visible = False
        self.canvas.set_caret(0)
        self.assertTrue(self.canvas.caret_visible)

    def test_the_blink_only_repaints_the_caret(self):
        """闪烁是常驻开销：刷整框等于编辑态永远在重绘。"""
        item = self.make_box()
        self.type_text("abc")
        areas = self.record_repaints(self.canvas._caret_tick)
        self.assertEqual(len(areas), 1)
        caret = self.canvas.caret_rect(item)
        painted = areas[0][0]
        self.assertLess(painted.width(), caret.width() + 20)
        self.assertLess(painted.height(), caret.height() + 20)

    def test_the_caret_tick_never_raises_without_an_edit(self):
        self.canvas.end_text_edit()
        self.canvas._caret_tick()       # 不应抛异常

    def test_the_caret_draws_in_both_modes(self):
        from PyQt6.QtGui import QPixmap, QPainter

        for build in (lambda: None, lambda: self.panel._symbol_pressed(("!frac", "a/b"))):
            with self.subTest(mode=build):
                item = self.make_box()
                build()
                self.type_text("1")
                pixmap = QPixmap(400, 300)
                painter = QPainter(pixmap)
                try:
                    self.canvas._draw_caret(painter, item)
                finally:
                    painter.end()
                self.canvas.end_text_edit()


class SymbolPanelContentTests(WorkflowCase):
    """5.4.0 report: "打几个字，文本框里出现了，符号面板却没出现".

    In 5.3.x the input widget was deliberately blank in formula mode, so the user saw
    their characters on the canvas and nothing in the panel.
    """

    def panel_text(self):
        return self.panel.text_input.toPlainText()

    def test_plain_text_shows_in_the_panel(self):
        self.make_box()
        self.type_text("hello")
        self.assertEqual(self.panel_text(), "hello")

    def test_formula_characters_show_in_the_panel(self):
        self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("123")
        self.assertEqual(self.panel_text(), "123")

    def test_the_panel_shows_the_slot_the_caret_is_in(self):
        self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("12")
        self.canvas.editing_slot = (0, "den")
        self.canvas.set_caret(0)
        self.type_text("9")
        self.assertEqual(self.panel_text(), "9")

    def test_a_structure_is_one_placeholder_character_in_the_panel(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!sqrt", "√‾"))
        self.canvas.editing_slot = None
        self.canvas.set_caret(0)
        self.panel.text_input.sync_from_canvas()
        self.assertEqual(self.panel_text(), formula.PLACEHOLDERS["sqrt"])

    def test_the_panel_keeps_up_with_backspace(self):
        self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("12")
        self.type_key(self.main.Qt.Key.Key_Backspace)
        self.assertEqual(self.panel_text(), "1")

    def test_the_panel_keeps_up_with_the_backspace_button(self):
        self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("12")
        self.panel._text_backspace()
        self.pump()
        self.assertEqual(self.panel_text(), "1")

    def test_the_panel_cursor_follows_a_canvas_click(self):
        item = self.make_box()
        self.type_text("abcd")
        self.canvas.caret_offset = 1
        rect = self.canvas.caret_rect(item)
        self.click(int(round(rect.center().x())), int(round(rect.center().y())))
        self.assertEqual(self.panel.text_input.textCursor().position(), 1)

    def test_moving_the_panel_cursor_moves_the_canvas_caret(self):
        """反向也要通：在面板里点一下光标，画布插入点跟着走。"""
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("123")
        cursor = self.panel.text_input.textCursor()
        cursor.setPosition(1)
        self.panel.text_input.setTextCursor(cursor)
        self.pump()
        self.assertEqual(self.canvas.caret_offset, 1)
        self.type_text("9")
        self.assertEqual(formula.plain_text(item["formula"]), "(1923)/()")

    def test_the_panel_never_writes_a_placeholder_into_the_formula(self):
        """占位符只是显示用的：它要是被当成真字符回写，公式里会多出一个 ▨。"""
        item = self.make_box()
        self.panel._symbol_pressed(("!sqrt", "√‾"))
        self.canvas.editing_slot = None
        self.canvas.set_caret(1)
        self.panel.text_input.sync_from_canvas()
        self.type_text("x")
        self.assertNotIn(formula.PLACEHOLDERS["sqrt"],
                         formula.plain_text(item["formula"]))

    def test_switching_boxes_reloads_the_panel(self):
        first = self.make_box(300, 300, 500, 380)
        self.type_text("one")
        self.panel._text_done()
        second = self.make_box(300, 450, 500, 530)
        self.type_text("two")
        self.assertEqual(self.panel_text(), "two")


class TypingCostTests(WorkflowCase):
    """5.4.0 report: "且字越多越卡".

    The per-keystroke work was full-scope: whole-screen repaint, whole-page deep
    copy, whole floating-window restack. These pin the shape of the fix, because a
    wall-clock assertion would be flaky on a loaded machine.
    """

    def test_a_keystroke_repaints_only_the_box(self):
        item = self.make_box(300, 300, 560, 420)
        self.type_text("abc")
        areas = self.record_repaints(lambda: self.canvas.text_insert("d"))
        self.assertTrue(areas, "一个字符都没触发重绘")
        for call in areas:
            self.assertTrue(call, "整屏重绘：update() 无参数意味着刷整个画布")
            painted = call[0]
            self.assertLess(painted.width(), 700, "重绘范围远大于文本框")

    def test_wrapping_is_computed_once_per_change(self):
        """text_lines 每键会被问 3 次，入参完全相同——缓存必须命中。"""
        item = self.make_box()
        self.type_text("some text here")
        calls = []
        canvas_type = self.main.DrawingCanvas
        original = canvas_type.__dict__["_wrap_paragraph"]
        inner = original.__func__
        try:
            canvas_type._wrap_paragraph = classmethod(
                lambda cls, *a, **k: (calls.append(1), inner(cls, *a, **k))[1])
            self.canvas.text_lines(item)
            self.canvas.text_lines(item)
            self.canvas.text_lines(item)
        finally:
            canvas_type._wrap_paragraph = original
        self.assertEqual(len(calls), 0, "折行没有缓存，同一内容被反复重算")

    def test_the_layout_is_computed_once_per_change(self):
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("12")
        calls = []
        original = formula.layout
        try:
            formula.layout = lambda *a, **k: (calls.append(1), original(*a, **k))[1]
            self.canvas.formula_box(item)
            self.canvas.formula_box(item)
        finally:
            formula.layout = original
        self.assertEqual(len(calls), 0, "公式排版没有缓存")

    def test_changing_content_invalidates_the_layout_cache(self):
        """缓存漏失效比慢更难查：表现是「打了字公式不变」。"""
        item = self.make_box()
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.type_text("1")
        before = self.canvas.formula_box(item).w
        self.type_text("234")
        self.assertGreater(self.canvas.formula_box(item).w, before)

    def test_changing_content_invalidates_the_wrap_cache(self):
        item = self.make_box()
        self.type_text("a")
        before = len(self.canvas.text_lines(item))
        self.type_text("一二三四五六七八九十一二三四五六七八九十")
        self.assertGreater(len(self.canvas.text_lines(item)), before)

    def test_wrapping_stays_linear_in_length(self):
        """O(n²) 折行就是「越打越卡」：原来每个字符都要量整行的宽度。"""
        item = self.make_box(300, 300, 500, 400)
        font = self.canvas.text_font(item)
        metrics = self.canvas.text_metrics(font)
        key = (font.family(), font.pointSizeF(), font.bold())
        counts = {}
        for length in (60, 240):
            calls = []
            original = metrics.horizontalAdvance

            class Counting:
                def __getattr__(self, name):
                    return getattr(metrics, name)

                def horizontalAdvance(self, *a):
                    calls.append(1)
                    return original(*a)

            self.main.DrawingCanvas._wrap_paragraph("一" * length, Counting(),
                                                    200.0, key)
            counts[length] = len(calls)
        # 线性时 4 倍长度约 4 倍调用；平方时约 16 倍。取 8 倍作为分界。
        self.assertLess(counts[240], counts[60] * 8,
                        f"折行开销超线性增长：{counts}")

    def test_wrapping_still_respects_the_box_width(self):
        """加速不能牺牲正确性：每一行都必须真的装得下。"""
        item = self.make_box(300, 300, 460, 500)
        self.type_text("一二三四五六七八九十abcdefghij一二三四五六七八九十")
        metrics = self.canvas.text_metrics(self.canvas.text_font(item))
        limit = self.canvas.text_local_rect(item).width() - self.canvas.TEXT_PAD * 2
        for line in self.canvas.text_lines(item):
            self.assertLessEqual(metrics.horizontalAdvance(line), limit + 0.5,
                                 f"这一行装不下：{line!r}")

    def test_typing_does_not_restack_the_window_chain(self):
        """重排是 Win32 调用（实测 1.9ms/键），而打字不会改变层级。"""
        item = self.make_box()
        calls = []
        self.panel.restack_floatings = lambda *a, **k: calls.append(1)
        try:
            self.type_text("abcdef")
        finally:
            del self.panel.restack_floatings
        self.assertEqual(calls, [], "打字触发了窗口重排")

    def test_typing_on_the_whiteboard_does_not_copy_the_page_per_key(self):
        self.canvas.enter_whiteboard()
        self.pump()
        try:
            item = self.make_box()
            calls = []
            self.canvas.save_current_page = lambda *a, **k: calls.append(1)
            try:
                self.type_text("abcdefgh")
            finally:
                del self.canvas.save_current_page
            self.assertLessEqual(len(calls), 1, f"每键都在深拷贝整页：{len(calls)} 次")
        finally:
            self.canvas.exit_whiteboard()
            self.pump()

    def test_the_debounced_snapshot_still_lands(self):
        """省下的拷贝不能把内容丢了：最后那一次必须写进页面。"""
        self.canvas.enter_whiteboard()
        self.pump()
        try:
            item = self.make_box()
            self.type_text("kept")
            self.canvas.flush_pending_snapshot()
            page = self.canvas.pages[self.canvas.current_page]
            self.assertIn("kept", [t.get("text", "") for t in page.get("texts", [])])
        finally:
            self.canvas.exit_whiteboard()
            self.pump()

    def test_a_pending_snapshot_cannot_land_on_the_wrong_page(self):
        """延后的快照要是在翻页之后才落，会把内容写进另一页。"""
        self.canvas.enter_whiteboard()
        self.pump()
        try:
            self.make_box()
            self.type_text("page one")
            self.canvas.new_page()
            self.pump()
            self.canvas.flush_pending_snapshot()
            texts = [t.get("text", "")
                     for t in self.canvas.pages[self.canvas.current_page].get("texts", [])]
            self.assertNotIn("page one", texts)
        finally:
            self.canvas.exit_whiteboard()
            self.pump()

    def test_cache_keys_never_reach_a_saved_project(self):
        """缓存键住在 item 字典里，漏进存档就会写进用户的项目文件。"""
        item = self.make_box()
        self.type_text("abc")
        self.canvas.text_lines(item)
        self.assertIn("_wrap_cache", item, "这个用例假设缓存就在 item 里")
        page = self.main.serialize_page(self.canvas.capture_page())
        for stored in page.get("texts", []):
            for key in ("_wrap_cache", "_box_cache", "_rev"):
                self.assertNotIn(key, stored, f"{key} 漏进了存档")


class ClippedPaintTests(WorkflowCase):
    """paintEvent 只重画失效区域，是 5.4.0 降低每键耗时最大的一项改动。

    风险不在慢，在残影和导出缺内容：裁剪一旦漏画，屏幕上留的是上一帧的像素，而
    导出要是也跟着裁，用户的文件里就会少东西。所以这里两头都钉住。
    """

    def drawn_texts(self, **kwargs):
        """draw_content 实际画过的文本对象内容。"""
        seen = []
        canvas = self.canvas
        original = type(canvas).draw_text_item
        canvas.draw_text_item = lambda painter, item, editing=False: seen.append(
            (item.get("text", ""), editing))
        try:
            original_segments = canvas.draw_segments
            canvas.draw_segments = lambda *a, **k: None
            try:
                canvas.draw_content(self.painter(), **kwargs)
            finally:
                del canvas.draw_segments
        finally:
            del canvas.draw_text_item
        return seen

    def painter(self):
        """一个只吞调用的假 painter：这些用例关心谁被画，不关心画成什么样。"""
        class Sink:
            def __getattr__(self, name):
                return lambda *a, **k: None
        return Sink()

    def two_far_apart_boxes(self):
        from PyQt6.QtCore import QRectF

        near = self.canvas.finish_text_box(QRectF(100, 100, 200, 80))
        near["text"] = "near"
        far = self.canvas.finish_text_box(QRectF(1200, 900, 200, 80))
        far["text"] = "far"
        return near, far

    def test_a_clipped_paint_skips_boxes_it_cannot_reach(self):
        from PyQt6.QtCore import QRectF

        self.two_far_apart_boxes()
        drawn = self.drawn_texts(clip=QRectF(80, 80, 260, 140))
        self.assertEqual([t for t, _ in drawn], ["near"])

    def test_export_draws_every_box(self):
        """导出走 clip=None：一个对象都不能少。"""
        self.two_far_apart_boxes()
        drawn = self.drawn_texts()
        self.assertEqual(sorted(t for t, _ in drawn), ["far", "near"])

    def test_the_editing_box_is_drawn_once_per_frame(self):
        """编辑中的框由 paintEvent 带虚框画一次，draw_content 不能再画一遍。"""
        item = self.make_box()
        self.type_text("hi")
        seen = []
        canvas = self.canvas
        canvas.draw_text_item = lambda painter, it, editing=False: seen.append(
            (it["id"], editing))
        try:
            canvas.paintEvent(self.paint_event(canvas.rect()))
        finally:
            del canvas.draw_text_item
        mine = [entry for entry in seen if entry[0] == item["id"]]
        self.assertEqual(len(mine), 1, f"编辑中的框画了 {len(mine)} 遍")
        self.assertTrue(mine[0][1], "唯一那次必须是带虚框的编辑态渲染")

    def test_a_pass_through_paint_still_draws_the_edited_box(self):
        """穿透模式不画编辑 HUD，那时这一框必须走常态渲染，不能被跳过。"""
        item = self.make_box()
        self.type_text("hi")
        self.canvas.is_drawing_mode = False
        seen = []
        canvas = self.canvas
        canvas.draw_text_item = lambda painter, it, editing=False: seen.append(
            (it["id"], editing))
        try:
            canvas.paintEvent(self.paint_event(canvas.rect()))
        finally:
            del canvas.draw_text_item
            self.canvas.is_drawing_mode = True
        self.assertEqual([e[1] for e in seen if e[0] == item["id"]], [False])

    def paint_event(self, rect):
        from PyQt6.QtGui import QPaintEvent

        return QPaintEvent(rect)

    def test_a_clipped_paint_skips_strokes_it_cannot_reach(self):
        from PyQt6.QtCore import QLine, QRectF
        from PyQt6.QtGui import QColor, QPen

        pen = QPen(QColor("#ff0000"), 3)
        segments = [{"id": 1, "pen": pen, "line": QLine(10, 10, 40, 40)},
                    {"id": 2, "pen": pen, "line": QLine(1400, 900, 1430, 930)}]
        drawn = []

        class Sink:
            def drawLine(self, line):
                drawn.append((line.x1(), line.y1()))

            def __getattr__(self, name):
                return lambda *a, **k: None

        self.canvas.draw_segments(Sink(), segments, clip=QRectF(0, 0, 200, 200))
        self.assertEqual(drawn, [(10.0, 10.0)])

    def test_export_draws_every_stroke(self):
        from PyQt6.QtCore import QLine
        from PyQt6.QtGui import QColor, QPen

        pen = QPen(QColor("#ff0000"), 3)
        segments = [{"id": 1, "pen": pen, "line": QLine(10, 10, 40, 40)},
                    {"id": 2, "pen": pen, "line": QLine(1400, 900, 1430, 930)}]
        drawn = []

        class Sink:
            def drawLine(self, line):
                drawn.append((line.x1(), line.y1()))

            def __getattr__(self, name):
                return lambda *a, **k: None

        self.canvas.draw_segments(Sink(), segments)
        self.assertEqual(len(drawn), 2)

    def test_a_thick_stroke_just_outside_the_clip_still_draws(self):
        """笔宽会溢出到两侧：只比线段坐标会在粗笔下留下半条笔迹。"""
        from PyQt6.QtCore import QLine, QRectF
        from PyQt6.QtGui import QColor, QPen

        # 线在 x=210，裁剪区右边到 200；笔宽 40 意味着它向左溢出 20，正好压进来。
        segments = [{"id": 1, "pen": QPen(QColor("#ff0000"), 40),
                     "line": QLine(210, 100, 210, 140)}]
        drawn = []

        class Sink:
            def drawLine(self, line):
                drawn.append(line.x1())

            def __getattr__(self, name):
                return lambda *a, **k: None

        self.canvas.draw_segments(Sink(), segments, clip=QRectF(0, 0, 200, 200))
        self.assertEqual(drawn, [210.0], "粗笔的溢出没算进来，会留下半条笔迹")

    def test_a_marker_stroke_is_composited_as_one_path(self):
        """荧光笔整笔一次合成：裁剪不能把一笔切成两段，否则重叠处会叠色。"""
        from PyQt6.QtCore import QLine, QRectF
        from PyQt6.QtGui import QColor, QPen

        pen = QPen(QColor(255, 0, 0, 120), 20)
        segments = [{"id": 7, "marker": True, "pen": pen, "line": QLine(10, 10, 60, 10)},
                    {"id": 7, "marker": True, "pen": pen, "line": QLine(60, 10, 110, 10)}]
        paths = []

        class Sink:
            def drawPath(self, path):
                paths.append(path.elementCount())

            def __getattr__(self, name):
                return lambda *a, **k: None

        self.canvas.draw_segments(Sink(), segments, clip=QRectF(0, 0, 400, 400))
        self.assertEqual(len(paths), 1, "一笔荧光笔被画成了多条路径")

    def test_a_marker_stroke_outside_the_clip_is_skipped(self):
        from PyQt6.QtCore import QLine, QRectF
        from PyQt6.QtGui import QColor, QPen

        pen = QPen(QColor(255, 0, 0, 120), 20)
        segments = [{"id": 7, "marker": True, "pen": pen,
                     "line": QLine(1400, 900, 1450, 900)}]
        paths = []

        class Sink:
            def drawPath(self, path):
                paths.append(1)

            def __getattr__(self, name):
                return lambda *a, **k: None

        self.canvas.draw_segments(Sink(), segments, clip=QRectF(0, 0, 200, 200))
        self.assertEqual(paths, [])

    def test_the_repainted_rect_covers_the_box_after_it_grows(self):
        """内容变长会把框撑高，失效区域必须盖住变高之后的样子。"""
        item = self.make_box(300, 300, 560, 380)
        self.type_text("一二三")
        areas = self.record_repaints(lambda: self.canvas.text_insert("四" * 40))
        after = self.canvas.text_bounds(item)
        covered = None
        for call in areas:
            if not call:
                return          # 整屏重绘也算盖住了
            rect = call[0]
            covered = rect if covered is None else covered.united(rect)
        self.assertIsNotNone(covered)
        self.assertTrue(covered.contains(after.toAlignedRect()),
                        "重绘区域没盖住长高之后的文本框，屏幕上会留下残影")

    def test_the_repainted_rect_covers_the_box_after_it_shrinks(self):
        """删字会让框变矮，旧区域也得一起擦掉。"""
        item = self.make_box(300, 300, 560, 380)
        self.type_text("一二三" * 20)
        before = self.canvas.text_bounds(item)
        areas = self.record_repaints(
            lambda: [self.canvas.text_backspace() for _ in range(40)])
        covered = None
        for call in areas:
            if not call:
                return
            rect = call[0]
            covered = rect if covered is None else covered.united(rect)
        self.assertIsNotNone(covered)
        self.assertTrue(covered.contains(before.toAlignedRect()),
                        "变矮后没擦掉原来的区域，屏幕上会留下残影")


class PaintResidueTests(WorkflowCase):
    """裁剪重绘会不会留残影——按像素比，不靠肉眼。

    做法：把画布渲染进两张同样的图。一张只重放打字过程中真正失效的那些矩形（屏幕
    上就是这么刷的），另一张最后整屏画一遍。两张不一致的地方，就是用户会看到的残影。

    容差不是零。同一条线裁剪着画和整屏画，抗锯齿在裁剪边界上的覆盖率会差一两级，
    这是光栅化的正常差异；残影则是整个字留在原地，差值几百。所以按幅度判，不按个数。
    """

    TOLERANCE = 24              # 单通道差值上限：抗锯齿差个位数，残影是几百

    def render_region(self, image, rect):
        """按 Qt 刷一块区域的方式渲染：先清成透明，再画。

        半透明窗口上 Qt 会先把失效区域清掉再发 paintEvent。少了这一步，每帧会叠在
        上一帧上（画布背景 alpha=1），叠出来的重影是这套量法自己的毛病，不是残影。
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QRegion

        painter = QPainter(image)
        try:
            painter.setClipRect(rect)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self.canvas.render(painter, QPoint(rect.x(), rect.y()), QRegion(rect))
        finally:
            painter.end()

    def blank_image(self):
        from PyQt6.QtGui import QImage

        image = QImage(self.canvas.width(), self.canvas.height(),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        return image

    def worst_delta(self, a, b):
        """两张图最大的单通道差值，以及差得离谱的像素个数。"""
        if a.constBits().asstring(a.sizeInBytes()) == b.constBits().asstring(b.sizeInBytes()):
            return 0, 0
        worst, bad = 0, 0
        for y in range(a.height()):
            for x in range(a.width()):
                pa, pb = a.pixel(x, y), b.pixel(x, y)
                if pa == pb:
                    continue
                delta = max(abs(((pa >> s) & 255) - ((pb >> s) & 255))
                            for s in (0, 8, 16, 24))
                worst = max(worst, delta)
                if delta > self.TOLERANCE:
                    bad += 1
        return worst, bad

    def lay_down_strokes(self):
        """一些已有笔迹，好让裁剪有东西可以漏画。"""
        from PyQt6.QtCore import QLine
        from PyQt6.QtGui import QColor, QPen

        # QLine, not QLine: clone_segments 用 QLine(seg["line"]) 深拷贝，喂 QLine
        # 会在撤销快照里炸——这里跟真实数据保持一致。
        pen = QPen(QColor("#e74c3c"), 6)
        for i in range(24):
            self.canvas.all_segments.append(
                {"id": 900 + i, "pen": pen,
                 "line": QLine(200 + i * 14, 250, 260 + i * 14, 620)})

    def replay(self, image, actions):
        """执行每个动作，只把它失效的那些矩形重画到 image 上。"""
        from PyQt6.QtCore import QRect

        full = QRect(0, 0, self.canvas.width(), self.canvas.height())
        for action in actions:
            rects = self.record_repaints(action)
            for call in rects:
                if not call:
                    self.render_region(image, full)      # 整屏重绘
                    continue
                rect = call[0] if len(call) == 1 else QRect(*call)
                clipped = QRect(rect).intersected(full)
                if not clipped.isEmpty():
                    self.render_region(image, clipped)

    def check_no_residue(self, actions):
        from PyQt6.QtCore import QRect

        full = QRect(0, 0, self.canvas.width(), self.canvas.height())
        incremental = self.blank_image()
        self.render_region(incremental, full)       # 先有一帧正确的整屏，跟真屏一样
        self.replay(incremental, actions)
        reference = self.blank_image()
        self.render_region(reference, full)
        # 先证明这一帧真的画出了东西。离屏平台没有字体目录，字形可能一个都不光栅化，
        # 那时两张图都是空的，比出来永远「没有残影」——用例会变成一句空话。
        self.assertGreater(self.opaque_pixels(reference), 200,
                           "参考帧几乎是空的，这台环境画不出内容，比对没有意义")
        worst, bad = self.worst_delta(incremental, reference)
        self.assertEqual(bad, 0,
                         f"{bad} 个像素与整屏重绘不符（最大差 {worst}），屏幕上会留残影")

    def opaque_pixels(self, image):
        """画上了东西的像素数。背景 alpha=1，所以门槛取 8 就够分开背景和内容。"""
        count = 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                if ((image.pixel(x, y) >> 24) & 255) > 8:
                    count += 1
        return count

    def test_typing_leaves_no_residue(self):
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        text = "上山打老虎一二三四五六七八九十甲乙丙丁戊己庚辛壬癸"
        self.check_no_residue([
            (lambda ch=ch: self.canvas.text_insert(ch)) for ch in text])

    def test_deleting_leaves_no_residue(self):
        """删字让框变矮，旧的那几行必须被擦掉。"""
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.type_text("上山打老虎一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯")
        self.check_no_residue([self.canvas.text_backspace for _ in range(24)])

    def test_a_blinking_caret_leaves_no_residue(self):
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.type_text("闪烁")
        self.check_no_residue([self.canvas._caret_tick for _ in range(4)])

    def test_inserting_at_a_clicked_caret_leaves_no_residue(self):
        """插在中间会把后面的字全推走，重绘范围必须覆盖整框。"""
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.type_text("一二三四五六七八九十")
        actions = [lambda: self.canvas.set_caret(3)]
        actions += [(lambda ch=ch: self.canvas.text_insert(ch)) for ch in "插进来"]
        self.check_no_residue(actions)

    def test_one_insert_that_adds_many_lines_leaves_no_residue(self):
        """一次插入好几行：输入法一次上屏一整串，框会一下长高很多。

        逐字打的时候，「变更前的包围盒」跟变更后只差一行，重绘范围的余量顺手就盖住了；
        一次插进十几个字，差的是好几行，盖不住就会看到下半截是旧内容。
        """
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.check_no_residue([
            lambda: self.canvas.text_insert("上山打老虎一二三四五六七八九十甲乙丙丁戊己庚辛壬癸")])

    def test_deleting_many_lines_at_once_leaves_no_residue(self):
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.type_text("上山打老虎一二三四五六七八九十甲乙丙丁戊己庚辛壬癸")
        self.check_no_residue([
            lambda: [self.canvas.text_backspace() for _ in range(22)]])

    def test_a_formula_leaves_no_residue(self):
        self.lay_down_strokes()
        self.make_box(300, 300, 660, 338)
        self.panel._symbol_pressed(("!frac", "a/b"))
        self.check_no_residue([
            (lambda ch=ch: self.canvas.text_insert(ch)) for ch in "1234"])


class UndoWorkflowTests(WorkflowCase):
    def test_a_finished_box_can_be_undone(self):
        self.make_box()
        self.type_text("undo me")
        self.panel._text_done()
        self.assertEqual(len(self.canvas.text_items), 1)
        self.canvas.undo()
        self.assertEqual(self.canvas.text_items, [])

    def test_undo_while_editing_does_not_leave_a_ghost(self):
        self.make_box()
        self.type_text("x")
        self.canvas.undo()
        self.pump()
        self.assertIsNone(self.canvas.editing_text_item())


if __name__ == "__main__":
    unittest.main(verbosity=2)
