"""Headless checks for deterministic chalk powder, independent of main/UI state."""
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chalk_texture import make_chalk_texture


def alphas(image):
    return [image.pixelColor(x, y).alpha()
            for y in range(image.height()) for x in range(image.width())]


def raw(image):
    return image.constBits().asstring(image.sizeInBytes())


def correlation(values, width, dx, dy):
    height = len(values) // width
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return sum((values[y * width + x] - mean)
               * (values[((y + dy) % height) * width + (x + dx) % width] - mean)
               for y in range(height) for x in range(width)) / len(values) / variance


class ChalkTextureTests(unittest.TestCase):
    def test_image_is_large_enough_to_avoid_old_48_pixel_repeat(self):
        image = make_chalk_texture(QColor("#bd304f"))
        self.assertIsInstance(image, QImage)
        self.assertEqual((image.width(), image.height()), (192, 192))
        self.assertEqual(image.devicePixelRatio(), 1)

    def test_deterministic_without_changing_global_random_state(self):
        before = random.getstate()
        first = make_chalk_texture(QColor("#2188cc"))
        make_chalk_texture(QColor("#dd3322"), 89, 32)
        self.assertEqual(raw(first), raw(make_chalk_texture(QColor("#2188cc"))))
        self.assertEqual(before, random.getstate())

    def test_deterministic_in_fresh_processes_without_gui_application(self):
        script = ("import hashlib; from PyQt6.QtGui import QColor; "
                  "from chalk_texture import make_chalk_texture; "
                  "i=make_chalk_texture(QColor('#2188cc')); "
                  "print(hashlib.sha256(i.constBits().asstring(i.sizeInBytes())).hexdigest())")
        outputs = []
        for seed in ("1", "93487"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
            outputs.append(subprocess.check_output([sys.executable, "-c", script], cwd=ROOT, env=env))
        self.assertEqual(outputs[0], outputs[1])

    def test_rgb_is_exact_input_color_not_whitened(self):
        for rgb in ("#d30000", "#00bd24", "#173bc9", "#000000", "#ffffff"):
            color = QColor(rgb)
            image = make_chalk_texture(color)
            for y in range(image.height()):
                for x in range(image.width()):
                    pixel = image.pixelColor(x, y)
                    if pixel.alpha():
                        self.assertEqual(pixel.getRgb()[:3], color.getRgb()[:3])

    def test_color_does_not_change_powder_geometry_or_mutate_input(self):
        color = QColor(21, 173, 237, 182)
        before = color.rgba()
        first = alphas(make_chalk_texture(color))
        second = alphas(make_chalk_texture(QColor(234, 56, 23, 182)))
        self.assertEqual(first, second)
        self.assertEqual(color.rgba(), before)

    def test_density_increases_coverage_without_shuffling_powder(self):
        previous = [0] * (192 * 192)
        means = []
        for density in (10, 30, 58, 80, 100):
            current = alphas(make_chalk_texture(QColor("#224466"), density, 100))
            self.assertTrue(all(a <= b for a, b in zip(previous, current)))
            means.append(sum(current) / len(current))
            previous = current
        self.assertTrue(all(b > a + 10 for a, b in zip(means, means[1:])), means)

    def test_opacity_and_color_alpha_are_linear_independent_multipliers(self):
        full = alphas(make_chalk_texture(QColor(20, 80, 220), 60, 100))
        half = alphas(make_chalk_texture(QColor(20, 80, 220), 60, 50))
        translucent = alphas(make_chalk_texture(QColor(20, 80, 220, 128), 60, 50))
        self.assertTrue(all(abs(a / 2 - b) <= 1 for a, b in zip(full, half)))
        self.assertTrue(all(abs(a * .5 * 128 / 255 - b) <= 1 for a, b in zip(full, translucent)))
        self.assertTrue(all(a == 0 for a in alphas(make_chalk_texture(QColor(20, 80, 220, 0)))))
        self.assertLessEqual(max(translucent), 64)

    def test_has_patchy_clusters_fine_grain_and_local_voids(self):
        image = make_chalk_texture(QColor("#333333"), 60, 100)
        values = alphas(image)
        holes = sum(v < 12 for v in values) / len(values)
        self.assertGreater(holes, .25)
        self.assertLess(holes, .65)
        self.assertGreater(len(set(values)), 100)
        near = (correlation(values, 192, 1, 0) + correlation(values, 192, 0, 1)) / 2
        middle = (correlation(values, 192, 4, 0) + correlation(values, 192, 0, 4)) / 2
        far = (correlation(values, 192, 48, 0) + correlation(values, 192, 0, 48)) / 2
        self.assertGreater(near, .20, "Powder should cluster, not be independent pixel noise")
        self.assertLess(near, .95, "Fine dry grain must survive smoothing")
        self.assertGreater(middle, .03, "Include larger powder patches")
        self.assertGreater(near, middle + .08)
        self.assertGreater(middle, far + .03)

    def test_no_short_period_dot_lattice_or_directional_banding(self):
        values = alphas(make_chalk_texture(QColor("#333333"), 60, 100))
        for shift in (12, 16, 24, 32, 48, 64, 96):
            horizontal = correlation(values, 192, shift, 0)
            vertical = correlation(values, 192, 0, shift)
            self.assertLess(abs(horizontal), .30, (shift, horizontal))
            self.assertLess(abs(vertical), .30, (shift, vertical))
            self.assertNotEqual(values, values[shift:] + values[:shift])
        self.assertLess(abs(correlation(values, 192, 1, 0) - correlation(values, 192, 0, 1)), .12)

    def test_legacy_48_pixel_sample_still_has_visible_powder_gaps(self):
        image = make_chalk_texture(QColor("#222222"), 60, 100)
        holes = sum(image.pixelColor(x, y).alpha() < 12 for y in range(48) for x in range(48)) / 2304
        self.assertGreater(holes, .25, "Keep the existing pen-profile material contract")
        dense = alphas(make_chalk_texture(QColor("#222222"), 100, 100))
        self.assertGreater(sum(v == 0 for v in dense) / len(dense), .03)
        self.assertGreater(sum(v > 100 for v in dense) / len(dense), .70)

    def test_returned_image_survives_bounded_mask_cache_eviction(self):
        import chalk_texture
        image = make_chalk_texture(QColor("#2199cc"), 60)
        expected = raw(image)
        for density in range(10, 21):
            make_chalk_texture(QColor("#cc9921"), density)
        self.assertLessEqual(chalk_texture._density_mask.cache_info().currsize, 8)
        chalk_texture._density_mask.cache_clear()
        chalk_texture._powder_field.cache_clear()
        self.assertEqual(raw(image), expected)

    def test_tiling_seams_are_not_more_contrasty_than_interior(self):
        values = alphas(make_chalk_texture(QColor("#333333"), 60, 100))
        horizontal = sum(abs(values[y * 192 + x] - values[y * 192 + x + 1])
                         for y in range(192) for x in range(191)) / (192 * 191)
        vertical = sum(abs(values[y * 192 + x] - values[(y + 1) * 192 + x])
                       for y in range(191) for x in range(192)) / (192 * 191)
        seam_x = sum(abs(values[y * 192] - values[y * 192 + 191]) for y in range(192)) / 192
        seam_y = sum(abs(values[x] - values[191 * 192 + x]) for x in range(192)) / 192
        self.assertLess(seam_x, horizontal * 1.6)
        self.assertLess(seam_y, vertical * 1.6)

    def test_images_do_not_share_mutable_cached_qimage_state(self):
        expected = raw(make_chalk_texture(QColor("#1188cc")))
        modified = make_chalk_texture(QColor("#1188cc"))
        modified.fill(QColor("#ff00ff"))
        self.assertEqual(raw(make_chalk_texture(QColor("#1188cc"))), expected)

    def test_parameters_follow_existing_percent_defaults_and_validation(self):
        color = QColor("#112233")
        default = raw(make_chalk_texture(color, 58, 94))
        self.assertEqual(raw(make_chalk_texture(color)), default)
        for bad in (None, True, False, [], "30", -10, 0, 101, float("nan"), float("inf"), 10 ** 400):
            self.assertEqual(raw(make_chalk_texture(color, bad, bad)), default)
        self.assertEqual(raw(make_chalk_texture(color, 58.9, 94.9)), default)

    def test_recoloring_reuses_immutable_density_mask(self):
        import chalk_texture
        make_chalk_texture(QColor("#111111"), 60)
        with patch.object(chalk_texture, "_powder_field", side_effect=AssertionError("expensive rebuild")):
            result = make_chalk_texture(QColor("#00bbcc"), 60, 33)
        self.assertFalse(result.isNull())

    def test_qimage_brush_renders_headlessly_without_white_contamination(self):
        target = QImage(320, 48, QImage.Format.Format_ARGB32_Premultiplied)
        target.fill(QColor("#000000"))
        painter = QPainter(target)
        try:
            pen = QPen(QBrush(make_chalk_texture(QColor("#dd0000"), 60, 100)), 24,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(8, 24), QPointF(312, 24))
        finally:
            painter.end()
        colors = [target.pixelColor(x, 24) for x in range(8, 313)]
        self.assertGreater(sum(c.red() > 10 for c in colors), 80)
        self.assertTrue(all(c.green() == 0 and c.blue() == 0 for c in colors))


if __name__ == "__main__":
    unittest.main()
