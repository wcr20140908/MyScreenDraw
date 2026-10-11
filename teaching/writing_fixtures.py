# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted setup for the five offline writing/erasing chapters."""
WRITING_FIXTURES = frozenset('writing.' + chapter for chapter in (
    'c02.styles', 'c02.color_width', 'c02.transient', 'c03.erase', 'c03.history_clear'))


def prepare_writing_fixture(panel, fixture, paths):
    if fixture not in WRITING_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError('writing setup requires this active private practice')
    canvas = panel.canvas
    canvas._discard_teaching_laser_operations()
    canvas.laser_trail = []
    panel.pen_defaults_enabled = False
    panel.choose_pen_style('fountain' if fixture == 'writing.c02.styles' else 'pen')
    panel.set_drawing_mode(True)
    panel.show_only_sub(None)
    canvas.smart_shapes_enabled = False
    if fixture == 'writing.c03.erase':
        panel.set_eraser_type('STROKE')
        panel.e_slider.setValue(40)
    elif fixture == 'writing.c03.history_clear':
        previous = canvas.capture_page()
        last_id = previous['segments'][-1]['id']
        previous['segments'] = [segment for segment in previous['segments'] if segment['id'] != last_id]
        canvas.undo_stack = [previous]
        canvas.redo_stack = []
        panel.update_history_ui()
