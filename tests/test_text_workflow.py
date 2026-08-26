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
