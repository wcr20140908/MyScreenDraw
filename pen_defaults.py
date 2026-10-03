# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent JSON pen presets and an embeddable PyQt6 editor.

No application, window, timer, persistence, tool switching, or main/i18n import is
performed here. The parent owns the default-off enabled switch, persists emitted
values, and calls ``apply_preset`` at startup/tool re-entry (not on each stroke).
It must also refresh its own toolbar after applying live settings.

Schema: regular pens have color, width, speed_width and options; calligraphy also
has calligraphy_angle. Marker has color, width and alpha_pct; laser has color and
width. Unknown fields/keys are dropped. Missing or corrupt fields use factory
values. Numeric strings and booleans are not numbers; finite numeric dimensions
are truncated to integers and clamped to the application's persisted ranges.
Out-of-range style options use their tuple defaults, matching main's validator.
Colors are canonical #rrggbb or #aarrggbb strings (alpha is preserved).

Pass the host's PEN_STYLES/PEN_STYLE_OPTIONS to avoid duplicating schema ownership.
The immutable built-ins support the simple capture_current(canvas, key) and
apply_preset(canvas, key, preset) forms for the current eleven styles.

Editor notifications: preset_saved(str, dict), current_captured(str, dict), or
optional on_save(key, value)/on_capture(key, value) callbacks. Capture both loads
and notifies a new preset; it does not apply it. Each notification receives a copy
independent of the editor, input, canvas and the other notification mechanism.
Connect a signal OR its matching callback to avoid handling an action twice.

