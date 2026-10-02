"""Pen styles (beta.8): creation, persistence, undo/duplicate/rotate, rendering, colour badge.

Each test drives the same entry points the UI uses (_begin_stroke / add_smooth_segments /
_finish_pointer_stroke, choose_pen_style, the colour slots), not private rendering helpers.
"""
import json
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class PenStyleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import main
        cls.main = main
        cls.panel = main.ControlPanel()
        cls.canvas = main.DrawingCanvas(cls.panel)
        cls.panel.canvas = cls.canvas
        cls.panel.set_ui_mode("icon", persist=False)

    @classmethod
    def tearDownClass(cls):
        for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
            try:
                getattr(cls.panel, name).stop()
            except Exception:
                pass

    def setUp(self):
        c = self.canvas
        c.all_segments = []
        c.text_items = []
        c.shape_items = []
        c.image_items = []
        c.selected_ids.clear()
        c.undo_stack.clear()
        c.redo_stack.clear()
        c.whiteboard_mode = False
        c.draw_state = "PEN"
        c.pen_profiles = {}
        c.pen_style = "pen"
        for style in self.main.PEN_STYLES:
            c.pen_profile(style)["width"] = 6
        c.pen_width = 6
        c.smart_shapes_enabled = True

    def stroke(self, style, points=((20, 40), (60, 44), (120, 60), (200, 90), (260, 92))):
        from PyQt6.QtCore import QPoint
        c = self.canvas
        c.pen_style = style
        c._begin_stroke(QPoint(*points[0]))
        c._start_smart_hold(QPoint(*points[0]))
        hold_started = c._hold_active
        for x, y in points[1:]:
            c.current_stroke_points.append(QPoint(x, y))
            c.add_smooth_segments(QPoint(x, y))
        stroke_id = c.current_stroke_id
        c._cancel_smart_recognition(drop_pending=True)
        c._finish_pointer_stroke()
        c.last_point = None
        return stroke_id, [s for s in c.all_segments if s["id"] == stroke_id], hold_started


class CreationTests(PenStyleTestCase):
    def test_every_style_leaves_ink_tagged_with_its_style(self):
        for style in self.main.PEN_STYLES:
            with self.subTest(style=style):
                self.setUp()
                _sid, segs, _hold = self.stroke(style)
                self.assertTrue(segs)
                expected = None if style == "pen" else style
                self.assertEqual({s.get("style") for s in segs}, {expected})

    def test_smart_shapes_only_arm_for_the_plain_pen(self):
        _sid, _segs, hold = self.stroke("pen")
        self.assertTrue(hold)
        for style in ("calligraphy", "dashed", "arrow", "fountain"):
            with self.subTest(style=style):
                _sid, _segs, hold = self.stroke(style)
                self.assertFalse(hold, f"{style} 不该进入停笔定形")

    def test_fountain_pen_tapers_at_both_ends(self):
        points = tuple((20 + i * 12, 60) for i in range(30))
        _sid, segs, _ = self.stroke("fountain", points)
        widths = [s["pen"].widthF() for s in segs]
        middle = max(widths)
        self.assertLess(widths[0], middle * 0.7, "起笔没有渐粗")
        self.assertLess(widths[-1], middle * 0.5, "收笔没有出锋")

    def test_arrow_pen_adds_a_two_stroke_head_at_the_tip(self):
        _sid, segs, _ = self.stroke("arrow", ((20, 100), (120, 100), (240, 100)))
        tip = segs[-3]["line"].p2()
        head = segs[-2:]
        self.assertEqual([s["line"].p1() for s in head], [tip, tip])
        # 水平向右画：两翼都在笔尖左侧，一上一下
        self.assertTrue(all(s["line"].p2().x() < tip.x() for s in head))
        self.assertEqual(sorted((s["line"].p2().y() > tip.y()) for s in head), [False, True])

    def test_rainbow_pen_changes_hue_along_the_stroke(self):
        _sid, segs, _ = self.stroke("rainbow", tuple((20 + i * 20, 80) for i in range(20)))
        hues = {s["pen"].color().hsvHue() for s in segs}
        self.assertGreater(len(hues), 10)

    def test_calligraphy_records_nib_angle(self):
        self.canvas.calligraphy_angle = 30
        _sid, segs, _ = self.stroke("calligraphy")
        self.assertEqual({s["nib"] for s in segs}, {30.0})


