"""Regression coverage for project-file loading and whiteboard page retention."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import display_utils
import persistence


class NormalizeProjectDataTests(unittest.TestCase):
    BLANK = {"segments": [], "texts": [], "shapes": []}

    def test_unusable_schema_version_falls_back_instead_of_raising(self):
        for bad in ("abc", None, [1], {}):
            with self.subTest(schema_version=bad):
                data = persistence.normalize_project_data({"pages": [self.BLANK], "schema_version": bad})
                self.assertEqual(data["schema_version"], persistence.SCHEMA_VERSION)

    def test_numeric_schema_version_is_preserved(self):
        # 数字字符串应被转成 int 并保留（在当前 schema 范围内）。
        # 高于当前 schema 的版本会被拒绝（见 test_persistence_safety 的
        # test_schema_version_above_current_is_rejected）。
        data = persistence.normalize_project_data({"pages": [self.BLANK], "schema_version": "1"})
        self.assertEqual(data["schema_version"], 1)
        data = persistence.normalize_project_data({"pages": [self.BLANK], "schema_version": 1.0})
        self.assertEqual(data["schema_version"], 1)

    def test_autosave_kind_uses_the_normalized_project_shape(self):
        data = persistence.make_project_data(
            pages=[self.BLANK], current_page=0, whiteboard_mode=True,
            board_style="WHITE", app_version="v9.9.9",
            kind=persistence.AUTOSAVE_KIND,
        )
        # The literal is deliberately not the current version: this pins that
        # app_version passes through untouched, whatever it says. Using the real
        # version made the test need a bump on every release for no reason.
        self.assertEqual(data["kind"], persistence.AUTOSAVE_KIND)
        self.assertEqual(data["app_version"], "v9.9.9")
        self.assertNotIn("version", data)
        normalized = persistence.normalize_project_data(data, kind=persistence.AUTOSAVE_KIND)
        self.assertEqual(normalized["app_version"], "v9.9.9")
class ProtractorBaselineTests(unittest.TestCase):
    def test_tolerance_band_reads_the_near_baseline_not_the_far_one(self):
        # y just inside the +1e-6 tolerance must still read as the left baseline (0°),
        # not get clamped to the opposite end (180°).
        self.assertAlmostEqual(display_utils.protractor_angle_degrees(-1.0, 5e-7), 0.0)
        self.assertAlmostEqual(display_utils.protractor_angle_degrees(1.0, 5e-7), 180.0)
        self.assertAlmostEqual(display_utils.protractor_angle_degrees(-1.0, 0.0), 0.0)
        self.assertAlmostEqual(display_utils.protractor_angle_degrees(1.0, 0.0), 180.0)
        self.assertIsNone(display_utils.protractor_angle_degrees(-1.0, 1.0))


class DeserializePageTests(unittest.TestCase):
    """A file the validator accepts must also be renderable.

    validate_page_data allows any finite number for size/width, but QFont/QPen only
    take int; passing 24.0 straight through used to raise TypeError inside paintEvent.
    """

    def setUp(self):
        import main

        self.main = main

    def test_float_numbers_are_coerced_to_the_types_qt_requires(self):
        page = {
            "segments": [{"p1": [0, 0], "p2": [5, 5], "color": "#ff0000", "width": 3.0}],
            "texts": [{"text": "hi", "pos": [1.0, 2.0], "color": "#ff0000",
                       "width": 2.0, "size": 24.5, "scale": 1.0, "rotation": 0.0}],
            "shapes": [{"kind": "circle", "type": "CIRCLE", "center": [0, 0],
                        "radius": 5, "color": "#00ff00", "width": 2.5}],
        }
        self.assertEqual(persistence.validate_page_data(page), (True, ""))
        runtime = self.main.deserialize_page(page)
        self.assertIsInstance(runtime["texts"][0]["size"], int)
        self.assertIsInstance(runtime["texts"][0]["width"], int)
        self.assertIsInstance(runtime["shapes"][0]["width"], int)
        self.assertEqual(runtime["segments"][0]["pen"].width(), 3)
        # Round-tripping the coerced page must still satisfy the validator.
        self.assertEqual(persistence.validate_page_data(self.main.serialize_page(runtime)), (True, ""))

    def test_widths_never_drop_below_one(self):
        page = {"segments": [], "texts": [], "shapes": [
            {"kind": "poly", "type": "LINE", "points": [[0, 0], [1, 1]], "color": "#000000", "width": 0.2}]}
        runtime = self.main.deserialize_page(page)
        self.assertEqual(runtime["shapes"][0]["width"], 1)


def _application():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class WhiteboardPageRetentionTests(unittest.TestCase):
    """Leaving and re-entering the whiteboard must not discard pages 2..N."""

    @classmethod
    def setUpClass(cls):
        cls.app = _application()
        import main

        cls.main = main

    def test_pages_survive_an_exit_and_re_enter_cycle(self):
        canvas = self.main.DrawingCanvas(None)
        try:
            canvas.enter_whiteboard()
            canvas.new_page()
            canvas.new_page()
            self.assertEqual(len(canvas.pages), 3)
            canvas.current_page = 1

            canvas.exit_whiteboard()
            canvas.enter_whiteboard()

            self.assertEqual(len(canvas.pages), 3)
            self.assertEqual(canvas.current_page, 1)
        finally:
            canvas.close()

    def test_first_entry_still_starts_a_single_page(self):
        canvas = self.main.DrawingCanvas(None)
        try:
            canvas.enter_whiteboard()
            self.assertEqual(len(canvas.pages), 1)
            self.assertEqual(canvas.current_page, 0)
        finally:
            canvas.close()


if __name__ == "__main__":
    unittest.main()
