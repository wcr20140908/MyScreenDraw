"""Independent pen profiles and perceptually different nib/material structures."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_pen_styles import PenStyleTestCase
from PyQt6.QtGui import QColor


class PenProfileTests(PenStyleTestCase):
    def test_switch_restores_color_width_speed_and_badge(self):
        c, p = self.canvas, self.panel
        p.choose_pen_style("pencil")
        c.pen_color = QColor("#126734")
        p.pen_slider.setValue(13)
        c.speed_width_enabled = False
        p.refresh_annotate_badge()
        pencil_icon = p.pen_style_buttons["pencil"].icon().pixmap(24, 24).toImage()
        p.choose_pen_style("crayon")
        self.assertEqual(c.pen_color.name(), "#ff4757")
        self.assertEqual(p.pen_slider.value(), 6)
        self.assertTrue(c.speed_width_enabled)
        c.pen_color = QColor("#ad2381")
        p.pen_slider.setValue(21)
        p.refresh_annotate_badge()
        self.assertEqual(pencil_icon, p.pen_style_buttons["pencil"].icon().pixmap(24, 24).toImage())
        p.choose_pen_style("pencil")
        self.assertEqual(c.pen_color.name(), "#126734")
        self.assertEqual(c.pen_width, 13)
        self.assertEqual(p.pen_slider.value(), 13)
        self.assertFalse(c.speed_width_enabled)

    def test_profiles_roundtrip_and_legacy_migration(self):
        c, p = self.canvas, self.panel
        for i, style in enumerate(self.main.PEN_STYLES):
            c.pen_style = style
            c.pen_color = QColor.fromHsv(i * 25, 200, 210)
            c.pen_width = i + 2
            c.speed_width_enabled = bool(i % 2)
        settings = p.collect_settings()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(settings), encoding="utf-8")
            c.pen_profiles = {}
            with patch.object(self.main, "CONFIG_FILE", path):
                p.load_settings()
            self.assertEqual(p.collect_settings()["pen_profiles"], settings["pen_profiles"])
            path.write_text(json.dumps({"pen_color": "#456789", "pen_width": 17, "speed_width": False}), encoding="utf-8")
            with patch.object(self.main, "CONFIG_FILE", path):
                p.load_settings()
            for style in self.main.PEN_STYLES:
                self.assertEqual(c.pen_profile(style), {"color": "#456789", "width": 17, "speed_width": False})
            c.pen_style = "pencil"
            c.pen_width = 3
            self.assertEqual(c.pen_profile("chalk")["width"], 17)

    def test_materials_have_different_spatial_structure(self):
        def metrics(style):
            image = self.main.style_texture(style, QColor("#222222"), {"density": 60, "opacity": 100})
            alphas = [[image.pixelColor(x, y).alpha() for x in range(48)] for y in range(48)]
            holes = sum(a < 12 for row in alphas for a in row) / 2304
            near = sum(abs(alphas[y][x] - alphas[y][x + 1]) for y in range(48) for x in range(47)) / (48 * 47)
            return holes, near
        pencil, crayon, chalk = (metrics(s) for s in ("pencil", "crayon", "chalk"))
        self.assertLess(crayon[0], 0.02, "Wax needs a continuous body")
        self.assertGreater(chalk[0], 0.25, "Chalk needs visible broken powder patches")
        self.assertGreater(pencil[1], crayon[1] * 1.4, "Graphite needs fine directional grain, not wax blocks")

    def test_fountain_nib_direction_visible_without_pressure_or_speed(self):
        c = self.canvas
        c.pen_style = "fountain"
        c.pen_width = 8
        c.speed_width_enabled = False
        c.current_pressure = 1
        widths = []
        for dx, dy in ((1, 1), (1, -1)):
            c._stroke_options = {"taper": 0, "pressure": 0}
            c._last_seg_width = None
            widths.append(c._style_width("fountain", dx, dy))
        self.assertGreater(widths[1], widths[0] * 3, "Fountain nib must visibly contrast cross-nib and along-nib strokes")
