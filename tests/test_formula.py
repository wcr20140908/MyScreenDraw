# SPDX-License-Identifier: GPL-3.0-or-later
"""Structured formula model, layout geometry and hit-testing.

formula.py is deliberately Qt-free, so these tests use a fake metrics object with
round numbers: every glyph is half an em wide, ascent is 0.8em, descent 0.2em.
That makes the expected geometry exact arithmetic rather than "roughly right",
which is the only way to catch a layout regression -- you cannot assert on
"looks correct".
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import formula


class FakeMetrics:
    """Predictable metrics: advance = 0.5em per character."""

    def advance(self, text, size):
        return 0.5 * size * len(text)

    def ascent(self, size):
        return 0.8 * size

    def descent(self, size):
        return 0.2 * size


M = FakeMetrics()


def text_node(value):
    return {"k": "t", "v": value}


class NodeModelTests(unittest.TestCase):
    def test_every_kind_declares_its_slots(self):
        for kind, slots in formula.SLOTS.items():
            node = formula.new_node(kind, "x")
            self.assertEqual(node["k"], kind)
            for slot in slots:
                self.assertIn(slot, node, f"{kind} 缺少槽 {slot}")
                self.assertEqual(node[slot], [], "新建节点的槽必须是空的")

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            formula.new_node("matrix")

    def test_normalize_drops_unknown_kinds(self):
        got = formula.normalize([text_node("a"), {"k": "matrix"}, {"k": "t", "v": "b"}])
        self.assertEqual([n["v"] for n in got], ["a", "b"])

    def test_normalize_survives_garbage(self):
        """项目文件可被手改，也可能来自别的版本，normalize 必须永不抛异常。"""
        for junk in (None, "string", 42, [None, 1, "x"], [{"k": None}], [{}],
                     [{"k": "frac"}], [{"k": "frac", "num": "no"}]):
            with self.subTest(junk=junk):
                got = formula.normalize(junk)
                self.assertIsInstance(got, list)

    def test_normalize_fills_missing_slots(self):
        got = formula.normalize([{"k": "frac"}])
        self.assertEqual(got, [{"k": "frac", "num": [], "den": []}])

    def test_normalize_recurses(self):
        got = formula.normalize([{"k": "frac", "num": [{"k": "t", "v": "1"}],
                                  "den": [{"k": "bogus"}]}])
        self.assertEqual(got[0]["num"], [{"k": "t", "v": "1"}])
        self.assertEqual(got[0]["den"], [])

    def test_empty_text_runs_are_dropped(self):
        self.assertEqual(formula.normalize([{"k": "t", "v": ""}]), [])

    def test_non_string_text_is_coerced(self):
        self.assertEqual(formula.normalize([{"k": "t", "v": 7}]), [{"k": "t", "v": "7"}])


class SlotPathTests(unittest.TestCase):
    def setUp(self):
        self.tree = [text_node("a"),
                     {"k": "frac", "num": [text_node("1")], "den": [text_node("2")]}]

    def test_resolves_a_valid_path(self):
        self.assertEqual(formula.get_slot(self.tree, (1, "num")), [{"k": "t", "v": "1"}])

    def test_a_stale_index_returns_none(self):
        self.assertIsNone(formula.get_slot(self.tree, (9, "num")))

    def test_a_wrong_slot_name_returns_none(self):
        self.assertIsNone(formula.get_slot(self.tree, (1, "exp")))

    def test_a_path_ending_on_an_index_returns_none(self):
        """路径必须落在槽上，不能落在节点上。"""
        self.assertIsNone(formula.get_slot(self.tree, (1,)))

    def test_a_text_node_has_no_slots(self):
        self.assertIsNone(formula.get_slot(self.tree, (0, "num")))

    def test_nested_path(self):
        tree = [{"k": "frac",
                 "num": [{"k": "sup", "base": [text_node("x")], "exp": [text_node("2")]}],
                 "den": []}]
        self.assertEqual(formula.get_slot(tree, (0, "num", 0, "exp")),
                         [{"k": "t", "v": "2"}])


class RowLayoutTests(unittest.TestCase):
    def test_a_text_run_is_as_wide_as_its_glyphs(self):
        box = formula.layout([text_node("abc")], 20.0, M)
        self.assertAlmostEqual(box.w, 0.5 * 20.0 * 3)
        self.assertAlmostEqual(box.ascent, 16.0)
        self.assertAlmostEqual(box.descent, 4.0)

    def test_runs_are_placed_left_to_right(self):
        box = formula.layout([text_node("ab"), text_node("c")], 20.0, M)
        offsets = [dx for dx, _dy, _child in box.children]
        self.assertEqual(offsets, [0.0, 20.0])
        self.assertAlmostEqual(box.w, 30.0)

    def test_an_empty_row_still_has_a_tappable_size(self):
        box = formula.layout([], 20.0, M)
        self.assertGreater(box.w, 0.0, "空槽必须有宽度，否则点不中")
        self.assertGreater(box.height, 0.0)

    def test_an_empty_row_reports_a_placeholder_child(self):
        box = formula.layout([], 20.0, M)
        self.assertEqual([c.kind for _dx, _dy, c in box.children], ["empty"])


class FractionLayoutTests(unittest.TestCase):
    def frac(self, num="1", den="23", size=20.0):
        node = {"k": "frac", "num": [text_node(num)], "den": [text_node(den)]}
        return formula.layout([node], size, M).children[0][2]

    def test_width_follows_the_wider_half(self):
        box = self.frac(num="1", den="234")
        inner = 20.0 * formula.FRAC_RATIO
        expected = 0.5 * inner * 3 + 2 * formula.FRAC_PAD * 20.0
        self.assertAlmostEqual(box.w, expected)

    def test_both_halves_are_centred(self):
        box = self.frac(num="1", den="234")
        num_dx = box.children[0][0]
        den_dx = box.children[1][0]
        self.assertGreater(num_dx, den_dx, "较窄的分子应更靠中间")

    def test_the_numerator_sits_above_the_baseline(self):
        box = self.frac()
        num_dy = box.children[0][1]
        self.assertLess(num_dy, 0.0, "分子必须在基线之上（dy 为负）")

    def test_the_denominator_sits_below_the_bar(self):
        box = self.frac()
        den_dy = box.children[1][1]
        self.assertGreater(den_dy, 0.0)

    def test_a_bar_is_emitted(self):
        box = self.frac()
        self.assertIsNotNone(box.bar)
        _x, _y, width, thickness = box.bar
        self.assertAlmostEqual(width, box.w)
        self.assertGreaterEqual(thickness, 1.0, "分数线至少 1px，否则看不见")

    def test_the_box_covers_both_halves(self):
        box = self.frac()
        self.assertGreater(box.ascent, 0.0)
        self.assertGreater(box.descent, 0.0)
        self.assertGreater(box.height, 20.0, "分数必然比单行文字高")

    def test_nesting_shrinks_the_inner_fraction(self):
        inner = {"k": "frac", "num": [text_node("1")], "den": [text_node("2")]}
        outer = {"k": "frac", "num": [inner], "den": [text_node("3")]}
        box = formula.layout([outer], 40.0, M).children[0][2]
        inner_box = box.children[0][2].children[0][2]
        self.assertLess(inner_box.size, 40.0, "嵌套分数必须缩小")

    def test_nesting_never_shrinks_below_the_floor(self):
        """无限嵌套不能把字号缩到点不中。"""
        node = {"k": "frac", "num": [text_node("1")], "den": [text_node("2")]}
        for _ in range(12):
            node = {"k": "frac", "num": [node], "den": [text_node("9")]}
        box = formula.layout([node], 24.0, M)
        sizes = []

        def walk(b):
            if b.size:
                sizes.append(b.size)
            for _dx, _dy, child in b.children:
                walk(child)

        walk(box)
        self.assertGreaterEqual(min(sizes), formula.SCRIPT_MIN * 0.99)


class ScriptLayoutTests(unittest.TestCase):
    def build(self, kind, size=20.0):
        slot = "exp" if kind == "sup" else "sub"
        node = {"k": kind, "base": [text_node("x")], slot: [text_node("2")]}
        return formula.layout([node], size, M).children[0][2]

    def test_a_superscript_is_raised(self):
        box = self.build("sup")
        self.assertLess(box.children[1][1], 0.0, "上标 dy 必须为负（向上）")

    def test_a_subscript_is_lowered(self):
        box = self.build("sub")
        self.assertGreater(box.children[1][1], 0.0)

    def test_the_script_is_smaller_than_the_base(self):
        box = self.build("sup")
        base, script = box.children[0][2], box.children[1][2]
        self.assertLess(script.size, base.size)

    def test_the_script_follows_the_base_horizontally(self):
        box = self.build("sup")
        base_w = box.children[0][2].w
        self.assertAlmostEqual(box.children[1][0], base_w)

    def test_a_superscript_raises_the_ascent(self):
        plain = formula.layout([text_node("x")], 20.0, M)
        box = self.build("sup")
        self.assertGreater(box.ascent, plain.ascent)

    def test_a_subscript_deepens_the_descent(self):
        plain = formula.layout([text_node("x")], 20.0, M)
        box = self.build("sub")
        self.assertGreater(box.descent, plain.descent)

    def test_descent_is_never_negative(self):
        box = self.build("sup")
        self.assertGreaterEqual(box.descent, 0.0)


class RadicalLayoutTests(unittest.TestCase):
    def sqrt(self, inner="9", size=20.0):
        node = {"k": "sqrt", "arg": [text_node(inner)]}
        return formula.layout([node], size, M).children[0][2]

    def test_the_radical_leaves_room_for_its_hook(self):
        box = self.sqrt()
        arg_dx = box.children[0][0]
        self.assertGreater(arg_dx, 0.0, "内容必须右移，给钩部留位置")

    def test_the_overline_spans_the_content(self):
        box = self.sqrt("123")
        arg = box.children[0][2]
        _x, _y, width, _t = box.bar
        self.assertGreaterEqual(width, arg.w)

    def test_it_is_taller_than_its_content(self):
        box = self.sqrt()
        arg = box.children[0][2]
        self.assertGreater(box.ascent, arg.ascent, "上横线要占额外高度")

    def test_a_tall_argument_makes_a_tall_radical(self):
        short = self.sqrt("9")
        frac = {"k": "frac", "num": [text_node("1")], "den": [text_node("2")]}
        tall = formula.layout([{"k": "sqrt", "arg": [frac]}], 20.0, M).children[0][2]
        self.assertGreater(tall.height, short.height,
                           "根号必须随内容高度伸长")


class BigOperatorTests(unittest.TestCase):
    def build(self, kind="sum", size=20.0):
        node = {"k": kind, "lo": [text_node("0")], "hi": [text_node("n")],
                "arg": [text_node("i")]}
        return formula.layout([node], size, M).children[0][2]

    def test_limits_sit_above_and_below(self):
        box = self.build()
        dys = [dy for _dx, dy, _c in box.children]
        self.assertLess(min(dys), 0.0, "上限在符号上方")
        self.assertGreater(max(dys), 0.0, "下限在符号下方")

    def test_the_operand_follows_the_operator(self):
        box = self.build()
        arg_dx = box.children[2][0]
        self.assertGreater(arg_dx, 0.0)

    def test_a_glyph_is_emitted(self):
        for kind, symbol in (("sum", "∑"), ("int", "∫")):
            with self.subTest(kind=kind):
                box = self.build(kind)
                self.assertIsNotNone(box.glyph)
                self.assertEqual(box.glyph[0], symbol)

    def test_the_operator_is_drawn_larger_than_body_text(self):
        box = self.build()
        self.assertGreater(box.glyph[1], 20.0)


class HitTestTests(unittest.TestCase):
    def setUp(self):
        self.tree = [{"k": "frac", "num": [text_node("1")], "den": [text_node("2")]}]
        self.box = formula.layout(self.tree, 30.0, M)

    def test_every_slot_gets_a_rect(self):
        paths = {path for path, *_ in formula.slot_rects(self.box)}
        self.assertIn((0, "num"), paths)
        self.assertIn((0, "den"), paths)

    def test_clicking_the_numerator_hits_the_numerator(self):
        rects = {path: rect for path, *rect in formula.slot_rects(self.box)}
        x, y, w, h = rects[(0, "num")]
        self.assertEqual(formula.hit_slot(self.box, x + w / 2, y + h / 2), (0, "num"))

    def test_clicking_the_denominator_hits_the_denominator(self):
        rects = {path: rect for path, *rect in formula.slot_rects(self.box)}
        x, y, w, h = rects[(0, "den")]
        self.assertEqual(formula.hit_slot(self.box, x + w / 2, y + h / 2), (0, "den"))

    def test_the_deepest_slot_wins(self):
        """槽是嵌套的：落在分子里的点同时也落在整行里，用户要的是分子。"""
        tree = [{"k": "frac",
                 "num": [{"k": "sqrt", "arg": [text_node("2")]}],
                 "den": [text_node("3")]}]
        box = formula.layout(tree, 30.0, M)
        rects = {path: rect for path, *rect in formula.slot_rects(box)}
        x, y, w, h = rects[(0, "num", 0, "arg")]
        self.assertEqual(formula.hit_slot(box, x + w / 2, y + h / 2),
                         (0, "num", 0, "arg"))

    def test_a_point_outside_hits_nothing(self):
        self.assertIsNone(formula.hit_slot(self.box, -500.0, -500.0))

    def test_an_empty_slot_is_hittable(self):
        box = formula.layout([{"k": "frac", "num": [], "den": []}], 30.0, M)
        rects = {path: rect for path, *rect in formula.slot_rects(box)}
        self.assertIn((0, "num"), rects)
        x, y, w, h = rects[(0, "num")]
        self.assertEqual(formula.hit_slot(box, x + w / 2, y + h / 2), (0, "num"))

    def test_every_reported_rect_resolves_to_a_real_slot(self):
        """slot_rects 报出来的路径必须都能被 get_slot 解析——否则点击会落空。"""
        tree = [{"k": "sum", "lo": [text_node("0")], "hi": [text_node("n")],
                 "arg": [{"k": "frac", "num": [text_node("1")], "den": [text_node("k")]}]}]
        box = formula.layout(tree, 24.0, M)
        for path, *_rect in formula.slot_rects(box):
            with self.subTest(path=path):
                self.assertIsNotNone(formula.get_slot(tree, path),
                                     f"路径 {path} 解析不到槽")


class PlainTextTests(unittest.TestCase):
    def test_a_fraction_reads_sensibly(self):
        tree = [{"k": "frac", "num": [text_node("a")], "den": [text_node("b")]}]
        self.assertEqual(formula.plain_text(tree), "(a)/(b)")

    def test_nested_structures_read_sensibly(self):
        tree = [{"k": "sqrt", "arg": [{"k": "sup", "base": [text_node("x")],
                                       "exp": [text_node("2")]}]}]
        self.assertEqual(formula.plain_text(tree), "sqrt(x^(2))")

    def test_empty_is_empty(self):
        self.assertEqual(formula.plain_text([]), "")
        self.assertEqual(formula.plain_text(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