Localization: labels[key] overrides translate(key), with DEFAULT_LABELS as an
English fallback when translation returns None, an empty string, or the key.
All visible labels, hints and error text use the pen_defaults_* namespace.
"""
from collections.abc import Mapping
from copy import deepcopy
import math
from types import MappingProxyType

from PyQt6 import sip
from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from themed_controls import apply_combo_theme, controls_stylesheet, theme_palette


DEFAULT_PEN_STYLES = (
    "pen", "fountain", "brush", "calligraphy", "pencil", "crayon",
    "chalk", "neon", "dashed", "rainbow", "arrow",
)
DEFAULT_STYLE_OPTIONS = MappingProxyType({
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
})

DEFAULT_LABELS = {
    "pen_defaults_tool": "Pen",
    "pen_defaults_choose_color": "Choose color…",
    "pen_defaults_color": "Color",
    "pen_defaults_width": "Width",
    "pen_defaults_speed_width": "Vary width with speed",
    "pen_defaults_calligraphy_angle": "Nib angle (degrees)",
    "pen_defaults_alpha_pct": "Opacity (%)",
    "pen_defaults_save": "Save preset",
    "pen_defaults_capture": "Capture current",
    "pen_defaults_color_hint": "#RRGGBB, #AARRGGBB, or a color name",
    "pen_defaults_invalid_color": "Enter a valid color before saving.",
    "pen_defaults_style_pen": "Pen",
    "pen_defaults_style_fountain": "Fountain pen",
    "pen_defaults_style_brush": "Brush",
    "pen_defaults_style_calligraphy": "Calligraphy",
    "pen_defaults_style_pencil": "Pencil",
    "pen_defaults_style_crayon": "Crayon",
    "pen_defaults_style_chalk": "Chalk",
    "pen_defaults_style_neon": "Neon",
    "pen_defaults_style_dashed": "Dashed pen",
    "pen_defaults_style_rainbow": "Rainbow pen",
    "pen_defaults_style_arrow": "Arrow pen",
    "pen_defaults_style_marker": "Marker",
    "pen_defaults_style_laser": "Laser",
    "pen_defaults_option_taper": "Taper length (%)",
    "pen_defaults_option_pressure": "Pressure response (%)",
    "pen_defaults_option_nib_aspect": "Flat nib width (%)",
    "pen_defaults_option_density": "Grain coverage (%)",
    "pen_defaults_option_opacity": "Ink opacity (%)",
    "pen_defaults_option_glow_size": "Glow width (%)",
    "pen_defaults_option_glow_strength": "Glow strength (%)",
    "pen_defaults_option_dash_length": "Dash length (1/10 width)",
    "pen_defaults_option_dash_gap": "Dash gap (1/10 width)",
    "pen_defaults_option_hue_speed": "Hue speed (degrees/100px)",
    "pen_defaults_option_saturation": "Saturation (%)",
    "pen_defaults_option_head_size": "Arrowhead size",
    "pen_defaults_option_head_angle": "Arrow half-angle (degrees)",
}

# Marker accepts 1..80 in persisted/live settings even though the toolbar's
# current slider starts at 6. Do not silently discard valid existing widths.
_WIDTH_RANGES = {"marker": (1, 80), "laser": (6, 40)}


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value)))


def _bounded_int(value, default, low, high):
    if not _is_number(value):
        return default
    return int(max(low, min(high, value)))


def _color(value, default):
    if not isinstance(value, (str, QColor)):
        return default
    color = QColor(value.strip() if isinstance(value, str) else value)
    if not color.isValid():
        return default
    return color.name(QColor.NameFormat.HexArgb) if color.alpha() != 255 else color.name()


def _keys(pen_styles):
    return tuple(dict.fromkeys((*pen_styles, "marker", "laser")))


def _check_key(key, pen_styles):
    if key not in _keys(pen_styles):
        raise ValueError(f"Unknown pen preset key: {key!r}")


def _normalize_preset(raw, key, style_options):
    raw = _mapping(raw)
    if key in ("marker", "laser"):
        marker = key == "marker"
        result = {
            "color": _color(raw.get("color"), "#fff200" if marker else "#ff0000"),
            "width": _bounded_int(raw.get("width"), 24 if marker else 14, *_WIDTH_RANGES[key]),
        }
        if marker:
            result["alpha_pct"] = _bounded_int(raw.get("alpha_pct"), 35, 10, 90)
        return result

    options = _mapping(raw.get("options"))
    normalized_options = {}
    for name, low, high, default in style_options.get(key, ()):
        value = options.get(name)
        valid = _is_number(value) and low <= value <= high
        normalized_options[name] = int(value) if valid else int(default)
    speed = raw.get("speed_width")
    result = {
        "color": _color(raw.get("color"), "#ff4757"),
        "width": _bounded_int(raw.get("width"), 4, 1, 40),
        "speed_width": speed if isinstance(speed, bool) else True,
        "options": normalized_options,
    }
    if key == "calligraphy":
        result["calligraphy_angle"] = _bounded_int(raw.get("calligraphy_angle"), 45, 0, 180)
    return result


def normalize_presets(raw, pen_styles, style_options):
    """Return a complete JSON preset mapping with no shared mutable values.

    ``pen_styles`` is a sequence of style keys; ``style_options`` maps style keys
    to (name, minimum, maximum, default) tuples. These are trusted schema supplied
    by the host. ``raw`` is untrusted saved data and may have any JSON shape.
    """
    raw = _mapping(raw)
    return {key: _normalize_preset(raw.get(key), key, style_options) for key in _keys(pen_styles)}


def capture_current(canvas, key, *, pen_styles=DEFAULT_PEN_STYLES,
                    style_options=DEFAULT_STYLE_OPTIONS):
    """Read the selected key's LIVE settings, returning a normalized JSON copy.

    Does not call canvas.pen_profile(): that accessor lazily creates profiles.
    Missing live settings therefore produce defaults without changing the canvas.
    Marker alpha is converted from 0..255 to an integer percent in 10..90.
    Unknown keys raise ValueError; the active tool/pen style is never changed.
    """
    _check_key(key, pen_styles)
    if key in ("marker", "laser"):
        raw = {"color": getattr(canvas, key + "_color", None),
               "width": getattr(canvas, key + "_width", None)}
        if key == "marker":
            alpha = getattr(canvas, "marker_alpha", None)
            # Bound before multiplying, including arbitrarily large corrupt ints.
            raw["alpha_pct"] = (round(max(0, min(255, alpha)) * 100 / 255)
                                if _is_number(alpha) else None)
    else:
        profiles = _mapping(getattr(canvas, "pen_profiles", None))
        raw = dict(_mapping(profiles.get(key)))
        raw["options"] = _mapping(getattr(canvas, "pen_options", None)).get(key)
        if key == "calligraphy":
            raw["calligraphy_angle"] = getattr(canvas, "calligraphy_angle", None)
    return _normalize_preset(raw, key, style_options)


def apply_preset(canvas, key, preset, *, pen_styles=DEFAULT_PEN_STYLES,
                 style_options=DEFAULT_STYLE_OPTIONS):
    """Apply a normalized copy to ONLY the selected key's live settings.

    Returns another independent JSON copy. Does not select a tool, finish a
    stroke, repaint, mutate saved presets, or change any other style's settings.
    The caller controls when applying is enabled and safe (startup/tool re-entry).
    """
    _check_key(key, pen_styles)
    value = _normalize_preset(preset, key, style_options)
    if key in ("marker", "laser"):
        setattr(canvas, key + "_color", QColor(value["color"]))
        setattr(canvas, key + "_width", value["width"])
        if key == "marker":
            canvas.marker_alpha = round(value["alpha_pct"] * 255 / 100)
    else:
        # Replace dictionaries rather than mutate a possibly shared saved entry.
        profiles = dict(_mapping(getattr(canvas, "pen_profiles", None)))
        profiles[key] = {field: value[field] for field in ("color", "width", "speed_width")}
        canvas.pen_profiles = profiles
        options = dict(_mapping(getattr(canvas, "pen_options", None)))
        if key in style_options or key in options:
            options[key] = dict(value["options"])
            canvas.pen_options = options
        if key == "calligraphy":
            canvas.calligraphy_angle = value["calligraphy_angle"]
    return deepcopy(value)


class PenDefaultsEditor(QWidget):
    """Editor with no persistence, application or global enabled-switch policy.

    ``presets()`` returns the saved/captured snapshot; ``current_preset()`` reads
    the current normalized draft. Unsaved valid edits survive dropdown changes,
    but only Save/Capture commit a key and notify the parent. ``set_presets``
    replaces all snapshots/drafts without notification, preserving the selection.
    Capture is disabled when no canvas was supplied.

    Public controls: pen_combo, color_edit, width_spin, speed_check, angle_spin,
    alpha_spin, option_controls (name -> QSpinBox), save_button, capture_button.
    The option controls are rebuilt when the selection changes.
    """

    preset_saved = pyqtSignal(str, dict)
    current_captured = pyqtSignal(str, dict)

    def __init__(self, pen_styles, style_options, presets=None, canvas=None, *,
                 translate=None, labels=None, on_save=None, on_capture=None, parent=None):
        super().__init__(parent)
        self._pen_styles = tuple(pen_styles)
        self._style_options = {key: tuple(tuple(spec) for spec in specs)
                               for key, specs in style_options.items()}
        self._canvas = canvas
        self._translate = translate
        self._labels = dict(labels or {})
        self._on_save = on_save
        self._on_capture = on_capture
        self._presets = normalize_presets(presets, self._pen_styles, self._style_options)
        self._drafts = deepcopy(self._presets)
        self._key = None
        self._theme = None

        layout = QVBoxLayout(self)
        form = self._form()
        layout.addLayout(form)
        self.pen_combo = QComboBox(self)
        self.pen_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.pen_combo.setMinimumContentsLength(10)
        self.pen_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for key in self._presets:
            self.pen_combo.addItem(self._text("style_" + key, key.replace("_", " ").title()), key)
        form.addRow(self._label("tool"), self.pen_combo)
        color_row = QHBoxLayout()
        self.color_button = QPushButton(self)
        self.color_button.setToolTip(self._text("choose_color"))
        self.color_button.setMinimumWidth(68)
        self.color_button.setAccessibleName(self._text("choose_color"))
        self.color_button.setMinimumHeight(36)
        self.color_button.setIconSize(QSize(44, 24))
        self.color_button.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_button)
        self.color_edit = QLineEdit(self)
        self.color_edit.setReadOnly(True)
        self.color_edit.setAccessibleName(self._text("color"))
        self.color_edit.setToolTip(self._text("color_hint"))
        self.color_edit.setMaximumWidth(112)
        color_row.addWidget(self.color_edit)
        form.addRow(self._label("color"), color_row)
        self.color_error = self._label("invalid_color")
        form.addRow(self.color_error)
        self.width_spin = QSpinBox(self)
        form.addRow(self._label("width"), self.width_spin)
        self.speed_check = QCheckBox(self)
        self.speed_check.setAccessibleName(self._text("speed_width"))
        self._speed_label = self._label("speed_width")
        self._speed_label.setBuddy(self.speed_check)
        form.addRow(self._speed_label, self.speed_check)
        self.angle_spin = QSpinBox(self)
        self.angle_spin.setRange(0, 180)
        self._angle_label = self._label("calligraphy_angle")
        form.addRow(self._angle_label, self.angle_spin)
        self.alpha_spin = QSpinBox(self)
        self.alpha_spin.setRange(10, 90)
        self._alpha_label = self._label("alpha_pct")
        form.addRow(self._alpha_label, self.alpha_spin)
        self._options_form = self._form()
        layout.addLayout(self._options_form)
        self.option_controls = {}

        actions = QHBoxLayout()
        self.save_button = QPushButton(self._text("save"), self)
        self.capture_button = QPushButton(self._text("capture"), self)
        self.capture_button.setEnabled(canvas is not None)
        actions.addWidget(self.save_button)
        actions.addWidget(self.capture_button)
        layout.addLayout(actions)
        self.color_edit.textChanged.connect(self._validate_color)
        self.pen_combo.currentIndexChanged.connect(self._selection_changed)
        self.save_button.clicked.connect(self._save)
        self.capture_button.clicked.connect(self._capture)
        self._selection_changed()

    def _text(self, suffix, fallback=None):
        key = "pen_defaults_" + suffix
        explicit = self._labels.get(key)
        if isinstance(explicit, str):
            return explicit
        translated = self._translate(key) if self._translate is not None else None
        if isinstance(translated, str) and translated and translated != key:
            return translated
        return DEFAULT_LABELS.get(key, fallback if fallback is not None else key)

    @staticmethod
    def _form():
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return form

    def _label(self, suffix, fallback=None):
        label = QLabel(self._text(suffix, fallback), self)
        label.setWordWrap(True)
        # Label-above-field rows allow long translations to grow vertically.
        # Preferred width keeps labels visible; Ignored collapses form labels.
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        label.setMinimumWidth(0)
        return label

    def current_key(self):
        """Return the selected schema key, not its translated display name."""
        return self._key

    def set_current_key(self, key):
        """Select a pen without saving, capturing or applying; reject unknown keys."""
        _check_key(key, self._pen_styles)
        self.pen_combo.setCurrentIndex(self.pen_combo.findData(key))

    def presets(self):
        """Return a detached snapshot of the last loaded/saved/captured presets."""
        return deepcopy(self._presets)

    def set_presets(self, raw):
        """Replace snapshots and drafts without notification or live application."""
        self._presets = normalize_presets(raw, self._pen_styles, self._style_options)
        self._drafts = deepcopy(self._presets)
        self._load(self._presets[self._key])

    def current_preset(self):
        """Return a fresh normalized draft; invalid colors use the factory color."""
        raw = {"color": self.color_edit.text(), "width": self.width_spin.value()}
        if self._key == "marker":
            raw["alpha_pct"] = self.alpha_spin.value()
        elif self._key != "laser":
            raw["speed_width"] = self.speed_check.isChecked()
            raw["options"] = {name: spin.value() for name, spin in self.option_controls.items()}
            if self._key == "calligraphy":
                raw["calligraphy_angle"] = self.angle_spin.value()
        return _normalize_preset(raw, self._key, self._style_options)

    def _selection_changed(self, _index=None):
        if self._key is not None:
            self._drafts[self._key] = self.current_preset()
        self._key = self.pen_combo.currentData()
        self._load(self._drafts[self._key])

    def _load(self, value):
        key = self._key
        self.width_spin.setRange(*_WIDTH_RANGES.get(key, (1, 40)))
        self.color_edit.setText(value["color"])
        self.width_spin.setValue(value["width"])
        self.speed_check.setVisible(key not in ("marker", "laser"))
        self._speed_label.setVisible(key not in ("marker", "laser"))
        self.speed_check.setChecked(value.get("speed_width", True))
        self.angle_spin.setVisible(key == "calligraphy")
        self._angle_label.setVisible(key == "calligraphy")
        self.angle_spin.setValue(value.get("calligraphy_angle", 45))
        self.alpha_spin.setVisible(key == "marker")
        self._alpha_label.setVisible(key == "marker")
        self.alpha_spin.setValue(value.get("alpha_pct", 35))
        while self._options_form.rowCount():
            self._options_form.removeRow(0)
        self.option_controls = {}
        for name, low, high, default in self._style_options.get(key, ()):
            spin = QSpinBox(self)
            spin.setRange(low, high)
            spin.setValue(value["options"][name])
            label = self._label("option_" + name, name.replace("_", " ").title())
            self._options_form.addRow(label, spin)
            self.option_controls[name] = spin
        self._validate_color()

    def apply_theme(self, theme):
        """Restyle controls and popup views without changing any pen draft."""
        self._theme = dict(theme)
        self.setPalette(theme_palette(theme))
        self.setStyleSheet(controls_stylesheet(theme))
        apply_combo_theme(self.pen_combo, theme)

    def _pick_color(self, _checked=False):
        dialog = QColorDialog(QColor(self.color_edit.text()), self)
        dialog.setWindowTitle(self._text("choose_color"))
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        # Qt discards alpha set before ShowAlphaChannel is enabled.
        dialog.setCurrentColor(QColor(self.color_edit.text()))
        if self._theme is not None:
            dialog.setPalette(theme_palette(self._theme))
            dialog.setStyleSheet(controls_stylesheet(self._theme))
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                color = dialog.selectedColor()
                if color.isValid():
                    self.color_edit.setText(color.name(QColor.NameFormat.HexArgb)
                                            if color.alpha() != 255 else color.name())
        finally:
            sip.delete(dialog)

    def _update_color_preview(self, color):
        preview = QPixmap(44, 24)
        painter = QPainter(preview)
        try:
            for y in range(0, 24, 6):
                for x in range(0, 44, 6):
                    painter.fillRect(x, y, 6, 6, QColor("#eeeeee" if (x // 6 + y // 6) % 2 else "#aaaaaa"))
            painter.fillRect(preview.rect(), color)
        finally:
            painter.end()
        self.color_button.setIcon(QIcon(preview))

    def _validate_color(self, _text=None):
        valid = QColor(self.color_edit.text().strip()).isValid()
        self.save_button.setEnabled(valid)
        self.color_error.setVisible(not valid)
        if valid:
            self._update_color_preview(QColor(self.color_edit.text().strip()))

    def _notify(self, key, value, signal, callback):
        self._presets[key] = deepcopy(value)
        self._drafts[key] = deepcopy(value)
        self._load(value)
        signal.emit(key, deepcopy(value))
        if callback is not None:
            callback(key, deepcopy(value))

    def _save(self, _checked=False):
        if QColor(self.color_edit.text().strip()).isValid():
            self._notify(self._key, self.current_preset(), self.preset_saved, self._on_save)

    def _capture(self, _checked=False):
        if self._canvas is not None:
            value = capture_current(self._canvas, self._key, pen_styles=self._pen_styles,
                                    style_options=self._style_options)
            self._notify(self._key, value, self.current_captured, self._on_capture)
