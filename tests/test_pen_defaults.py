# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused, desktop-free tests for independent annotation pen presets."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication, QCheckBox, QColorDialog, QDialog, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from pen_defaults import (
    DEFAULT_LABELS,
    DEFAULT_PEN_STYLES,
    DEFAULT_STYLE_OPTIONS,
    PenDefaultsEditor,
    apply_preset,
    capture_current,
    normalize_presets,
)


STYLES = (
    "pen", "fountain", "brush", "calligraphy", "pencil", "crayon",
    "chalk", "neon", "dashed", "rainbow", "arrow",
)
OPTIONS = {
    "fountain": (("taper", 0, 200, 100), ("pressure", 0, 100, 100)),
    "brush": (("taper", 0, 200, 100), ("pressure", 0, 100, 100)),
    "calligraphy": (("nib_aspect", 30, 200, 100),),
    "pencil": (("density", 10, 100, 62), ("opacity", 10, 100, 67)),
    "crayon": (("density", 10, 100, 78), ("opacity", 10, 100, 92)),
    "chalk": (("density", 10, 100, 58), ("opacity", 10, 100, 94)),
    "neon": (("glow_size", 100, 500, 300), ("glow_strength", 0, 100, 100)),
    "dashed": (("dash_length", 10, 100, 24), ("dash_gap", 10, 100, 22)),
    "rainbow": (("hue_speed", 5, 200, 55), ("saturation", 0, 100, 88)),
    "arrow": (("head_size", 10, 100, 40), ("head_angle", 10, 70, 28)),
}


def make_canvas():
    return SimpleNamespace(
        pen_style="pen", draw_state="ERASER",
        pen_profiles={
            key: {"color": "#ff4757", "width": 4, "speed_width": True}
            for key in STYLES
        },
        pen_options={
            key: {name: default for name, low, high, default in specs}
            for key, specs in OPTIONS.items()
        },
        calligraphy_angle=45,
        marker_color=QColor("#fff200"), marker_width=24, marker_alpha=89,
        laser_color=QColor("#ff0000"), laser_width=14,
        laser_trail=["untouched"], segments=["untouched"],
    )