class PersistenceTests(PenStyleTestCase):
    def test_plain_pen_json_has_no_new_keys(self):
        """没用新笔形的页面必须与旧版 JSON 一致：旧版本读新文件、diff 撤销都依赖这一点。"""
        self.stroke("pen")
        data = self.main.serialize_page(self.canvas.capture_page())
        for seg in data["segments"]:
            self.assertNotIn("style", seg)
            self.assertNotIn("nib", seg)
            self.assertIsInstance(seg["width"], int)

    def test_styles_round_trip_through_json(self):
        for style in ("fountain", "calligraphy", "pencil", "neon", "dashed"):
            self.stroke(style)
        before = self.main.serialize_page(self.canvas.capture_page())
        text = json.dumps(before)
        restored = self.main.deserialize_page(json.loads(text))
        after = self.main.serialize_page(restored)
        self.assertEqual(before, after)
        self.assertTrue(any(isinstance(s["width"], float) for s in before["segments"]),
                        "钢笔的渐变宽度应以小数保存")

    def test_unknown_style_in_file_degrades_to_plain_pen(self):
        page = {"segments": [{"id": "a", "p1": [0, 0], "p2": [5, 5], "color": "#ff0000",
                              "width": 3, "style": "<script>"}]}
        seg = self.main.deserialize_page(page)["segments"][0]
        self.assertNotIn("style", seg)

    def test_settings_remember_style_and_nib(self):
        self.canvas.pen_style = "chalk"
        self.canvas.calligraphy_angle = 70
        settings = self.panel.collect_settings()
        self.assertEqual(settings["pen_style"], "chalk")
        self.assertEqual(settings["calligraphy_angle"], 70)


class EditingTests(PenStyleTestCase):
    def test_undo_redo_keeps_style(self):
        sid, _segs, _ = self.stroke("crayon")
        self.canvas.undo()
        self.assertFalse(any(s["id"] == sid for s in self.canvas.all_segments))
        self.canvas.redo()
        styles = {s.get("style") for s in self.canvas.all_segments if s["id"] == sid}
        self.assertEqual(styles, {"crayon"})

    def test_snapshot_undo_keeps_style(self):
        sid, _segs, _ = self.stroke("neon")
        self.canvas.push_undo()       # 整页快照路径（改色/擦除等走这条）
        self.canvas.all_segments = []
        self.canvas.undo()
        self.assertEqual({s.get("style") for s in self.canvas.all_segments}, {"neon"})

    def test_duplicate_keeps_style_and_nib(self):
        sid, _segs, _ = self.stroke("calligraphy")
        self.canvas.selected_ids = {sid}
        self.canvas.duplicate_selection()
        (new_id,) = self.canvas.selected_ids
        copies = [s for s in self.canvas.all_segments if s["id"] == new_id]
        self.assertTrue(copies)
        self.assertTrue(all(s.get("style") == "calligraphy" and s.get("nib") is not None for s in copies))

    def test_rotating_calligraphy_rotates_the_nib(self):
        self.canvas.calligraphy_angle = 45
        sid, _segs, _ = self.stroke("calligraphy")
        self.canvas.selected_ids = {sid}
        self.canvas.rotate_selection(90)
        nibs = {s["nib"] for s in self.canvas.all_segments if s["id"] == sid}
        self.assertEqual(nibs, {135.0})

    def test_drag_rotate_restores_nib_before_each_step(self):
        """拖动旋转每一帧都先还原再旋转；nib 不跟着还原就会一帧帧累加。"""
        self.canvas.calligraphy_angle = 10
        sid, _segs, _ = self.stroke("calligraphy")
        self.canvas.selected_ids = {sid}
        state = self.canvas.capture_selection_state()
        for _ in range(3):
            self.canvas.restore_selection_state(state)
            self.canvas.rotate_selection(20, emit_event=False)
        nibs = {s["nib"] for s in self.canvas.all_segments if s["id"] == sid}
        self.assertEqual(nibs, {30.0})

    def test_duplicated_formula_text_does_not_share_its_tree(self):
        import uuid
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QColor
        item = {"id": uuid.uuid4(), "text": "", "pos": QPointF(50, 50), "color": QColor("#000"),
                "width": 1, "size": 24, "scale": 1.0, "rotation": 0.0,
                "formula": [{"t": "text", "v": "x"}]}
        self.canvas.text_items = [item]
        self.canvas.selected_ids = {item["id"]}
        self.canvas.duplicate_selection()
        copy = next(t for t in self.canvas.text_items if t["id"] != item["id"])
        self.assertIsNot(copy["formula"], item["formula"])
        copy["formula"].append({"t": "text", "v": "y"})
        self.assertEqual(len(item["formula"]), 1)


