# SPDX-License-Identifier: GPL-3.0-or-later
"""Named UI palettes and their local editor, independent of document colors."""
from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget)

ROLES = ('surface', 'panel', 'button', 'hover', 'border', 'text', 'muted',
         'accent', 'selected', 'on_selected', 'disabled', 'focus', 'danger', 'on_danger')
ALIASES = {'frame': 'surface', 'button_hover': 'hover', 'label': 'accent',
           'hint': 'muted', 'active_text': 'on_selected', 'mode': 'selected',
           'mode_off': 'disabled', 'clear': 'danger'}


def palette_from_theme(theme):
    legacy = {'surface': 'frame', 'hover': 'button_hover', 'border': 'accent',
              'muted': 'hint', 'selected': 'accent', 'on_selected': 'active_text',
              'disabled': 'mode_off', 'focus': 'accent', 'danger': 'clear', 'on_danger': 'active_text'}
    return {role: theme.get(role, theme.get(legacy.get(role, role), '#ffffff'))
            for role in ROLES}


def resolved_theme(palette):
    result = dict(palette)
    result.update({alias: result[role] for alias, role in ALIASES.items()})
    return result


def normalize_custom_schemes(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, preset in value.items():
        if not isinstance(key, str) or not key.startswith('custom_') or not isinstance(preset, dict):
            continue
        name, colors = preset.get('name'), preset.get('colors')
        if not isinstance(name, str) or not name.strip() or not isinstance(colors, dict):
            continue
        if not all(isinstance(colors.get(mode), dict) and all(
                isinstance(colors[mode].get(role), str) and QColor(colors[mode][role]).isValid()
                for role in ROLES) for mode in ('light', 'dark')):
            continue
        result[key] = {'name': name.strip(), 'colors': {
            mode: {role: QColor(colors[mode][role]).name() for role in ROLES}
            for mode in ('light', 'dark')}}
    return result


class CustomColorsDialog(QDialog):
    def __init__(self, name, colors, translate, parent=None):
        super().__init__(parent)
        self.tr_text = translate
        self.colors = deepcopy(colors)
        self.setWindowTitle(translate('custom_colors'))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(420, 560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.name_edit.setMaxLength(60)
        form.addRow(translate('custom_scheme_name'), self.name_edit)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(translate('light_theme'), 'light')
        self.mode_combo.addItem(translate('dark_theme'), 'dark')
        form.addRow(translate('custom_scheme_mode'), self.mode_combo)
        layout.addLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        fields = QFormLayout(content)
        self.color_buttons = {}
        for role in ROLES:
            button = QPushButton()
            button.clicked.connect(lambda _checked=False, role=role: self.choose_color(role))
            fields.addRow(translate('theme_role_' + role), button)
            self.color_buttons[role] = button
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.preview = QWidget()
        preview_layout = QHBoxLayout(self.preview)
        preview_layout.addWidget(QLabel(translate('custom_scheme_preview')))
        self.preview_button = QPushButton(translate('custom_scheme_selected'))
        preview_layout.addWidget(self.preview_button)
        layout.addWidget(self.preview)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                       QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(translate('save'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(translate('cancel'))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self.update_save_button)
        self.mode_combo.currentIndexChanged.connect(self.refresh_colors)
        self.update_save_button()
        self.refresh_colors()

    def update_save_button(self):
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(bool(self.name_edit.text().strip()))

    def refresh_colors(self):
        palette = self.colors[self.mode_combo.currentData()]
        for role, button in self.color_buttons.items():
            color = palette[role]
            foreground = '#ffffff' if QColor(color).lightnessF() < 0.5 else '#17212b'
            button.setText(color.upper())
            button.setStyleSheet('background-color: ' + color + '; color: ' + foreground + ';')
        self.preview.setStyleSheet('QWidget { background-color: ' + palette['panel'] +
                                  '; color: ' + palette['text'] + '; }')
        self.preview_button.setStyleSheet('background-color: ' + palette['selected'] +
                                         '; color: ' + palette['on_selected'] + ';')

    def choose_color(self, role):
        palette = self.colors[self.mode_combo.currentData()]
        color = QColorDialog.getColor(QColor(palette[role]), self, self.tr_text('theme_role_' + role))
        if color.isValid():
            palette[role] = color.name()
            self.refresh_colors()

    def preset(self):
        return {'name': self.name_edit.text().strip(), 'colors': deepcopy(self.colors)}