class NormalizationTests(unittest.TestCase):
    def test_schema_defaults_cover_all_thirteen_tools(self):
        self.assertEqual(DEFAULT_PEN_STYLES, STYLES)
        self.assertEqual(dict(DEFAULT_STYLE_OPTIONS), OPTIONS)
        result = normalize_presets(None, STYLES, OPTIONS)
        self.assertEqual(list(result), list(STYLES) + ["marker", "laser"])
        for key in STYLES:
            self.assertEqual(result[key]["color"], "#ff4757")
            self.assertEqual(result[key]["width"], 4)
            self.assertIs(result[key]["speed_width"], True)
            expected = {name: default for name, low, high, default in OPTIONS.get(key, ())}
            self.assertEqual(result[key]["options"], expected)
            self.assertEqual("calligraphy_angle" in result[key], key == "calligraphy")
        self.assertEqual(result["calligraphy"]["calligraphy_angle"], 45)
        self.assertEqual(result["marker"], {"color": "#fff200", "width": 24, "alpha_pct": 35})
        self.assertEqual(result["laser"], {"color": "#ff0000", "width": 14})
        json.dumps(result, allow_nan=False)

    def test_corrupt_containers_and_fields_fall_back_independently(self):
        defaults = normalize_presets({}, STYLES, OPTIONS)
        for bad in (None, [], "bad", 12, True):
            self.assertEqual(normalize_presets(bad, STYLES, OPTIONS), defaults)
            self.assertEqual(normalize_presets({key: bad for key in defaults}, STYLES, OPTIONS), defaults)
        for bad in (None, [], {}, "12", True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(bad=bad):
                result = normalize_presets({
                    "fountain": {"width": bad, "color": "invalid color", "speed_width": "false",
                                 "options": {"taper": bad, "pressure": 28}},
                    "marker": {"alpha_pct": bad},
                    "calligraphy": {"calligraphy_angle": bad},
                }, STYLES, OPTIONS)
                self.assertEqual(result["fountain"]["width"], 4)
                self.assertEqual(result["fountain"]["color"], "#ff4757")
                self.assertIs(result["fountain"]["speed_width"], True)
                self.assertEqual(result["fountain"]["options"], {"taper": 100, "pressure": 28})
                self.assertEqual(result["marker"]["alpha_pct"], 35)
                self.assertEqual(result["calligraphy"]["calligraphy_angle"], 45)
                json.dumps(result, allow_nan=False)

    def test_ranges_types_colors_and_unknown_fields(self):
        result = normalize_presets({
            "pen": {"color": "#80ABCDEF", "width": 10**1000, "speed_width": False,
                    "alpha_pct": 12, "options": {"unexpected": 99}},
            "pencil": {"color": "Blue", "width": 7.9, "options": {"density": 101, "opacity": 42.9}},
            "calligraphy": {"width": -100, "calligraphy_angle": 1000},
            "marker": {"width": 0, "alpha_pct": 100, "speed_width": True},
            "laser": {"width": -10, "options": {}}, "unknown": {"width": 2},
        }, STYLES, OPTIONS)
        self.assertEqual(result["pen"], {"color": "#80abcdef", "width": 40, "speed_width": False, "options": {}})
        self.assertEqual(result["pencil"]["color"], "#0000ff")
        self.assertEqual(result["pencil"]["width"], 7)
        self.assertEqual(result["pencil"]["options"], {"density": 62, "opacity": 42})
        self.assertEqual(result["calligraphy"]["calligraphy_angle"], 180)
        self.assertEqual(result["calligraphy"]["width"], 1)
        self.assertEqual(result["marker"], {"color": "#fff200", "width": 1, "alpha_pct": 90})
        self.assertEqual(result["laser"], {"color": "#ff0000", "width": 6})
        self.assertNotIn("unknown", result)
        self.assertEqual(normalize_presets(result, STYLES, OPTIONS), result)

    def test_no_aliasing_across_inputs_styles_or_calls(self):
        shared = {"color": "red", "options": {"taper": 80, "pressure": 30}}
        raw = {"fountain": shared, "brush": shared}
        original = deepcopy(raw)
        first = normalize_presets(raw, STYLES, OPTIONS)
        second = normalize_presets(raw, STYLES, OPTIONS)
        first["fountain"]["options"]["taper"] = 1
        first["pen"]["color"] = "blue"
        self.assertEqual(raw, original)
        self.assertEqual(first["brush"]["options"]["taper"], 80)
        self.assertEqual(second["fountain"]["options"]["taper"], 80)
        self.assertEqual(second["pen"]["color"], "#ff4757")
        self.assertIsNot(first["pen"]["options"], first["arrow"]["options"])

    def test_supplied_schema_is_used_not_global_table(self):
        schema = {"custom": (("grain", 2, 9, 5),)}
        result = normalize_presets({"custom": {"options": {"grain": 8}}}, ("custom",), schema)
        self.assertEqual(list(result), ["custom", "marker", "laser"])
        self.assertEqual(result["custom"]["options"], {"grain": 8})
        self.assertEqual(schema, {"custom": (("grain", 2, 9, 5),)})


class CanvasTests(unittest.TestCase):
    def test_capture_all_styles_as_json_without_mutating_canvas(self):
        canvas = make_canvas()
        canvas.pen_profiles["calligraphy"] = {"color": "#80234567", "width": 18, "speed_width": False}
        canvas.pen_options["calligraphy"]["nib_aspect"] = 160
        canvas.calligraphy_angle = 75
        before = deepcopy(vars(canvas))
        for key in STYLES + ("marker", "laser"):
            preset = capture_current(canvas, key)
            self.assertEqual(json.loads(json.dumps(preset, allow_nan=False)), preset)
            self.assertEqual(vars(canvas), before)
        captured = capture_current(canvas, "calligraphy")
        self.assertEqual(captured, {"color": "#80234567", "width": 18, "speed_width": False,
                                   "options": {"nib_aspect": 160}, "calligraphy_angle": 75})
        captured["options"]["nib_aspect"] = 40
        self.assertEqual(vars(canvas), before)
        self.assertEqual(capture_current(canvas, "marker")["alpha_pct"], 35)

    def test_capture_missing_or_corrupt_live_fields_does_not_create_them(self):
        canvas = SimpleNamespace(pen_profiles=[], pen_options="bad", marker_alpha=float("nan"))
        before = deepcopy(vars(canvas))
        defaults = normalize_presets({}, STYLES, OPTIONS)
        for key in STYLES + ("marker", "laser"):
            self.assertEqual(capture_current(canvas, key), defaults[key])
        self.assertEqual(list(vars(canvas)), list(before))
        self.assertEqual(canvas.pen_profiles, [])
        self.assertEqual(canvas.pen_options, "bad")
        empty = SimpleNamespace()
        self.assertEqual(capture_current(empty, "pen"), defaults["pen"])
        self.assertEqual(vars(empty), {})

    def test_apply_all_styles_only_updates_target_live_settings(self):
        for key in STYLES:
            with self.subTest(key=key):
                canvas = make_canvas()
                before = deepcopy(vars(canvas))
                preset = {"color": "#90445566", "width": 17, "speed_width": False,
                          "options": {name: low for name, low, high, default in OPTIONS.get(key, ())},
                          "calligraphy_angle": 120}
                saved = deepcopy(preset)
                applied = apply_preset(canvas, key, preset)
                self.assertEqual(preset, saved)
                self.assertEqual(canvas.pen_profiles[key], {"color": "#90445566", "width": 17, "speed_width": False})
                self.assertEqual(capture_current(canvas, key), applied)
                for other in STYLES:
                    if other != key:
                        self.assertEqual(canvas.pen_profiles[other], before["pen_profiles"][other])
                        self.assertEqual(canvas.pen_options.get(other), before["pen_options"].get(other))
                for attr in ("pen_style", "draw_state", "marker_color", "marker_width", "marker_alpha",
                             "laser_color", "laser_width", "segments", "laser_trail"):
                    self.assertEqual(getattr(canvas, attr), before[attr])
                self.assertEqual(canvas.calligraphy_angle, 120 if key == "calligraphy" else 45)
                applied["options"]["new"] = 0
                self.assertNotIn("new", canvas.pen_options.get(key, {}))
                canvas.pen_profiles[key]["width"] = 2
                self.assertEqual(preset, saved)

    def test_marker_laser_roundtrip_and_no_preset_aliasing(self):
        canvas = make_canvas()
        profiles = deepcopy(canvas.pen_profiles)
        for pct in range(10, 91):
            preset = {"color": "#fedcba", "width": 35, "alpha_pct": pct}
            self.assertEqual(apply_preset(canvas, "marker", preset), preset)
            self.assertEqual(canvas.marker_alpha, round(pct * 255 / 100))
            self.assertEqual(capture_current(canvas, "marker"), preset)
        laser = {"color": "#123456", "width": 23}
        result = apply_preset(canvas, "laser", laser)
        result["width"] = 40
        self.assertEqual(canvas.laser_width, 23)
        self.assertEqual(capture_current(canvas, "laser"), laser)
        self.assertEqual(canvas.pen_profiles, profiles)
        self.assertEqual(canvas.pen_style, "pen")
        self.assertEqual(canvas.draw_state, "ERASER")

    def test_apply_corruption_and_custom_schema(self):
        canvas = SimpleNamespace(pen_profiles=None, pen_options=[])
        schema = {"custom": (("grain", 2, 9, 5),)}
        result = apply_preset(canvas, "custom", {"width": float("nan"), "options": {"grain": 8}},
                              pen_styles=("custom",), style_options=schema)
        self.assertEqual(result["width"], 4)
        self.assertEqual(canvas.pen_options["custom"], {"grain": 8})
        self.assertEqual(capture_current(canvas, "custom", pen_styles=("custom",), style_options=schema), result)
        apply_preset(canvas, "marker", {"width": True, "alpha_pct": float("inf")})
        self.assertEqual(canvas.marker_width, 24)
        self.assertEqual(canvas.marker_alpha, 89)
        apply_preset(canvas, "laser", [])
        self.assertEqual(canvas.laser_width, 14)

    def test_unknown_key_is_rejected_before_any_mutation(self):
        canvas = make_canvas()
        before = deepcopy(vars(canvas))
        for key in ("bogus", "PEN", None):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    capture_current(canvas, key)
                with self.assertRaises(ValueError):
                    apply_preset(canvas, key, {})
        self.assertEqual(vars(canvas), before)


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = make_canvas()
        self.raw = normalize_presets({}, STYLES, OPTIONS)
        self.editor = PenDefaultsEditor(STYLES, OPTIONS, self.raw, self.canvas)

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()
        self.app.processEvents()

    def _pick_color(self, color, *, accepted=True, inspect=None):
        def interact(dialog):
            self.assertTrue(dialog.testOption(QColorDialog.ColorDialogOption.DontUseNativeDialog))
            self.assertTrue(dialog.testOption(QColorDialog.ColorDialogOption.ShowAlphaChannel))
            self.assertEqual(dialog.currentColor(), QColor(self.editor.current_preset()["color"]))
            self.assertIs(dialog.parentWidget(), self.editor)
            if inspect is not None:
                inspect(dialog)
            dialog.setCurrentColor(QColor(color))
            if accepted:
                dialog.accept()
                return QDialog.DialogCode.Accepted
            dialog.reject()
            return QDialog.DialogCode.Rejected

        # Exercise a real Qt color picker without starting a visible/modal window.
        with patch.object(QColorDialog, "exec", interact):
            self.editor._pick_color()

    def test_color_preview_opens_picker_and_hex_display_is_read_only(self):
        editor = self.editor
        self.assertIsInstance(editor.color_button, QPushButton)
        self.assertTrue(editor.color_edit.isReadOnly())
        self.assertFalse(editor.color_button.icon().isNull())
        self.assertTrue(editor.color_button.accessibleName())
        old_icon = editor.color_button.icon().cacheKey()
        self._pick_color("#80112233")
        self.assertEqual(editor.color_edit.text(), "#80112233")
        self.assertNotEqual(editor.color_button.icon().cacheKey(), old_icon)
        self.assertTrue(editor.save_button.isEnabled())
        self.assertEqual(editor.findChildren(QColorDialog), [])

    def test_picker_cancel_does_not_change_draft_snapshot_or_canvas(self):
        editor = self.editor
        editor.set_current_key("marker")
        editor.color_edit.setText("#80123456")
        editor.width_spin.setValue(51)
        editor.alpha_spin.setValue(67)
        before = (editor.current_preset(), editor.presets(), deepcopy(vars(self.canvas)))
        events = []
        editor.preset_saved.connect(lambda *args: events.append(args))
        editor.current_captured.connect(lambda *args: events.append(args))
        old_icon = editor.color_button.icon().cacheKey()
        self._pick_color("#00010203", accepted=False)
        self.assertEqual((editor.current_preset(), editor.presets(), vars(self.canvas)), before)
        self.assertEqual(editor.color_button.icon().cacheKey(), old_icon)
        self.assertEqual(events, [])
        self.assertEqual(editor.findChildren(QColorDialog), [])

    def test_picker_retains_thirteen_independent_drafts_and_serialized_alpha(self):
        editor = self.editor
        before = deepcopy(vars(self.canvas))
        saved = []
        editor.preset_saved.connect(lambda *args: saved.append(args))
        colors = {}
        for i, key in enumerate(STYLES + ("marker", "laser")):
            editor.set_current_key(key)
            color = QColor(20 + i, 90, 150, (0, 128, 255)[i % 3])
            colors[key] = color.name(QColor.NameFormat.HexArgb) if color.alpha() != 255 else color.name()
            draft_before = editor.current_preset()
            self._pick_color(colors[key], inspect=lambda dialog: self.assertEqual(editor.current_preset(), draft_before))
            expected = dict(draft_before, color=colors[key])
            self.assertEqual(editor.current_preset(), expected)
        self.assertEqual(editor.presets(), self.raw)
        self.assertEqual(saved, [])
        for key, color in colors.items():
            editor.set_current_key(key)
            self.assertEqual(editor.current_preset()["color"], color)
            editor.save_button.click()
            self.assertEqual(saved[-1][0], key)
        self.assertEqual(len(saved), 13)
        exported = json.loads(json.dumps(editor.presets()))
        self.assertEqual(normalize_presets(exported, STYLES, OPTIONS), exported)
        self.assertEqual(exported["marker"]["alpha_pct"], 35)
        self.assertEqual(vars(self.canvas), before)

    @staticmethod
    def _host_themes():
        # Use the host's actual contract without importing/launching main.
        path = Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        return next(ast.literal_eval(node.value) for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "THEMES"
                            for target in node.targets))

    def _assert_theme_palette(self, widget, theme):
        widget.ensurePolished()
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            for role, key in ((QPalette.ColorRole.Base, "panel"),
                              (QPalette.ColorRole.Text, "text"),
                              (QPalette.ColorRole.Highlight, "accent"),
                              (QPalette.ColorRole.HighlightedText, "active_text")):
                self.assertEqual(widget.palette().color(group, role), QColor(theme[key]),
                                 (widget.objectName(), group, role))

    def test_theme_covers_popup_selection_fields_and_rebuilt_options(self):
        editor = self.editor
        themes = self._host_themes()
        before = editor.presets()
        for name in ("dark", "light", "dark"):
            with self.subTest(theme=name):
                theme = themes[name]
                editor.apply_theme(theme)
                editor.set_current_key("neon")
                editor.width_spin.setValue(17)
                for widget in (editor.pen_combo, editor.pen_combo.view(),
                               editor.pen_combo.view().viewport(), editor.color_edit,
                               editor.width_spin, editor.width_spin.findChild(QLineEdit),
                               editor.alpha_spin, editor.angle_spin, *editor.option_controls.values()):
                    self._assert_theme_palette(widget, theme)
                self.assertEqual(editor.current_preset()["width"], 17)
                self.assertEqual(editor.presets(), before)
                self.assertEqual(editor.pen_combo.view().palette().color(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text), QColor(theme["mode_off"]))
                self.assertIn("QComboBox QAbstractItemView", editor.styleSheet())
                self.assertIn("QAbstractItemView::item:selected", editor.styleSheet())

    def test_picker_uses_current_theme_and_theme_does_not_mutate_draft(self):
        editor = self.editor
        editor.width_spin.setValue(19)
        before = (editor.current_preset(), editor.presets(), deepcopy(vars(self.canvas)))
        for theme in self._host_themes().values():
            editor.apply_theme(theme)
            self.assertEqual((editor.current_preset(), editor.presets(), vars(self.canvas)), before)
            self._pick_color("#ff00aa", accepted=False,
                             inspect=lambda dialog: self._assert_theme_palette(dialog, theme))
            self.assertEqual((editor.current_preset(), editor.presets(), vars(self.canvas)), before)

    def test_dropdown_and_applicable_controls_for_all_tools(self):
        editor = self.editor
        self.assertEqual([editor.pen_combo.itemData(i) for i in range(editor.pen_combo.count())],
                         list(STYLES) + ["marker", "laser"])
        for key in STYLES + ("marker", "laser"):
            with self.subTest(key=key):
                editor.set_current_key(key)
                self.assertEqual(editor.current_key(), key)
                self.assertEqual(editor.current_preset(), self.raw[key])
                self.assertEqual(editor.speed_check.isHidden(), key in ("marker", "laser"))
                self.assertEqual(editor.angle_spin.isHidden(), key != "calligraphy")
                self.assertEqual(editor.alpha_spin.isHidden(), key != "marker")
                expected = {name for name, low, high, default in OPTIONS.get(key, ())}
                self.assertEqual(set(editor.option_controls), expected)
                for name, low, high, default in OPTIONS.get(key, ()):
                    spin = editor.option_controls[name]
                    self.assertIsInstance(spin, QSpinBox)
                    self.assertEqual((spin.minimum(), spin.maximum()), (low, high))
        self.assertEqual(len(editor.findChildren(QCheckBox)), 1)  # No global enabled switch.

    def test_save_notifies_parent_with_isolated_values_without_applying(self):
        received = []
        callback_values = []
        editor = PenDefaultsEditor(STYLES, OPTIONS, self.raw, self.canvas,
                                   on_save=lambda key, value: callback_values.append((key, value)))
        self.addCleanup(editor.deleteLater)
        before = deepcopy(vars(self.canvas))
        editor.preset_saved.connect(lambda key, value: received.append((key, value)))
        editor.set_current_key("calligraphy")
        editor.color_edit.setText("#80112233")
        editor.width_spin.setValue(16)
        editor.speed_check.setChecked(False)
        editor.angle_spin.setValue(95)
        editor.option_controls["nib_aspect"].setValue(130)
        self.assertEqual(received, [])
        editor.save_button.click()
        expected = {"color": "#80112233", "width": 16, "speed_width": False,
                    "options": {"nib_aspect": 130}, "calligraphy_angle": 95}
        self.assertEqual(received, [("calligraphy", expected)])
        self.assertEqual(callback_values, received)
        self.assertEqual(vars(self.canvas), before)
        received[0][1]["options"]["nib_aspect"] = 31
        self.assertEqual(callback_values[0][1], expected)
        self.assertEqual(editor.presets()["calligraphy"], expected)
        self.assertEqual(self.raw["calligraphy"]["options"]["nib_aspect"], 100)
        editor.set_current_key("pen")
        editor.set_current_key("calligraphy")
        self.assertEqual(editor.current_preset(), expected)

    def test_capture_uses_selected_tool_not_active_tool(self):
        received, callbacks, saved = [], [], []
        editor = PenDefaultsEditor(STYLES, OPTIONS, self.raw, self.canvas,
                                   on_capture=lambda key, value: callbacks.append((key, value)))
        self.addCleanup(editor.deleteLater)
        editor.current_captured.connect(lambda key, value: received.append((key, value)))
        editor.preset_saved.connect(lambda key, value: saved.append((key, value)))
        self.canvas.pen_profiles["neon"]["width"] = 21
        self.canvas.pen_options["neon"]["glow_size"] = 410
        before = deepcopy(vars(self.canvas))
        editor.set_current_key("neon")
        editor.capture_button.click()
        expected = capture_current(self.canvas, "neon")
        self.assertEqual(received, [("neon", expected)])
        self.assertEqual(callbacks, received)
        self.assertEqual(saved, [])
        self.assertEqual(editor.current_preset(), expected)
        self.assertEqual(editor.presets()["neon"], expected)
        self.assertEqual(vars(self.canvas), before)
        callbacks[0][1]["options"]["glow_size"] = 100
        self.assertEqual(editor.presets()["neon"], expected)
        self.assertEqual(received[0][1], expected)
        self.assertEqual(vars(self.canvas), before)

    def test_marker_and_laser_editing_and_capture(self):
        editor = self.editor
        notifications = []
        editor.preset_saved.connect(lambda key, value: notifications.append((key, value)))
        editor.set_current_key("marker")
        editor.color_edit.setText("#113355")
        editor.width_spin.setValue(62)
        editor.alpha_spin.setValue(63)
        editor.save_button.click()
        self.assertEqual(notifications[-1], ("marker", {"color": "#113355", "width": 62, "alpha_pct": 63}))
        editor.set_current_key("laser")
        editor.width_spin.setValue(29)
        editor.save_button.click()
        self.assertEqual(notifications[-1], ("laser", {"color": "#ff0000", "width": 29}))
        self.canvas.laser_width = 31
        editor.capture_button.click()
        self.assertEqual(editor.width_spin.value(), 31)
        self.assertEqual(self.canvas.marker_width, 24)

    def test_refresh_and_getters_never_alias_and_do_not_notify(self):
        editor = self.editor
        events = []
        editor.preset_saved.connect(lambda *args: events.append(args))
        editor.current_captured.connect(lambda *args: events.append(args))
        editor.set_current_key("fountain")
        self.raw["fountain"]["options"]["taper"] = 12
        self.assertEqual(editor.current_preset()["options"]["taper"], 100)
        editor.set_presets(self.raw)
        self.assertEqual(editor.current_key(), "fountain")
        self.assertEqual(editor.current_preset()["options"]["taper"], 12)
        exported = editor.presets()
        exported["fountain"]["options"]["taper"] = 0
        draft = editor.current_preset()
        draft["options"]["taper"] = 0
        self.assertEqual(editor.current_preset()["options"]["taper"], 12)
        self.raw["fountain"]["options"]["taper"] = 90
        self.assertEqual(editor.presets()["fountain"]["options"]["taper"], 12)
        self.assertEqual(events, [])
        with self.assertRaises(ValueError):
            editor.set_current_key("missing")
        self.assertEqual(editor.current_key(), "fountain")

    def test_invalid_color_cannot_save_and_no_canvas_disables_capture(self):
        editor = PenDefaultsEditor(STYLES, OPTIONS)
        self.addCleanup(editor.deleteLater)
        self.assertFalse(editor.capture_button.isEnabled())
        self.assertTrue(editor.save_button.isEnabled())
        editor.color_edit.setText("definitely not a color")
        self.assertFalse(editor.save_button.isEnabled())
        editor.color_edit.setText("#102030")
        self.assertTrue(editor.save_button.isEnabled())

    def test_unsaved_drafts_survive_switching_without_saving_or_applying(self):
        editor = self.editor
        before = deepcopy(vars(self.canvas))
        editor.set_current_key("pencil")
        editor.width_spin.setValue(19)
        editor.option_controls["density"].setValue(81)
        editor.set_current_key("marker")
        editor.alpha_spin.setValue(65)
        editor.set_current_key("pencil")
        self.assertEqual(editor.width_spin.value(), 19)
        self.assertEqual(editor.option_controls["density"].value(), 81)
        self.assertEqual(editor.presets(), self.raw)
        self.assertEqual(vars(self.canvas), before)
        editor.save_button.click()
        self.assertEqual(editor.presets()["pencil"]["width"], 19)
        self.assertEqual(editor.presets()["marker"]["alpha_pct"], 35)
        editor.set_current_key("marker")
        self.assertEqual(editor.alpha_spin.value(), 65)

    def test_long_chinese_labels_wrap_inside_narrow_parent(self):
        long_label = "这是需要自动折行的中文笔形设置参数说明，不能撑宽设置面板。" * 3
        labels = {key: long_label for key in DEFAULT_LABELS}
        labels.update(pen_defaults_save="保存预设", pen_defaults_capture="捕获当前")
        parent = QWidget()
        # Windows' offscreen plugin does not automatically discover system fonts.
        # Read a local font for meaningful CJK metrics without touching the desktop.
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                parent.setFont(QFont(families[0], 10))
                self.addCleanup(QFontDatabase.removeApplicationFont, font_id)
        layout = QVBoxLayout(parent)
        editor = PenDefaultsEditor(STYLES, OPTIONS, labels=labels, parent=parent)
        layout.addWidget(editor)
        self.addCleanup(parent.deleteLater)
        for key in ("calligraphy", "neon", "marker", "laser"):
            editor.set_current_key(key)
            for label in editor.findChildren(QLabel):
                self.assertTrue(label.wordWrap(), label.text())
            parent.resize(300, 900)
            parent.show()  # QT_QPA_PLATFORM=offscreen: never uses the desktop.
            self.app.processEvents()
            self.assertLessEqual(parent.minimumSizeHint().width(), 300)
            self.assertEqual(parent.width(), 300)
            self.assertLessEqual(editor.width(), 300)
            for label in editor.findChildren(QLabel):
                if not label.isHidden():
                    self.assertGreater(label.width(), 0)
                    self.assertLessEqual(label.geometry().right(), editor.width())
                    self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
            for child in (editor.pen_combo, editor.color_edit, editor.width_spin,
                          editor.save_button, editor.capture_button, *editor.option_controls.values()):
                self.assertLessEqual(child.geometry().right(), editor.width())
        parent.close()

    def test_all_labels_can_be_localized_and_custom_schema_works(self):
        requested = []

        def translate(key):
            requested.append(key)
            return "Localized: " + key

        schema = {"custom": (("grain", 2, 9, 5),)}
        editor = PenDefaultsEditor(("custom",), schema, translate=translate,
                                   labels={"pen_defaults_save": "Explicit save"})
        self.addCleanup(editor.deleteLater)
        self.assertEqual(editor.save_button.text(), "Explicit save")
        self.assertEqual(editor.capture_button.text(), "Localized: pen_defaults_capture")
        self.assertEqual(editor.pen_combo.itemText(0), "Localized: pen_defaults_style_custom")
        self.assertIn("pen_defaults_option_grain", requested)
        editor.option_controls["grain"].setValue(8)
        self.assertEqual(editor.current_preset()["options"], {"grain": 8})
        self.assertEqual(len(editor.presets()), 3)
        self.assertTrue(all(key.startswith("pen_defaults_") for key in requested))
        fallback = PenDefaultsEditor(STYLES, OPTIONS, translate=lambda key: key)
        self.addCleanup(fallback.deleteLater)
        self.assertEqual(fallback.save_button.text(), DEFAULT_LABELS["pen_defaults_save"])
        expected_keys = {"pen_defaults_" + name for name in (
            "tool", "color", "width", "speed_width", "calligraphy_angle", "alpha_pct",
            "save", "capture", "choose_color", "color_hint", "invalid_color",
        )}
        expected_keys.update("pen_defaults_style_" + key for key in STYLES + ("marker", "laser"))
        expected_keys.update("pen_defaults_option_" + spec[0] for specs in OPTIONS.values() for spec in specs)
        self.assertEqual(set(DEFAULT_LABELS), expected_keys)