class RenderingTests(PenStyleTestCase):
    def render(self, engine_image=True):
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtCore import Qt
        image = QImage(320, 160, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas.draw_segments(painter, self.canvas.all_segments)
        painter.end()
        return image

    def inked(self, image):
        from PyQt6.QtGui import QColor
        count = 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                if QColor(image.pixel(x, y)).lightness() < 235:
                    count += 1
        return count

    def test_every_style_puts_visible_ink_on_the_page(self):
        from PyQt6.QtGui import QColor
        self.canvas.pen_color = QColor("#1e3799")
        for style in self.main.PEN_STYLES:
            with self.subTest(style=style):
                self.setUp()
                self.canvas.pen_color = QColor("#1e3799")
                self.stroke(style)
                self.assertGreater(self.inked(self.render()), 30)

    def test_calligraphy_is_thick_across_the_nib_and_thin_along_it(self):
        from PyQt6.QtGui import QColor
        self.canvas.pen_color = QColor("#000000")
        self.canvas.calligraphy_angle = 90          # 竖直笔尖
        self.stroke("calligraphy", ((20, 40), (300, 40)))         # 横画：垂直于笔尖 → 粗
        horizontal = self.inked(self.render())
        self.setUp()
        self.canvas.pen_color = QColor("#000000")
        self.canvas.calligraphy_angle = 90
        self.stroke("calligraphy", ((160, 5), (160, 155)))        # 竖画：平行于笔尖 → 细
        vertical_len_scaled = self.inked(self.render()) * (280 / 150)
        self.assertGreater(horizontal, vertical_len_scaled * 2.5)

    def test_textured_style_exports_to_svg(self):
        from PyQt6.QtCore import QBuffer, QIODevice, QSize, QRect
        from PyQt6.QtGui import QPainter, QColor
        from PyQt6.QtSvg import QSvgGenerator
        self.canvas.pen_style = "pencil"
        self.canvas.pen_color = QColor("#1e3799")
        self.stroke("pencil")
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        generator = QSvgGenerator()
        generator.setOutputDevice(buffer)
        generator.setSize(QSize(320, 160))
        generator.setViewBox(QRect(0, 0, 320, 160))
        painter = QPainter(generator)
        self.canvas.draw_segments(painter, self.canvas.all_segments)
        painter.end()
        svg = bytes(buffer.data()).decode("utf-8", "replace")
        self.assertIn("path", svg)
        # QSvgGenerator 不认纹理画刷，会把笔迹写成纯黑 stroke="#000000"
        self.assertIn('stroke="#1e3799"', svg.lower())


class BadgeTests(PenStyleTestCase):
    def icon_image(self, btn):
        return btn.icon().pixmap(self.main.ICON_GLYPH, self.main.ICON_GLYPH).toImage()

    def test_badge_follows_pen_colour_without_resizing_the_button(self):
        from PyQt6.QtGui import QColor
        btn = self.panel.icon_buttons["pen"]
        size = btn.size()
        self.canvas.draw_state = "PEN"
        self.canvas.pen_color = QColor("#ff0000")
        self.panel.refresh_annotate_badge()
        red = self.icon_image(btn)
        self.canvas.pen_color = QColor("#0000ff")
        self.panel.refresh_annotate_badge()
        blue = self.icon_image(btn)
        self.assertNotEqual(red, blue)
        self.assertEqual(btn.size(), size)

    def test_main_button_icon_shows_the_chosen_style(self):
        self.panel.choose_pen_style("chalk")
        self.assertEqual(self.panel.icon_buttons["pen"].property("icon_name"), "chalk")
        self.assertEqual(self.canvas.draw_state, "PEN")
        self.assertEqual(self.panel.pen_style_buttons["chalk"].objectName(), "ActiveTool")
        self.assertEqual(self.panel.pen_style_buttons["pen"].objectName(), "")
        self.panel.choose_pen_style("pen")

    def test_nib_setting_only_shows_for_calligraphy(self):
        self.panel.choose_pen_style("calligraphy")
        self.assertFalse(self.panel.nib_row.isHidden())
        self.panel.choose_pen_style("pencil")
        self.assertTrue(self.panel.nib_row.isHidden())
        self.panel.choose_pen_style("pen")


class AdvancedOptionTests(PenStyleTestCase):
    render = RenderingTests.render

    def setUp(self):
        super().setUp()
        self.canvas.pen_options = {s: self.main.normalize_pen_options(s) for s in self.main.PEN_STYLE_OPTIONS}
        self.canvas._cancel_all_pointers()

    def test_each_option_changes_the_actual_ink(self):
        from PyQt6.QtGui import QColor
        points = tuple((20 + i * 8, 80) for i in range(34))
        for style, specs in self.main.PEN_STYLE_OPTIONS.items():
            for name, low, high, default in specs:
                with self.subTest(style=style, option=name):
                    images = []
                    for value in (low, high):
                        self.setUp()
                        self.canvas.pen_color = QColor("#1e3799")
                        self.canvas.speed_width_enabled = False
                        self.canvas.current_pressure = 0.25
                        self.canvas.calligraphy_angle = 90
                        self.canvas.pen_options[style][name] = value
                        self.stroke(style, points)
                        images.append(self.render())
                    self.assertNotEqual(images[0], images[1], f"{style}/{name} slider has no effect")

    def test_options_survive_snapshot_json_duplicate_and_undo(self):
        self.canvas.pen_options["dashed"] = {"dash_length": 75, "dash_gap": 65}
        sid, segs, _ = self.stroke("dashed")
        before = self.main.serialize_page(self.canvas.capture_page())
        self.assertEqual(before, self.main.serialize_page(self.main.deserialize_page(before)))
        self.canvas.selected_ids = {sid}
        self.canvas.duplicate_selection()
        copies = [s for s in self.canvas.all_segments if s["id"] != sid]
        self.assertEqual(copies[0]["options"], segs[0]["options"])
        self.assertIsNot(copies[0]["options"], segs[0]["options"])
        self.canvas.undo()
        self.canvas.undo()
        self.canvas.redo()
        self.assertEqual(self.canvas.all_segments[0]["options"], {"dash_length": 75, "dash_gap": 65})

    def test_settings_sliders_update_per_style_and_reset(self):
        for style, specs in self.main.PEN_STYLE_OPTIONS.items():
            self.panel.choose_pen_style(style)
            for name, low, high, default in specs:
                with self.subTest(style=style, option=name):
                    row, label, slider = self.panel.style_option_controls[name]
                    self.assertFalse(row.isHidden())
                    slider.setValue(high)
                    self.assertEqual(self.panel.collect_settings()["pen_options"][style][name], high)
            self.panel.reset_pen_options_btn.click()
            self.assertEqual(self.canvas.pen_options[style], self.main.normalize_pen_options(style))

    def test_settings_load_restores_each_style_options(self):
        import tempfile
        from unittest.mock import patch
        self.canvas.pen_options["pencil"]["density"] = 23
        self.canvas.pen_options["arrow"]["head_angle"] = 65
        self.canvas.pen_style = "arrow"
        settings = self.panel.collect_settings()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(settings), encoding="utf-8")
            self.canvas.pen_options = {}
            with patch.object(self.main, "CONFIG_FILE", str(path)):
                self.panel.load_settings()
        self.assertEqual(self.canvas.pen_options["pencil"]["density"], 23)
        self.assertEqual(self.canvas.pen_options["arrow"]["head_angle"], 65)
        self.assertEqual(self.panel.style_option_controls["head_angle"][2].value(), 65)

    def test_invalid_options_use_safe_defaults(self):
        for bad in (None, [], "bad", True, float("nan"), float("inf"), 10 ** 400, -900):
            with self.subTest(value=type(bad).__name__):
                options = self.main.normalize_pen_options("neon", {"glow_size": bad})
                self.assertEqual(options["glow_size"], 300)

    def test_switching_style_finishes_old_stroke_and_opens_settings(self):
        from PyQt6.QtCore import QPoint
        c = self.canvas
        c.pen_style = "arrow"
        c._begin_stroke(QPoint(20, 80))
        c.add_smooth_segments(QPoint(160, 80))
        before = len(c.all_segments)
        self.panel.pen_style_buttons["pencil"].click()
        self.assertEqual(len(c.all_segments), before + 2)
        self.assertEqual(len(c.undo_stack), 1)
        self.assertIsNone(c.last_point)
        self.assertFalse(self.panel.draw_sub.isHidden())
        self.panel.pen_style_buttons["pencil"].click()
        self.assertFalse(self.panel.draw_sub.isHidden())
        self.assertFalse(self.panel.style_option_controls["density"][0].isHidden())

    def test_interleaved_fingers_do_not_restart_dash_pattern(self):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor
        c = self.canvas
        c.pen_color = QColor("#123456")
        c.pen_style = "dashed"
        c._pointer_press(101, QPoint(10, 45), 1.0)
        c._pointer_press(102, QPoint(10, 100), 1.0)
        for x in range(20, 281, 10):
            c._pointer_move(101, QPoint(x, 45), 1.0)
            c._pointer_move(102, QPoint(x, 100), 1.0)
        c._pointer_release(101, QPoint(280, 45))
        c._pointer_release(102, QPoint(280, 100))
        interleaved = self.render()
        self.assertGreater(len(c.all_segments), 50)
        self.assertEqual({s.get("style") for s in c.all_segments}, {"dashed"})
        # 参考图直接绘制两条完整路径，不再调用被测的分组代码；否则分组坏掉时
        # 「交错输入」和「排序输入」会同时画错、仍然相等。
        from PyQt6.QtGui import QImage, QPainter, QPainterPath
        from PyQt6.QtCore import QPointF, Qt
        expected = QImage(320, 160, QImage.Format.Format_ARGB32)
        expected.fill(Qt.GlobalColor.white)
        painter = QPainter(expected)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for y in (45, 100):
            path = QPainterPath(QPointF(10, y))
            path.lineTo(QPointF(280, y))
            c._draw_styled_path(painter, path, c.all_segments[0]["pen"], "dashed", c.all_segments[0]["options"])
        painter.end()
        self.assertEqual(interleaved, expected)

    def test_eps_keeps_nib_polygon_fractional_width_and_dash_phase(self):
        from eps_export import _eps_lines
        self.canvas.calligraphy_angle = 90
        self.stroke("calligraphy")
        self.stroke("fountain")
        self.stroke("dashed", ((20, 120), (40, 120), (200, 120)))
        lines = _eps_lines(self.main.serialize_page(self.canvas.capture_page()), 320, 160, "WHITE", {})
        self.assertIn("closepath gsave fill grestore", lines)
        self.assertTrue(any("." in line.split()[0] for line in lines if line.endswith(" setlinewidth")))
        phases = [line for line in lines if line.endswith(" setdash") and not line.startswith("[]")]
        self.assertGreater(len(set(phases)), 2)


if __name__ == "__main__":
    unittest.main()
