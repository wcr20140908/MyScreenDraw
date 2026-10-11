# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic C05 page samples only inside this active private practice."""
PAGES_FIXTURES = frozenset('pages.c05.'+chapter for chapter in
                           ('board','add_switch','rename_delete','copy_position','reorder'))


def prepare_pages_fixture(panel,fixture,paths):
    if fixture not in PAGES_FIXTURES:
        return
    context=panel.runtime_context
    if not paths.practice or context.paths!=paths or not context.ui_active:
        raise ValueError('page setup requires this active private practice')
    canvas=panel.canvas
    canvas._discard_teaching_laser_operations()
    canvas.laser_trail=[]
    canvas.selected_ids.clear()
    panel.pen_defaults_enabled=False
    panel.choose_pen_style('pen')
    panel.set_drawing_mode(True)
    panel.show_only_sub(None)
    panel.close_thumbnail_panel()
    settings=getattr(panel,'settings_panel',None)
    if settings is not None:
        settings.hide()
    panel.set_page_copy_placement('after',persist=False)
    canvas.smart_shapes_enabled=False
    canvas.board_style='WHITE'
    panel.update_whiteboard_ui()
