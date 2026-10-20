# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C07 setup, bound to the current active private practice."""
from uuid import NAMESPACE_URL, uuid5

TEXT_FIXTURES = frozenset('text.c07.'+name for name in ('edit', 'format', 'formula'))
FORMAT_TEXT_ID = str(uuid5(NAMESPACE_URL, 'myscreendraw-teaching-c07-format-original'))
SYMBOL_TEXT_ID = str(uuid5(NAMESPACE_URL, 'myscreendraw-teaching-c07-symbols'))
FORMULA_TEXT_ID = str(uuid5(NAMESPACE_URL, 'myscreendraw-teaching-c07-formula'))


def prepare_text_fixture(panel, fixture, paths):
    if fixture not in TEXT_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError('text setup requires this active private practice')
    canvas = panel.canvas
    panel._teaching_text_original_id = None
    panel._teaching_reedit_prefix = None
    panel._teaching_symbol_original_id = SYMBOL_TEXT_ID if fixture.endswith('.formula') else None
    canvas._discard_teaching_laser_operations()
    canvas.laser_trail = []
    canvas.cancel_pending_points()
    canvas.selected_ids.clear()
    panel.close_text_input()
    if getattr(panel, '_open_symbol_group', None) is not None:
        panel._toggle_symbol_group(panel._open_symbol_group)
    panel.pen_defaults_enabled = False
    panel.choose_pen_style('pen')
    panel.set_drawing_mode(True)
    panel.set_tool('PEN', panel.btn_pen)
    canvas.text_font_size = 24
    canvas.pen_width = 4
    from PyQt6.QtGui import QColor
    canvas.pen_color = QColor('#202020')
    canvas.smart_shapes_enabled = False
    panel.show_only_sub(None)
    panel.close_thumbnail_panel()
    settings = getattr(panel, 'settings_panel', None)
    if settings is not None:
        settings.hide()
    panel.update_whiteboard_ui()
