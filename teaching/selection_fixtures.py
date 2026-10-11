# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C04 setup only inside this active private practice."""
SELECTION_FIXTURES = frozenset('selection.c04.' + name for name in
                              ('select_move', 'transform', 'copy_delete'))


def prepare_selection_fixture(panel, fixture, paths):
    if fixture not in SELECTION_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError('selection setup requires this active private practice')
    canvas = panel.canvas
    canvas._discard_teaching_laser_operations()
    canvas.laser_trail = []
    canvas.selected_ids.clear()
    panel.pen_defaults_enabled = False
    panel.choose_pen_style('pen')
    panel.set_drawing_mode(True)
    panel.show_only_sub(None)
    canvas.smart_shapes_enabled = False
