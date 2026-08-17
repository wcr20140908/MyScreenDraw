"""Landscape/portrait layout, live thumbnails, and hold-to-recognize behaviour.

Every test here pins a defect that was reported from the classroom touch screen:
the rotate key covering the title bar, submenus opening at the far left instead of
under the button that spawned them, submenus covering the toolbar when the panel
sits at the bottom of the screen, the panel sliding off screen when rotated while
docked to the right edge, whiteboard button labels being clipped in landscape,
thumbnails lagging behind the ink, and straight lines converting after the pen is
lifted instead of while it rests on the last point.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_panel():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import main

    panel = main.ControlPanel()
    canvas = main.DrawingCanvas(panel)
    panel.canvas = canvas
    panel.show()
    return app, main, panel, canvas


class PanelTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app, cls.main, cls.panel, cls.canvas = _build_panel()
        except Exception as exc:  # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")

    @classmethod
    def tearDownClass(cls):
        for stopper in (getattr(getattr(cls, "panel", None), "listener", None),
                        getattr(getattr(cls, "panel", None), "timer", None),
                        getattr(getattr(cls, "panel", None), "autosave_timer", None),
                        getattr(getattr(cls, "panel", None), "_thumbnail_live_timer", None)):
            try:
                stopper.stop()
            except Exception:
                pass

    def setUp(self):
        self.panel.set_orientation("portrait")
        self.panel.show_only_sub(None)

    def screen(self):
        from PyQt6.QtWidgets import QApplication

        obj = self.panel.active_screen(self.panel)
        return obj.availableGeometry() if obj else QApplication.primaryScreen().availableGeometry()


class RotateButtonTests(PanelTestCase):
    def test_rotate_button_is_icon_only(self):
        """带文字的旋转键会吃掉标题栏一半宽度，横版下把标题挤到显示不全。"""
        self.assertEqual(self.panel.btn_rotate.text(), "")
        self.assertFalse(self.panel.btn_rotate.icon().isNull(), "旋转键必须有图标")

    def test_rotate_button_has_no_tooltip(self):
        """提示气泡弹在光标下方会盖住标题栏，且排不进本程序的置顶层。"""
        self.assertEqual(self.panel.btn_rotate.toolTip(), "")

    def test_rotate_button_stays_square_and_touch_sized(self):
        self.panel.btn_rotate.ensurePolished()
        size = self.panel.btn_rotate.sizeHint()
        self.assertLessEqual(size.width(), self.main.TOUCH_SQUARE + 2)
        self.assertGreaterEqual(self.main.TOUCH_SQUARE, 32, "图标按钮不应小于 32px")


class OrientationClampTests(PanelTestCase):
    def test_rotating_at_the_right_edge_keeps_the_panel_on_screen(self):
        """竖版贴右边缘旋转成横版后会宽出一大截，必须收回屏幕内。"""
        screen = self.screen()
        self.panel.move(screen.right() - self.panel.width(), screen.top() + 40)
        self.panel.set_orientation("landscape")
        self.assertGreaterEqual(self.panel.x(), screen.left())
        # 横版比屏幕还宽时（离屏测试环境是 800x600）只能贴左边露出前半截，
        # 但绝不允许维持旋转前那个「整条挂在屏幕右外侧」的位置。
        limit = max(screen.right(), screen.left() + self.panel.width())
        self.assertLessEqual(self.panel.x() + self.panel.width(), limit + 1)

    def test_rotating_at_the_bottom_edge_keeps_the_panel_on_screen(self):
        """横转竖同理：高度暴涨后不能掉到屏幕下方。"""
        self.panel.set_orientation("landscape")
        screen = self.screen()
        self.panel.move(screen.left() + 40, screen.bottom() - self.panel.height())
        self.panel.set_orientation("portrait")
        self.assertLessEqual(self.panel.y() + self.panel.height(), screen.bottom() + 1)
        self.assertGreaterEqual(self.panel.y(), screen.top())

    def test_portrait_panel_stays_compact(self):
        """回归：普通按钮不能被全局 min-height+padding 撑成截图里的超高大块。"""
        self.panel.set_orientation("portrait")
        self.canvas.whiteboard_mode = False
        self.panel.update_whiteboard_ui()
        self.assertLessEqual(self.panel.height(), 430,
                             "竖版主面板过高，普通按钮可能又继承了全局最小高度")
        for button in (self.panel.btn_mode, self.panel.btn_pen, self.panel.btn_eraser,
                       self.panel.btn_select, self.panel.btn_text, self.panel.btn_shape,
                       self.panel.btn_tools):
            self.assertLessEqual(button.sizeHint().height(), 36,
                                 f"{button.text()} 按钮被异常撑高")

    def test_pen_settings_panel_stays_compact_and_ordered(self):
        """回归：颜色区、预览条、粗细标签、滑块不能再互相错位。"""
        self.panel.show_only_sub(self.panel.draw_sub)
        panel = self.panel.menu_panel
        self.assertLessEqual(panel.height(), 260, "批注设置面板被全局按钮高度撑高")
        self.assertLess(self.panel.color_preview.geometry().bottom(),
                        self.panel.label_w.geometry().top() + 1,
                        "颜色预览条与粗细标签发生重叠/错位")
        self.assertGreaterEqual(self.panel.color_preview.width(), 120,
                                "颜色预览条被压缩错位")

    def test_orientation_is_remembered_across_restarts(self):
        """教室大屏一旦横着用就会一直横着用，不该每次开机都退回竖版。"""
        self.panel.set_orientation("landscape")
        self.assertEqual(self.panel.collect_settings().get("orientation"), "landscape")
        self.panel.set_orientation("portrait")
        self.assertEqual(self.panel.collect_settings().get("orientation"), "portrait")

    def test_whiteboard_controls_stay_a_compact_two_row_group_in_landscape(self):
        """横版不能把 5 个白板按钮横摊成一长排，否则主题/退出按钮会被挤出屏幕。"""
        self.panel.set_orientation("landscape")
        rows = {self.panel.wb_grid.getItemPosition(i)[0]
                for i in range(self.panel.wb_grid.count())}
        self.assertEqual(rows, {0, 1}, "白板控制区应保持紧凑两行")
        self.assertLessEqual(self.panel.wb_box.sizeHint().width(), 190,
                             "白板控制区过宽会挤乱横版主栏")

    def test_whiteboard_buttons_are_wide_enough_for_their_labels(self):
        """白板小按钮应完整显示文字，同时不能靠撑高整条主栏来解决。"""
        from PyQt6.QtGui import QFontMetrics

        self.panel.set_orientation("landscape")
        self.canvas.whiteboard_mode = True
        self.panel.update_whiteboard_ui()
        for button in (self.panel.btn_prev_page, self.panel.btn_next_page,
                       self.panel.btn_new_page, self.panel.btn_board_style):
            metrics = QFontMetrics(button.font())
            self.assertGreaterEqual(button.sizeHint().width(),
                                    metrics.horizontalAdvance(button.text()),
                                    f"{button.text()} 的按钮宽度不足以显示文字")
        self.canvas.whiteboard_mode = False
        self.panel.update_whiteboard_ui()


class SubMenuAnchorTests(PanelTestCase):
    def open_shape_sub(self):
        self.panel.show_only_sub(self.panel.shape_sub)
        return self.panel.menu_panel

    def test_landscape_submenu_opens_under_its_own_button(self):
        """横版子菜单原来一律贴在面板左下角，和点的是哪个功能键完全无关。"""
        self.panel.set_orientation("landscape")
        screen = self.screen()
        self.panel.move(screen.left() + 20, screen.top() + 20)
        menu = self.open_shape_sub()
        button = self.panel.btn_shape
        button_center = button.mapToGlobal(button.rect().center()).x()
        menu_center = menu.x() + menu.width() / 2
        self.assertLess(abs(menu_center - button_center), max(60, menu.width() / 2),
                        "子菜单没有对齐到触发它的功能键")
        self.assertGreaterEqual(menu.y(), self.panel.y() + self.panel.height() - 2)

    def test_landscape_submenu_flips_above_a_bottom_docked_panel(self):
        """面板停在屏幕下方时，子菜单往下开就会盖住主菜单，必须翻到上方。"""
        self.panel.set_orientation("landscape")
        screen = self.screen()
        self.panel.move(screen.left() + 20, screen.bottom() - self.panel.height())
        menu = self.open_shape_sub()
        self.assertLessEqual(menu.y() + menu.height(), self.panel.y() + 2,
                             "子菜单应整体位于主面板上方")

    def test_portrait_submenu_flips_left_at_the_right_edge(self):
        screen = self.screen()
        self.panel.move(screen.right() - self.panel.width(), screen.top() + 20)
        menu = self.open_shape_sub()
        self.assertLessEqual(menu.x() + menu.width(), self.panel.x() + 2,
                             "子菜单应翻到主面板左侧")

    def test_portrait_submenu_lines_up_with_its_button(self):
        screen = self.screen()
        self.panel.move(screen.left() + 20, screen.top() + 20)
        menu = self.open_shape_sub()
        button_top = self.panel.btn_shape.mapToGlobal(self.panel.btn_shape.rect().topLeft()).y()
        self.assertLess(abs(menu.y() - button_top), 40, "子菜单没有与功能键同高")

    def test_dragging_the_panel_moves_an_open_submenu(self):
        """子菜单展开时拖动主面板，子菜单必须跟着走而不是钉在原地。"""
        screen = self.screen()
        self.panel.move(screen.left() + 20, screen.top() + 20)
        menu = self.open_shape_sub()
        before = (menu.x(), menu.y())
        self.panel.move(screen.left() + 20, screen.top() + 200)
        self.panel.position_menu_panel()
        self.assertNotEqual(before, (menu.x(), menu.y()))

    def test_every_submenu_has_an_anchor_button(self):
        for sub in self.panel.all_subs():
            with self.subTest(sub=sub.objectName() or sub.property("class")):
                self.assertIsNotNone(self.panel.sub_anchor_button(sub),
                                     "子菜单缺少锚点按钮，会退化成对齐面板左上角")


class LiveThumbnailTests(PanelTestCase):
    def test_thumbnail_uses_live_page_for_the_current_page(self):
        """pages[current] 要等松手才更新，用它渲染缩略图永远慢一笔。"""
        from PyQt6.QtCore import QLine, QPoint
        from PyQt6.QtGui import QPen

        self.canvas.enter_whiteboard()
        try:
            before = self.canvas.content_signature()
            self.canvas.all_segments.append(
                {"line": QLine(QPoint(10, 10), QPoint(200, 200)), "pen": QPen(), "id": "live"})
            self.assertNotEqual(before, self.canvas.content_signature(),
                                "内容指纹没能反映刚落下的笔迹")
            live = self.canvas.live_page()
            self.assertIs(live["segments"], self.canvas.all_segments, "实时页面不应拷贝")
        finally:
            self.canvas.all_segments = [s for s in self.canvas.all_segments if s.get("id") != "live"]
            self.canvas.exit_whiteboard()

    def test_live_timer_runs_only_while_the_panel_is_open(self):
        self.canvas.enter_whiteboard()
        try:
            self.assertFalse(self.panel._thumbnail_live_timer.isActive())
            self.panel.toggle_thumbnail_panel()
            self.assertTrue(self.panel._thumbnail_live_timer.isActive(), "打开后应进入实时渲染")
            self.panel.toggle_thumbnail_panel()
            self.assertFalse(self.panel._thumbnail_live_timer.isActive(), "关闭后必须停掉定时器")
        finally:
            self.canvas.exit_whiteboard()

    def test_heavy_pages_back_off_instead_of_stealing_the_ui_thread(self):
        """缩略图渲染在主线程上，重页面必须降频，否则写字会越来越顿。"""
        from PyQt6.QtCore import QLine, QPoint
        from PyQt6.QtGui import QColor, QPen

        self.canvas.enter_whiteboard()
        saved = list(self.canvas.all_segments)
        try:
            self.panel.toggle_thumbnail_panel()
            self.panel._tick_live_thumbnail()
            light = self.panel._thumbnail_live_timer.interval()
            self.assertEqual(light, self.panel.THUMBNAIL_LIVE_MS, "轻页面应保持最快节拍")

            pen = QPen(QColor("#ff4757"), 4)
            self.canvas.all_segments = [
                {"line": QLine(QPoint(100 + (i % 700), 100 + i // 700),
                               QPoint(106 + (i % 700), 103 + i // 700)), "pen": pen, "id": i}
                for i in range(9000)]
            self.panel._tick_live_thumbnail()
            heavy = self.panel._thumbnail_live_timer.interval()
            self.assertGreaterEqual(heavy, light, "重页面的节拍不应比轻页面还快")
            self.assertLessEqual(heavy, self.panel.THUMBNAIL_MAX_MS)
        finally:
            self.canvas.all_segments = saved
            self.panel.toggle_thumbnail_panel()
            self.canvas.exit_whiteboard()

    def test_tick_repaints_only_when_content_changed(self):
        from PyQt6.QtCore import QLine, QPoint
        from PyQt6.QtGui import QPen

        self.canvas.enter_whiteboard()
        try:
            self.panel.toggle_thumbnail_panel()
            self.panel._tick_live_thumbnail()
            unchanged = self.panel._thumbnail_signature
            self.panel._tick_live_thumbnail()
            self.assertEqual(unchanged, self.panel._thumbnail_signature)
            self.canvas.all_segments.append(
                {"line": QLine(QPoint(1, 1), QPoint(90, 90)), "pen": QPen(), "id": "tick"})
            self.panel._tick_live_thumbnail()
            self.assertNotEqual(unchanged, self.panel._thumbnail_signature)
        finally:
            self.canvas.all_segments = [s for s in self.canvas.all_segments if s.get("id") != "tick"]
            self.panel.toggle_thumbnail_panel()
            self.canvas.exit_whiteboard()


class HoldToRecognizeTests(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.canvas.draw_state = "PEN"
        self.canvas.smart_shapes_enabled = True
        self.canvas.all_segments = []
        self.canvas.shape_items = []
        self.canvas._cancel_smart_recognition()

    def draw_wobbly_line(self):
        """按下 → 沿一条几乎笔直的路径拖动，模拟手绘直线（笔未抬起）。"""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPen

        stroke_id = "held-stroke"
        self.canvas.current_stroke_id = stroke_id
        self.canvas.current_stroke_points = [QPointF(100 + i * 6, 300 + (i % 2)) for i in range(45)]
        self.canvas.pending_undo = self.canvas.capture_page()
        self.canvas.all_segments = [{"line": self.main.QLine(100, 300, 364, 301),
                                     "pen": QPen(), "id": stroke_id}]
        self.canvas.last_point = None
        return stroke_id

    def test_lifting_the_pen_never_converts(self):
        """旧行为是「抬笔后等 450ms 再变形」，这正是用户要去掉的那条。"""
        stroke_id = self.draw_wobbly_line()
        self.canvas._cancel_smart_recognition(drop_pending=True)   # mouseRelease 走的就是这一步
        self.assertTrue(any(s["id"] == stroke_id for s in self.canvas.all_segments),
                        "抬笔不应触发识别")
        self.assertFalse(self.canvas.shape_items)

    def test_holding_at_the_last_point_converts_in_place(self):
        stroke_id = self.draw_wobbly_line()
        self.canvas._commit_hold_recognition()
        self.assertFalse(any(s["id"] == stroke_id for s in self.canvas.all_segments),
                         "停笔后原笔迹应被替换")
        self.assertEqual([item["type"] for item in self.canvas.shape_items], ["LINE"])

    def test_conversion_ends_the_stroke_so_drawing_can_continue(self):
        self.draw_wobbly_line()
        self.canvas._commit_hold_recognition()
        self.assertIsNone(self.canvas.current_stroke_id)
        self.assertIsNone(self.canvas.last_point)

    def test_moving_the_pen_restarts_the_dwell_clock(self):
        from PyQt6.QtCore import QPointF

        self.canvas.current_stroke_id = "s"
        self.canvas._start_smart_hold(QPointF(10, 10))
        first = self.canvas._hold_since
        self.canvas._track_smart_hold(QPointF(10.5, 10.5))       # 抖动，不算移动
        self.assertEqual(first, self.canvas._hold_since)
        self.canvas._track_smart_hold(QPointF(60, 60))           # 真的移动了
        self.assertNotEqual(first, self.canvas._hold_since)
        self.canvas._cancel_smart_recognition()

    def test_dwell_is_disabled_for_other_tools(self):
        from PyQt6.QtCore import QPointF

        self.canvas.draw_state = "MARKER"
        self.canvas._start_smart_hold(QPointF(10, 10))
        self.assertFalse(self.canvas._hold_active, "荧光笔不参与图形识别")
        self.canvas.draw_state = "PEN"

    def test_dwell_is_disabled_when_smart_shapes_are_off(self):
        from PyQt6.QtCore import QPointF

        self.canvas.smart_shapes_enabled = False
        self.canvas._start_smart_hold(QPointF(10, 10))
        self.assertFalse(self.canvas._hold_active)
        self.canvas.smart_shapes_enabled = True


class StrokeLifecycleIntegrationTests(PanelTestCase):
    """用真实的 QMouseEvent 走一遍 按下→拖动→停笔→继续画→抬笔 的完整链路。"""

    def setUp(self):
        super().setUp()
        self.canvas.is_drawing_mode = True
        self.canvas.draw_state = "PEN"
        self.canvas.smart_shapes_enabled = True
        self.canvas.all_segments = []
        self.canvas.shape_items = []
        self.canvas.undo_stack = []
        self.canvas.pending_undo = None
        self.canvas._cancel_smart_recognition()

    def event(self, kind, x, y, buttons, button=None):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QMouseEvent

        if button is None:
            button = self.main.Qt.MouseButton.LeftButton
        return QMouseEvent(kind, QPointF(x, y), QPointF(x, y),
                           button, buttons,
                           self.main.Qt.KeyboardModifier.NoModifier)

    def press(self, x, y):
        from PyQt6.QtCore import QEvent

        self.canvas.mousePressEvent(self.event(QEvent.Type.MouseButtonPress, x, y,
                                               self.main.Qt.MouseButton.LeftButton))

    def move(self, x, y):
        from PyQt6.QtCore import QEvent

        self.canvas.mouseMoveEvent(self.event(QEvent.Type.MouseMove, x, y,
                                              self.main.Qt.MouseButton.LeftButton))

    def release(self, x, y):
        from PyQt6.QtCore import QEvent

        self.canvas.mouseReleaseEvent(self.event(QEvent.Type.MouseButtonRelease, x, y,
                                                 self.main.Qt.MouseButton.NoButton))

    def stroke_a_line(self):
        self.press(100, 300)
        for i in range(1, 46):
            self.move(100 + i * 6, 300 + (i % 2))

    def expire_dwell(self):
        """把停笔起点推回过去，然后手动跑一拍节拍，等价于「停住不动够久了」。"""
        self.canvas._hold_since -= (self.canvas.SMART_HOLD_MS + 50) / 1000.0
        self.canvas._tick_smart_hold()

    def test_non_left_release_does_not_abort_an_active_stroke(self):
        """笔侧键/右键释放不能把仍按着的左键笔画切成两段。"""
        from PyQt6.QtCore import QEvent

        self.stroke_a_line()
        stroke_id = self.canvas.current_stroke_id
        before = len(self.canvas.current_stroke_points)
        right_release = self.event(QEvent.Type.MouseButtonRelease, 370, 301,
                                   self.main.Qt.MouseButton.LeftButton,
                                   button=self.main.Qt.MouseButton.RightButton)
        self.canvas.mouseReleaseEvent(right_release)
        self.assertEqual(self.canvas.current_stroke_id, stroke_id)
        self.assertEqual(len(self.canvas.current_stroke_points), before)
        self.assertTrue(self.canvas._hold_active)
        self.release(370, 301)

    def test_middle_press_does_not_replace_the_undo_snapshot(self):
        """中键按下不能在一笔中途重建 pending_undo。"""
        from PyQt6.QtCore import QEvent

        self.stroke_a_line()
        snapshot = self.canvas.pending_undo
        middle_press = self.event(QEvent.Type.MouseButtonPress, 250, 300,
                                  self.main.Qt.MouseButton.LeftButton | self.main.Qt.MouseButton.MiddleButton,
                                  button=self.main.Qt.MouseButton.MiddleButton)
        self.canvas.mousePressEvent(middle_press)
        self.assertIs(self.canvas.pending_undo, snapshot)
        self.release(370, 301)

    def test_undo_mid_dwell_cancels_stale_recognition(self):
        """撤销后旧停笔计时不能把已撤掉的笔迹又识别成图形写回来。"""
        self.stroke_a_line()
        self.canvas.commit_undo(self.canvas.capture_page())
        self.canvas.undo()
        self.assertFalse(self.canvas._hold_active)
        self.assertIsNone(self.canvas.pending_undo)
        self.assertFalse(self.canvas._smart_recognize_timer.isActive())
        shapes_before = list(self.canvas.shape_items)
        self.canvas._tick_smart_hold()
        self.assertEqual(self.canvas.shape_items, shapes_before)

    def test_release_without_dwell_keeps_the_hand_drawn_stroke(self):
        self.stroke_a_line()
        self.release(370, 301)
        self.assertTrue(self.canvas.all_segments, "抬笔后手绘笔迹必须留下")
        self.assertFalse(self.canvas.shape_items, "抬笔不应产生标准图形")

    def test_dwell_while_still_pressed_converts_to_a_line(self):
        self.stroke_a_line()
        self.assertTrue(self.canvas._hold_active, "拖动过程中应处于停笔判定状态")
        self.expire_dwell()
        self.assertEqual([i["type"] for i in self.canvas.shape_items], ["LINE"])
        self.assertFalse(self.canvas.all_segments, "原笔迹应被替换掉")

    def test_drawing_continues_without_lifting_after_a_conversion(self):
        self.stroke_a_line()
        self.expire_dwell()
        self.assertIsNone(self.canvas.current_stroke_id)
        self.move(380, 380)          # 笔没抬起，接着画
        self.move(390, 400)
        self.assertIsNotNone(self.canvas.current_stroke_id, "应就地另起一笔")
        self.assertTrue(self.canvas.all_segments, "续笔应正常落墨")
        self.assertEqual(len(self.canvas.shape_items), 1, "已定形的直线不应受影响")
        self.release(390, 400)

    def test_dwell_conversion_is_undoable_in_two_steps(self):
        self.stroke_a_line()
        self.expire_dwell()
        self.release(370, 301)
        self.canvas.undo()
        self.assertTrue(self.canvas.all_segments, "第一次撤销应找回原手绘笔迹")
        self.assertFalse(self.canvas.shape_items)
        self.canvas.undo()
        self.assertFalse(self.canvas.all_segments, "第二次撤销应回到落笔之前")

    def test_release_leaves_no_timer_running(self):
        self.stroke_a_line()
        self.release(370, 301)
        self.assertFalse(self.canvas._hold_active)
        self.assertFalse(self.canvas._smart_recognize_timer.isActive(), "抬笔后停笔计时必须停掉")
        self.assertEqual(self.canvas._hold_progress, 0.0)

    def test_switching_tool_mid_dwell_cancels_it(self):
        self.stroke_a_line()
        self.panel.handle_eraser_click()
        self.assertFalse(self.canvas._hold_active)
        self.assertFalse(self.canvas._smart_recognize_timer.isActive())
        self.panel.handle_annotate_click()


class TouchReachabilityTests(PanelTestCase):
    """关掉「按住变右键」后，原本只能靠右键完成的操作必须另有可点入口。"""

    def test_each_aid_has_a_tappable_close_handle(self):
        for kind in ("ruler", "set_square_45", "set_square_30", "protractor"):
            with self.subTest(kind=kind):
                self.canvas.clear_aids()
                aid = self.canvas.add_aid(kind)
                spot = self.canvas.aid_transform(aid).map(
                    self.canvas._aid_close_handle_local(aid))
                hit_aid, mode = self.canvas.aid_hit(spot.toPoint())
                self.assertIsNotNone(hit_aid, f"{kind} 的关闭柄点不到")
                self.assertEqual(mode, "close")
        self.canvas.clear_aids()

    def test_tapping_the_close_handle_removes_only_that_aid(self):
        from PyQt6.QtCore import QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent

        self.canvas.clear_aids()
        keeper = self.canvas.add_aid("protractor")
        keeper["pos"] = QPointF(keeper["pos"].x() - 500, keeper["pos"].y())
        doomed = self.canvas.add_aid("ruler")
        spot = self.canvas.aid_transform(doomed).map(self.canvas._aid_close_handle_local(doomed))
        self.canvas.is_drawing_mode = True
        self.canvas.mousePressEvent(QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(spot), QPointF(spot),
            self.main.Qt.MouseButton.LeftButton, self.main.Qt.MouseButton.LeftButton,
            self.main.Qt.KeyboardModifier.NoModifier))
        remaining = [a["id"] for a in self.canvas.aids]
        self.assertNotIn(doomed["id"], remaining, "点击 ✕ 应移除该教具")
        self.assertIn(keeper["id"], remaining, "不应误删其他教具")
        self.assertIsNone(self.canvas.aid_drag, "点 ✕ 不应顺手开始拖动")
        self.canvas.clear_aids()

    def test_close_handle_does_not_shadow_the_rotate_handle(self):
        self.canvas.clear_aids()
        aid = self.canvas.add_aid("ruler")
        spot = self.canvas.aid_transform(aid).map(self.canvas._aid_rotate_handle_local(aid))
        _, mode = self.canvas.aid_hit(spot.toPoint())
        self.assertEqual(mode, "rotate")
        self.canvas.clear_aids()

    def test_spotlight_button_toggles_off_without_a_right_click(self):
        """聚光灯下整屏是暗的，触屏用户只能再点一次这个按钮退出。"""
        self.panel.handle_spotlight_click()
        self.assertEqual(self.canvas.draw_state, "SPOTLIGHT")
        self.panel.handle_spotlight_click()
        self.assertNotEqual(self.canvas.draw_state, "SPOTLIGHT")
        self.assertIn(self.canvas.draw_state, ("PEN", "MARKER", "LASER"))

    def test_pending_shape_points_can_be_cancelled_without_a_right_click(self):
        from PyQt6.QtCore import QPointF

        self.canvas.draw_state = "SHAPE"
        self.canvas.shape_type = "TRAPEZOID"
        self.canvas.pending_points = [QPointF(10, 10), QPointF(90, 10)]
        self.panel.cancel_shape_points()
        self.assertEqual(self.canvas.pending_points, [], "「取消取点」按钮应清掉已落顶点")
        self.canvas.draw_state = "PEN"


class ShapeRecognitionTests(unittest.TestCase):
    """用理想顶点加噪声合成手绘笔迹，锁住两类被明确报障的误判。"""

    @staticmethod
    def trace(vertices, jitter=1.2, step=5.0):
        import math
        import random

        rng = random.Random(20260811)
        points = []
        loop = list(vertices) + [vertices[0]]
        for start, end in zip(loop, loop[1:]):
            span = math.hypot(end[0] - start[0], end[1] - start[1])
            for k in range(max(2, int(span / step))):
                t = k / max(2, int(span / step))
                points.append((start[0] + (end[0] - start[0]) * t + rng.gauss(0, jitter),
                               start[1] + (end[1] - start[1]) * t + rng.gauss(0, jitter)))
        points.append(loop[-1])
        return points

    def recognize(self, vertices, **kwargs):
        import main

        spec = main.StrokeShapeRecognizer.recognize(self.trace(vertices, **kwargs))
        return spec["type"] if spec else "NONE"

    def test_trapezoid_is_not_mistaken_for_an_ellipse(self):
        for top_ratio in (0.4, 0.55, 0.7):
            with self.subTest(top_ratio=top_ratio):
                bottom, height = 320.0, 170.0
                top = bottom * top_ratio
                inset = (bottom - top) / 2
                verts = [(0.0, height), (bottom, height), (bottom - inset, 0.0), (inset, 0.0)]
                self.assertEqual(self.recognize(verts), "TRAPEZOID")

    def test_parallelogram_is_not_mistaken_for_a_triangle(self):
        for skew in (60.0, 100.0, 140.0):
            with self.subTest(skew=skew):
                width, height = 260.0, 150.0
                verts = [(0.0, height), (width, height), (width + skew, 0.0), (skew, 0.0)]
                self.assertEqual(self.recognize(verts), "PARALLELOGRAM")

    def test_rectangle_and_triangle_still_win_over_looser_models(self):
        import main

        self.assertEqual(self.recognize([(0, 0), (300, 0), (300, 180), (0, 180)]), "RECT")
        self.assertEqual(self.recognize([(0, 200), (280, 200), (130, 0)]), "TRIANGLE")
        circle = [(200 + 120 * __import__("math").cos(i / 60 * 6.28318),
                   200 + 120 * __import__("math").sin(i / 60 * 6.28318)) for i in range(61)]
        self.assertEqual(main.StrokeShapeRecognizer.recognize(circle)["type"], "CIRCLE")


if __name__ == "__main__":
    unittest.main()
