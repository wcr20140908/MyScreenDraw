"""Vector EPS export tests: feed a serialized page dict and inspect the PostScript output."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eps_export

# 序列化页面样例（serialize_page 的格式），覆盖线段/图形/文本/图片
PAGE = {
    "segments": [
        {"id": "s1", "p1": [10, 10], "p2": [100, 50], "color": "#ff0000", "width": 4, "marker": False},
        {"id": "s2", "p1": [10, 20], "p2": [100, 60], "color": "#40ff0000", "width": 20, "marker": True},
    ],
    "shapes": [
        {"id": "sh1", "type": "LINE", "kind": "poly", "points": [[10, 10], [200, 10]],
         "closed": False, "color": "#000000", "width": 2},
        {"id": "sh2", "type": "DASHED_LINE", "kind": "poly", "points": [[10, 30], [200, 30]],
         "closed": False, "color": "#000000", "width": 2},
        {"id": "sh3", "type": "TRIANGLE", "kind": "poly", "points": [[10, 100], [110, 100], [60, 40]],
         "closed": True, "color": "#0000ff", "width": 3},
        {"id": "sh4", "type": "CIRCLE", "kind": "circle", "center": [300, 300], "radius": 50,
         "color": "#00ff00", "width": 2},
        {"id": "sh5", "type": "ELLIPSE", "kind": "ellipse", "center": [400, 200], "rx": 80, "ry": 40,
         "rotation": 30, "color": "#ff00ff", "width": 2},
        {"id": "sh6", "type": "ANGLE", "kind": "angle", "vertex": [500, 300], "p1": [600, 300],
         "p2": [500, 200], "color": "#000000", "width": 2},
        {"id": "sh7", "type": "CUBE", "kind": "rect", "rect": [50, 200, 80, 80], "rotation": 0,
         "color": "#000000", "width": 2},
    ],
    "texts": [
        {"id": "t1", "text": "Hello", "pos": [100, 400], "color": "#000000",
         "width": 1, "size": 24, "scale": 1.0, "rotation": 0},
    ],
    "images": [
        {"id": "i1", "pos": [400, 400], "size": [20, 10], "rotation": 0, "data": "AA=="},
    ],
}


def _render(**kwargs):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.eps")
        eps_export.write_eps(path, PAGE, 800, 600, **kwargs)
        with open(path, encoding="latin-1") as handle:
            return handle.read()


class EpsHeaderTests(unittest.TestCase):
    def test_epsf_header_and_bounding_box(self):
        text = _render()
        self.assertIn("%!PS-Adobe-3.0 EPSF-3.0", text)
        self.assertIn("%%BoundingBox: 0 0 800 600", text)
        self.assertIn("%%HiResBoundingBox: 0 0 800 600", text)
        self.assertIn("%%EOF", text)

    def test_background_fill_present(self):
        text = _render()
        self.assertIn("closepath fill", text)

    def test_black_board_uses_dark_background(self):
        text = _render(board_style="BLACK")
        # #254237 → 0.145 0.259 0.216
        self.assertIn("0.145 0.259 0.216 setrgbcolor", text)


class EpsGeometryTests(unittest.TestCase):
    def test_line_uses_moveto_lineto_stroke(self):
        text = _render()
        self.assertIn("moveto", text)
        self.assertIn("lineto", text)
        self.assertIn("stroke", text)

    def test_dashed_line_sets_dash(self):
        text = _render()
        self.assertIn("[8 6] 0 setdash", text)

    def test_round_caps_set(self):
        text = _render()
        self.assertIn("1 setlinecap", text)

    def test_text_emits_show(self):
        text = _render()
        self.assertIn("(Hello) show", text)
        self.assertIn("/Helvetica findfont", text)

    def test_cjk_text_is_replaced_with_placeholder(self):
        page = dict(PAGE)
        page["texts"] = [dict(PAGE["texts"][0], text="你好")]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "page.eps")
            eps_export.write_eps(path, page, 800, 600)
            with open(path, encoding="latin-1") as handle:
                text = handle.read()
        self.assertIn("(??) show", text)   # 非 latin-1 字符替换为 '?'

    def test_ps_string_escaping(self):
        page = dict(PAGE)
        page["texts"] = [dict(PAGE["texts"][0], text="a(b)\\c")]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "page.eps")
            eps_export.write_eps(path, page, 800, 600)
            with open(path, encoding="latin-1") as handle:
                text = handle.read()
        self.assertIn(r"(a\(b\)\\c) show", text)

    def test_alpha_marker_blended_over_white(self):
        # #40ff0000 (alpha 0x40/255≈0.251) 预乘到白底 → 荧光笔不再输出纯红 1 0 0。
        # 样例里只有 s1 是纯红实线，因此整份输出中「1 0 0 setrgbcolor」应恰好出现 1 次。
        text = _render()
        self.assertEqual(text.count("1 0 0 setrgbcolor"), 1)


class EpsImageTests(unittest.TestCase):
    def test_rgb_image_embedded_with_colorimage(self):
        decoded = {"i1": (2, 1, b"\xff\x00\x00\x00\xff\x00")}
        text = _render(decoded_images=decoded)
        self.assertIn("false 3 colorimage", text)
        self.assertIn("ff000000ff00", text)   # RGB hex 数据

    def test_image_skipped_when_pixels_are_not_rgb(self):
        decoded = {"i1": (2, 1, b"\xff\x00\x00")}
        text = _render(decoded_images=decoded)
        self.assertNotIn(" colorimage", text)


class EpsNumberFormatTests(unittest.TestCase):
    def test_integers_have_no_decimal_point(self):
        self.assertEqual(eps_export._fmt(800.0), "800")
        self.assertEqual(eps_export._fmt(1.5), "1.5")
        self.assertEqual(eps_export._fmt(-4), "-4")

    def test_color_parse(self):
        self.assertEqual(eps_export._parse_color("#ff0000"), (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(eps_export._parse_color("#80ff0000")[3], 0x80 / 255.0)


if __name__ == "__main__":
    unittest.main()