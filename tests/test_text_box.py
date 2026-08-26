# SPDX-License-Identifier: GPL-3.0-or-later
"""Drag-sized multi-line text boxes and the structured formula editor.

The text object grew two optional fields in 5.3.0: `box` (the dragged size) and
`formula` (the structured tree). Everything here guards the paths that a field
addition silently breaks -- clone, save/load round-trip, bounds, hit-testing and
erase -- because a dropped field shows up as "my formula vanished after saving"
with no error anywhere.

Backward compatibility is pinned deliberately: a text item written by 5.2.x has
neither field and must keep rendering and measuring exactly as before.
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


class TextBoxCase(unittest.TestCase):
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
        c.draw_state = "TEXT"
        c.whiteboard_mode = False
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
        c.pen_color = self.main.QColor("#ff4757")
        c.pen_width = 3
        c.text_font_size = 24

    def make_box(self, x=100.0, y=100.0, w=200.0, h=80.0):
        from PyQt6.QtCore import QRectF

        return self.canvas.finish_text_box(QRectF(x, y, w, h))


class DragToSizeTests(TextBoxCase):
    def test_a_drag_creates_a_box_of_that_size(self):
        item = self.make_box(w=240.0, h=90.0)
        self.assertIsNotNone(item)
        self.assertEqual([round(v) for v in item["box"]], [240, 90])

    def test_the_box_anchors_at_the_drag_origin(self):
        item = self.make_box(x=150.0, y=220.0)
        self.assertAlmostEqual(item["pos"].x(), 150.0)
        self.assertAlmostEqual(item["pos"].y(), 220.0)

    def test_a_tap_sized_drag_creates_nothing(self):
        """位移小于阈值就是点击，不该建框。

        5.3.0 把这种情况当成「拖得太小」并按最小尺寸给一个框，结果在画布上点一下
        就冒出一个空框。用户要的是拖拽定框，点击不该有任何东西出现。
        """
        self.assertIsNone(self.make_box(w=2.0, h=1.0))
        self.assertEqual(self.canvas.text_items, [])

    def test_a_drag_over_the_threshold_still_gets_a_minimum_size(self):
        """确实拖动了、但拖得很小：给最小尺寸的框，别给一个装不下字的框。"""
        span = self.canvas.TEXT_DRAG_MIN_PX + 2
        item = self.make_box(w=span, h=span)
        self.assertIsNotNone(item)
        self.assertGreaterEqual(item["box"][0], self.canvas.TEXT_MIN_W)
        self.assertGreaterEqual(item["box"][1], self.canvas.TEXT_MIN_H)

    def test_a_reversed_drag_is_normalised(self):
        from PyQt6.QtCore import QRectF

        item = self.canvas.finish_text_box(QRectF(300.0, 300.0, -120.0, -70.0))
        self.assertAlmostEqual(item["pos"].x(), 180.0)
        self.assertAlmostEqual(item["pos"].y(), 230.0)

    def test_creating_a_box_enters_edit_mode(self):
        item = self.make_box()
        self.assertEqual(self.canvas.editing_text_id, item["id"])

    def test_bounds_follow_the_dragged_box_not_the_text(self):
        item = self.make_box(w=300.0, h=120.0)
        item["text"] = "x"
        bounds = self.canvas.text_bounds(item)
        self.assertAlmostEqual(bounds.width(), 300.0)
        self.assertAlmostEqual(bounds.height(), 120.0)

    def test_bounds_track_rotation(self):
        item = self.make_box(w=200.0, h=40.0)
        flat = self.canvas.text_bounds(item)
        item["rotation"] = 90.0
        turned = self.canvas.text_bounds(item)
        self.assertAlmostEqual(turned.width(), flat.height(), places=3)

    def test_bounds_track_scale(self):
        item = self.make_box(w=100.0, h=50.0)
        item["scale"] = 2.0
        bounds = self.canvas.text_bounds(item)
        self.assertAlmostEqual(bounds.width(), 200.0)


class LegacyCompatibilityTests(TextBoxCase):
    def legacy_item(self):
        """A 5.2.x text object: no box, no formula."""
        from PyQt6.QtCore import QPointF

        return {"id": "legacy", "text": "旧文本", "pos": QPointF(50.0, 60.0),
                "color": self.main.QColor("#000000"), "width": 2, "size": 24,
                "scale": 1.0, "rotation": 0.0}

    def test_a_legacy_item_measures_from_its_content(self):
        item = self.legacy_item()
        bounds = self.canvas.text_bounds(item)
        self.assertGreater(bounds.width(), 0.0)
        self.assertGreater(bounds.height(), 0.0)

    def test_a_legacy_item_has_no_box_field(self):
        item = self.legacy_item()
        self.canvas.text_bounds(item)
        self.assertNotIn("box", item, "读包围盒不应给旧对象凭空加字段")

    def test_a_legacy_item_survives_a_clone(self):
        item = self.legacy_item()
        clone = self.canvas.clone_text_item(item)
        self.assertEqual(clone["text"], "旧文本")
        self.assertNotIn("box", clone)
        self.assertNotIn("formula", clone)

    def test_serialising_a_legacy_item_adds_no_new_keys(self):
        """升级后打开旧项目再保存，不该凭空多出 box/formula 字段。"""
        self.canvas.text_items = [self.legacy_item()]
        page = self.main.serialize_page(self.canvas.capture_page())
        entry = page["texts"][0]
        self.assertNotIn("box", entry)
        self.assertNotIn("formula", entry)


class MultilineTests(TextBoxCase):
    def test_newlines_split_into_lines(self):
        item = self.make_box()
        item["text"] = "第一行\n第二行\n第三行"
        self.assertEqual(len(self.canvas.text_lines(item)), 3)

    def test_more_lines_need_more_height(self):
        item = self.make_box()
        item.pop("box")             # 自适应模式才看得出内容高度
        item["text"] = "一行"
        one = self.canvas.text_content_size(item)[1]
        item["text"] = "一行\n两行\n三行"
        three = self.canvas.text_content_size(item)[1]
        self.assertGreater(three, one)

    def test_the_widest_line_sets_the_width(self):
        item = self.make_box()
        item.pop("box")
        item["text"] = "短\n很长很长很长的一行"
        width = self.canvas.text_content_size(item)[0]
        item["text"] = "短"
        self.assertGreater(width, self.canvas.text_content_size(item)[0])

    def test_newline_is_appended_in_edit_mode(self):
        item = self.make_box()
        self.canvas.text_insert("甲")
        self.canvas.text_newline()
        self.canvas.text_insert("乙")
        self.assertEqual(item["text"], "甲\n乙")

    def test_backspace_removes_one_character(self):
        item = self.make_box()
        self.canvas.text_insert("abc")
        self.canvas.text_backspace()
        self.assertEqual(item["text"], "ab")

    def test_backspace_on_empty_text_is_harmless(self):
        self.make_box()
        self.assertFalse(self.canvas.text_backspace())


class FormulaEditingTests(TextBoxCase):
    def test_inserting_a_structure_creates_a_formula(self):
        item = self.make_box()
        self.assertTrue(self.canvas.text_insert_structure("frac"))
        self.assertEqual(item["formula"][0]["k"], "frac")

    def test_the_insert_point_moves_into_the_new_structure(self):
        self.make_box()
        self.canvas.text_insert_structure("frac")
        self.assertEqual(self.canvas.editing_slot, (0, "num"))

    def test_typing_lands_in_the_active_slot(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("1")
        self.assertEqual(item["formula"][0]["num"], [{"k": "t", "v": "1"}])
        self.assertEqual(item["formula"][0]["den"], [])

    def test_consecutive_characters_merge_into_one_node(self):
        """每个字符一个节点会把树撑爆，也让退格行为变得奇怪。"""
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        for ch in "123":
            self.canvas.text_insert(ch)
        self.assertEqual(item["formula"][0]["num"], [{"k": "t", "v": "123"}])

    def test_existing_plain_text_is_carried_into_the_formula(self):
        """已经打的字不能因为按了「分数」就消失。"""
        item = self.make_box()
        self.canvas.text_insert("y=")
        self.canvas.text_insert_structure("frac")
        self.assertEqual(item["text"], "")
        self.assertEqual(item["formula"][0], {"k": "t", "v": "y="})
        self.assertEqual(item["formula"][1]["k"], "frac")

    def test_backspace_inside_a_slot(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("12")
        self.canvas.text_backspace()
        self.assertEqual(item["formula"][0]["num"], [{"k": "t", "v": "1"}])

    def test_backspace_removes_an_emptied_node(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("1")
        self.canvas.text_backspace()
        self.assertEqual(item["formula"][0]["num"], [])

    def test_nesting_a_structure_inside_a_slot(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert_structure("sqrt")
        self.assertEqual(item["formula"][0]["num"][0]["k"], "sqrt")
        self.assertEqual(self.canvas.editing_slot, (0, "num", 0, "arg"))

    def test_newline_is_refused_inside_a_formula(self):
        self.make_box()
        self.canvas.text_insert_structure("frac")
        self.assertFalse(self.canvas.text_newline(), "公式里换行没有意义")

    def test_a_formula_box_measures_from_the_tree(self):
        item = self.make_box()
        item.pop("box")
        plain = self.canvas.text_content_size(item)
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("1")
        self.assertGreater(self.canvas.text_content_size(item)[1], plain[1],
                           "分数必然比空文本高")

    def test_every_structure_button_can_be_inserted(self):
        """符号面板里的结构按钮必须每个都真的能插入。"""
        for entry in formula.group_entries("structure"):
            kind = formula.structure_kind(entry)
            with self.subTest(kind=kind):
                self.setUp()
                self.make_box()
                self.assertIsNotNone(kind)
                self.assertTrue(self.canvas.text_insert_structure(kind))

    def test_inserting_without_an_edit_target_is_refused(self):
        self.canvas.editing_text_id = None
        self.assertFalse(self.canvas.text_insert("x"))
        self.assertFalse(self.canvas.text_insert_structure("frac"))

    def test_a_stale_slot_path_recovers(self):
        """槽路径可能因为退格而失效，此时输入应落到某个可用槽而不是报错。"""
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.editing_slot = (9, "num")       # 明显失效的路径
        self.canvas.text_insert("x")
        self.assertIn("x", formula.plain_text(item["formula"]))


class FormulaPersistenceTests(TextBoxCase):
    def build(self):
        item = self.make_box(w=260.0, h=110.0)
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("1")
        self.canvas.editing_slot = (0, "den")
        self.canvas.text_insert("2")
        return item

    def test_a_formula_survives_a_clone(self):
        item = self.build()
        clone = self.canvas.clone_text_item(item)
        self.assertEqual(formula.plain_text(clone["formula"]), "(1)/(2)")

    def test_a_clone_does_not_share_the_tree(self):
        """撤销快照与实时对象共享同一棵树时，编辑公式会就地改掉历史。"""
        item = self.build()
        clone = self.canvas.clone_text_item(item)
        item["formula"][0]["num"][0]["v"] = "9"
        self.assertEqual(clone["formula"][0]["num"][0]["v"], "1")

    def test_a_formula_survives_a_save_load_round_trip(self):
        self.build()
        page = self.main.serialize_page(self.canvas.capture_page())
        restored = self.main.deserialize_page(page)
        self.assertEqual(formula.plain_text(restored["texts"][0]["formula"]), "(1)/(2)")

    def test_the_dragged_box_survives_a_round_trip(self):
        self.build()
        page = self.main.serialize_page(self.canvas.capture_page())
        restored = self.main.deserialize_page(page)
        self.assertEqual([round(v) for v in restored["texts"][0]["box"]], [260, 110])

    def test_a_formula_survives_load_page(self):
        self.build()
        page = self.canvas.capture_page()
        self.canvas.text_items = []
        self.canvas.load_page(page)
        self.assertEqual(formula.plain_text(self.canvas.text_items[0]["formula"]),
                         "(1)/(2)")

    def test_a_corrupt_formula_in_a_file_does_not_crash(self):
        """项目文件可被手改，也可能来自别的版本。"""
        page = {"segments": [], "shapes": [], "images": [],
                "texts": [{"id": "x", "text": "", "pos": [10, 10], "color": "#000000",
                           "width": 1, "size": 24, "scale": 1.0, "rotation": 0.0,
                           "formula": [{"k": "nope"}, "junk", 42]}]}
        restored = self.main.deserialize_page(page)
        self.assertNotIn("formula", restored["texts"][0],
                         "无效公式应被丢弃，而不是留下半棵坏树")

    def test_a_corrupt_box_in_a_file_does_not_crash(self):
        page = {"segments": [], "shapes": [], "images": [],
                "texts": [{"id": "x", "text": "hi", "pos": [10, 10], "color": "#000000",
                           "width": 1, "size": 24, "scale": 1.0, "rotation": 0.0,
                           "box": "not a size"}]}
        restored = self.main.deserialize_page(page)
        self.assertNotIn("box", restored["texts"][0])


class EraseAndSelectTests(TextBoxCase):
    def test_a_boxed_text_can_be_erased(self):
        """包围盒与渲染必须同源，否则会「看得见但擦不掉」。"""
        from PyQt6.QtCore import QPoint

        item = self.make_box(x=100.0, y=100.0, w=200.0, h=80.0)
        self.canvas.end_text_edit(discard_empty=False)
        self.canvas.draw_state = "ERASER"
        self.canvas.eraser_type = "OBJECT"
        self.canvas.execute_erase(QPoint(150, 130))
        self.assertEqual(self.canvas.text_items, [], "框内一点应能擦掉它")

    def test_erasing_outside_the_box_keeps_it(self):
        from PyQt6.QtCore import QPoint

        self.make_box(x=100.0, y=100.0, w=60.0, h=40.0)
        self.canvas.end_text_edit(discard_empty=False)
        self.canvas.draw_state = "ERASER"
        self.canvas.eraser_type = "OBJECT"
        self.canvas.execute_erase(QPoint(600, 600))
        self.assertEqual(len(self.canvas.text_items), 1)

    def test_hit_test_finds_the_topmost_box(self):
        from PyQt6.QtCore import QPoint

        lower = self.make_box(x=100.0, y=100.0, w=200.0, h=100.0)
        self.canvas.end_text_edit(discard_empty=False)
        upper = self.make_box(x=120.0, y=120.0, w=200.0, h=100.0)
        self.canvas.end_text_edit(discard_empty=False)
        hit = self.canvas.text_at(QPoint(150, 150))
        self.assertEqual(hit["id"], upper["id"], "应命中后画的那一个")
        self.assertNotEqual(hit["id"], lower["id"])


class EditLifecycleTests(TextBoxCase):
    def test_an_empty_box_is_discarded_on_exit(self):
        """空框留在画布上就是一堆看不见的盒子。"""
        self.make_box()
        self.canvas.end_text_edit()
        self.assertEqual(self.canvas.text_items, [])

    def test_a_box_with_text_is_kept(self):
        self.make_box()
        self.canvas.text_insert("有内容")
        self.canvas.end_text_edit()
        self.assertEqual(len(self.canvas.text_items), 1)

    def test_a_box_with_only_a_formula_is_kept(self):
        self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.end_text_edit()
        self.assertEqual(len(self.canvas.text_items), 1)

    def test_whitespace_only_counts_as_empty(self):
        self.make_box()
        self.canvas.text_insert("   ")
        self.canvas.end_text_edit()
        self.assertEqual(self.canvas.text_items, [])

    def test_exiting_clears_the_edit_state(self):
        self.make_box()
        self.canvas.text_insert("x")
        self.canvas.end_text_edit()
        self.assertIsNone(self.canvas.editing_text_id)
        self.assertIsNone(self.canvas.editing_slot)

    def test_editing_a_second_box_switches_target(self):
        first = self.make_box(x=100.0)
        self.canvas.text_insert("a")
        second = self.make_box(x=400.0)
        self.canvas.begin_text_edit(second)
        self.assertEqual(self.canvas.editing_text_id, second["id"])
        self.assertNotEqual(self.canvas.editing_text_id, first["id"])

    def test_editing_a_formula_box_lands_on_an_empty_slot(self):
        item = self.make_box()
        self.canvas.text_insert_structure("frac")
        self.canvas.text_insert("1")
        self.canvas.end_text_edit()
        self.canvas.begin_text_edit(item)
        self.assertEqual(self.canvas.editing_slot, (0, "den"),
                         "重新编辑应落在第一个空格子上")


class SlotClickTests(TextBoxCase):
    def test_clicking_a_slot_moves_the_insert_point(self):
        from PyQt6.QtCore import QPointF

        item = self.make_box(x=100.0, y=100.0, w=300.0, h=160.0)
        self.canvas.text_insert_structure("frac")
        box = self.canvas.formula_box(item)
        rect = self.canvas.text_local_rect(item)
        target = None
        for path, x, y, w, h in formula.slot_rects(box):
            if path == (0, "den"):
                target = (x + w / 2.0, y + h / 2.0)
                break
        self.assertIsNotNone(target)
        canvas_point = QPointF(item["pos"].x() + rect.left() + self.canvas.TEXT_PAD + target[0],
                               item["pos"].y() + rect.top() + self.canvas.TEXT_PAD
                               + box.ascent + target[1])
        self.assertTrue(self.canvas.set_editing_slot_at(canvas_point))
        self.assertEqual(self.canvas.editing_slot, (0, "den"))

    def test_clicking_outside_any_slot_reports_false(self):
        from PyQt6.QtCore import QPointF

        self.make_box()
        self.canvas.text_insert_structure("frac")
        self.assertFalse(self.canvas.set_editing_slot_at(QPointF(-900.0, -900.0)))

    def test_clicking_a_plain_text_box_reports_false(self):
        from PyQt6.QtCore import QPointF

        item = self.make_box()
        self.canvas.text_insert("no formula")
        self.assertFalse(self.canvas.set_editing_slot_at(QPointF(item["pos"])))


class ColourAndWidthTests(TextBoxCase):
    def test_a_new_box_takes_the_current_pen_colour(self):
        self.canvas.pen_color = self.main.QColor("#123456")
        item = self.make_box()
        self.assertEqual(item["color"].name(), "#123456")

    def test_a_new_box_takes_the_current_pen_width(self):
        self.canvas.pen_width = 7
        item = self.make_box()
        self.assertEqual(item["width"], 7)

    def test_colour_and_width_survive_a_round_trip(self):
        self.canvas.pen_color = self.main.QColor("#abcdef")
        self.canvas.pen_width = 5
        item = self.make_box()
        item["text"] = "x"
        page = self.main.serialize_page(self.canvas.capture_page())
        restored = self.main.deserialize_page(page)
        self.assertEqual(restored["texts"][0]["color"].name(), "#abcdef")
        self.assertEqual(restored["texts"][0]["width"], 5)


class SymbolCatalogueTests(unittest.TestCase):
    def test_every_group_has_entries(self):
        for key in formula.group_keys():
            with self.subTest(group=key):
                self.assertTrue(formula.group_entries(key))

    def test_every_structure_entry_names_a_real_kind(self):
        for entry in formula.group_entries("structure"):
            with self.subTest(entry=entry):
                self.assertIn(formula.structure_kind(entry), formula.SLOTS)

    def test_plain_symbols_are_not_structures(self):
        for key in ("greek", "operator", "relation"):
            for entry in formula.group_entries(key):
                with self.subTest(entry=entry):
                    self.assertIsNone(formula.structure_kind(entry))

    def test_every_group_has_a_translation_in_all_languages(self):
        """8 国语言必须都有——漏一种会在那个界面语言下显示成 key 本身。"""
        import i18n

        for key in formula.group_keys():
            label_key = formula.group_label(key)
            for lang, table in i18n.TEXT.items():
                with self.subTest(group=key, lang=lang):
                    self.assertIn(label_key, table)
                    self.assertTrue(table[label_key])

    def test_labels_render_for_every_entry(self):
        for key in formula.group_keys():
            for entry in formula.group_entries(key):
                with self.subTest(entry=entry):
                    label = formula.entry_label(entry)
                    self.assertIsInstance(label, str)
                    self.assertTrue(label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