class LocalizationTests(unittest.TestCase):
    def test_editor_keys_have_eight_languages_without_placeholders(self):
        from i18n import TEXT, _LANGS

        for lang in _LANGS:
            for key in DEFAULT_LABELS:
                with self.subTest(lang=lang, key=key):
                    self.assertIn(key, TEXT[lang])
                    value = TEXT[lang][key]
                    self.assertTrue(value.strip())
                    self.assertNotIn("{", value)
                    self.assertNotIn("}", value)
            for style in STYLES + ("marker", "laser"):
                source = ("pen_" + style) if style in STYLES and style != "pen" else style
                self.assertEqual(TEXT[lang]["pen_defaults_style_" + style], TEXT[lang][source])
            for name in {spec[0] for specs in OPTIONS.values() for spec in specs}:
                source = TEXT[lang]["pen_option_" + name].partition("{value}")[0].rstrip(" :：")
                self.assertTrue(TEXT[lang]["pen_defaults_option_" + name].startswith(source))

    def test_spdx_headers_in_first_three_lines(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("pen_defaults.py", "tests/test_pen_defaults.py", "i18n.py"):
            header = (root / name).read_text(encoding="utf-8-sig").splitlines()[:3]
            self.assertIn("# SPDX-License-Identifier: GPL-3.0-or-later", header)


class IndependenceTests(unittest.TestCase):
    def test_import_does_not_load_main_or_create_application(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; import pen_defaults; "
            "from PyQt6.QtWidgets import QApplication; "
            "assert 'main' not in sys.modules; assert 'i18n' not in sys.modules; "
            "assert QApplication.instance() is None"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_builtin_schema_matches_main_without_importing_it(self):
        source = Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("PEN_STYLES", "PEN_STYLE_OPTIONS"):
                        assignments[target.id] = ast.literal_eval(node.value)
        self.assertEqual(DEFAULT_PEN_STYLES, assignments["PEN_STYLES"])
        self.assertEqual(dict(DEFAULT_STYLE_OPTIONS), assignments["PEN_STYLE_OPTIONS"])


if __name__ == "__main__":
    unittest.main()
