import math
import unittest

from display_utils import (
    clamp_ruler_width,
    normalize_calibrations,
    pixels_per_mm_from_dpi,
    protractor_angle_degrees,
    ruler_geometry,
    ruler_mm_from_local_x,
    screen_key,
    valid_pixels_per_mm,
)


class MeasurementUtilsTests(unittest.TestCase):
    def test_dpi_to_pixels_per_mm(self):
        self.assertAlmostEqual(pixels_per_mm_from_dpi(96), 96 / 25.4)
        self.assertAlmostEqual(pixels_per_mm_from_dpi(0), 96 / 25.4)
        self.assertTrue(valid_pixels_per_mm(96 / 25.4))
        self.assertFalse(valid_pixels_per_mm(float("nan")))
        self.assertFalse(valid_pixels_per_mm(True))
        self.assertFalse(valid_pixels_per_mm(0.5))

    def test_screen_key_changes_with_display_scale(self):
        first = screen_key("DISPLAY1", (0, 0, 1920, 1080), 1.0, 96)
        same = screen_key("DISPLAY1", (0, 0, 1920, 1080), 1.0, 96)
        scaled = screen_key("DISPLAY1", (0, 0, 1920, 1080), 1.25, 120)
        self.assertEqual(first, same)
        self.assertNotEqual(first, scaled)

    def test_calibration_records_are_filtered(self):
        value = {
            "valid": {
                "px_per_mm": 4.25,
                "known_length_mm": 100,
                "dpr": 1.25,
                "logical_dpi": 120,
                "geometry": [0, 0, 1920, 1080],
            },
            "low": {"px_per_mm": 0.5},
            "nan": {"px_per_mm": float("nan")},
            "wrong": "record",
        }
        result = normalize_calibrations(value)
        self.assertEqual(list(result), ["valid"])
        self.assertEqual(result["valid"]["px_per_mm"], 4.25)
        self.assertEqual(result["valid"]["geometry"], [0, 0, 1920, 1080])
        clamped = normalize_calibrations({"screen": {"px_per_mm": 4, "known_length_mm": 5000, "dpr": 20, "logical_dpi": 0, "geometry": [1, 2]}})
        self.assertEqual(clamped["screen"]["known_length_mm"], 1000.0)
        self.assertEqual(clamped["screen"]["dpr"], 8.0)
        self.assertEqual(clamped["screen"]["logical_dpi"], 96.0)
        self.assertEqual(clamped["screen"]["geometry"], [])

    def test_ruler_range_does_not_change_millimetre_spacing(self):
        short = ruler_geometry(100, 1, 10, 4.0)
        long = ruler_geometry(300, 1, 10, 4.0)
        self.assertEqual(short["spacing"], 4.0)
        self.assertEqual(long["spacing"], 4.0)
        self.assertEqual(short["major_spacing"], 40.0)
        self.assertEqual(long["major_spacing"], 40.0)
        self.assertEqual(short["length"], 400.0)
        self.assertEqual(long["length"], 1200.0)

    def test_ruler_width_is_visual_and_clamped(self):
        self.assertEqual(clamp_ruler_width(20), 28.0)
        self.assertEqual(clamp_ruler_width(72.5), 72.5)
        self.assertEqual(clamp_ruler_width(999), 120.0)
        self.assertEqual(clamp_ruler_width(float("nan")), 36.0)
        self.assertEqual(clamp_ruler_width("invalid"), 36.0)
        geometry = ruler_geometry(150, 1, 10, 4.0)
        self.assertEqual(geometry["spacing"], 4.0)
        self.assertEqual(geometry["length"], 600.0)

    def test_ruler_coordinate_maps_to_millimetres(self):
        length_mm = 150.0
        length_px = length_mm * 4.0
        self.assertAlmostEqual(ruler_mm_from_local_x(-length_px / 2, length_px, length_mm), 0.0)
        self.assertAlmostEqual(ruler_mm_from_local_x(0, length_px, length_mm), 75.0)
        self.assertAlmostEqual(ruler_mm_from_local_x(length_px / 2, length_px, length_mm), 150.0)
        self.assertAlmostEqual(ruler_mm_from_local_x(9999, length_px, length_mm), 150.0)
        self.assertIsNone(ruler_mm_from_local_x(0, 0, length_mm))

    def test_protractor_angles_use_left_baseline(self):
        self.assertAlmostEqual(protractor_angle_degrees(-1, 0), 0.0)
        self.assertAlmostEqual(protractor_angle_degrees(-1, -1), 45.0)
        self.assertAlmostEqual(protractor_angle_degrees(0, -1), 90.0)
        self.assertAlmostEqual(protractor_angle_degrees(1, -1), 135.0)
        self.assertAlmostEqual(protractor_angle_degrees(1, 0), 180.0)
        self.assertIsNone(protractor_angle_degrees(0, 1))
        self.assertIsNone(protractor_angle_degrees(0, 0))

    def test_protractor_snap_rounds_to_whole_degree(self):
        radians = math.radians(37.4)
        x = -math.cos(radians)
        y = -math.sin(radians)
        self.assertAlmostEqual(protractor_angle_degrees(x, y), 37.4)
        self.assertEqual(protractor_angle_degrees(x, y, snap=True), 37)


if __name__ == "__main__":
    unittest.main()
