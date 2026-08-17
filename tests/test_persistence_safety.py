"""Regression coverage for untrusted project data and autosave boundary checks."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import persistence


class FileSizeLimitTests(unittest.TestCase):
    def test_oversized_project_is_rejected_before_parsing(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            tmp.write("x" * (persistence.MAX_PROJECT_BYTES + 1))
            tmp.flush()
            path = tmp.name
        try:
            with self.assertRaises(ValueError) as ctx:
                persistence.ensure_file_size(path)
            self.assertIn("过大", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_maximum_allowed_size_is_accepted(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            tmp.write("x" * persistence.MAX_PROJECT_BYTES)
            tmp.flush()
            path = tmp.name
        try:
            persistence.ensure_file_size(path)
        finally:
            os.unlink(path)


class IDValidationTests(unittest.TestCase):
    MINIMAL_PAGE = {"segments": [], "texts": [], "shapes": []}

    def test_missing_id_is_allowed(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [10, 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, _ = persistence.validate_page_data(page)
        self.assertTrue(ok)

    def test_list_id_is_rejected(self):
        page = {
            "segments": [{"id": [1, 2], "p1": [0, 0], "p2": [10, 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("ID", msg)

    def test_dict_id_is_rejected(self):
        page = {
            "segments": [],
            "texts": [{"id": {"a": 1}, "text": "foo", "pos": [0, 0], "color": "#000000"}],
            "shapes": [],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("ID", msg)

    def test_integer_id_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"id": 42, "kind": "circle", "type": "CIRCLE", "center": [0, 0], "radius": 10, "color": "#ff0000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("ID", msg)

    def test_overlength_id_is_rejected(self):
        page = {
            "segments": [{"id": "x" * 129, "p1": [0, 0], "p2": [10, 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("ID", msg)

    def test_shared_stroke_id_is_allowed_across_segments(self):
        stroke_id = "stroke-123"
        page = {
            "segments": [
                {"id": stroke_id, "p1": [0, 0], "p2": [10, 10], "color": "#000000", "width": 2},
                {"id": stroke_id, "p1": [10, 10], "p2": [20, 20], "color": "#000000", "width": 2},
            ],
            "texts": [],
            "shapes": [],
        }
        ok, _ = persistence.validate_page_data(page)
        self.assertTrue(ok)

    def test_text_and_shape_cannot_share_id(self):
        conflict_id = "object-1"
        page = {
            "segments": [],
            "texts": [{"id": conflict_id, "text": "A", "pos": [0, 0], "color": "#000000"}],
            "shapes": [{"id": conflict_id, "kind": "circle", "type": "CIRCLE", "center": [10, 10], "radius": 5, "color": "#ff0000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("冲突", msg)

    def test_stroke_and_shape_cannot_share_id(self):
        conflict_id = "shared"
        page = {
            "segments": [{"id": conflict_id, "p1": [0, 0], "p2": [10, 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [{"id": conflict_id, "kind": "circle", "type": "CIRCLE", "center": [10, 10], "radius": 5, "color": "#ff0000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("冲突", msg)


class CoordinateBoundaryTests(unittest.TestCase):
    def test_nan_coordinate_is_rejected(self):
        page = {
            "segments": [{"p1": [float("nan"), 0], "p2": [10, 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("坐标", msg)

    def test_infinity_coordinate_is_rejected(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [float("inf"), 10], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("坐标", msg)

    def test_extreme_but_finite_coordinate_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "circle", "type": "CIRCLE", "center": [persistence.MAX_ABS_COORD + 1, 0], "radius": 10, "color": "#ff0000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_maximum_allowed_coordinate_is_accepted(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [persistence.MAX_ABS_COORD, persistence.MAX_ABS_COORD], "color": "#000000", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, _ = persistence.validate_page_data(page)
        self.assertTrue(ok)


class ColorValidationTests(unittest.TestCase):
    def test_rgb_hex_color_is_accepted(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [10, 10], "color": "#ff4757", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, _ = persistence.validate_page_data(page)
        self.assertTrue(ok)

    def test_argb_hex_color_is_accepted(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [10, 10], "color": "#80ff4757", "width": 2}],
            "texts": [],
            "shapes": [],
        }
        ok, _ = persistence.validate_page_data(page)
        self.assertTrue(ok)

    def test_invalid_hex_color_is_rejected(self):
        for bad_color in ("#gg0000", "#12345", "#1234567", "red", "", "#"):
            with self.subTest(color=bad_color):
                page = {
                    "segments": [{"p1": [0, 0], "p2": [10, 10], "color": bad_color, "width": 2}],
                    "texts": [],
                    "shapes": [],
                }
                ok, msg = persistence.validate_page_data(page)
                self.assertFalse(ok)
                self.assertIn("样式", msg)


class PolyPointCountTests(unittest.TestCase):
    def test_line_must_have_exactly_two_points(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "LINE", "points": [[0, 0], [10, 10], [20, 20]], "closed": False, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("点", msg)

    def test_triangle_must_have_exactly_three_points(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "TRIANGLE", "points": [[0, 0], [10, 10]], "closed": True, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_rectangle_must_have_exactly_four_points(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "RECT", "points": [[0, 0], [10, 0], [10, 10]], "closed": True, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_poly_with_excessive_points_is_rejected(self):
        points = [[i, i] for i in range(persistence.MAX_POLY_POINTS + 1)]
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "LINE", "points": points, "closed": False, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_total_poly_points_across_shapes_is_limited(self):
        # Each rect needs 4 points. Create many small shapes, then one large one to exceed limit.
        shapes = []
        accumulated = 0
        while accumulated + 4 < persistence.MAX_TOTAL_POLY_POINTS:
            shapes.append({"kind": "poly", "type": "RECT", "points": [[0, 0], [10, 0], [10, 10], [0, 10]], "closed": True, "color": "#000000", "width": 2})
            accumulated += 4
        # Now add one more with enough points to exceed the limit
        remaining = persistence.MAX_TOTAL_POLY_POINTS - accumulated
        overflow_points = [[i, i] for i in range(remaining + 100)]
        shapes.append({"kind": "poly", "type": "RECT", "points": overflow_points, "closed": True, "color": "#000000", "width": 2})
        page = {"segments": [], "texts": [], "shapes": shapes}
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)


class KindTypeConsistencyTests(unittest.TestCase):
    def test_poly_line_must_be_open(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "LINE", "points": [[0, 0], [10, 10]], "closed": True, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("闭合", msg)

    def test_poly_triangle_must_be_closed(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "TRIANGLE", "points": [[0, 0], [10, 0], [5, 10]], "closed": False, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_angle_kind_must_have_angle_type(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "angle", "type": "CIRCLE", "vertex": [0, 0], "p1": [10, 0], "p2": [0, 10], "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_circle_kind_must_have_circle_type(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "circle", "type": "RECT", "center": [0, 0], "radius": 10, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_ellipse_kind_must_have_ellipse_type(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "ellipse", "type": "CIRCLE", "center": [0, 0], "rx": 10, "ry": 5, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_rect_kind_must_have_3d_type(self):
        for bad_type in ("RECT", "LINE", "CIRCLE"):
            with self.subTest(type=bad_type):
                page = {
                    "segments": [],
                    "texts": [],
                    "shapes": [{"kind": "rect", "type": bad_type, "rect": [0, 0, 100, 50], "color": "#000000", "width": 2}],
                }
                ok, msg = persistence.validate_page_data(page)
                self.assertFalse(ok)

    def test_unknown_kind_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "hexagon", "type": "HEXAGON", "center": [0, 0], "radius": 10, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)
        self.assertIn("类型", msg)

    def test_unknown_poly_type_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "poly", "type": "HEXAGON", "points": [[0, 0], [10, 0], [10, 10]], "closed": True, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)


class DegenerateShapeTests(unittest.TestCase):
    def test_zero_radius_circle_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "circle", "type": "CIRCLE", "center": [0, 0], "radius": 0, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_negative_radius_circle_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "circle", "type": "CIRCLE", "center": [0, 0], "radius": -10, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_zero_rx_ellipse_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "ellipse", "type": "ELLIPSE", "center": [0, 0], "rx": 0, "ry": 10, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_zero_ry_ellipse_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "ellipse", "type": "ELLIPSE", "center": [0, 0], "rx": 10, "ry": 0, "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_zero_width_rect_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "rect", "type": "CUBE", "rect": [0, 0, 0, 50], "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)

    def test_zero_height_rect_is_rejected(self):
        page = {
            "segments": [],
            "texts": [],
            "shapes": [{"kind": "rect", "type": "CUBE", "rect": [0, 0, 100, 0], "color": "#000000", "width": 2}],
        }
        ok, msg = persistence.validate_page_data(page)
        self.assertFalse(ok)


class ProjectLimitsTests(unittest.TestCase):
    BLANK = {"segments": [], "texts": [], "shapes": []}

    def test_excessive_page_count_is_rejected(self):
        data = {"pages": [self.BLANK] * (persistence.MAX_PAGES + 1)}
        with self.assertRaises(ValueError) as ctx:
            persistence.normalize_project_data(data)
        self.assertIn("pages", str(ctx.exception))

    def test_schema_version_above_current_is_rejected(self):
        data = {"schema_version": persistence.SCHEMA_VERSION + 1, "pages": [self.BLANK]}
        with self.assertRaises(ValueError) as ctx:
            persistence.normalize_project_data(data)
        self.assertIn("版本", str(ctx.exception))

    def test_schema_version_zero_is_rejected(self):
        data = {"schema_version": 0, "pages": [self.BLANK]}
        with self.assertRaises(ValueError) as ctx:
            persistence.normalize_project_data(data)
        self.assertIn("版本", str(ctx.exception))

    def test_mismatched_kind_is_rejected(self):
        data = {"kind": persistence.PROJECT_KIND, "pages": [self.BLANK]}
        with self.assertRaises(ValueError) as ctx:
            persistence.normalize_project_data(data, kind=persistence.AUTOSAVE_KIND)
        self.assertIn("类型", str(ctx.exception))

    def test_unknown_kind_is_rejected(self):
        data = {"kind": "unknown-kind", "pages": [self.BLANK]}
        with self.assertRaises(ValueError) as ctx:
            persistence.normalize_project_data(data)
        self.assertIn("类型", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
