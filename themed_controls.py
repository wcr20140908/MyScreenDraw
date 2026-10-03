# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared palette and popup styling for settings controls and color dialogs."""
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QStyledItemDelegate


def theme_palette(theme):
    palette = QPalette()
    roles = {"Window": "panel", "WindowText": "text", "Base": "panel",
             "AlternateBase": "button_hover", "Text": "text", "Button": "button",
             "ButtonText": "text", "Highlight": "accent", "HighlightedText": "active_text",
             "ToolTipBase": "panel", "ToolTipText": "text"}
    for role, key in roles.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(theme[key]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(theme["mode_off"]))
    return palette


def controls_stylesheet(t):
    return f"""
        QComboBox, QSpinBox, QLineEdit {{
            background-color: {t['panel']}; color: {t['text']};
            selection-background-color: {t['accent']}; selection-color: {t['active_text']};
            border: 1px solid {t['accent']}; border-radius: 5px; padding: 5px; min-height: 24px;
        }}
        QComboBox {{ padding-right: 24px; }}
        QComboBox::drop-down {{ width: 24px; border: none; }}
        QComboBox QAbstractItemView {{
            background-color: {t['panel']}; color: {t['text']};
            selection-background-color: {t['accent']}; selection-color: {t['active_text']};
            border: 1px solid {t['accent']}; outline: 0;
        }}
        QAbstractItemView::item {{ min-height: 30px; padding: 4px 8px; }}
        QAbstractItemView::item:selected {{ background-color: {t['accent']}; color: {t['active_text']}; }}
        QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled,
        QAbstractItemView::item:disabled {{ color: {t['mode_off']}; }}
        QColorDialog {{ background-color: {t['panel']}; color: {t['text']}; }}
        QColorDialog QLabel {{ color: {t['text']}; }}
        QColorDialog QPushButton {{ background-color: {t['button']}; color: {t['text']};
            border: 1px solid {t['accent']}; border-radius: 5px; padding: 6px 10px; }}
        QColorDialog QPushButton:hover {{ background-color: {t['button_hover']}; }}
    """


def apply_combo_theme(combo, theme):
    # The Windows menu delegate can ignore QSS selection colors. A regular
    # styled item delegate and an explicit popup palette work in both themes.
    if not isinstance(combo.itemDelegate(), QStyledItemDelegate):
        combo.setItemDelegate(QStyledItemDelegate(combo))
    palette = theme_palette(theme)
    for widget in (combo, combo.view(), combo.view().viewport(), combo.view().parentWidget()):
        widget.setPalette(palette)
